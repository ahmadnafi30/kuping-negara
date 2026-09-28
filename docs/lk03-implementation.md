# Implementasi Pengambilan dan Pengolahan Data

Dokumen ini menjelaskan penerapan alur data yang dirancang pada LK-03,
mulai dari mengambil unggahan di X sampai membersihkan hasilnya. Alur ini
juga digunakan untuk pengerjaan LK-04.

Data yang dikumpulkan membahas empat program: Makan Bergizi Gratis (MBG),
Cek Kesehatan Gratis (CKG), Koperasi Desa Merah Putih, dan Sekolah Rakyat.
Kata kunci masing-masing program disimpan di
`configs/keywords/programs.example.yaml`, sehingga bisa disesuaikan tanpa
mengubah skrip.

## Skrip dan data yang digunakan

| Berkas atau folder | Kegunaan |
| --- | --- |
| `src/ingest_data.py` | Mengambil data dari X dan menjalankan pengambilan berulang |
| `src/preprocess.py` | Membersihkan satu CSV atau seluruh CSV dalam sebuah folder |
| `data/raw/x/` | Menyimpan hasil pengambilan data lengkap secara lokal |
| `data/raw/samples/x/` | Menyimpan sampel kecil yang disertakan di repo |
| `data/processed/x/` | Menyimpan hasil pembersihan dan laporan kualitas data |
| `docs/lk04-verification.json` | Mencatat hasil pengujian dan jumlah data yang berhasil diproses |

Pengambilan data memakai Tweet Harvest versi 2.7.1, yang berjalan dengan
Playwright. Jika paket versi tersebut sudah terpasang di npm cache, skrip
langsung menjalankannya lewat Node.js. Jika belum ada, skrip memakai `npx`.
Lokasi paket juga bisa ditentukan melalui `--tweet-harvest-bin`.

## Menyiapkan lingkungan

Jalankan perintah berikut dari folder utama repo. Pastikan Python 3.12, uv,
Node.js LTS, dan browser sudah tersedia.

```bash
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
node --version
npx --version
```

Di Windows, skrip bisa memakai Chrome atau Edge yang sudah terpasang.
Di Codespaces atau Linux, siapkan Chromium yang sesuai dengan Playwright
milik Tweet Harvest. Jika browser tidak ditemukan, tentukan lokasinya
melalui `--browser-executable`.

## Mengambil data dari X

Sebelum mengambil data, cek dulu daftar program, kata kunci, dan rentang
tanggal yang akan digunakan:

```bash
uv run --frozen python src/ingest_data.py --lookback-days 7 --dry-run
```

Perintah ini hanya menampilkan rencana pengambilan. Untuk mengambil unggahan
dalam tujuh hari terakhir dan langsung membersihkan hasilnya, jalankan:

```bash
uv run --frozen python src/ingest_data.py --lookback-days 7 --limit 50 --preprocess
```

Saat skrip berjalan, Tweet Harvest meminta token X melalui prompt tersembunyi.
Masukkan token di sana. Untuk mengambil satu program saja, tambahkan
`--program mbg`, misalnya. Opsi `--program` bisa diulang untuk memilih beberapa
program.

Rentang tanggal juga bisa ditentukan sendiri:

```bash
uv run --frozen python src/ingest_data.py --from-date 22-09-2026 --to-date 28-09-2026 --limit 50 --preprocess
```

Tanggal awal dan akhir ikut dihitung. Opsi `--limit` menjadi target jumlah
unggahan, tetapi satu batch dari X bisa berisi lebih banyak data. Jumlah yang
benar-benar didapat dicatat di `ingestion_report.json`.

Setiap pengambilan disimpan dalam folder baru:

```text
data/raw/x/
  collected_date=YYYY-MM-DD/
    program=<nama_program>/
      run_id=<waktu_pengambilan>/
        <nama_program>_<tanggal_awal>_<tanggal_akhir>.csv
        ingestion_report.json
```

`run_id` memakai waktu pengambilan sampai mikrodetik, sehingga hasil baru
tidak menimpa data lama. Tiap percobaan juga punya folder sementara sendiri.
CSV baru dipindahkan ke `data/raw/x/` setelah dipastikan memiliki header dan
setidaknya satu baris data.

Jika pengambilan gagal, skrip mencoba lagi. Pengaturan awalnya adalah tiga
percobaan, dengan jeda 5 lalu 10 detik. Tiap percobaan dibatasi 600 detik.
Pengaturan ini bisa diubah melalui `--attempts`, `--retry-delay`, dan
`--timeout`. Jika semua percobaan gagal, skrip berhenti dengan status gagal;
data dari program yang sudah berhasil tetap tersimpan.

## Menjalankan pengambilan secara berkala

Untuk menjalankan dua pengambilan berturut-turut dengan jeda satu menit:

```bash
uv run --frozen python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess --cycles 2 --interval-seconds 60
```

Mode `--non-interactive` mengambil token dari variabel environment
`X_AUTH_TOKEN`, jadi tidak perlu mengisi prompt pada setiap pengambilan.
Token harus tersedia di environment sebelum perintah dijalankan; skrip
tidak membaca `.env` secara otomatis. Token tetap disimpan di luar Git.

Jeda dihitung setelah satu pengambilan selesai. Jika tanggal tidak ditentukan
secara manual, rentang tujuh hari terakhir dihitung kembali pada setiap siklus
mengikuti waktu Asia/Jakarta.

Untuk jadwal harian di Linux, perintah satu siklus dapat dijalankan melalui
cron. Contoh berikut berjalan pukul 00.00 UTC atau 07.00 WIB:

```cron
0 0 * * * cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess >> logs/lk04.log 2>&1
```

Sesuaikan lokasi repo, buat folder `logs/`, dan pastikan token tersedia bagi
proses cron. Contoh ini perlu dipasang sendiri. Jadwal hanya berjalan selama
mesin atau Codespace aktif.

## Mencoba alur dengan sampel

Repo menyertakan 20 baris dari pengambilan pada 21 September 2026, yaitu lima
baris untuk setiap program. Identitas akun, ID unggahan, dan tautan telah
disamarkan. Asal sampel dan perubahan yang dilakukan dijelaskan di
`data/raw/samples/README.md` dan `provenance.json`. Data lengkap tetap ada
secara lokal.

Sampel ini bisa dipakai untuk mencoba pengambilan berulang tanpa login X:

```bash
uv run --frozen python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Simulasi menyalin sampel ke dua folder pengambilan baru, lalu menjalankan
preprocessing. Hasilnya adalah delapan CSV mentah dan delapan CSV yang sudah
diproses. Sampel awal tetap utuh. Laporan memberi tanda
`source=offline_replay`, sehingga hasil simulasi mudah dibedakan dari
pengambilan langsung di X.

## Membersihkan data

Preprocessing bisa dijalankan bersama ingestion melalui `--preprocess`,
atau secara terpisah. Untuk memproses seluruh sampel:

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --skip-existing
```

Untuk satu CSV, gunakan `--input <lokasi_file.csv>`. Pertahankan susunan folder
`collected_date`, `program`, dan `run_id`, karena informasi tersebut dipakai
untuk mencatat asal data.

Pembersihan dimulai dengan memeriksa kolom wajib, tanggal, teks kosong, dan
angka engagement. ID dibaca sebagai teks agar angka panjang tidak berubah.
Setelah itu, skrip merapikan Unicode, HTML entities, huruf besar-kecil, dan
spasi, lalu menghapus URL, mention, serta karakter kontrol dari `cleaned_text`.
Kata dalam hashtag tetap dipertahankan.

Emoji, tanda baca, dan kata negasi seperti "tidak" masih disimpan karena bisa
membantu membaca sentimen. Tokenisasi, stopword removal, dan stemming ditunda
ke tahap ekstraksi fitur agar bisa disesuaikan dengan model yang dipilih.

Baris duplikat, bahasa yang tidak sesuai, teks yang kurang relevan, atau teks
yang kosong setelah dibersihkan diberi tanda untuk diperiksa. Hanya baris
dengan `is_eligible_for_labeling=True` yang ditandai siap untuk pelabelan.
Baris lain tetap tersimpan agar hasil pemeriksaan bisa ditelusuri.

Hasilnya disimpan di `data/processed/x/`, dengan pembagian folder berdasarkan
tanggal pemrosesan, program, dan `run_id`. Setiap hasil terdiri dari CSV dan
`quality_report.json`. Laporan mencatat jumlah baris, hasil pemeriksaan, serta
checksum data dan konfigurasi. File mentah tidak diubah.

Opsi `--skip-existing` melewati hasil yang sudah lengkap dan checksum-nya
masih cocok. Jika data atau konfigurasi berubah, hasil lama tidak ditimpa.
Untuk memproses ulang ke tempat lain, gunakan
`--output-root data/processed/recheck`.

## Hasil pengujian

Pada 28 September 2026, pengambilan langsung untuk rentang 22–28 September
berhasil mendapatkan 80 unggahan: masing-masing 20 untuk MBG, CKG, Kopdes
Merah Putih, dan Sekolah Rakyat. Seluruhnya langsung diproses oleh skrip.
Sebanyak 59 baris ditandai siap untuk pelabelan dan 21 baris perlu diperiksa
lagi.

Simulasi dua siklus juga berhasil membuat file baru tanpa mengubah data
sebelumnya. Pemeriksaan checksum memastikan file mentah dan sampel awal
tetap sama. Rincian hasilnya ada di `docs/lk04-verification.json`.

Untuk menjalankan pengujian kode:

```bash
uv run --frozen --extra dev pytest
uv run --frozen --extra dev python -m compileall -q src tests
```

Seluruh 40 pengujian lulus, termasuk percobaan ulang saat gagal, batas waktu,
pemilihan versi Tweet Harvest, pembersihan teks, dan penyimpanan hasil tanpa
menimpa data lama. Pemeriksaan otomatis di GitHub juga sudah lulus.
