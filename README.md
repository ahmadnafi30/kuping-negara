# Kuping Negara

Pipeline data untuk riset analisis sentimen percakapan publik di X mengenai
program prioritas pemerintah Indonesia: Makan Bergizi Gratis, Cek Kesehatan
Gratis, Koperasi Desa Merah Putih, dan Sekolah Rakyat.

## Status

Branch `main` menyediakan pengumpulan data interaktif, preprocessing CSV,
dan penjadwalan melalui Airflow di Docker untuk pengembangan lokal.
DVC menyediakan versi dataset raw dan pemulihan data. Training model, API
prediksi, dashboard, dan MLflow masih direncanakan.

| Tersedia | Hasil |
| --- | --- |
| Kolektor Tweet Harvest | Query dari YAML, rentang tanggal inklusif, raw CSV per program/run |
| Preprocessing | Normalisasi teks, pemetaan kolom, flag kualitas, CSV dan laporan JSON |
| DVC | Snapshot raw tervalidasi, hash metadata, append tanpa duplikat, dan remote lokal/Google Drive |
| Lineage | Run ID, timestamp, SHA-256 sumber dan output |
| Lingkungan pengembangan | Python 3.12, uv lockfile, Dev Container, pytest, Ruff, CI |
| Airflow Docker | Dua container (Airflow + PostgreSQL), jadwal 23.59 WIB, preprocessing berurutan, retry tanpa overwrite |

Hasil analisis dirancang sebagai bahan riset. Percakapan pengguna X tidak
mewakili seluruh penduduk Indonesia.

## Mulai cepat

Jalankan dari root repositori dengan Python 3.12 dan `uv`:

```bash
git clone https://github.com/ahmadnafi30/kuping-negara.git
cd kuping-negara
uv sync --locked --extra dev
uv pip check
uv run --locked --extra dev --extra data-versioning python -m kuping_negara
```

Alternatif: buat Codespace dari `main`. Panduan setup dan troubleshooting ada
di [Codespaces Setup](docs/codespaces-setup.md).

Validasi rencana pengumpulan tanpa token atau akses X:

```bash
uv run --locked collect-x-data --from-date 14-09-2026 --to-date 21-09-2026 --limit 50 --dry-run
```

Untuk pengumpulan sungguhan, siapkan Node.js dengan `npx` dan browser sesuai
[panduan pengumpulan](docs/x-data-collection.md). Masukkan token hanya melalui
prompt tersembunyi Tweet Harvest.

Preprocess CSV yang dihasilkan kolektor:

```bash
uv run --locked preprocess-x-data --input "data/raw/x/collected_date=2026-09-21/program=mbg/run_id=20260921T182524+0700/mbg_2026-09-14_2026-09-21.csv"
```

Path tersebut adalah contoh format; ganti dengan file hasil pengumpulan Anda.
Dataset contoh tidak disertakan di Git. Preprocessing menghasilkan CSV dan
`quality_report.json`, mempertahankan semua baris dengan flag review, dan
menolak menimpa run yang sudah ada. Detail ada di
[panduan preprocessing](docs/x-data-preprocessing.md).

## Versi dataset dengan DVC (LK-05)

Git menyimpan penunjuk `data/raw/lk05_dataset.csv.dvc` dan metadata audit;
isi CSV disimpan melalui cache/remote DVC. Contoh tugas menggunakan dua versi:
`lk05-data-v1` (50 baris CKG) dan `lk05-data-v2` (200 baris empat program).
Penambahan 150 baris berasal dari koleksi nyata yang berhasil; 50 ID CKG yang
sudah ada dilewati. Ini simulasi pertumbuhan dataset, belum retraining model.

```bash
uv sync --locked --extra dev --extra data-versioning
uv run --locked --no-sync --extra data-versioning dvc status
uv run --locked --no-sync --extra data-versioning dvc diff --show-hash lk05-data-v1 lk05-data-v2
```

Untuk menambah versi: jalankan koleksi, buat snapshot dengan `--append`, jalankan
`dvc add`, lalu commit penunjuk serta metrik dan `dvc push`. Cara konfigurasi
remote, pengambilan versi lama, dan perintah lengkap ada pada
[panduan DVC](docs/dvc-data-versioning.md). Checkout baru perlu remote yang
berisi objek dataset sebelum `dvc pull`; dataset tidak ikut `git clone`.

Google Drive tersedia melalui extra `google-drive`. Gunakan OAuth Desktop app
milik sendiri, folder Drive khusus, serta konfigurasi lokal yang diabaikan Git.
[Setup Google Drive](docs/dvc-data-versioning.md#google-drive) menjelaskan login,
unggah versi, dan pemulihan tanpa memasukkan kredensial ke repositori.

## Struktur

Untuk pengambilan terjadwal, ikuti [panduan Airflow Docker](docs/airflow-docker.md).
Jadwal: MBG Senin, CKG Selasa, Kopdes Rabu, Sekolah Rakyat Kamis, pukul 23.59 WIB,
mengambil tujuh hari penuh sebelumnya. Token dipasang melalui file secret lokal.

```text
kuping-negara/
├── .devcontainer/          # Lingkungan Codespaces
├── .github/                # CI dan template Pull Request
├── configs/                # Keyword program dan rancangan kontrak data
├── dags/                   # Workflow Airflow: collect kemudian preprocess
├── docker/                 # Image, dependensi Node, dan bootstrap secret lokal
├── compose.yaml            # Airflow dan PostgreSQL lokal
├── data/
│   ├── raw/                # Output pengumpulan lokal; isi diabaikan Git
│   └── processed/          # Output preprocessing lokal; isi diabaikan Git
├── docs/                   # Panduan, proposal, roadmap, dan arsip desain
├── scripts/                # Hook browser untuk Tweet Harvest
├── src/kuping_negara/
│   ├── configuration.py    # Pembacaan dan validasi konfigurasi bersama
│   ├── paths.py            # Root repositori dan default pipeline
│   ├── healthcheck.py      # Pemeriksaan lingkungan pengembangan
│   ├── ingestion/          # Query, browser, raw storage, dan CLI koleksi
│   ├── data_versioning/   # Snapshot raw, append, dan audit metadata DVC
│   ├── preprocessing/      # Normalisasi teks, transformasi, dan pipeline file
│   └── orchestration/      # Adapter terjadwal, publikasi atomik, dan retry
├── tests/                  # Pengujian unit dan integrasi tanpa layanan eksternal
├── pyproject.toml          # Metadata, dependensi, dan aturan kualitas
├── uv.lock                 # Resolusi dependensi yang digunakan CI
└── requirements.txt        # Ekspor kompatibilitas untuk pip
```

Tambahkan folder dan paket saat ada implementasi yang memerlukannya.
Panduan batas modul tersedia di [Project Structure](docs/project-structure.md).

## Pemeriksaan kualitas

```bash
uv sync --locked --extra dev --extra data-versioning
uv run --locked --extra dev --extra data-versioning ruff check src tests dags docker/airflow
uv run --locked --extra dev --extra data-versioning ruff format --check src tests dags docker/airflow
uv run --locked --extra dev --extra data-versioning pytest
```

CI menjalankan pemeriksaan ini pada Pull Request dan push ke `main`/`develop`.
Perubahan dependensi harus menyertakan pembaruan `uv.lock` dan ekspor
`requirements.txt`. `--locked` memeriksa bahwa lockfile sesuai dengan deklarasi.

## Dokumentasi dan kontribusi

- [Indeks dokumentasi](docs/README.md)
- [Panduan pengembangan](docs/development-guidelines.md)
- [Alur branch dan Pull Request](docs/git-workflow.md)
- [Pedoman anotasi](docs/annotation-guidelines.md)
- [Proposal proyek](docs/project-proposal.md)
- [Roadmap](docs/roadmap.md)

Raw data, processed data, dataset berlabel, model, cache, dan kredensial disimpan
di luar Git. Preprocessing menghapus kolom akun eksplisit, tetapi `raw_text`
dan permalink tetap dapat mengandung informasi personal; output belum boleh
dianggap anonim.

## Lisensi

Kode menggunakan [MIT License](LICENSE). Lisensi kode tidak memberikan hak
redistribusi atas data dari pihak ketiga.
