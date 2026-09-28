# LK-04: Ingestion dinamis dan automasi prapemrosesan

## Cakupan dan luaran

Sumber sesuai LK-03 adalah posting X tentang MBG, CKG, Kopdes Merah Putih,
dan Sekolah Rakyat. Python mengorkestrasi Tweet Harvest **2.7.1**, yang
menggunakan Playwright. Kata kunci berasal dari YAML yang telah digunakan repo.
Jika versi 2.7.1 sudah ada di npm cache, kolektor menjalankan `node` langsung
untuk menghindari startup npm dan pemrosesan argumen batch Windows. Instalasi
pertama menggunakan `npx`; `--tweet-harvest-bin` dapat menunjuk `dist/bin.js`
secara eksplisit, dan versi lain ditolak.

| Luaran LK-04 | Implementasi |
| --- | --- |
| `ingest_data.py` di `src/` | `src/ingest_data.py` |
| `preprocess.py` di `src/` | `src/preprocess.py` |
| Sampel CSV mentah | `data/raw/samples/x/`: 20 baris sumber yang dianonimkan |
| Dokumentasi eksekusi | README dan panduan ini |
| Simulasi periodik | `--cycles`, `--interval-seconds`, run ID dengan mikrodetik |
| Automasi preprocessing | `--preprocess` memproses CSV yang berhasil diambil |
| Error koneksi | Percobaan terbatas, exponential backoff, timeout proses |

Dataset lengkap lokal tetap diabaikan Git. Pengecualian hanya diberikan pada
sampel kecil untuk tugas. Sampel berasal dari ingestion nyata 21 September 2026,
dan transformasi publikasinya dijelaskan di `data/raw/samples/README.md`.

## 1. Persiapan Codespaces atau lokal

Prasyarat: Python 3.12, uv, Node.js LTS, dan Chromium yang berfungsi.
Windows dapat memakai Chrome/Edge lokal. Semua perintah dijalankan dari root
repo pada branch `feat/lk04-ingestion-preprocessing`.

```bash
uv sync --frozen --extra dev
uv pip check
uv run --frozen --extra dev python -m kuping_negara.healthcheck
node --version
npx --version
```

Di Codespaces/Linux, siapkan Chromium yang sesuai dengan Playwright milik
Tweet Harvest sebelum menjalankan kolektor. Prasyarat browser tetap berlaku
untuk eksekusi tanpa interaksi. `--browser-executable` dapat menunjuk browser
yang sudah tersedia.

## 2. Ingestion dinamis langsung dari X

Cek rencana tanpa token atau akses jaringan X:

```bash
uv run --frozen python src/ingest_data.py --lookback-days 7 --dry-run
```

Ambil rentang tanggal eksplisit dan langsung proses:

```bash
uv run --frozen python src/ingest_data.py --from-date 22-09-2026 --to-date 28-09-2026 --limit 50 --preprocess
```

Mode interaktif meminta token melalui prompt tersembunyi. Masukkan token
hanya di prompt tersebut. Default adalah seluruh program; `--program mbg`
memilih satu program, dan opsi itu boleh diulang. `--limit` merupakan target
crawler; satu batch sumber dapat melebihi target, sehingga jumlah aktual
selalu dicatat di laporan ingestion. Tanggal awal dan akhir
inklusif. Tanpa keduanya, rentang dihitung ulang pada setiap siklus menggunakan
tanggal Asia/Jakarta dan `--lookback-days` (default 7).

Hasil ingestion:

```text
data/raw/x/collected_date=YYYY-MM-DD/program=<program>/
  run_id=YYYYMMDDTHHMMSSffffff+0700/
    <program>_<awal>_<akhir>.csv
    ingestion_report.json
```

Setiap percobaan crawler menggunakan direktori staging sendiri. Hanya CSV
nonkosong yang memiliki header dan baris data dipromosikan ke raw zone.
CSV dari percobaan sebelumnya tidak dapat dianggap sebagai hasil baru.
Data lama tidak ditimpa; kegagalan program berikutnya tetap mempertahankan
hasil program yang telah berhasil.

## 3. Mode tanpa interaksi dan pengambilan berulang

Sediakan `X_AUTH_TOKEN` lewat environment runtime atau Codespaces secret.
Jangan menuliskan token di kode, argumen perintah, screenshot, atau Git.
Mode ini tidak membaca `.env` secara otomatis. Kegagalan menyediakan secret
menghasilkan exit code 1 sebelum crawler dimulai.

```bash
uv run --frozen python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess --cycles 2 --interval-seconds 60
```

Hook Node memasok jawaban prompt Tweet Harvest di memori dari environment,
tanpa menambahkan token ke argumen proses. Prompt yang tidak dikenal ditolak.
Output upstream disembunyikan pada mode ini; wrapper menampilkan status dan
lokasi hasil. Token harus valid dan akun tetap harus memiliki akses X.

| Opsi | Default | Perilaku |
| --- | --- | --- |
| `--attempts` | 3 | Jumlah maksimum percobaan per program |
| `--retry-delay` | 5 detik | Jeda awal; dikalikan dua, maksimum 60 detik |
| `--timeout` | 600 detik | Batas tiap percobaan termasuk prompt/crawler |
| `--cycles` | 1 | Jumlah siklus, berhenti setelah selesai |
| `--interval-seconds` | 60 | Jeda setelah satu siklus selesai |
| `--preprocess` | Nonaktif | Proses otomatis semua CSV yang berhasil |
| `--processed-root` | `data/processed/x` | Lokasi output preprocessing |

Jika seluruh percobaan gagal atau preprocessing gagal, exit code 1 diberikan.
Timeout menghentikan pohon proses crawler/browser. Ctrl+C menghentikan
pipeline dengan exit code 130.

Untuk operasi berkala di Linux/Codespaces, scheduler eksternal dapat menjalankan
perintah satu siklus setiap hari. Contoh cron pukul 00:00 UTC (07:00 WIB):

```cron
0 0 * * * cd /workspaces/kuping-negara && .venv/bin/python src/ingest_data.py --non-interactive --lookback-days 7 --preprocess >> logs/lk04.log 2>&1
```

Sesuaikan root repo dan buat `logs/` terlebih dahulu. Secret harus tersedia di
environment proses scheduler. Cron hanya berjalan ketika mesin/Codespace
aktif; contoh ini tidak otomatis memasang atau mengaktifkan jadwal.

## 4. Simulasi periodik tanpa token

```bash
uv run --frozen python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Empat sampel disalin ke run baru pada setiap siklus: dua siklus menghasilkan
delapan raw CSV, delapan processed CSV, dan laporan masing-masing. Sampel asal
tidak berubah. `ingestion_report.json` menandai `source=offline_replay`;
tanggal publikasi tetap tanggal sumber. Ini membuktikan mekanisme pengulangan
dan prapemrosesan, **bukan keberhasilan akses X terbaru**.

## 5. Preprocessing mandiri

Proses semua sampel yang disertakan:

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --skip-existing
```

Satu file dapat dipilih dengan `--input <path-ke-csv>`. Parameter `--input`
dan `--input-dir` tidak dapat dipakai bersamaan. Path harus mempertahankan
partisi `collected_date`, `program`, dan `run_id` dari kolektor.

Langkah yang diterapkan:

1. Baca ID sebagai teks agar angka panjang tidak kehilangan presisi.
2. Validasi kolom wajib, timestamp, teks kosong, encoding, dan engagement.
3. Normalisasi Unicode NFKC, HTML entities, huruf kecil, dan whitespace.
4. Bersihkan URL, mention, karakter kontrol, dan tanda `#` dari cleaned text.
5. Pertahankan emoji, tanda baca, dan negasi sebagai sinyal sentimen.
6. Tandai duplikasi, ketidaksesuaian bahasa/relevansi, dan cleaned text kosong.
7. Hanya status `accepted` memiliki `is_eligible_for_labeling=True`.
8. Buang kolom profil akun dari output; raw asli lokal tetap utuh.
9. Simpan checksum input/output/config, lineage, dan laporan jumlah baris.

Duplikasi dan baris yang memerlukan review tetap tersedia untuk audit dan
harus dikecualikan dari dataset pemodelan melalui `is_eligible_for_labeling`.
Tokenisasi, stopword removal, dan stemming tidak diwajibkan untuk semua model;
pada tahap ini ditunda ke ekstraksi fitur agar negasi dan sinyal sentimen
tidak hilang sebelum pilihan model ditetapkan.

Output berada di `data/processed/x/processed_date=<tanggal>/program=<program>/
run_id=<ingestion_run_id>/`. CSV dan `quality_report.json` tidak ditimpa.
`--skip-existing` hanya melewati hasil lengkap dengan checksum input,
output, dan konfigurasi yang cocok. Konfigurasi berubah atau output rusak
tidak dilewati; gunakan `--output-root data/processed/recheck` untuk membuat
hasil baru tanpa menghapus hasil lama. Dataset kosong/invalid menghasilkan
kegagalan eksplisit, bukan hasil yang siap digunakan.

## 6. Verifikasi dan bukti tugas

```bash
uv run --frozen --extra dev pytest
uv run --frozen --extra dev python -m compileall -q src tests
```

Pengujian mencakup isolasi retry, kegagalan tanpa secret, kegagalan koneksi,
timestamp mikrodetik, dua siklus tanpa overwrite, integritas raw, batch skip,
runtime cache dengan versi yang tepat, dan hook prompt tanpa mencetak token. Hasil uji dan audit data lokal dicatat
di `docs/lk04-verification.json`. Audit agregat tidak berisi isi posting.

Untuk penyerahan, gunakan tautan branch eksperimen, kedua skrip, folder sampel,
dan dokumentasi. Jalankan ingestion live dengan token valid untuk melengkapi
bukti akses X terbaru. Bukti offline dan ingestion live perlu diberi label
yang berbeda.
