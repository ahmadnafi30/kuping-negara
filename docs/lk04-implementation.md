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
| `scripts/run_ingestion.ps1` | Menjalankan satu siklus lewat Task Scheduler Windows dan menyimpan log |
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

Jadwal operasional mengikuti pembagian mingguan pada rancangan sebelumnya:

| Hari | Kegiatan | Program yang dipilih |
| --- | --- | --- |
| Senin | Pengambilan dan preprocessing MBG | `mbg` |
| Selasa | Pengambilan dan preprocessing CKG | `ckg` |
| Rabu | Pengambilan dan preprocessing Kopdes Merah Putih | `kopdes_merah_putih` |
| Kamis | Pengambilan dan preprocessing Sekolah Rakyat | `sekolah_rakyat` |
| Jumat | Pelabelan dan pemeriksaan kualitas hasil minggu tersebut | Tidak ada pengambilan terjadwal |

Masing-masing program diambil sekali seminggu pada harinya. Hari pengambilan
berbeda dari rentang tanggal data: `--lookback-days 7` tetap mengambil
unggahan dalam rentang tujuh hari, bukan hanya unggahan pada hari tugas berjalan.
Zona waktu yang dipakai adalah Asia/Jakarta.

Jadwal Airflow lokal sekarang tersedia dan membaca `collection_day` dari
konfigurasi kata kunci. Keempat jadwal dibuat dalam keadaan nonaktif sampai
diperiksa dan diaktifkan di UI. Cara menjalankannya ada di
`docs/airflow-scheduling.md`. Panduan Task Scheduler di bawah tetap bisa
dipakai bila lebih cocok menjalankan skrip langsung di Windows.

### Mencoba pengulangan di terminal

Untuk simulasi periodik LK-04, perintah berikut menjalankan dua pengambilan
MBG dengan jeda satu menit setelah pengambilan pertama selesai:

```bash
uv run --frozen python src/ingest_data.py --program mbg --non-interactive --lookback-days 7 --preprocess --cycles 2 --interval-seconds 60
```

Mode `--non-interactive` memakai token dari variabel environment
`X_AUTH_TOKEN`, sehingga tidak perlu mengisi prompt berulang kali. Token
harus tersedia di environment sebelum skrip dijalankan. Berkas `.env`
tidak dibaca secara otomatis oleh skrip, dan token tidak disertakan di Git.

Jika tanggal tidak ditentukan secara manual, rentang tujuh hari terakhir
dihitung kembali pada setiap siklus mengikuti waktu Asia/Jakarta.

Skrip berhenti setelah dua siklus selesai. Jika satu siklus gagal setelah
semua percobaan ulang habis, skrip juga berhenti dengan status gagal.
Jeda dihitung setelah pekerjaan selesai, jadi perintah ini bukan jadwal
tetap yang berjalan setiap menit pada jam tertentu.

Simulasi singkat ini dipakai untuk memeriksa bahwa pengambilan dapat diulang
dan hasil lama tetap utuh. Jadwal operasionalnya tetap sekali seminggu
untuk setiap program.

### Jadwal mingguan di Windows

Untuk repo lokal, gunakan `scripts/run_ingestion.ps1`. Skrip ini menjalankan
satu pengambilan untuk program yang dipilih melalui `-Program`, langsung
melakukan preprocessing, lalu menyimpan log baru di `logs/`. Token diambil dari environment atau,
jika belum tersedia, dari baris `X_AUTH_TOKEN=...` di `.env` lokal. Nilainya
tidak dicetak ke log dan tidak dimasukkan ke argumen proses.

Cek rencana pengambilannya terlebih dahulu dari folder repo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_ingestion.ps1 -Program mbg -DryRun
```

Untuk mencoba alur dan pencatatan log tanpa mengakses X:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_ingestion.ps1 -ReplayDir data/raw/samples/x
```

Setelah `.env` lokal berisi token, coba pengambilan langsung untuk MBG:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_ingestion.ps1 -Program mbg
```

Pasang empat task terpisah di **Task Scheduler**, satu untuk setiap program.
Mulai dari MBG melalui **Create Task**:

1. Beri nama `Kuping Negara - MBG`. Gunakan akun Windows yang mempunyai
   akses ke repo, Node.js, serta Chrome atau Edge. Untuk percobaan awal, pilih
   **Run only when user is logged on**.
2. Di **Triggers**, pilih **Weekly**, isi **Recur every: 1 week**, lalu centang
   **Monday**. Jam **07.00** bisa dipakai sebagai contoh waktu pengambilan;
   rancangan sebelumnya menentukan hari, belum menentukan jamnya. Task
   Scheduler mengikuti zona waktu Windows; pastikan perangkat memakai WIB.
3. Di **Actions**, pilih **Start a program**. Isi **Program/script** dengan
   `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`.
4. Isi **Add arguments** dengan:

   ```text
   -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "D:\Mlops\kuping-negara\scripts\run_ingestion.ps1" -Program mbg
   ```

5. Isi **Start in** dengan `D:\Mlops\kuping-negara`. Sesuaikan kedua lokasi
   tersebut jika repo dipindahkan.
6. Di **Settings**, aktifkan **Run task as soon as possible after a scheduled
   start is missed**. Untuk pekerjaan yang masih berjalan, pilih **Do not
   start a new instance** agar pengambilan tidak bertumpuk.
7. Simpan task, klik **Run**, lalu periksa **Last Run Result** dan log terbaru
   di `logs/`. Hasil `0x0` berarti proses selesai dengan kode sukses. Tetap
   periksa jumlah baris dan laporan kualitas untuk melihat hasil datanya.

Ulangi pengaturan tersebut untuk tiga program lain. Ubah nama task, hari
trigger, dan nilai `-Program` sesuai tabel berikut:

| Nama task | Hari pada trigger Weekly | Argumen program |
| --- | --- | --- |
| `Kuping Negara - MBG` | Monday | `-Program mbg` |
| `Kuping Negara - CKG` | Tuesday | `-Program ckg` |
| `Kuping Negara - Kopdes Merah Putih` | Wednesday | `-Program kopdes_merah_putih` |
| `Kuping Negara - Sekolah Rakyat` | Thursday | `-Program sekolah_rakyat` |

Gunakan satu trigger untuk satu program. Satu task yang diberi trigger
Senin sampai Kamis akan menjalankan action yang sama pada keempat hari.
Opsi `-Program` yang menentukan program mana yang diambil.

Dengan pilihan awal di atas, akun harus sedang login dan laptop harus
menyala. Jika ingin berjalan saat layar terkunci, pastikan pengaturan daya
tidak membuat laptop tidur pada waktu pengambilan. Mode berjalan saat akun
tidak login perlu diuji lagi dengan akun dan environment yang dipakai task.

Pemanggilan tanpa `-Program` mengambil keempat program sekaligus. Gunakan
pilihan program pada setiap task mingguan agar sesuai pembagian hari.
Kegiatan pelabelan dan pemeriksaan pada Jumat masih dilakukan terpisah;
belum ada task otomatis untuk kegiatan tersebut.

Pengaturan trigger dan action mengikuti
[dokumentasi Task Scheduler dari Microsoft](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasks).

### Jadwal mingguan di Linux atau Codespaces

Perintah satu siklus juga bisa dijalankan melalui cron. Empat baris berikut
mengambil satu program pada harinya setiap minggu. Contoh ini berjalan pukul
00.00 **menurut zona waktu mesin**; jika mesinnya memakai UTC, waktunya sama
dengan 07.00 WIB pada hari yang sama:

```cron
0 0 * * 1 cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --program mbg --non-interactive --lookback-days 7 --preprocess >> logs/mbg.log 2>&1
0 0 * * 2 cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --program ckg --non-interactive --lookback-days 7 --preprocess >> logs/ckg.log 2>&1
0 0 * * 3 cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --program kopdes_merah_putih --non-interactive --lookback-days 7 --preprocess >> logs/kopdes.log 2>&1
0 0 * * 4 cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --program sekolah_rakyat --non-interactive --lookback-days 7 --preprocess >> logs/sekolah-rakyat.log 2>&1
```

Sesuaikan lokasi repo, buat folder `logs/`, dan pastikan token tersedia bagi
proses cron. Jadwal perlu dipasang sendiri dan hanya berjalan selama mesin
atau Codespace aktif. Gunakan path lengkap untuk Node.js atau siapkan `PATH`
di environment cron, karena environment-nya bisa berbeda dari terminal.
Contoh cron ini memanggil Python secara langsung, jadi `.env` tidak dibaca
otomatis. Tidak ada jadwal ingestion di GitHub Actions; workflow yang tersedia
saat ini menjalankan pemeriksaan kode.

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
Karakter penghubung yang membentuk emoji gabungan tetap disimpan.

Emoji, tanda baca, dan kata negasi seperti "tidak" tetap disimpan karena
bisa memengaruhi makna sentimen. Tokenisasi, stopword removal, dan stemming
akan disesuaikan dengan model pada tahap ekstraksi fitur.

Pencocokan kata kunci dilakukan pada teks yang sudah dibersihkan. Nama akun
atau potongan URL yang kebetulan berisi kata seperti `mbg` tidak cukup untuk
menandai unggahan sebagai relevan. Pemeriksaan bahasa masih memakai label
`lang` dari X, dan kecocokan kata kunci belum menjamin konteksnya benar.

Baris duplikat, bahasa yang tidak sesuai, teks yang kurang relevan, serta
teks yang kosong setelah dibersihkan diberi tanda untuk diperiksa. Hanya
baris dengan `is_eligible_for_labeling=True` yang ditandai siap untuk
pelabelan. Baris lainnya tetap tersimpan agar bisa diperiksa kembali.

Duplikat saat ini diperiksa berdasarkan ID dalam satu CSV. Saat beberapa
pengambilan digabung untuk pelabelan atau training, sisakan satu baris untuk
setiap pasangan `target_program` dan `tweet_id`. Ini perlu dilakukan karena
rentang tujuh hari yang berulang bisa mengambil unggahan yang sama lagi.

Jika kolom wajib, tanggal, teks mentah, atau jumlah interaksi tidak valid,
skrip menolak CSV tersebut dan mengembalikan status gagal. Nilai yang hilang
tidak diisi dengan angka atau teks tebakan. Data mentahnya tetap tersimpan
untuk diperiksa dan file lain dalam pemrosesan batch tetap dilanjutkan.

Hasil disimpan di `data/processed/x/`, dengan pembagian folder berdasarkan
tanggal pemrosesan, program, dan `run_id`. Setiap hasil terdiri dari CSV
dan `quality_report.json`. Laporan tersebut berisi jumlah baris, hasil
pemeriksaan, dan checksum data serta konfigurasi. File mentah tidak diubah.

Opsi `--skip-existing` melewati hasil yang sudah lengkap dan checksum-nya
masih cocok. Jika data atau konfigurasi berubah, hasil lama tidak ditimpa.
Untuk membuat hasil pemrosesan ulang di tempat lain, gunakan
`--output-root data/processed/recheck`.

Pemeriksaan ulang memperbarui aturan menjadi `preprocessing_version=3`.
Hasil dari versi lama tidak dianggap cocok oleh `--skip-existing`. Gunakan
folder hasil baru saat memproses ulang agar hasil pemeriksaan lama tetap ada.

## Hasil yang sudah diperoleh

Pada 28 September 2026, pengambilan langsung untuk rentang 22–28 September
berhasil mendapatkan 80 unggahan: masing-masing 20 untuk MBG, CKG, Kopdes
Merah Putih, dan Sekolah Rakyat. Seluruhnya langsung diproses oleh skrip.
Dari hasil pemeriksaan, 59 baris ditandai siap untuk pelabelan dan 21 baris
masih perlu diperiksa.

Simulasi dua siklus juga berhasil membuat file baru tanpa mengubah data
sebelumnya. Pemeriksaan checksum memastikan file mentah dan sampel awal
tetap sama. Rinciannya ada di `docs/lk04-verification.json`.

Setelah aturan preprocessing diperbaiki, 80 unggahan hasil pengambilan
langsung diproses ulang di folder terpisah. Hasilnya tetap 59 baris siap
untuk pelabelan dan 21 perlu diperiksa. File mentah tetap sama. Catatan
pemeriksaan ulang ada di `docs/lk04-preprocessing-review.json`.

Pengujian kode dapat dijalankan dengan:

```bash
uv run --frozen --extra dev pytest
uv run --frozen --extra dev python -m compileall -q src tests
```

Pada pemeriksaan ulang, seluruh 48 pengujian lokal lulus. Pengujian mencakup
percobaan ulang saat gagal, batas waktu, pemilihan versi Tweet Harvest,
pembersihan teks, dan penyimpanan hasil tanpa menimpa data lama. Tambahan
pengujian memeriksa kata kunci di URL/mention, emoji gabungan, dan peluncur
Windows. Peluncur diuji memakai proses pengganti untuk memastikan token
tidak tercetak serta kode sukses atau gagal diteruskan dengan benar.

Pengujian tersebut memeriksa alur skrip, sedangkan jadwal Airflow diuji
terpisah. Jadwal baru dapat dibuktikan berjalan otomatis setelah DAG
diaktifkan dan satu trigger mingguan benar-benar selesai.
