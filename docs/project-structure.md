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
| `ingestion/tweet_harvest.py` | CLI dan orkestrasi koleksi; entry point `collect-x-data` |
| `preprocessing/text.py` | Normalisasi Unicode, cleaning, dan pencocokan keyword |
| `preprocessing/x_posts.py` | Transformasi DataFrame dan ringkasan flag kualitas |
| `preprocessing/x_pipeline.py` | Lineage file, checksum, persistensi, dan CLI `preprocess-x-data` |

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
| `data/processed/` | CSV dan laporan kualitas lokal; run lama tidak ditimpa |
| `scripts/` | Hook browser Node.js yang digunakan kolektor |
| `docs/archive/` | Riwayat desain yang belum diimplementasikan |
| `tests/unit/` | Pengujian perilaku fungsi dan konfigurasi |
| `tests/integration/` | Pengujian alur raw CSV hingga output dan laporan |

`data/raw/.gitkeep` dan `data/processed/.gitkeep` menjaga lokasi output terlihat
di checkout baru. Isi dataset diabaikan Git. Aturan ignore untuk `data/labeled/`
dan `models/` tetap disiapkan walaupun foldernya belum ada.

## Penambahan fitur

Buat paket `training`, `inference`, `api`, atau `monitoring` bersama kode,
kontrak, dokumentasi, dan pengujiannya saat fitur tersebut dikerjakan. Tambahkan
`dags/` saat ada workflow Airflow dan `notebooks/` saat ada eksplorasi yang
memerlukan notebook. Lihat [roadmap](roadmap.md).
