# EDA data awal

EDA dibuat setelah preprocessing, sebelum anotasi dan pelatihan. Jalankan:

```bash
python src/eda_initial_data.py
```

Skrip membaca semua CSV di `data/processed/x`, memeriksa hash dan laporan
kualitas setiap file, lalu membuat `summary.json` dan `index.html` pada run
baru di `data/analysis/eda/`. HTML dapat dibuka di browser. Isinya hanya
angka agregat dan grafik batang; teks unggahan, ID, serta akun tidak
ditampilkan.

Laporan mencakup jumlah file dan baris, kandidat unik setelah deduplikasi,
status kualitas, sebaran program, label bahasa dari X, tanggal dan minggu
publikasi, panjang teks bersih, nilai kosong, dan ringkasan interaksi.
Ia juga menghitung ID unggahan yang muncul pada lebih dari satu program,
karena nanti pembagian data latih dan uji perlu menjaga ID yang sama tetap
di satu sisi. Hash input disimpan di JSON untuk menelusuri data yang dipakai.

Pada empat sampel kecil yang disertakan di repo, ada 20 baris dan 13 kandidat
unik. Angka tersebut hanya uji alur. Untuk EDA yang layak dipakai memutuskan
strategi anotasi, jalankan skrip lagi setelah pengumpulan awal mencakup
periode dan jumlah unggahan yang lebih besar. Periksa khususnya apakah satu
program atau satu minggu terlalu dominan dan apakah banyak unggahan perlu
review bahasa/relevansi.

EDA ini belum dapat menunjukkan proporsi sentimen. Label `positive`,
`neutral`, dan `negative` baru ada setelah anotasi manual. Kode bahasa juga
berasal dari X, bukan deteksi bahasa otomatis oleh preprocessing.

