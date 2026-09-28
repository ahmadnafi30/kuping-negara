param(
    [string]$RepositoryRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$PythonExecutable,
    [ValidateSet('mbg', 'ckg', 'kopdes_merah_putih', 'sekolah_rakyat')]
    [string]$Program,
    [ValidateRange(1, 3650)]
    [int]$LookbackDays = 7,
    [ValidateRange(1, 1000000)]
    [int]$Limit = 50,
    [switch]$DryRun,
    [string]$ReplayDir
)

# Run a single pipeline cycle. Task Scheduler supplies the daily/weekly trigger.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$originalToken = [Environment]::GetEnvironmentVariable('X_AUTH_TOKEN', 'Process')
$exitCode = 1
$locationChanged = $false

try {
    $RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
    if (-not $PythonExecutable) {
        $PythonExecutable = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw 'Python environment not found. Run uv sync before scheduling.'
    }
    if ($ReplayDir -and ($DryRun -or $Program)) {
        throw 'ReplayDir cannot be combined with DryRun or Program.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot 'src\ingest_data.py'))) {
        throw 'The repository does not contain src/ingest_data.py.'
    }

    $pipelineArguments = @('src/ingest_data.py', '--preprocess')
    if ($ReplayDir) {
        $pipelineArguments += @('--replay-dir', $ReplayDir)
    } else {
        $pipelineArguments += @('--lookback-days', "$LookbackDays", '--limit', "$Limit")
        if ($Program) { $pipelineArguments += @('--program', $Program) }
        if ($DryRun) {
            $pipelineArguments += '--dry-run'
        } else {
            if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
                throw 'Node.js is not available in the scheduled process PATH.'
            }
            if ([string]::IsNullOrWhiteSpace($originalToken)) {
                $tokenFile = Join-Path $RepositoryRoot '.env'
                if (Test-Path -LiteralPath $tokenFile -PathType Leaf) {
                    foreach ($line in [System.IO.File]::ReadAllLines($tokenFile)) {
                        if ($line -match '^\s*(?:export\s+)?X_AUTH_TOKEN\s*=\s*(.*?)\s*$') {
                            $tokenValue = $Matches[1].Trim()
                            if ($tokenValue.Length -ge 2) {
                                $first = $tokenValue.Substring(0, 1)
                                $last = $tokenValue.Substring($tokenValue.Length - 1, 1)
                                if (($first -eq '"' -or $first -eq "'") -and $last -eq $first) {
                                    $tokenValue = $tokenValue.Substring(1, $tokenValue.Length - 2)
                                }
                            }
                            [Environment]::SetEnvironmentVariable('X_AUTH_TOKEN', $tokenValue, 'Process')
                        }
                    }
                }
            }
            if ([string]::IsNullOrWhiteSpace($env:X_AUTH_TOKEN)) {
                throw 'Set X_AUTH_TOKEN in the environment or the local .env file.'
            }
            $pipelineArguments += '--non-interactive'
        }
    }

    $logDirectory = Join-Path $RepositoryRoot 'logs'
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $logFile = Join-Path $logDirectory ("ingestion-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss-fffffff'))
    "Pipeline started: $(Get-Date -Format o)" | Out-File -LiteralPath $logFile -Encoding utf8
    Push-Location -LiteralPath $RepositoryRoot
    $locationChanged = $true
    # Windows PowerShell represents native stderr as error records. Keep those
    # in the log and propagate the native exit code to Task Scheduler.
    $ErrorActionPreference = 'Continue'
    & $PythonExecutable @pipelineArguments 2>&1 | ForEach-Object {
        $_ | Out-File -LiteralPath $logFile -Encoding utf8 -Append
        Write-Output $_
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    "Pipeline finished: $(Get-Date -Format o); exit_code=$exitCode" |
        Out-File -LiteralPath $logFile -Encoding utf8 -Append
    Write-Output "Log: $logFile"
} catch {
    [Console]::Error.WriteLine("Scheduled ingestion: {0}", $_.Exception.Message)
} finally {
    if ($locationChanged) { Pop-Location }
    [Environment]::SetEnvironmentVariable('X_AUTH_TOKEN', $originalToken, 'Process')
}
exit $exitCode
