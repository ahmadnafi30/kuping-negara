# Alur Penambahan Versi Data dengan DVC

Proyek **Kuping Negara** menggunakan DVC untuk menyimpan riwayat dataset raw.
Setiap tambahan data menghasilkan snapshot yang diperbarui, penunjuk `.dvc`
dengan hash baru, dan commit Git yang dapat dipakai untuk mengambil versi itu
kembali. Isi CSV disimpan pada cache DVC dan remote Google Drive; Git menyimpan
penunjuk, kode, dan metadata audit.

Alur penambahan versi:

```text
Pengumpulan data X
        ↓
Raw CSV per program/run + collection.json
        ↓
Validasi dan append snapshot tanpa pasangan ID duplikat
        ↓
dvc add → penunjuk hash dataset diperbarui
        ↓
dvc push → objek dataset tersimpan di Google Drive
        ↓
git commit + tag → versi metadata tercatat
        ↓
dvc diff / dvc pull → perbandingan dan pemulihan versi
```

## 1. Menyiapkan lingkungan

Jalankan perintah dari root repositori. Pasang dependensi DVC dan Google Drive:

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive
uv run --locked --no-sync dvc version
```

Repositori sudah diinisialisasi dengan `dvc init`. Berkas `.dvc/config`,
`.dvc/.gitignore`, dan `.dvcignore` sudah tersedia, sehingga clone proyek dapat
langsung digunakan setelah dependensinya dipasang.

Remote utama pada instalasi lokal ini bernama `gdrive`, menuju folder
`kuping-negara-dvc`. Mesin baru perlu mengatur remote dan melakukan login
mengikuti [setup Google Drive](dvc-data-versioning.md#google-drive). Konfigurasi
remote dan token disimpan secara lokal serta diabaikan Git.

`--no-sync` menggunakan lingkungan yang sudah dipasang, sehingga dependensi
Google Drive tetap tersedia saat menjalankan contoh berikut.

## 2. Mengumpulkan data tambahan

Pengumpulan dapat dilakukan melalui task `collect` pada DAG Airflow atau
melalui CLI. Contoh pola perintah CLI:

```bash
uv run --locked --no-sync collect-x-data --program mbg --from-date "<tanggal-awal>" --to-date "<tanggal-akhir>" --limit 50
```

Ganti placeholder tanggal dengan rentang data yang sudah tersedia dalam format
`DD-MM-YYYY`. Pilih
program `mbg`, `ckg`, `kopdes_merah_putih`, atau `sekolah_rakyat` sesuai batch
baru. Gunakan rentang tujuh hari sesuai konfigurasi validasi proyek.

Setiap pengumpulan menghasilkan raw CSV pada partisi program/run dan manifest
`collection.json`. Raw tersebut dipertahankan sebagai sumber asli. Snapshot
gabungan yang dilacak DVC adalah `data/raw/lk05_dataset.csv`.

## 3. Menambahkan data ke snapshot

Gunakan adapter snapshot dalam mode append:

```bash
uv run --locked --no-sync python -m kuping_negara.data_versioning.snapshots --input "<path-raw-run-baru.csv>" --append
```

Ganti `<path-raw-run-baru.csv>` dengan lokasi raw CSV dari pengumpulan yang
berhasil. Untuk beberapa batch, ulangi opsi `--input` dalam perintah yang sama.

Adapter memeriksa checksum raw, manifest, konfigurasi, skema kolom, rentang
tanggal, dan batas baris. Baris lama dipertahankan; baris baru ditambahkan
berdasarkan kunci unik `(target_program, id_str)`. Pasangan yang sudah ada
dilewati. Append tanpa pasangan baru ditolak agar tidak menghasilkan versi
data tambahan yang semu.

Hasil langkah ini:

- Snapshot `data/raw/lk05_dataset.csv` bertambah.
- `reports/lk05/dataset_metrics.json` mencatat jumlah baris lama, baris baru,
  sumber pengumpulan, duplikat yang dilewati, dan SHA-256 snapshot.
- Raw per run tetap tersimpan tanpa perubahan.

## 4. Memperbarui penunjuk DVC

Periksa perubahan, lalu lacak ulang snapshot:

```bash
uv run --locked --no-sync dvc status
uv run --locked --no-sync dvc add data/raw/lk05_dataset.csv
git diff -- data/raw/lk05_dataset.csv.dvc reports/lk05/dataset_metrics.json
```

`dvc add` menyimpan isi snapshot ke cache DVC dan memperbarui hash serta ukuran
pada `data/raw/lk05_dataset.csv.dvc`. File penunjuk ini dilacak Git, sementara
isi CSV diabaikan melalui `data/raw/.gitignore`.

## 5. Mengunggah objek versi baru

Kirim objek dataset ke Google Drive sebelum memublikasikan commit versinya:

```bash
uv run --locked --no-sync dvc push --remote gdrive data/raw/lk05_dataset.csv.dvc
uv run --locked --no-sync dvc status --cloud --remote gdrive
```

Setelah sinkronisasi berhasil, status menampilkan:

```text
Cache and remote 'gdrive' are in sync.
```

Drive menyimpan objek berdasarkan hash. Nama objek di folder remote dapat
berbeda dari nama CSV asli; penunjuk `.dvc` menghubungkan versi Git dengan objek
tersebut. Remote `localstore` tetap tersedia sebagai salinan lokal tambahan.

Pengunggahan DVC dilakukan secara eksplisit. DAG Airflow collect/preprocess
belum otomatis mengunggah setiap hasil pengumpulan ke Drive.

## 6. Mencatat versi dalam Git

Simpan perubahan penunjuk dan metrik dalam satu commit. Contoh untuk versi
berikutnya, setelah versi pertama dan kedua yang sudah tersedia:

```bash
git add data/raw/lk05_dataset.csv.dvc reports/lk05/dataset_metrics.json
git commit -m "data(dvc): append validated raw records"
git tag data-v3
git push origin HEAD
git push origin data-v3
```

`data-v3` adalah contoh nama tag baru; pilih nama yang belum digunakan.
Jalankan commit dan push pada branch pekerjaan sesuai
[alur Git proyek](git-workflow.md). Commit dan tag menunjuk metadata versi;
objek CSV sudah tersimpan di remote melalui langkah sebelumnya.

## 7. Membandingkan dan mengambil versi

Dua versi yang sudah tersedia pada proyek ini dapat dibandingkan dengan:

```bash
uv run --locked --no-sync dvc diff --show-hash lk05-data-v1 lk05-data-v2
git diff lk05-data-v1 lk05-data-v2 -- reports/lk05/dataset_metrics.json
```

`dvc diff` memperlihatkan perubahan file dan hash. Perubahan jumlah baris
tercatat pada metrik dataset. Untuk melihat perubahan versi berikutnya, ganti
nama tag dengan dua versi yang ingin dibandingkan.

Untuk mengambil dataset versi lama, gunakan checkout terpisah, checkout tag
versi yang dipilih, atur remote lokalnya, lalu jalankan:

```bash
uv run --locked --no-sync dvc pull --remote gdrive data/raw/lk05_dataset.csv.dvc
```

Git memulihkan penunjuk versi, sedangkan `dvc pull` mengunduh objek CSV yang
sesuai. Gunakan checkout terpisah agar snapshot pada workspace Airflow tetap
tersedia untuk pipeline yang berjalan. Dependensi dan konfigurasi remote pada
checkout tersebut perlu disiapkan sebagaimana langkah pertama.

## Contoh perubahan yang sudah terjadi

| Program | `lk05-data-v1` | `lk05-data-v2` | Tambahan |
| --- | ---: | ---: | ---: |
| CKG | 50 | 50 | 0 |
| MBG | 0 | 50 | 50 |
| Kopdes Merah Putih | 0 | 50 | 50 |
| Sekolah Rakyat | 0 | 50 | 50 |
| **Total** | **50** | **200** | **150** |

Pada pengumpulan berikutnya, 50 pasangan CKG sudah tersedia sehingga dilewati.
Sebanyak 150 pasangan baru berasal dari tiga program lain. Data mencakup
periode **4-10 Oktober 2026 WIB**. Simulasi ini memperlihatkan pertumbuhan
dataset antarprogram dalam periode yang sama; training model belum dilakukan.

| Metadata | Versi awal | Versi berikutnya |
| --- | --- | --- |
| Tag | `lk05-data-v1` | `lk05-data-v2` |
| Ukuran CSV | 18.950 byte | 69.661 byte |
| MD5 DVC | `644e1e4e9d4db18c31dd42510b60452e` | `4c49742a13ec88c81119bd00dfa26652` |

Kedua versi sudah diunggah ke Google Drive dan berhasil dipulihkan pada
checkout dengan cache kosong. Jumlah baris, MD5, dan SHA-256 hasil unduhan
sesuai dengan metadata sumber.

Bukti dan rincian implementasi tersedia pada:

- [Metrik dataset](../reports/lk05/dataset_metrics.json).
- [Perbandingan dua versi](../reports/lk05/version_comparison.json).
- [Verifikasi pemulihan dari Google Drive](../reports/lk05/google_drive_verification.json).
- [Panduan teknis DVC](dvc-data-versioning.md).
