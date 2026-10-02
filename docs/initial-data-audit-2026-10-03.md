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
pengganti pengumpulan data awal yang representatif. Sebelum melatih model,
pengambilan historis perlu diulang sampai ada unggahan yang lolos pemeriksaan
tanggal, kemudian diperiksa relevansi dan diberi label secara manual.
