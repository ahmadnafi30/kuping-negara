# Airflow di Docker

Stack lokal menggunakan Airflow 3.3.2/Python 3.12, PostgreSQL 16, dan
LocalExecutor. Airflow serta pipeline memiliki lingkungan Python terpisah.
Node.js dan Chromium dipasang dalam image; host tidak perlu memasang browser
tambahan untuk pengumpulan terjadwal.

## Dua container

| Container | Peran |
| --- | --- |
| `airflow` | UI/API, scheduler, DAG processor, triggerer, dan eksekusi task |
| `postgres` | Database metadata dan riwayat Airflow |

Container Airflow menggunakan perintah resmi `airflow standalone`. Persiapan
direktori, login, migrasi database, dan pool berjalan otomatis saat startup;
tidak ada container init terpisah. Startup hanya memakai root untuk menyiapkan
izin mount, lalu proses Airflow/browser berjalan sebagai UID 50000.

Seluruh komponen Airflow memiliki satu siklus hidup: restart container akan
memulai ulang semuanya. Jumlah container berkurang, tetapi komponen internal
tetap berupa beberapa proses. Health check menilai database serta heartbeat
scheduler, DAG processor, dan triggerer; HTTP UI yang hidup saja belum cukup.
Jika ada komponen gagal, periksa log lalu restart `airflow`.

## Jadwal dan alur

| Program | Hari | Jam WIB | DAG |
| --- | --- | --- | --- |
| MBG | Senin | 23.59 | `x_collect_preprocess_mbg` |
| CKG | Selasa | 23.59 | `x_collect_preprocess_ckg` |
| Kopdes Merah Putih | Rabu | 23.59 | `x_collect_preprocess_kopdes_merah_putih` |
| Sekolah Rakyat | Kamis | 23.59 | `x_collect_preprocess_sekolah_rakyat` |

Setiap DAG menjalankan `collect → preprocess`. Rentang pengambilan adalah
tujuh hari kalender penuh sebelum hari jadwal, dengan timezone `Asia/Jakarta`.
Contoh: Senin 12 Oktober 2026 pukul 23.59 mengambil 5–11 Oktober inklusif.
Hari pengambilan tidak disertakan karena belum selesai. Batas awal 50 tweet
per run; hasil boleh kurang dari 50, tetapi tidak boleh melebihi batas ini.

Pengulangan tugas menggunakan timestamp dan ID run yang sama. Run manual memakai
waktu pemicuannya. Bukan waktu worker mulai berjalan: keterlambatan task tidak
menggeser rentang tanggal. Ubah cron di `dags/x_collection.py`; rentang dan batas
data dapat diubah melalui argumen runtime pada task `collect`.

## Menjalankan

Aktifkan Docker Desktop dalam mode Linux containers. Sediakan minimal 4 GB RAM
untuk Docker; 8 GB lebih nyaman. Dari root repo:

```bash
python docker/airflow/bootstrap.py
docker compose config --quiet
docker compose build airflow
docker compose up -d --wait
```

Bootstrap hanya memerlukan Python 3 dan standard library; environment aplikasi
tidak perlu dipasang pada host untuk menjalankan stack Docker. Bootstrap
menghasilkan secret acak lokal, tidak mencetak nilainya, dan tidak mengubah
file yang sudah ada. File rahasia diabaikan Git dan tidak dikirim ke build Docker.

Buka <http://localhost:8080>. Username `admin`; lihat password **secara lokal**
dalam `docker/airflow/secrets/admin_password`. Jangan unggah folder secrets atau
menyalin password/token ke issue, chat, log, maupun dokumentasi.

Sebelum menjalankan pengumpulan:

1. Isi `docker/airflow/secrets/x_auth_token` dengan nilai cookie `auth_token`
   akun X milik Anda, tanpa tanda kutip. File awal kosong, sehingga tidak ada
   akun yang digunakan tanpa konfigurasi.
2. Jika secret diubah setelah container dibuat, jalankan
   `docker compose up -d --force-recreate airflow` untuk memasangnya ulang.
3. Aktifkan DAG yang diinginkan melalui UI. Semua DAG dibuat dalam keadaan pause.
4. Gunakan **Trigger** untuk satu run manual atau tunggu jadwal berikutnya.

Laptop, Docker, dan koneksi internet harus tetap aktif pukul 23.59 WIB. Dengan
`catchup=False`, Airflow tidak mengambil ulang seluruh jadwal lama saat mesin
dihidupkan. UI bisa mengikuti timezone browser; pilih Asia/Jakarta untuk
menampilkan jam yang sama dengan tabel.

## Penyimpanan dan pengulangan

- Raw: `data/raw/x/execution=<hash>/collected_date=.../program=.../run_id=.../`.
- Processed: `data/processed/x/execution=<hash>/processed_date=.../program=.../run_id=.../`.
- Raw memuat `collection.json`, CSV, checksum sumber, query, dan rentang tanggal.
- Processed memuat CSV dan `quality_report.json`, termasuk checksum sumber,
  output, dan konfigurasi. Dataset tidak disimpan dalam XCom; hanya path artefak.

File diproses di direktori sementara lalu dipublikasikan sekaligus. Kegagalan
kolektor, termasuk saat CSV parsial sudah ditulis, tidak menghasilkan raw run
yang dianggap berhasil. CSV kosong/gagal, tanggal di luar periode WIB, timestamp invalid, atau jumlah
melebihi batas tidak dilanjutkan ke preprocessing.
Hasil sukses dipakai ulang pada retry setelah checksum diverifikasi; hasil yang
berubah atau konfigurasi yang berbeda ditolak, bukan ditimpa. Run manual baru
mendapat namespace berbeda. Preprocessing memakai satu lock bersama dan
riwayat ID/teks lintas run untuk setiap program, sehingga contoh yang sudah
eligible tidak lolos ulang pada target yang sama. Satu tweet dapat dinilai
terhadap program berbeda dengan petunjuk grup dataset bersama. Teks yang
hanya mirip memerlukan review. Teks kosong setelah cleaning selalu diblokir dari pelabelan.

Tugas memiliki satu retry setelah lima menit, timeout, dan batas satu run aktif
per DAG. Pool `x_collection` membatasi pengumpulan menjadi satu tugas pada satu
waktu untuk mengurangi beban akun. Penjadwalan mengikuti cron pada DAG; metadata
`collection_day` dalam YAML harus dijaga konsisten saat hari jadwal diubah.

## Validasi collector dan output lama

Adapter memeriksa source Tweet Harvest 2.7.1 sebelum menerapkan perbaikan dalam
memori: menunggu pencarian selesai diisi, menerima respons pencarian bertanggal,
memfilter timestamp dengan batas tepat Asia/Jakarta, dan memotong batch sesuai
sisa limit. Batch kosong tidak ditulis agar header CSV tetap utuh. Versi/source yang berbeda ditolak agar perubahan upstream tidak
melewati pemeriksaan. Python memvalidasi ulang CSV sebelum publikasi dan pada
retry/preprocessing, lalu merekam buktinya dalam `collection.json`.

Output aturan lama harus diaudit sebelum dipakai. Ikuti prosedur karantina pada
[panduan preprocessing](x-data-preprocessing.md#integrity-gates-and-cross-run-history).
Raw tetap disimpan; hasil karantina tidak boleh masuk labeling/training.

## Batas keamanan

Konfigurasi ini untuk pengembangan lokal. UI hanya terikat ke `127.0.0.1`,
PostgreSQL tidak membuka port host, dan container task memakai user non-root
tanpa akses Docker socket. Token dipasang sebagai Docker Compose secret ke
container Airflow yang menjalankan task. Adapter menyuplai prompt dalam memori;
token tidak masuk argumen proses, nilai environment, XCom, atau output log.
Output dan screenshot kolektor eksternal dibuang; error task diringkas.

Docker Compose secrets tetap berupa file di host, bukan vault terenkripsi.
Lindungi akses Windows/Linux ke folder tersebut. Administrator host dan kode
task yang berjalan dalam Airflow tetap bisa mengakses token. Jalankan hanya
kode DAG/dependensi yang dipercaya. SimpleAuthManager dipakai untuk login lokal;
untuk server bersama/produksi perlu auth manager yang sesuai, TLS, pengelolaan
secret, backup, dan review deployment tersendiri.

Docker tidak menjamin akun X aman dari pembatasan, token kedaluwarsa, atau
perubahan halaman X. Tweet Harvest menggunakan cookie sesi serta komponen
upstream yang perlu dipantau. Image mengunci Playwright 1.64.0 dan SheetJS 0.20.3
melalui override untuk menggantikan dependensi upstream dengan temuan keamanan;
SheetJS berasal dari CDN resminya. Gunakan sesuai ketentuan platform dan izin pengumpulan; API
resmi dapat menggantikan adapter kolektor bila dibutuhkan. Pengujian sintetis
memverifikasi pipeline tanpa membuktikan keberhasilan pengambilan akun nyata.

## Pemeriksaan dan operasi

```bash
docker compose ps
docker compose exec --user 50000:0 airflow airflow dags list-import-errors
docker compose exec --user 50000:0 airflow python /opt/airflow/verify_dags.py
docker compose exec --user 50000:0 airflow node /opt/collector/verify.cjs
docker compose logs --tail 100 airflow
docker compose restart airflow
docker compose stop
docker compose start
```

Untuk perubahan kode/keyword/DAG, bangun ulang image dan buat ulang container:

```bash
docker compose up -d --build --wait
```

`docker compose down` menghapus container dan network, tetapi mempertahankan
volume database, login, dan log. Hindari opsi `--volumes` kecuali memang ingin
menghapus metadata/log lokal. Dataset pada `./data` tetap berada di host.
Untuk rotasi password DB/login, perubahan file secret saja tidak memperbarui
akun yang sudah dibuat; lakukan perubahan akun melalui mekanisme layanan.

Rujukan: [panduan Docker Airflow](https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/docker-compose/index.html),
[Airflow standalone](https://airflow.apache.org/docs/apache-airflow/3.3.2/start.html),
[SimpleAuthManager](https://airflow.apache.org/docs/apache-airflow/3.3.2/core-concepts/auth-manager/simple/index.html),
dan [Tweet Harvest](https://github.com/helmisatria/tweet-harvest).
