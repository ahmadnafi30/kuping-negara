# Project Structure

Kode yang dapat digunakan ulang berada dalam `src/kuping_negara/`. Struktur
repositori mengikuti implementasi yang tersedia; folder untuk fitur masa depan
dibuat ketika pekerjaan dimulai, bukan sebagai placeholder.

## Kepemilikan modul

| Path | Tanggung jawab |
| --- | --- |
| `configuration.py` | Membaca YAML, memvalidasi schema/ID/nama/keyword, dan memilih program |
| `paths.py` | Menemukan root repositori dan menyediakan default konfigurasi/timezone |
| `healthcheck.py` | Memeriksa metadata dan dependensi lingkungan pengembangan |
| `ingestion/queries.py` | Membentuk query, rentang tanggal, dan argumen Tweet Harvest |
| `ingestion/browser.py` | Menemukan browser dan menyiapkan environment proses anak |
| `ingestion/storage.py` | Memvalidasi staging CSV dan memindahkannya ke raw zone |
| `ingestion/validation.py` | Memeriksa CSV, batas tanggal WIB/jumlah, checksum, dan manifest |
| `ingestion/tweet_harvest.py` | CLI dan orkestrasi koleksi; entry point `collect-x-data` |
| `preprocessing/text.py` | Normalisasi Unicode, cleaning, dan pencocokan keyword |
| `preprocessing/x_posts.py` | Transformasi DataFrame dan ringkasan flag kualitas |
| `preprocessing/history.py` | Lock publikasi dan riwayat ID eligible lintas run/program |
| `preprocessing/x_pipeline.py` | Lineage file, checksum, persistensi, dan CLI `preprocess-x-data` |
| `orchestration/audit.py` | Mengarantina processed lama/invalid tanpa mengubah raw |
| `orchestration/runtime.py` | Koleksi tanpa prompt, isolasi run, publish atomik, dan validasi retry |

CLI tetap menggunakan entry point yang sama. Import fungsi lama di
`ingestion.tweet_harvest` dan `preprocessing.x_posts.clean_text` tetap tersedia
untuk kompatibilitas; kode baru dapat mengimpor langsung dari modul pemiliknya.

## Batas dependensi

```text
ingestion CLI ──> configuration / paths / queries / browser / storage
preprocessing pipeline ──> configuration / paths / x_posts ──> text
```

- Fungsi query dan teks tidak melakukan akses jaringan atau penyimpanan file.
- Koleksi dan preprocessing menggunakan pembacaan keyword yang sama.
- Business logic tidak bergantung pada parsing argumen CLI.
- Subprocess Tweet Harvest hanya dijalankan oleh orkestrator koleksi.
- Pengujian unit memakai fixture kecil; integrasi memakai file sintetis lokal.

## Folder pendukung

| Path | Isi dan aturan |
| --- | --- |
| `configs/keywords/` | YAML versi 1 dan dokumentasi keyword; tanpa token |
| `configs/schemas/` | Rancangan kontrak JSON Schema; validator runtime belum terintegrasi |
| `data/raw/` | Raw CSV lokal, dipartisi menurut tanggal/program/run; immutable |
| `data/quarantine/` | Output processed lama/invalid; dikecualikan dari labeling/training |
| `data/processed/` | CSV dan laporan kualitas lokal; run lama tidak ditimpa |
| `scripts/` | Hook browser, perbaikan integritas collector, dan adapter secret Node.js |
| `dags/` | Empat jadwal Airflow yang memanggil runtime dalam virtual environment terpisah |
| `docker/` dan `compose.yaml` | Stack Airflow/PostgreSQL, image, lock Node, dan setup secrets lokal |
| `docs/archive/` | Riwayat desain yang belum diimplementasikan |
| `tests/unit/` | Pengujian perilaku fungsi dan konfigurasi |
| `tests/integration/` | Pengujian alur raw CSV hingga output dan laporan |

`data/raw/.gitkeep` dan `data/processed/.gitkeep` menjaga lokasi output terlihat
di checkout baru. Isi dataset diabaikan Git. Aturan ignore untuk `data/labeled/`
dan `models/` tetap disiapkan walaupun foldernya belum ada.

## Penambahan fitur

Buat paket `training`, `inference`, `api`, atau `monitoring` bersama kode,
kontrak, dokumentasi, dan pengujiannya saat fitur tersebut dikerjakan. Tambahkan
`notebooks/` saat ada eksplorasi yang memerlukan notebook. Workflow Airflow
sudah ada di `dags/`; cara menjalankannya ada di [Airflow Docker](airflow-docker.md).
