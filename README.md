# Kuping Negara

Untuk training dan dashboard menggunakan container, ikuti [panduan MLflow Docker](docs/mlflow-docker.md).

Pipeline data untuk riset analisis sentimen percakapan publik di X mengenai
Makan Bergizi Gratis, Cek Kesehatan Gratis, Koperasi Desa Merah Putih, dan
Sekolah Rakyat.

## Fitur yang tersedia

| Komponen | Fungsi |
| --- | --- |
| Pengumpulan X | Keyword bersama, batas tanggal WIB, raw CSV dan manifest per run |
| Preprocessing | Normalisasi yang mempertahankan petunjuk sentimen, flag kualitas, dan lineage |
| Airflow di Docker | Dua container: Airflow dan PostgreSQL; collect dilanjutkan preprocess |
| DVC | Snapshot raw, append tanpa pasangan ID duplikat, perbandingan dan pemulihan versi |
| Google Drive | Remote DVC untuk dua versi dataset yang telah diuji pemulihannya |
| Anotasi | Pedoman review dan laporan agregat; hasil review AI masih memerlukan validasi manusia |
| Eksperimen model | TF-IDF/Logistic Regression, tiga trial MLflow, Registry kandidat eksperimen |
| Pengembangan | Python 3.12, uv lockfile, Dev Container, pengujian, dan CI Windows/Linux |

Panduan [eksperimen MLflow](docs/mlflow.md) menjelaskan baseline klasifikasi
dan batas evaluasinya. API prediksi serta dashboard publik tercantum dalam
[roadmap](docs/roadmap.md). Percakapan di X digunakan sebagai bahan riset dan
tidak mewakili seluruh penduduk Indonesia.

Pembaruan data: snapshot raw **666 baris** dan snapshot eksperimen **396 baris**
dari empat program sudah di-versioning. Label masih hasil AI; lihat
[perluasan data, hasil baru, dan batasnya](docs/sentiment-data.md).

## Mulai cepat

Gunakan Python 3.12 dan `uv`, lalu jalankan dari root repositori:

```bash
git clone https://github.com/ahmadnafi30/kuping-negara.git
cd kuping-negara
uv sync --locked --extra dev
uv pip check
uv run --locked --no-sync python -m kuping_negara
```

`uv run --no-sync` memakai lingkungan yang sudah dipasang. Pilih extra yang
diperlukan saat `uv sync`: `dev` untuk pengembangan, `data-versioning` untuk
DVC lokal, dan `google-drive` untuk backend Drive. Sertakan kembali extra
tersebut saat menyinkronkan lingkungan agar tetap tersedia.

[Setup Codespaces](docs/codespaces-setup.md) menjelaskan lingkungan tanpa
instalasi Python lokal.

### Pengumpulan dan preprocessing

Periksa rencana pengumpulan tanpa token atau akses X:

```bash
uv run --locked --no-sync collect-x-data --from-date 04-10-2026 --to-date 10-10-2026 --limit 50 --dry-run
```

Untuk koleksi interaktif, siapkan Node.js/`npx` dan browser sesuai
[panduan pengumpulan](docs/x-data-collection.md). Raw yang berhasil dapat
diproses menggunakan:

```bash
uv run --locked --no-sync preprocess-x-data --input "<path-raw-run.csv>"
```

Ganti placeholder dengan raw CSV dari kolektor. Dataset tidak disertakan di
Git. [Panduan preprocessing](docs/x-data-preprocessing.md) menjelaskan output,
flag review, duplikat, dan batas kesiapan data untuk anotasi.

### Penjadwalan Airflow

Ikuti [Airflow di Docker](docs/airflow-docker.md) untuk menjalankan stack lokal.

| Program | Hari | Jam |
| --- | --- | --- |
| MBG | Senin | 23.59 WIB |
| CKG | Selasa | 23.59 WIB |
| Kopdes Merah Putih | Rabu | 23.59 WIB |
| Sekolah Rakyat | Kamis | 23.59 WIB |

Setiap run mengambil tujuh hari kalender penuh sebelumnya, lalu menjalankan
preprocessing. Secret akun X dipasang secara lokal. Docker, laptop, dan koneksi
internet perlu aktif agar jadwal berjalan.

## Versi dataset dengan DVC (LK-05)

Git melacak `data/raw/lk05_dataset.csv.dvc` dan metrik audit. Isi CSV disimpan
pada cache serta remote DVC. Dua versi yang tersedia:

| Tag | Baris | Isi |
| --- | ---: | --- |
| `lk05-data-v1` | 50 | CKG |
| `lk05-data-v2` | 200 | Empat program, masing-masing 50 baris |

Sebanyak 150 pasangan program/post ditambahkan; 50 pasangan CKG yang sudah ada
dilewati. Ini pertumbuhan dataset dari koleksi nyata dalam periode
4-10 Oktober 2026 WIB, belum training ulang model.

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv run --locked --no-sync dvc status
uv run --locked --no-sync dvc diff --show-hash lk05-data-v1 lk05-data-v2
```

[Alur penambahan versi data](docs/dvc.md) menjelaskan collect, append,
`dvc add`, upload objek, commit/tag, diff, dan pemulihan. [Konfigurasi DVC](docs/dvc-data-versioning.md)
menjelaskan remote lokal, OAuth Google Drive, dan setup pada mesin baru.

Kedua versi sudah diunggah ke folder `kuping-negara-dvc` dan berhasil dipulihkan
dengan cache kosong; [bukti verifikasi](reports/lk05/google_drive_verification.json)
tersedia di repo. Konfigurasi remote dan token tidak ikut `git clone`.
Pengunggahan DVC masih dilakukan secara eksplisit setelah penambahan versi.

## Eksperimen Machine Learning

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv run --locked --no-sync python train.py run --allow-provisional
```

Pulihkan snapshot training dengan DVC terlebih dahulu. Mode awal memakai label
AI sementara atas persetujuan pemilik proyek; model Registry berstatus
`experimental` dan belum disetujui untuk deployment. Lihat [panduan MLflow](docs/mlflow.md)
untuk persiapan data, dashboard, dan hasil tiga eksperimen.

## Struktur repositori

```text
kuping-negara/
├── .devcontainer/          # Lingkungan Codespaces
├── .github/                # CI dan template Pull Request
├── .dvc/                   # Konfigurasi DVC; cache/token lokal diabaikan Git
├── configs/                # Keyword program dan rancangan kontrak data
├── dags/                   # Empat DAG collect → preprocess
├── docker/                 # Image, lock Node, dan bootstrap secret
├── compose.yaml            # Stack Airflow/PostgreSQL
├── data/                   # Raw, processed, dan metadata dataset
├── docs/                   # Panduan penggunaan, pengembangan, dan arsip
├── reports/                # Metrik agregat dan audit tanpa isi post
├── scripts/                # Adapter browser dan secret Tweet Harvest
├── src/kuping_negara/       # Modul ingestion, preprocessing, orchestration, DVC
├── tests/                  # Pengujian unit dan integrasi
├── pyproject.toml          # Dependensi dan pengaturan proyek
├── uv.lock                 # Resolusi dependensi
└── requirements.txt        # Ekspor kompatibilitas untuk pip
```

[Kepemilikan modul](docs/project-structure.md) menjelaskan batas tanggung jawab
setiap komponen. Folder fitur baru dibuat bersama implementasinya.

## Pemeriksaan kualitas

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv pip check
uv run --locked --no-sync python -m kuping_negara.healthcheck
uv run --locked --no-sync ruff check src tests dags docker/airflow
uv run --locked --no-sync ruff format --check src tests dags docker/airflow
uv run --locked --no-sync pytest
```

CI memeriksa lingkungan Python pada Windows/Linux serta menjalankan verifikasi
stack Airflow. Perubahan dependensi menyertakan `uv.lock` dan ekspor
`requirements.txt` yang sesuai.

## Dokumentasi dan branch

- [Indeks dokumentasi](docs/README.md)
- [Pedoman anotasi](docs/annotation-guidelines.md)
- [Standar pengembangan](docs/development-guidelines.md)
- [Alur Git dan sinkronisasi branch](docs/git-workflow.md)
- [Proposal proyek](docs/project-proposal.md)
- [Arsip pekerjaan terdahulu](docs/archive/README.md)

`main` menyimpan versi stabil; `develop` mengikuti rilis terbaru dan digunakan
sebagai basis pekerjaan berikutnya. Branch pekerjaan bersifat sementara dan
dihapus setelah selesai. Riwayat eksperimen lama dipertahankan dalam tag arsip.

## Data dan lisensi

Raw, processed, label, model, cache, dan kredensial diabaikan Git. Preprocessing
menghapus kolom akun eksplisit, tetapi teks serta permalink masih dapat memuat
informasi personal; output belum dapat dianggap anonim.

Kode menggunakan [MIT License](LICENSE). Lisensi kode tidak memberikan hak
redistribusi atas data pihak ketiga.
