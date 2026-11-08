# Otomatisasi Pelatihan dan Evaluasi Model

[Workflow GitHub Actions](../.github/workflows/mlops-automation.yaml) berjalan
saat push ke main dan pull request yang menargetkan main. Branch
feat/mlops-automation juga digunakan untuk demonstrasi perubahan konfigurasi
pelatihan.

1. Pytest memeriksa integritas kode.
2. DVC memulihkan snapshot raw dan training yang dilacak repositori.
3. train.py melatih kandidat di Docker dengan opsi --no-register.
4. Kandidat dipilih melalui grouped CV. Macro-F1 kandidat pada holdout harus
   mencapai 0,75 sesuai [proposal](project-proposal.md#initial-model-acceptance-criteria).
5. Evaluasi yang lolos mengizinkan registrasi ke Staging. Langkah ini memeriksa
   kembali run, checksum dataset, commit, dan metrik yang tercatat di MLflow.

## Jalur yang tersedia

| Jalur | Data | Registry |
| --- | --- | --- |
| Demo GitHub Actions | Snapshot sintetis yang dipulihkan dari remote DVC sementara | MLflow Docker pada runner, bukti Staging disimpan pada ringkasan run |
| Proyek di Docker lokal | Snapshot raw dan training yang dipulihkan dari remote DVC lokal | MLflow proyek |
| Proyek di GitHub Actions | Snapshot proyek dari Google Drive melalui service account | Endpoint MLflow persisten dengan autentikasi |

Demo berjalan pada push dan pull request tanpa kredensial proyek. Dataset demo
dibuat pada runner, disimpan ke remote DVC lokal sementara, dan dipulihkan
melalui cache baru. Registry demo berumur sepanjang run. Ringkasan Actions
menyimpan metrik dan bukti pembacaan kembali stage sebelum container dihentikan.

Jalur proyek pada GitHub Actions bersifat opsional hingga layanan tersedia.
Konfigurasikan environment mlops-training untuk branch main dan tambahkan
secrets DVC_REMOTE_URL, GDRIVE_CREDENTIALS_DATA, MLFLOW_TRACKING_URI, serta
MLFLOW_TRACKING_TOKEN. Service account memerlukan akses baca ke folder DVC.
Endpoint MLflow harus menggunakan HTTPS dan mengizinkan penulisan eksperimen,
artefak, serta versi registry pilot. Setelah layanan siap, set repository
variable MLOPS_PROJECT_ENABLED=true. Job proyek berjalan pada push ke main.

## Verifikasi dengan snapshot proyek di Docker lokal

Jalankan dari root repo. Remote localstore harus dapat mengakses kedua objek
DVC. Gunakan nama output baru untuk setiap percobaan.

```powershell
dvc pull -r localstore data/raw/expanded_20261019.csv.dvc data/training/sentiment_expanded_20261019.csv.dvc
docker compose --profile training build mlflow
docker compose --profile training up -d --no-deps --wait mlflow
$out = 'reports/training/automation/local-check'
docker compose --profile training run --rm --no-deps trainer run --dataset data/training/sentiment_expanded_20261019.csv --config configs/training/automation.json --output $out --allow-provisional --no-register --tracking-uri http://mlflow:5000
if ($LASTEXITCODE -ne 0) { throw 'Training gagal' }
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.automation evaluate --summary "$out/experiment_summary.json" --evaluation "$out/evaluation.json"
if ($LASTEXITCODE -ne 0) { throw 'Evaluasi gagal atau kandidat di bawah ambang' }
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.automation stage --summary "$out/experiment_summary.json" --evaluation "$out/evaluation.json"
```

Baca evaluation.json untuk keputusan ambang dan registry_receipt.json untuk
konfirmasi Staging. Kandidat menggunakan label sementara hasil AI dengan
deployment_approved=false. Ambang holdout berfungsi sebagai syarat teknis
untuk Staging. Kelayakan layanan publik memerlukan evaluasi tambahan pada
label yang divalidasi manusia.

## Bukti eksekusi

[Run perubahan konfigurasi training](https://github.com/ahmadnafi30/kuping-negara/actions/runs/42472425434) mencatat push yang mengubah C dari 0,5 ke 0,75 pada salah satu trial. Pytest, pemulihan snapshot sintetis, training, evaluasi, dan registrasi Staging selesai pada run tersebut.

Snapshot proyek juga diuji di Docker lokal. Model dengan C=10 dipilih melalui CV dan memperoleh Macro-F1 holdout 0,747638 pada 80 baris. Evaluasi menahan registrasi karena ambang minimum adalah 0,75.
