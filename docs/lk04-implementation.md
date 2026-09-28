# LK-04: Pengambilan Data dan Prapemrosesan

Pada LK-04, rancangan alur data dari LK-03 mulai dijalankan. Data diambil dari
X, disimpan sebagai CSV, lalu dibersihkan melalui skrip Python. Pengambilan
bisa diulang tanpa menimpa hasil sebelumnya.

Data yang dikumpulkan berkaitan dengan empat program: Makan Bergizi Gratis
(MBG), Cek Kesehatan Gratis (CKG), Koperasi Desa Merah Putih, dan Sekolah
Rakyat. Kata kuncinya ada di `configs/keywords/programs.example.yaml`.
Jika ingin menyesuaikan pencarian, cukup ubah berkas tersebut.

## Berkas yang digunakan

| Berkas atau folder | Isi |
| --- | --- |
| `src/ingest_data.py` | Skrip untuk mengambil data dan menjalankannya secara berulang |
| `src/preprocess.py` | Skrip untuk membersihkan satu CSV atau sekumpulan CSV |
| `data/raw/x/` | Hasil pengambilan data lengkap yang disimpan secara lokal |
| `data/raw/samples/x/` | Sampel kecil yang disertakan di repo |
| `data/processed/x/` | Data yang sudah dibersihkan dan laporan pemeriksaannya |
| `docs/lk04-verification.json` | Catatan hasil pengambilan data dan pengujian |

Skrip pengambilan data menggunakan Tweet Harvest versi 2.7.1 yang berjalan
dengan Playwright. Jika paketnya sudah ada di npm cache, skrip menjalankannya
langsung lewat Node.js. Jika belum, skrip menggunakan `npx`. Lokasi paket bisa
ditentukan sendiri melalui `--tweet-harvest-bin`.

## Sebelum menjalankan skrip

Pastikan Python 3.12, uv, Node.js LTS, dan browser sudah tersedia. Jalankan
perintah berikut dari folder utama repo:

```bash
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
node --version
npx --version
```

Di Windows, skrip bisa memakai Chrome atau Edge yang sudah terpasang.
Untuk Codespaces atau Linux, siapkan Chromium yang sesuai dengan Playwright
milik Tweet Harvest. Gunakan `--browser-executable` jika lokasi browser perlu
ditentukan secara manual.

## Mengambil data dari X

Cek dulu program, kata kunci, dan rentang tanggal yang akan digunakan:

```bash
uv run --frozen python src/ingest_data.py --lookback-days 7 --dry-run
```

Opsi `--dry-run` hanya menampilkan rencana pengambilan. Untuk mengambil data
tujuh hari terakhir sekaligus membersihkannya, jalankan:

```bash
uv run --frozen python src/ingest_data.py --lookback-days 7 --limit 50 --preprocess
```

Tweet Harvest akan meminta token X melalui prompt tersembunyi. Masukkan
token pada prompt tersebut. Secara bawaan, skrip mengambil data untuk keempat
program. Tambahkan `--program mbg` jika hanya ingin mengambil data MBG.
Opsi `--program` juga bisa diulang untuk memilih beberapa program.

Rentang tanggal dapat ditentukan sendiri, misalnya:

```bash
uv run --frozen python src/ingest_data.py --from-date 22-09-2026 --to-date 28-09-2026 --limit 50 --preprocess
```

Tanggal awal dan akhir ikut dihitung. Nilai `--limit` menjadi target jumlah
unggahan. Karena X mengirim data dalam batch, jumlah yang diperoleh bisa
melebihi target. Jumlah sebenarnya dicatat di `ingestion_report.json`.

### Penyimpanan hasil dan penanganan kegagalan

Setiap pengambilan disimpan dalam folder baru:

```text
data/raw/x/
  collected_date=YYYY-MM-DD/
    program=<nama_program>/
      run_id=<waktu_pengambilan>/
        <nama_program>_<tanggal_awal>_<tanggal_akhir>.csv
        ingestion_report.json
```

`run_id` memakai waktu pengambilan hingga mikrodetik untuk membedakan hasil
setiap kali skrip dijalankan. Tiap percobaan juga memiliki folder sementara
sendiri. CSV baru dipindahkan ke `data/raw/x/` setelah dipastikan memiliki
header dan setidaknya satu baris data.

Jika pengambilan gagal, skrip mencoba kembali. Pengaturan awalnya adalah
tiga percobaan, dengan jeda 5 lalu 10 detik. Setiap percobaan dibatasi
600 detik. Pengaturan ini bisa diubah melalui `--attempts`, `--retry-delay`,
dan `--timeout`. Jika seluruh percobaan gagal, skrip berhenti dan memberi
status gagal. Data dari program yang sudah berhasil tetap tersimpan.

## Menjalankan pengambilan secara berkala

Perintah berikut menjalankan dua pengambilan dengan jeda satu menit setelah
pengambilan pertama selesai:

```bash
uv run --frozen python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess --cycles 2 --interval-seconds 60
```

Mode `--non-interactive` memakai token dari variabel environment
`X_AUTH_TOKEN`, sehingga tidak perlu mengisi prompt berulang kali. Token
harus tersedia di environment sebelum skrip dijalankan. Berkas `.env`
tidak dibaca secara otomatis oleh skrip, dan token tidak disertakan di Git.

Jika tanggal tidak ditentukan secara manual, rentang tujuh hari terakhir
dihitung kembali pada setiap siklus mengikuti waktu Asia/Jakarta.

Untuk pengambilan harian di Linux, perintah satu siklus bisa dijalankan
melalui cron. Contoh ini berjalan pukul 00.00 UTC atau 07.00 WIB:

```cron
0 0 * * * cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess >> logs/lk04.log 2>&1
```

Sesuaikan lokasi repo, buat folder `logs/`, dan pastikan token tersedia bagi
proses cron. Jadwal perlu dipasang sendiri dan hanya berjalan selama mesin
atau Codespace aktif.

## Mencoba alur dengan sampel

Repo menyertakan 20 baris dari pengambilan pada 21 September 2026, yaitu
lima baris untuk setiap program. Identitas akun, ID unggahan, dan tautannya
telah disamarkan. Asal sampel dan perubahan yang dilakukan dijelaskan di
`data/raw/samples/README.md` serta `provenance.json`. Data lengkap tetap
disimpan secara lokal.

Untuk mencoba pengambilan berulang tanpa login X, jalankan:

```bash
uv run --frozen python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Simulasi ini menyalin sampel ke dua folder pengambilan baru, lalu menjalankan
preprocessing. Hasilnya berupa delapan CSV mentah dan delapan CSV yang sudah
diproses. Sampel awal tetap utuh. Laporan mencatat `source=offline_replay`
untuk membedakan simulasi dari pengambilan langsung di X.

## Membersihkan data

Preprocessing bisa dijalankan bersama ingestion melalui `--preprocess` atau
secara terpisah. Untuk membersihkan seluruh sampel:

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --skip-existing
```

Gunakan `--input <lokasi_file.csv>` untuk satu CSV. Susunan folder
`collected_date`, `program`, dan `run_id` perlu dipertahankan karena dipakai
untuk mencatat asal dan waktu pengambilan data.

Skrip terlebih dahulu memeriksa kolom wajib, tanggal, teks kosong, dan
jumlah interaksi seperti like atau repost. ID dibaca sebagai teks agar
angka panjang tidak berubah. Setelah itu, skrip merapikan Unicode, HTML
entities, huruf besar-kecil, dan spasi. URL, mention, dan karakter kontrol
dihapus dari `cleaned_text`, sedangkan kata dalam hashtag dipertahankan.

Emoji, tanda baca, dan kata negasi seperti "tidak" tetap disimpan karena
bisa memengaruhi makna sentimen. Tokenisasi, stopword removal, dan stemming
akan disesuaikan dengan model pada tahap ekstraksi fitur.

Baris duplikat, bahasa yang tidak sesuai, teks yang kurang relevan, serta
teks yang kosong setelah dibersihkan diberi tanda untuk diperiksa. Hanya
baris dengan `is_eligible_for_labeling=True` yang ditandai siap untuk
pelabelan. Baris lainnya tetap tersimpan agar bisa diperiksa kembali.

Hasil disimpan di `data/processed/x/`, dengan pembagian folder berdasarkan
tanggal pemrosesan, program, dan `run_id`. Setiap hasil terdiri dari CSV
dan `quality_report.json`. Laporan tersebut berisi jumlah baris, hasil
pemeriksaan, dan checksum data serta konfigurasi. File mentah tidak diubah.

Opsi `--skip-existing` melewati hasil yang sudah lengkap dan checksum-nya
masih cocok. Jika data atau konfigurasi berubah, hasil lama tidak ditimpa.
Untuk membuat hasil pemrosesan ulang di tempat lain, gunakan
`--output-root data/processed/recheck`.

## Hasil yang sudah diperoleh

Pada 28 September 2026, pengambilan langsung untuk rentang 22–28 September
berhasil mendapatkan 80 unggahan: masing-masing 20 untuk MBG, CKG, Kopdes
Merah Putih, dan Sekolah Rakyat. Seluruhnya langsung diproses oleh skrip.
Dari hasil pemeriksaan, 59 baris ditandai siap untuk pelabelan dan 21 baris
masih perlu diperiksa.

Simulasi dua siklus juga berhasil membuat file baru tanpa mengubah data
sebelumnya. Pemeriksaan checksum memastikan file mentah dan sampel awal
tetap sama. Rinciannya ada di `docs/lk04-verification.json`.

Pengujian kode dapat dijalankan dengan:

```bash
uv run --frozen --extra dev pytest
uv run --frozen --extra dev python -m compileall -q src tests
```

Seluruh 40 pengujian lulus. Pengujian mencakup percobaan ulang saat gagal,
batas waktu, pemilihan versi Tweet Harvest, pembersihan teks, dan penyimpanan
hasil tanpa menimpa data lama. Pemeriksaan otomatis di GitHub juga lulus.
