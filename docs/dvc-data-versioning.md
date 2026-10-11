# Konfigurasi DVC, Remote, dan Pemulihan

## Cakupan dan hasil

DVC melacak `data/raw/lk05_dataset.csv`; Git hanya menyimpan penunjuk `.dvc`,
aturan ignore, kode, dan `reports/lk05/dataset_metrics.json` yang tidak berisi
teks pengguna. Raw per run tetap immutable. Snapshot gabungan dapat berubah
hanya melalui mode append yang eksplisit.

| Versi | Tag Git | Baris | Program | MD5 DVC |
| --- | --- | ---: | --- | --- |
| Awal | `lk05-data-v1` | 50 | CKG | `644e1e4e9d4db18c31dd42510b60452e` |
| Tambahan | `lk05-data-v2` | 200 | MBG, CKG, Kopdes, Sekolah Rakyat: 50 masing-masing | `4c49742a13ec88c81119bd00dfa26652` |

Versi awal berasal dari koleksi CKG yang tervalidasi. Koleksi manual berikutnya
berhasil untuk empat program dalam periode 4-10 Oktober 2026 WIB. Append
menambahkan 150 pasangan unik `(target_program, id_str)`; 50 ID CKG yang sudah
ada dilewati, termasuk bila hitungan engagement berubah. Post yang sama dapat
memiliki target berbeda, sehingga jumlah baris adalah jumlah pasangan program
/post, bukan jumlah pengguna atau tweet unik lintas program.

Ini simulasi penambahan data nyata lintas program. Periode belum bergeser ke
minggu berikutnya; tidak ada baris sintetis yang diklaim sebagai hasil ingesti.
Contoh fixture pengujian menggunakan data sintetis dan terpisah dari dataset.
Versioning ini belum melakukan training, retraining, atau validasi label AI.
Kolektor LK-04 proyek ini adalah `collect-x-data`/DAG `collect`, bukan file
`ingest_data.py` terpisah.

## Setup

DVC 3.x disediakan lewat extra opsional, dengan versi tepat dalam `uv.lock`.
Docker Airflow tetap memakai dependensi aplikasi yang terpisah.

Contoh `uv run --no-sync` menggunakan lingkungan yang telah dipasang oleh
`uv sync`. Ini mempertahankan extra Google Drive saat menjalankan perintah
lain. Untuk remote Drive, lakukan setup extra `google-drive` pada bagian
berikut sebelum menjalankan push/pull.

```bash
uv sync --locked --extra dev --extra data-versioning
uv run --locked --no-sync --extra data-versioning dvc version
```

Repositori ini sudah menjalankan `dvc init` dan meng-commit `.dvc/config`,
`.dvc/.gitignore`, serta `.dvcignore`. Jangan menjalankan init ulang dengan
`--force`. Analytics dinonaktifkan dan cache menggunakan copy untuk menghindari
perubahan CSV ikut merusak objek cache melalui hardlink/symlink.

Git mengabaikan cache DVC, CSV, raw per run, processed, labeled, output PDF,
virtual environment, token, dan `.dvc/config.local`. Ignore raw ditempatkan
pada `data/raw/.gitignore`; jangan mengabaikan folder `data/raw` dari root
karena metadata `.dvc` harus tetap dapat ditemukan dan dilacak.

## Remote lokal

Contoh instalasi lokal Windows menggunakan direktori di luar repo:

```bash
uv run --locked --no-sync --extra data-versioning dvc remote add --local --default localstore D:/MLOPS/dvc-storage/kuping-negara
uv run --locked --no-sync --extra data-versioning dvc push
```

Jika nama remote sudah ada, ubah URL memakai `dvc remote modify --local
localstore url <lokasi>`. Path mesin disimpan hanya di `.dvc/config.local`.
Remote ini menyimpan objek dua versi, tetapi berada pada disk lokal yang sama;
belum merupakan backup di luar perangkat atau remote cloud bersama. Mesin lain
perlu salinan objek dan konfigurasi remote sendiri sebelum `dvc pull`.
S3/GCS/MinIO tidak diperlukan untuk memenuhi tugas inti dan belum dikonfigurasi.

## Google Drive

Backend opsional disediakan melalui extra terpisah:

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive
uv run --locked --no-sync --extra google-drive python -c "from pydrive2.auth import GoogleAuth; from pydrive2.fs import GDriveFileSystem"
```

Lockfile memakai PyDrive2 1.21.3 dan PyOpenSSL 24.2.1. Batas dependensi tersebut
menghindari kegagalan impor OAuth yang ditemukan pada pasangan PyDrive2 lama,
PyOpenSSL 22, dan cryptography baru. CI memeriksa impor backend pada Windows
serta Linux tanpa mengakses akun Google. Dependensi Drive tidak dipasang ke
container Airflow.

Kedua versi LK-05 telah diunggah ke folder `kuping-negara-dvc` dan dipulihkan
dari cache kosong pada checkout terpisah: v1 50 baris, v2 200 baris, total
88.611 byte. Jumlah baris, MD5, dan SHA-256 cocok dengan metadata audit. Bukti
ada pada `reports/lk05/google_drive_verification.json`. Remote utama pada
instalasi lokal ini adalah `gdrive`; `localstore` tetap tersedia. Pengaturan
remote dan login tidak ikut Git. PDF LK-05 sebelumnya merekam tahap remote
lokal; laporan verifikasi Drive melengkapi tahap tersebut.

### Persiapan OAuth dan folder

1. Buat folder Drive khusus dan catat ID dari tautan `drive/folders/<folder-id>`.
2. Pada project Google Cloud sendiri, aktifkan Google Drive API dan buat OAuth
   client dengan tipe **Desktop app**.
3. Jika Audience berstatus **Testing**, tambahkan akun pemilik folder ke
   **Test users**. Error `403: access_denied` tentang developer-approved testers
   diselesaikan pada daftar ini, bukan dengan membuat client baru.
4. Simpan JSON hasil unduhan sebagai `.dvc/credentials/google-drive-client.json`.
   Folder ini diabaikan Git, DVC, dan konteks build Docker. Jangan memasukkan
   client secret atau token ke YAML, README, perintah Git, maupun laporan.

Contoh konfigurasi PowerShell berikut membaca secret dari berkas, sehingga
nilainya tidak muncul pada argumen proses atau riwayat perintah. Ganti
`<folder-id>` sebelum menjalankannya dari root repo:

```powershell
@'
import json
from pathlib import Path
from dvc.repo import Repo

credentials_dir = Path(".dvc/credentials").resolve()
client = json.loads((credentials_dir / "google-drive-client.json").read_text())
installed = client["installed"]
with Repo() as repo:
    with repo.config.edit(level="local") as config:
        config.setdefault("remote", {})["gdrive"] = {
            "url": "gdrive://<folder-id>",
            "gdrive_client_id": installed["client_id"],
            "gdrive_client_secret": installed["client_secret"],
            "gdrive_user_credentials_file": str(credentials_dir / "google-drive-token.json"),
        }
'@ | uv run --locked --no-sync --extra google-drive python -
```

Konfigurasi masuk `.dvc/config.local`, bukan `.dvc/config` yang dilacak Git.
Token login disimpan dalam folder kredensial lokal yang sama. Mesin lain perlu
konfigurasi dan persetujuan login sendiri; `git clone` tidak membawa token.

### Unggah dan verifikasi

```bash
uv run --locked --no-sync --extra google-drive dvc push --remote gdrive data/raw/lk05_dataset.csv.dvc
uv run --locked --no-sync --extra google-drive dvc status --cloud --remote gdrive
```

Login pertama membuka browser. Pastikan akun, nama aplikasi, dan izin akses
Drive sesuai, lalu selesaikan persetujuan sendiri. Peringatan aplikasi belum
diverifikasi dapat tampil untuk client milik sendiri dalam mode Testing.
Airflow menggunakan port 8080, sehingga callback login lokal memakai port 8090
bila 8080 sudah terpakai.

Migrasi dua versi LK-05 sudah selesai dan diverifikasi. Untuk batch berikutnya,
unggah penunjuk dataset yang sedang aktif secara eksplisit. Repo juga memiliki
tag arsip eksperimen, sehingga `dvc push --all-tags` tidak menjadi perintah
operasional rutin. Gunakan checkout terpisah dan tag dataset yang dipilih untuk
mengunggah atau memulihkan versi lama.

DVC menyimpan objek berdasarkan hash; nama file pada Drive dapat berbeda dari
nama CSV. Untuk memeriksa pemulihan, jalankan `dvc pull --remote gdrive data/raw/lk05_dataset.csv.dvc` pada checkout tag dataset dengan cache kosong,
lalu cocokkan jumlah baris dan SHA-256 dengan metadata audit.

Setelah kedua versi berhasil dipulihkan, jadikan Drive remote utama:

```bash
uv run --locked --no-sync --extra google-drive dvc remote default --local gdrive
```

Remote `localstore` tetap dapat dipakai sebagai salinan lokal dengan
`dvc push --remote localstore`. Unggah DVC dijalankan secara eksplisit;
DAG collect/preprocess belum otomatis mengunggah setiap raw run ke Drive.

Untuk aplikasi External dalam mode Testing dengan izin Drive, refresh token
Google berakhir setelah tujuh hari; login ulang diperlukan untuk melanjutkan
sinkronisasi setelah masa tersebut. Dataset yang sudah diunggah tetap tersimpan.
Lihat [masa berlaku token Google](https://developers.google.com/identity/protocols/oauth2#expiration).

Panduan resmi: [DVC Google Drive](https://dvc.org/doc/user-guide/data-management/remote-storage/google-drive)
dan [pengaturan OAuth Google](https://developers.google.com/workspace/guides/configure-oauth-consent).

## Menambahkan versi data

[Alur penambahan versi data](dvc.md) menjelaskan pengumpulan, validasi, append,
`dvc add`, upload objek, commit metadata, serta pemberian tag baru. Gunakan tag
yang belum tersedia; `lk05-data-v1` dan `lk05-data-v2` mempertahankan dua versi
historis yang sudah diverifikasi.

## Audit dan pemulihan

```bash
uv run --locked --no-sync --extra data-versioning dvc diff --show-hash lk05-data-v1 lk05-data-v2
uv run --locked --no-sync --extra data-versioning dvc status
uv run --locked --no-sync --extra google-drive dvc status --cloud --remote gdrive
git diff lk05-data-v1 lk05-data-v2 -- reports/lk05/dataset_metrics.json
git ls-files -- data/raw/lk05_dataset.csv
```

`dvc diff` menampilkan perubahan objek/hash, bukan penambahan baris satu per
satu. Hitungan 50 ke 200 dan 150 ID baru dibuktikan lewat metrik serta pembacaan
CSV. `git ls-files` di atas harus kosong: isi CSV tidak masuk Git.
Dokumentasi resmi: [dvc add](https://dvc.org/doc/command-reference/add),
[dvc diff](https://dvc.org/doc/command-reference/diff),
[dvc remote](https://dvc.org/doc/command-reference/remote).

Unduh versi tertentu ke file terpisah agar snapshot yang dipakai pipeline
lokal tidak terganti:

```bash
uv run --locked --no-sync --extra data-versioning dvc get . data/raw/lk05_dataset.csv --rev lk05-data-v1 --config .dvc/config.local --remote gdrive --out tmp/lk05-v1.csv
uv run --locked --no-sync --extra data-versioning dvc get . data/raw/lk05_dataset.csv --rev lk05-data-v2 --config .dvc/config.local --remote gdrive --out tmp/lk05-v2.csv
```

Untuk rollback penuh, checkout tag Git lalu `dvc pull` pada checkout terpisah;
Git saja tidak memulihkan CSV. Pastikan objek tersedia pada remote dan cache.
Jangan mengubah live workspace Airflow hanya untuk demonstrasi rollback.

## Bukti dataset

- [Metrik penambahan](../reports/lk05/dataset_metrics.json).
- [Perbandingan versi](../reports/lk05/version_comparison.json).
- [Pemulihan dua versi dari Drive](../reports/lk05/google_drive_verification.json).

Laporan PDF lokal `output/pdf/laporan_lk05_dvc.pdf` merekam tahap remote lokal.
Laporan verifikasi Drive mencatat penyimpanan eksternal yang dilakukan
sesudahnya. Data dan PDF diabaikan Git; metrik audit tidak memuat isi post.
