# Mengumpulkan data awal untuk anotasi

Skrip `src/collect_training_data.py` menyiapkan kumpulan unggahan awal dari
empat program. Ia membagi rentang tanggal menjadi potongan tujuh hari,
memanggil pengambil data yang sudah dipakai pada LK-04, lalu menjalankan
preprocessing untuk setiap file yang berhasil disimpan. Hasil mentah dan hasil
bersih tetap berada di folder proyek seperti biasa. Setiap pengambilan membuat
run baru, sehingga data lama tidak tertimpa.

Lihat rencananya dulu tanpa menghubungi X:

```bash
python src/collect_training_data.py
```

Defaultnya adalah 28 hari penuh terakhir, empat program, dan batas 200
unggahan per program per potongan tanggal. Untuk membatasi periode atau
program, misalnya:

```bash
python src/collect_training_data.py --start-date 2026-09-01 --end-date 2026-09-28 --program mbg --window-days 7 --limit 200
```

Tambahkan `--execute` setelah rencana, token, Node.js, dan browser siap:

```bash
python src/collect_training_data.py --start-date 2026-09-01 --end-date 2026-09-28 --execute
```

Mode eksekusi membutuhkan `X_AUTH_TOKEN` di environment. Isi token secara
lokal tanpa menulisnya di perintah atau commit. File `.env` tidak dibaca
otomatis oleh skrip Python ini. Bila memakai Docker Airflow, Compose sudah
meneruskan nilai dari `.env` lokal kepada container; untuk terminal biasa,
atur environment pada sesi terminal terlebih dahulu.

Setiap eksekusi menulis manifest di `data/bootstrap/runs/`. Manifest berisi
rentang tanggal, program, status, serta lokasi hasil mentah dan hasil
preprocessing. Bila satu pengambilan gagal, proses berhenti dan manifest
menunjukkan bagian yang sudah selesai. Jalankan lagi hanya untuk bagian yang
gagal lewat `--start-date`, `--end-date`, dan `--program`. Karena file mentah
bersifat immutable, pengulangan akan membuat run baru. Gabungkan hasil untuk
anotasi dengan deduplikasi lintas run sebelum dipakai melatih model.

Hasil ini **belum menjadi data latih berlabel**. Kolom `language` berasal dari
X, bukan hasil deteksi bahasa independen. `is_eligible_for_labeling` hanya
menandai calon unggahan yang layak diperiksa. Sentimen harus diberi label
manual sesuai `docs/annotation-guidelines.md`, lalu diperiksa kesepakatan
antar anotator sebelum dipakai melatih model. Batas per potongan tanggal juga
berarti data ini sampel, bukan seluruh percakapan pada periode tersebut.

