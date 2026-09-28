# LK-04 Assignment — Kuping Negara

Folder ini berisi berkas yang disiapkan untuk pengumpulan LK-04. Skrip,
konfigurasi, dan sampel disalin dari repo utama. File aslinya tetap ada di
tempat semula.

## Yang dikumpulkan

| Berkas atau folder | Isi |
| --- | --- |
| `src/ingest_data.py` | Skrip pengambilan data dan simulasi periodik |
| `src/preprocess.py` | Skrip pembersihan data |
| `src/kuping_negara/` | Modul pendukung yang dipakai kedua skrip |
| `data/raw/samples/x/` | Empat CSV sebelum preprocessing, total 20 baris |
| `data/processed/samples/x/` | Empat CSV sesudah preprocessing beserta laporan kualitasnya |
| `comparison/before_after.csv` | Perbandingan teks sebelum dan sesudah untuk setiap baris |
| `comparison/summary.csv` | Ringkasan jumlah baris dan hasil pemeriksaan per program |
| `docs/lk04-implementation.md` | Penjelasan implementasi dan cara menjalankannya |
| `docs/lk04-verification.json` | Bukti pemeriksaan ingestion dan simulasi awal |
| `docs/lk04-preprocessing-review.json` | Hasil pemeriksaan ulang 80 unggahan dari pengambilan langsung |
| `evidence/submission_checks.json` | Hasil pemeriksaan paket pengumpulan ini |
| `manifest.json` | Daftar berkas dan checksum untuk memastikan salinannya cocok |

`pyproject.toml`, `uv.lock`, `requirements.txt`, `configs/`, dan `scripts/`
ikut disertakan supaya skrip dapat dijalankan setelah folder ini diekstrak.
Folder `tests/` berisi salinan pengujian dari repo utama.

Untuk LMS yang menerima unggahan berkas, kumpulkan **seluruh folder ini dalam
satu ZIP**. Jika diminta tautan GitHub, gunakan branch
`feat/lk04-ingestion-preprocessing` dan arahkan penguji ke folder
`LK04 Assignment`. Tidak ada kewajiban PDF atau screenshot pada instruksi
LK-04 yang diberikan.

## Melihat hasil sebelum dan sesudah

Data sebelum preprocessing ada di `data/raw/samples/x/`. Hasil untuk baris
yang sama ada di `data/processed/samples/x/`. Susunan folder program dan
`run_id` dipertahankan agar pasangan filenya mudah dicocokkan.

Buka `comparison/before_after.csv` untuk melihat `text_before`, `text_after`,
status pemeriksaan, dan kesiapan pelabelan dalam satu tabel. Seluruh 20 baris
tetap disimpan. Baris yang perlu diperiksa tidak dihapus.

Sampel berasal dari pengambilan X pada **21 September 2026**, lima baris
untuk masing-masing MBG, CKG, Kopdes Merah Putih, dan Sekolah Rakyat.
Identitas akun dan tautan sudah disamarkan sebelum sampel dipublikasikan.
Penjelasan asal serta perubahan pada sampel ada di
[catatan sampel](data/raw/samples/README.md) dan
[provenance.json](data/raw/samples/provenance.json).

Laporan pengambilan langsung **80 unggahan pada 28 September 2026** di
`docs/` merupakan bukti terpisah. Jumlah tersebut bukan jumlah baris sampel
yang disertakan dalam paket ini.

## Menjalankan dari folder ini

Masuk ke folder `LK04 Assignment`, lalu siapkan environment. Gunakan Python
3.12 dan uv:

```bash
uv sync --frozen --extra dev
uv pip check
```

Node.js dan Chrome/Edge atau Chromium dibutuhkan untuk pengambilan langsung
di X. Preprocessing dan simulasi dari sampel tidak membutuhkan login X.

### Memeriksa hasil yang sudah disertakan

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --output-root data/processed/samples/x --skip-existing
```

Skrip memeriksa checksum sampel, konfigurasi, dan hasil. Jika semuanya cocok,
empat hasil yang sudah tersedia akan dilewati tanpa diubah.

### Membuat hasil preprocessing sendiri

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --output-root data/processed/recheck --skip-existing
```

Perintah ini menulis ke folder baru. Hasil yang disertakan untuk pengumpulan
tetap ada di `data/processed/samples/x/`.

### Mencoba pengambilan berulang

```bash
uv run --frozen python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Ini adalah simulasi **offline**: sampel disalin ke dua run baru, lalu
dibersihkan. Hasilnya delapan CSV mentah dan delapan CSV hasil preprocessing
di folder runtime. Simulasi ini tidak mengambil unggahan baru dari X.

### Mengambil data langsung

Cek rencana pengambilan satu program terlebih dahulu:

```bash
uv run --frozen python src/ingest_data.py --program mbg --lookback-days 7 --dry-run
```

Untuk mengambil data dan langsung menjalankan preprocessing:

```bash
uv run --frozen python src/ingest_data.py --program mbg --lookback-days 7 --limit 50 --preprocess
```

Token dimasukkan melalui prompt tersembunyi. Pada Windows, peluncur
`scripts/run_ingestion.ps1` juga tersedia untuk membaca `X_AUTH_TOKEN` dari
environment atau `.env` lokal. Berkas `.env` berisi token tidak disertakan
dalam paket ini.

### Menjalankan pengujian

```bash
uv run --frozen --extra dev pytest
```

## Jadwal yang mengikuti rancangan sebelumnya

| Hari | Kegiatan |
| --- | --- |
| Senin | Pengambilan dan preprocessing MBG |
| Selasa | Pengambilan dan preprocessing CKG |
| Rabu | Pengambilan dan preprocessing Kopdes Merah Putih |
| Kamis | Pengambilan dan preprocessing Sekolah Rakyat |
| Jumat | Pelabelan dan pemeriksaan kualitas |

Setiap program diambil sekali seminggu. Simulasi dua siklus digunakan untuk
membuktikan pengambilan dapat diulang. Task Scheduler atau cron mingguan
belum diaktifkan. Cara memasangnya dijelaskan di
[panduan implementasi](docs/lk04-implementation.md); sesuaikan lokasi repo
pada contoh action dengan lokasi folder yang digunakan.

## Catatan pemakaian data

Gunakan `cleaned_text` dan pilih `is_eligible_for_labeling=True` untuk tahap
pelabelan. Pemeriksaan bahasa memakai label dari X, dan relevansi memakai
kata kunci, sehingga baris yang lolos tetap perlu diperiksa konteksnya.
Jika beberapa run digabung, hapus duplikat berdasarkan `target_program`
dan `tweet_id` sebelum menyiapkan dataset training.
