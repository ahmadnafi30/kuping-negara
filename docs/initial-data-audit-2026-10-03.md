# Catatan pengambilan data awal, 3 Oktober 2026

Saya mencoba mengambil 20 unggahan untuk masing-masing dari empat program
dengan tanggal pencarian 25 September sampai 1 Oktober 2026. Pengambil data
memang menghasilkan empat CSV, total 80 baris. Namun, setelah tanggal
publikasinya diperiksa dalam waktu Jakarta, **semua 80 unggahan ternyata
terbit pada 2 Oktober**. Jadi hasil uji ini tidak memenuhi rentang yang
diminta dan tidak boleh dipakai sebagai data latih historis.

| Hasil pemeriksaan ulang | Jumlah |
| --- | ---: |
| File mentah | 4 |
| Unggahan yang terbaca | 80 |
| Di luar rentang tanggal | 80 |
| Kandidat anotasi yang valid | 0 |

File mentah tetap tersimpan di `data/raw/x/collected_date=2026-10-02`.
Hasil preprocessing versi 3 juga tetap ada sebagai jejak uji awal, tetapi
angka kandidatnya **tidak berlaku** karena versi itu belum memeriksa rentang
tanggal. Versi 4 memproses ulang file yang sama di
`data/processed/training_initial/v4/x`. Semua baris diberi status
`review_out_of_window`, dan laporan EDA versi terbaru ada di
`data/analysis/eda/run_id=20261003-date-audit/index.html`.

Sekarang pengambil data memeriksa tanggal setiap unggahan sebelum file
dipromosikan ke `data/raw/x`. Bila hasil pencarian meleset, proses gagal
secara jelas dan Airflow dapat mencatat kegagalannya. Penyebab hasil
pencarian X meleset belum dipastikan; aturan tanggal di Tweet Harvest sudah
dikirim dalam format yang sesuai dengan kode versinya. Pemeriksaan hasil
tetap diperlukan walaupun parameter pencarian terlihat benar.

Untuk mengulang audit dari arsip yang sudah ada, gunakan folder output
baru agar laporan sebelumnya tidak tertimpa:

```bash
python src/preprocess.py --input-dir data/raw/x/collected_date=2026-10-02 --output-root data/processed/training_initial/recheck/x
python src/build_annotation_pool.py --input-dir data/processed/training_initial/recheck/x
python src/eda_initial_data.py --input-dir data/processed/training_initial/recheck/x
```

Empat CSV sampel LK-04 yang lebih lama tetap berguna untuk menguji
pipeline: 20 barisnya berada dalam tanggal yang diminta dan menghasilkan
13 calon anotasi. Itu hanya sampel kecil tanpa label sentimen, bukan
pengganti pengumpulan data awal yang representatif.

Pada percobaan berikutnya, saya mengambil **hari lengkap 2 Oktober 2026**
untuk keempat program. Empat CSV baru berisi 80 unggahan yang seluruhnya
sesuai tanggal. Setelah pemeriksaan bahasa, kata kunci, dan duplikat, 64
unggahan masuk daftar calon anotasi; 16 lainnya perlu ditinjau. Satu program
sempat mengembalikan beberapa unggahan di luar tanggal, tetapi percobaan
ulangnya menghasilkan batch yang lolos pemeriksaan.

| Pilot valid 2 Oktober | Jumlah |
| --- | ---: |
| File mentah baru | 4 |
| Unggahan sesuai tanggal | 80 |
| Calon anotasi unik | 64 |
| Perlu tinjauan bahasa/relevansi | 16 |

EDA keseluruhan di `reports/eda/initial-pilot-2026-10-03/index.html`
memuat delapan file versi 4: empat batch pertama yang gagal dan empat
batch 2 Oktober yang valid. Karena itu totalnya 160 baris, dengan 80
`review_out_of_window` dan 64 calon anotasi. Daftar calon anotasi terbaru
ada di `data/processed/training_initial/v4/annotation_pool/` dan dilacak
oleh DVC lokal. Laporan Git hanya berisi angka agregat, tanpa teks
unggahan atau identitas akun.

Ini baru sampel **satu hari**, belum data latih berlabel. Sebelum melatih
model, rentang hari dan jumlah unggahan perlu diperluas, lalu kandidat
diperiksa relevansinya dan diberi label sentimen secara manual.
