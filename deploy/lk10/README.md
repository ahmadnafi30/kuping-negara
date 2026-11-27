# LK-10 — MLflow Model Serving dan Horizontal Scaling

Folder ini berisi implementasi serving model Kuping Negara menggunakan
**MLflow Models**, dengan tiga replika model dan satu gateway Nginx.
Endpoint prediksi yang dipakai adalah `POST /invocations`.

| Komponen | Fungsi |
| --- | --- |
| Model Production LK-07 | Sumber artefak model yang diverifikasi sebelum serving |
| MLflow Models | Server inferensi native serta pembentukan image model |
| `api-service` | Tiga container dari image serving yang sama |
| `gateway` | Membagikan request ke replika melalui satu alamat API |
| `mlflow-server` | Profil opsional untuk membuka kembali registry lokal pada volume lama |

Alamat gateway adalah **http://localhost:8002**. Port 8002 dipilih agar tidak
bertabrakan dengan API LK-09 di port 8000. Serving native untuk pengujian lokal
menggunakan port 8001; registry tetap menggunakan port 5000.

## Prasyarat

- Docker Desktop dengan Linux Engine aktif.
- Python 3.12; `uv` membantu menyiapkan lingkungan Python.
- Model `kuping-negara-sentiment-lk07-simulation` berstatus Production dan READY,
  beserta artefaknya pada MLflow.
- Akses internet ketika memasang dependensi dan membangun image pertama kali.

Model Production dari LK-07 merupakan simulasi lifecycle pembelajaran dengan
label AI provisional. Implementasi ini memakai model tersebut dan tidak
mengubah status persetujuan deployment.

## Menjalankan dari Windows

Dari root repositori:

```powershell
cd deploy/lk10
.\Start-LK10.ps1
```

Script melakukan langkah berikut secara berurutan:

1. Memeriksa akses Docker dan menyiapkan virtual environment Python.
2. Memasang versi dependensi yang mengikuti lockfile training proyek.
3. Menggunakan registry pada `http://127.0.0.1:5000`. Jika belum tersedia,
   mencoba menjalankan profil registry dari Compose dengan image dan volume lama.
4. Memeriksa stage Production, status READY, serta source run yang telah FINISHED.
5. Mengunduh versi model yang tetap dan mencatat checksum artefaknya.
6. Menjalankan `mlflow models serve`, menguji endpoint native, lalu menghentikan
   hanya proses pengujian lokal yang dibuat script.
7. Menjalankan `mlflow models build-docker` untuk membangun image serving.
8. Menjalankan tiga replika, menunggu healthcheck, dan memeriksa setiap replika
   serta distribusi request melalui gateway.

Jika registry berada pada alamat lain:

```powershell
.\Start-LK10.ps1 -TrackingUri "http://alamat-registry:5000"
```

Kredensial registry, jika diperlukan, mengikuti environment variable MLflow,
misalnya `MLFLOW_TRACKING_TOKEN`.

Script berhenti jika model Production tidak ditemukan. Tidak ada pelatihan
ulang, promosi otomatis, atau pembuatan model demo sebagai pengganti.

## Langkah manual

Seluruh perintah berikut dijalankan dari folder `deploy/lk10`.

### 1. Menyiapkan lingkungan

Windows:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-tools.txt
.\.venv\Scripts\Activate.ps1
```

Linux atau Codespaces:

```bash
python -m pip install -r requirements-tools.txt
```

Versi MLflow dan library model mengikuti `uv.lock` proyek: MLflow 3.17.1,
scikit-learn 1.9.1, pandas 3.0.5, NumPy 2.5.3, dan cloudpickle 3.1.2.

### 2. Memeriksa dan mengekspor model Production

Pastikan server MLflow yang menyimpan registry LK-07 sudah aktif:

```bash
python manage.py prepare --tracking-uri http://127.0.0.1:5000
```

Jika image `kuping-negara-ml:latest` dan volume registry lama tersedia,
server dapat dibuka melalui:

```bash
docker compose --profile registry up -d --wait mlflow-server
```

Jalankan satu server MLflow untuk volume SQLite yang sama. Apabila server lama
sudah aktif pada port 5000, gunakan server tersebut.

Hasil ekspor berada di:

| Path | Isi |
| --- | --- |
| `.artifacts/model/` | Artefak MLflow Model, termasuk `MLmodel` |
| `.artifacts/production.json` | Nama, versi, stage, source run, dan checksum model |

Pemilihan awal memakai stage Production, lalu versi numeriknya dikunci untuk
ekspor. Script memeriksa kembali status model sebelum menyelesaikan ekspor.
Jika artefak berubah setelahnya, proses build dan verifikasi ditolak.

Untuk memeriksa kembali ekspor:

```bash
python manage.py check-model
```

### 3. Menjalankan serving native MLflow

Terminal pertama:

```bash
mlflow models serve -m .artifacts/model --env-manager local --host 0.0.0.0 -p 8001 --workers 1
```

Terminal kedua:

```bash
python manage.py test-api --url http://127.0.0.1:8001
```

Script menampilkan input dan output prediksi yang benar-benar diterima dari
server. Setelah selesai, hentikan server di terminal pertama menggunakan Ctrl+C.

Sebagai pemeriksaan otomatis lokal yang menyalakan dan menghentikan servernya
sendiri, gunakan:

```bash
python manage.py local-check
```

Opsi `--env-manager local` menggunakan dependensi pada lingkungan Python
yang telah disiapkan pada langkah pertama.

## Menjalankan serving di Codespaces

Konfigurasi tambahan repositori tersedia di
`.devcontainer/lk10/devcontainer.json`. Setelah file implementasi masuk ke
GitHub, konfigurasi **Kuping Negara — LK-10 serving** dapat dipilih saat
membuat Codespace. Konfigurasi ini menyediakan Python, Docker-in-Docker,
SSH untuk akses melalui `gh codespace ssh`, dan forwarding port 5000, 8001,
serta 8002. Dockerfile menonaktifkan repository Yarn bawaan yang tidak
dibutuhkan LK-10 agar kunci Yarn yang kedaluwarsa tidak menghalangi instalasi.

Registry pada Docker laptop tidak otomatis tersedia di Codespaces. Ada dua
cara menyiapkan model:

- Jika registry dapat diakses dari Codespaces, jalankan `manage.py prepare`
  dengan tracking URI yang dapat dijangkau dari lingkungan tersebut.
- Jika registry hanya tersedia di laptop, ekspor model Production di laptop,
  kemudian pindahkan folder `.artifacts` beserta `production.json` ke folder
  LK-10 di Codespaces.

Untuk memindahkan ekspor dari laptop, arsip dapat dibuat setelah `prepare`
berhasil:

```bash
python -m zipfile -c production-model-lk10.zip .artifacts
```

Unggah arsip tersebut melalui Explorer VS Code di Codespaces, lalu dari folder
LK-10 ekstrak dan periksa modelnya:

```bash
python -m zipfile -e production-model-lk10.zip .
python manage.py check-model
```

Model dan arsip ekspor tidak dimasukkan ke Git. Pada cara pemindahan ini,
`production.json` menyimpan bukti asal versi Production dan checksum;
pengujian endpoint dilakukan kembali di Codespaces.

Lanjutkan dengan dua terminal untuk `mlflow models serve` dan
`python manage.py test-api` seperti langkah sebelumnya. Hasil pengujian
mencatat lingkungan `codespaces` ketika dijalankan di Codespaces.

## Membangun image MLflow Model

Dari lingkungan Python yang sudah disiapkan:

```bash
python manage.py build
```

Perintah inti yang dijalankan adalah:

```bash
mlflow models build-docker -m .artifacts/model -n kuping-negara-serving:lk10 --env-manager local
```

MLflow membentuk image dengan model tersemat dan entrypoint serving native
pada port container 8080. Compose menggunakan entrypoint dari image tersebut.

Pada Windows, `manage.py build` menggunakan `mlflow models generate-dockerfile`
dengan `--env-manager local`, menormalkan separator path sumber `COPY` menjadi
`/`, lalu menjalankan `docker build`. Ini mengatasi separator Windows yang
tidak dapat dipakai oleh Docker Linux. Instalasi dependensi dan entrypoint
tetap berasal dari Dockerfile MLflow. Mode `local` di dalam image memakai
Python sesuai environment model dan memasang requirements model saat build.

Skrip build menyimpan identitas image dan checksum model pada
`.artifacts/image.json`. Dengan begitu, verifikasi dapat memeriksa apakah
semua replika menjalankan image yang sama dengan hasil build.

Jika model atau environment model berubah, siapkan ekspor yang sesuai lalu
bangun ulang image. Ekspor dengan artefak berbeda tidak menimpa ekspor lama;
gunakan folder kerja LK-10 baru untuk menjaga asal model tetap jelas.

## Menjalankan tiga replika

`docker-compose.yaml` mengatur:

```yaml
api-service:
  image: kuping-negara-serving:lk10
  deploy:
    replicas: 3
```

Setelah image selesai dibangun:

```bash
docker compose up -d --wait --wait-timeout 300
docker compose ps
```

Atau gunakan skrip yang sekaligus memeriksa hubungan image dengan ekspor model:

```bash
python manage.py up --replicas 3
```

Setiap replika hanya membuka port 8080 pada jaringan internal Docker. Gateway
mempublikasikan satu port host, sehingga replikasi tidak menimbulkan bentrok
port. Setiap container memiliki satu worker serving.

Nginx memakai DNS internal Docker dan resolusi ulang nama layanan. Ketika
jumlah replika berubah, alamat backend diperbarui tanpa perlu mengganti
alamat API pengguna.

## Mengakses endpoint API

| Endpoint | Fungsi |
| --- | --- |
| `GET /ping` | Pemeriksaan kesehatan serving |
| `GET /health` | Pemeriksaan kesehatan serving |
| `POST /invocations` | Prediksi dengan format input MLflow |
| `GET /version` | Versi MLflow serving |

File `request.json` berisi tiga contoh teks sintetis untuk pengujian input,
dengan kolom `model_text` dan `target_program`. Contoh teks ini digunakan untuk
memanggil model yang sudah tersedia.

Linux atau Codespaces:

```bash
curl -i http://localhost:8002/invocations -H "Content-Type: application/json" --data-binary @request.json
```

PowerShell:

```powershell
$body = Get-Content -LiteralPath .\request.json -Raw
Invoke-RestMethod -Uri "http://localhost:8002/invocations" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 6
```

Respons native MLflow berisi `predictions`. Identitas backend yang menangani
request dapat dilihat melalui header `X-Model-Replica`, misalnya menggunakan
`curl.exe -i` pada Windows. Identitas model sumber disimpan pada
`.artifacts/production.json`.

## Menguji semua replika

```bash
python manage.py verify --replicas 3
```

Pemeriksaan mencakup:

- Terdapat tepat tiga container model dengan ID berbeda, running, dan healthy.
- Seluruh container menggunakan ID image hasil build yang dicatat.
- Setiap replika dapat menerima prediksi secara langsung.
- Hasil prediksi antar-replika sama untuk input yang sama.
- Request melalui gateway mencapai seluruh replika.

Pesan PASS baru ditampilkan setelah pemeriksaan tersebut berhasil.
Output dan metadata teknis disimpan pada `.evidence/replicas-3.json`.
File tersebut adalah hasil pemeriksaan, bukan laporan PDF.

## Mengubah jumlah replika secara dinamis

Menambah menjadi lima replika:

```bash
docker compose up -d --scale api-service=5 --wait --wait-timeout 300
python manage.py verify --replicas 5
```

Mengurangi menjadi satu replika:

```bash
docker compose up -d --scale api-service=1 --wait --wait-timeout 300
python manage.py verify --replicas 1
```

Mengembalikan menjadi tiga replika:

```bash
docker compose up -d --scale api-service=3 --wait --wait-timeout 300
python manage.py verify --replicas 3
docker compose ps
```

Alamat `http://localhost:8002/invocations` tetap sama. Nilai default pada
manifest tetap tiga; ubah `deploy.replicas` jika ingin mengganti defaultnya.

Pengujian ini membuktikan replikasi dan distribusi request. Pengukuran
peningkatan throughput membutuhkan uji beban tersendiri.

## Pemeriksaan dan penghentian

Pada Windows, script menjalankan CLI MLflow dengan folder Scripts dari virtual
environment yang sama di PATH proses turunannya. Hal ini memungkinkan MLflow
menemukan uvicorn.exe meskipun virtual environment belum diaktifkan pada terminal.
Jika menjalankan perintah MLflow secara manual, aktifkan virtual environment
terlebih dahulu seperti pada langkah penyiapan lingkungan.

```bash
docker compose config --quiet
docker compose logs --tail 80 api-service gateway
docker compose stop
```

Untuk menghapus container dan network proyek:

```bash
docker compose down
```

Volume MLflow tidak dihapus oleh perintah tersebut. Hindari `down -v` jika
metadata registry dan artefak pada volume masih diperlukan.

Untuk pengujian kode tanpa Docker:

```bash
python -m pip install pytest pyyaml
python -m pytest tests -q
```

Paket ini berisi implementasi, contoh request, pengujian, dan petunjuk
pengoperasian. Bukti keberhasilan runtime berasal dari perintah yang
dijalankan terhadap model dan container sebenarnya.

## Referensi

- [MLflow local serving](https://mlflow.org/docs/latest/ml/deployment/deploy-model-locally/)
- [MLflow CLI: serve dan build-docker](https://mlflow.org/docs/latest/api_reference/cli.html)
- [Docker Compose replicas](https://docs.docker.com/reference/compose-file/deploy/#replicas)
- [Docker Compose up dan scaling](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Nginx upstream DNS resolution](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#resolve)
