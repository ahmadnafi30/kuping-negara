# LK-04 — Kuping Negara

Folder ini berisi berkas untuk pengumpulan LK-04. Skrip dan data merupakan
salinan; file aslinya tetap ada di repo utama.

## Isi pengumpulan

- `src/ingest_data.py`: mengambil data X dan menjalankan simulasi periodik.
- `src/preprocess.py`: membersihkan data mentah.
- `src/kuping_negara/`: modul yang dipanggil oleh kedua skrip tersebut.
- `data/raw/samples/x/`: empat CSV sebelum preprocessing.
- `data/processed/samples/x/`: empat CSV sesudah preprocessing.

Konfigurasi kata kunci di `configs/` dan pengaturan browser di `scripts/`
ikut disertakan karena digunakan saat pengambilan langsung. Dependensi
dicatat di `requirements.txt`; `pyproject.toml` juga menjadi penanda folder
proyek yang dibutuhkan skrip ingestion.

Kumpulkan folder ini dalam satu ZIP.

## Sampel sebelum dan sesudah

Sampel berisi **20 baris**, lima untuk masing-masing MBG, CKG, Kopdes Merah
Putih, dan Sekolah Rakyat. Data berasal dari pengambilan X pada **21 September
2026**. Identitas akun, ID unggahan, tautan, dan informasi pribadi sudah
disamarkan sebelum sampel disertakan dalam repo.

CSV sesudah preprocessing memuat baris yang sama dan menambahkan
`cleaned_text`, tanda pemeriksaan kualitas, serta metadata asal data. Dari
20 baris, **13 siap dilabeli dan 7 perlu diperiksa**. Seluruh baris tetap
disimpan. Cocokkan program dan `run_id` pada nama folder untuk menemukan
pasangan sebelum dan sesudahnya.

## Cara menjalankan

Gunakan Python 3.12 atau lebih baru. Jalankan perintah dari folder ini:

```bash
python -m pip install -r requirements.txt
```

Untuk memproses sampel dan menulis hasil baru tanpa mengganti CSV yang
dikumpulkan:

```bash
python src/preprocess.py --input-dir data/raw/samples/x --output-root data/processed/recheck --skip-existing
```

Preprocessing merapikan Unicode, HTML entities, huruf besar-kecil, dan spasi;
menghapus URL serta mention; dan mempertahankan kata negasi, hashtag, serta
emoji. Baris duplikat dalam satu CSV, bahasa yang tidak sesuai, dan teks yang
perlu diperiksa diberi tanda. Saat beberapa run digabung, duplikat antar-run
masih perlu disaring berdasarkan `target_program` dan `tweet_id`.

Untuk simulasi dua pengambilan dari sampel:

```bash
python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Simulasi ini berjalan offline dan membuat dua run baru. Ia tidak mengambil
unggahan baru dari X. Sampel awal tetap utuh.

Untuk mengambil data langsung, siapkan Node.js dan Chrome/Edge di Windows
atau Chromium yang sesuai dengan Playwright di Linux/Codespaces. Skrip memakai
Tweet Harvest versi 2.7.1. Periksa rencana pengambilan terlebih dahulu:

```bash
python src/ingest_data.py --program mbg --lookback-days 7 --dry-run
```

Lalu jalankan pengambilan dan preprocessing:

```bash
python src/ingest_data.py --program mbg --lookback-days 7 --limit 50 --preprocess
```

Masukkan token X melalui prompt tersembunyi. Token tidak disertakan dalam
paket ini. Data disimpan dalam folder dengan `run_id` berbeda agar hasil
sebelumnya tidak tertimpa. Kegagalan pengambilan dicoba ulang dan setiap
percobaan memiliki batas waktu.

## Jadwal mingguan

| Hari | Kegiatan |
| --- | --- |
| Senin | Pengambilan dan preprocessing MBG |
| Selasa | Pengambilan dan preprocessing CKG |
| Rabu | Pengambilan dan preprocessing Kopdes Merah Putih |
| Kamis | Pengambilan dan preprocessing Sekolah Rakyat |
| Jumat | Pelabelan dan pemeriksaan kualitas |

Setiap program diambil sekali seminggu. Simulasi periodik di atas dipakai
untuk mencoba pengulangan sesuai LK-04. Jadwal operasional belum diaktifkan.
