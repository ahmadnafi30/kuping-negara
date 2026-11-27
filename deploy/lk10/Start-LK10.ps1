param(
    [string]$TrackingUri = "http://127.0.0.1:5000",
    [int]$Replicas = 3,
    [switch]$SkipLocalCheck
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

docker info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Buka Docker Desktop sampai Engine running, lalu ulangi.' }

$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv venv --python 3.12 .venv
    } else {
        py -3.12 -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 belum tersedia. Pasang Python 3.12 atau uv.' }
}
$dependencyCheck = @'
import importlib.metadata as metadata
import sys
expected = {'mlflow':'3.17.1','scikit-learn':'1.9.1','pandas':'3.0.5','numpy':'2.5.3','cloudpickle':'3.1.2'}
try:
    ready = all(metadata.version(name) == version for name, version in expected.items())
except metadata.PackageNotFoundError:
    ready = False
sys.exit(0 if ready else 1)
'@
& $pythonPath -c $dependencyCheck
if ($LASTEXITCODE -ne 0) {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv pip install --python $pythonPath -r requirements-tools.txt
    } else {
        & $pythonPath -m pip install -r requirements-tools.txt
    }
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependensi LK-10 gagal.' }
}

$registryReady = $false
try {
    $response = Invoke-WebRequest -Uri ($TrackingUri.TrimEnd('/') + '/health') -TimeoutSec 5 -UseBasicParsing
    $registryReady = ($response.StatusCode -eq 200)
} catch { $registryReady = $false }

if (-not $registryReady) {
    if ($TrackingUri -ne 'http://127.0.0.1:5000') {
        throw 'Tracking URI tidak dapat diakses. Pastikan server registry tersedia.'
    }
    docker compose --profile registry up -d --wait --wait-timeout 180 mlflow-server
    if ($LASTEXITCODE -ne 0) { throw 'MLflow registry belum dapat dimulai; cek image dan volume LK-07/LK-09.' }
}

& $pythonPath manage.py prepare --tracking-uri $TrackingUri
if ($LASTEXITCODE -ne 0) { throw 'Model Production belum tersedia atau ekspornya gagal.' }
if (-not $SkipLocalCheck) {
    & $pythonPath manage.py local-check
    if ($LASTEXITCODE -ne 0) { throw 'Pengujian serving native MLflow gagal.' }
}
& $pythonPath manage.py build
if ($LASTEXITCODE -ne 0) { throw 'Build image serving MLflow gagal.' }
& $pythonPath manage.py up --replicas $Replicas
if ($LASTEXITCODE -ne 0) { throw 'Replika belum healthy.' }
& $pythonPath manage.py verify --replicas $Replicas
if ($LASTEXITCODE -ne 0) { throw 'Verifikasi replika atau distribusi request gagal.' }
