# Versi data dengan DVC

DVC sudah diinisialisasi pada branch ini. Kode, konfigurasi, `dvc.yaml`, dan
`dvc.lock` disimpan di Git. Isi data yang dihasilkan pipeline masuk ke cache
DVC lokal, bukan ke commit Git. Belum ada remote DVC yang diatur, jadi
`dvc push` dan `dvc pull` untuk berbagi data belum bisa dipakai.

Untuk memasang tool sesuai versi yang dipakai proyek:

```bash
uv tool install dvc==3.67.1
```

Untuk memeriksa pipeline tanpa mengambil unggahan baru dari X:

```bash
dvc repro
dvc status
```

Pipeline contoh memakai empat CSV sampel yang sudah ada di Git. Ia
menjalankan preprocessing dengan waktu proses tetap, menyusun kandidat
anotasi tanpa duplikat, lalu membuat EDA. Semua hasilnya berada di
`data/experiments/lk04-sample/` dan dilacak oleh DVC. Folder ini sengaja
terpisah dari `data/raw/x` dan `data/processed/x` yang dipakai pengambilan
langsung, sehingga `dvc repro` tidak menghapus hasil live. Jika tidak ada
perubahan sumber atau kode, DVC akan melewati tahap yang sudah mutakhir.

Setelah pengumpulan langsung menghasilkan data nyata dan izin penyimpanannya
sudah jelas, snapshot lokalnya bisa dicatat dengan:

```bash
dvc add data/raw/x data/processed/x
git add data/raw/x.dvc data/processed/x.dvc .gitignore
git commit -m "data: record new raw and processed snapshots"
```

Ulangi `dvc add` setelah ada data baru. Git menyimpan pointer dan hash;
file unggahan tetap tidak masuk commit. Jika kumpulan kandidat anotasi juga
ingin diberi versi, gunakan `dvc add data/processed/annotation_pool` setelah
hasilnya diperiksa. Jangan memasukkan token X, file `.env`, atau catatan
identitas anotator ke cache yang nantinya akan dibagikan.

Untuk berbagi cache antar mesin, tentukan **remote privat** milik proyek,
baru jalankan `dvc remote add`, `dvc push`, dan `dvc pull` sesuai jenis
penyimpanannya. Alamat dan kredensial belum ditentukan di sini. Kredensial
remote harus masuk konfigurasi lokal DVC (`--local`) atau pengelola secret,
bukan commit Git. Sampai remote disiapkan, hasil `dvc repro` dan snapshot
`dvc add` hanya tersedia di mesin ini.

DVC mencatat versi data; ia tidak menilai sentimen. Kumpulan kandidat masih
perlu anotasi manual, pemeriksaan kesepakatan label, serta pembagian data
latih/uji yang mencegah `tweet_id` sama muncul di kedua sisi.

