# Menjalankan jadwal mingguan dengan Airflow

Airflow menjalankan skrip yang sudah ada di repo ini. Setiap Senin pukul 07.00
WIB, Airflow mengambil data MBG lalu langsung menjalankan preprocessing.
Selasa untuk CKG, Rabu untuk Kopdes Merah Putih, dan Kamis untuk Sekolah
Rakyat. Jumat tetap dipakai untuk memeriksa kualitas data dan memberi label
secara manual.

Jadwal membaca `collection_day` dari
`configs/keywords/programs.example.yaml`. Jadi kalau hari sebuah program
diubah di sana, jadwalnya ikut berubah setelah Airflow membaca ulang DAG.
Setiap eksekusi mengambil tujuh **hari kalender yang sudah selesai** sebelum
hari berjalan. Contohnya, eksekusi MBG pada Senin 5 Oktober mengambil unggahan
28 September–4 Oktober. Pilihan ini mencegah bagian hari Senin yang belum
selesai terlewat dari pengambilan minggu berikutnya.

## Menyalakan Airflow

Jalankan dari folder utama repo setelah Docker aktif:

```bash
docker compose -f compose.airflow.yaml up --build -d
```

Build pertama mengunduh Airflow, Node.js, Chromium, dan Tweet Harvest 2.7.1,
jadi bisa memakan waktu dan ruang penyimpanan. Buka `http://localhost:8080`.
Airflow standalone membuat akun awal saat pertama menyala. Detailnya bisa
dilihat dengan:

```bash
docker compose -f compose.airflow.yaml logs airflow
docker compose -f compose.airflow.yaml exec airflow cat /opt/airflow/state/simple_auth_manager_passwords.json.generated
```

Kata sandi itu hanya untuk penggunaan lokal; jangan masukkan ke Git. Data
Airflow disimpan di volume Docker, sedangkan hasil penarikan tetap masuk ke
`data/raw/`, hasil preprocessing ke `data/processed/`, dan berkas kerja
Tweet Harvest ke `tweets-data/` di repo.

Keempat DAG dibuat **paused** saat pertama kali muncul. Sebelum diaktifkan,
cek apakah semuanya berhasil dibaca dan uji rencana pengambilan tanpa
mengakses X:

```bash
docker compose -f compose.airflow.yaml exec airflow airflow dags list-import-errors
docker compose -f compose.airflow.yaml exec airflow python src/ingest_data.py --program mbg --preprocess --dry-run
```

Untuk pengambilan langsung, isi `X_AUTH_TOKEN` di `.env` lokal. Docker Compose
membaca `.env` dari folder repo dan meneruskan token sebagai environment
container; nilainya tidak disimpan dalam DAG atau argumen proses. Setelah
token siap, aktifkan DAG yang ingin dijalankan dari UI Airflow. Sebaiknya
mulai dari satu program dan periksa hasil serta lognya sebelum mengaktifkan
yang lain.

Perintah untuk menghentikan layanan tanpa menghapus riwayatnya:

```bash
docker compose -f compose.airflow.yaml down
```

Setup satu container ini cocok untuk percobaan lokal. Docker dan komputer
harus tetap menyala pada jam jadwal. Jika dijalankan di Codespaces, proses
penjadwalan berhenti saat Codespace berhenti; untuk jadwal yang selalu aktif,
Airflow perlu dipindah ke mesin yang terus berjalan. Jangan gunakan setup
lokal berbasis SQLite ini sebagai layanan produksi.

