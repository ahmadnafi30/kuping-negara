# Pemeriksaan preprocessing sebelum anotasi

Preprocessing yang ada sudah menangani bagian dasar secara konsisten. Teks
diubah ke bentuk Unicode yang seragam, HTML entity dibaca sebagai karakter
aslinya, URL dan mention dihapus dari `cleaned_text`, serta kata pada hashtag
tetap dipertahankan. Spasi dirapikan dan huruf dinormalkan. Emoji memang
dipertahankan karena bisa mengandung sinyal sentimen. `raw_text` tetap
menyimpan teks sumber untuk pemeriksaan ulang.

Kolom `language` **disalin dari label `lang` milik X/Tweet Harvest**. Kode
ini belum mendeteksi bahasa secara mandiri. Unggahan yang tidak berlabel `in`
ditandai untuk diperiksa, bukan dibuang diam-diam. Relevansi juga masih
berdasarkan kemunculan kata kunci program, sehingga sebuah unggahan yang
memakai kata kunci dalam konteks lain tetap mungkin perlu koreksi manual.

Pipeline memeriksa kolom wajib, ID dan teks kosong, karakter pengganti yang
menandakan teks rusak, timestamp, serta angka interaksi yang tidak valid.
Versi 4 juga membandingkan tanggal publikasi dalam waktu Jakarta dengan
rentang pada nama file mentah. Baris di luar rentang tetap disimpan untuk
audit, tetapi berstatus `review_out_of_window` dan tidak lolos sebagai
kandidat anotasi.
Laporan kualitas mencatat jumlah baris, status pemeriksaan, bahasa, hash
sumber, hash hasil, dan versi preprocessing. Jika satu file berisi nilai wajib
yang rusak, pemrosesan file tersebut berhenti dan file mentah tetap tersimpan
untuk diperbaiki atau diambil ulang.

Pada empat CSV sampel yang disertakan di repo, pemeriksaan ulang menghasilkan
20 baris: 13 kandidat `accepted` dan 7 baris yang perlu ditinjau. Hasil ini
berguna untuk menguji alur, tetapi ukurannya terlalu kecil untuk menyimpulkan
kualitas data historis atau keseimbangan sentimen.

Duplikat `tweet_id` sudah ditandai di dalam satu file. Untuk menggabungkan
hasil beberapa minggu, jalankan:

```bash
python src/build_annotation_pool.py
```

Perintah itu membaca `data/processed/x`, memverifikasi setiap CSV terhadap
`quality_report.json`, memilih baris berstatus `accepted`, lalu menyisakan
satu kandidat untuk setiap pasangan `target_program` dan `tweet_id`.
Hasilnya masuk ke run baru di `data/processed/annotation_pool/` bersama
laporan jumlah kandidat dan duplikat yang dibuang. File lama tidak ditimpa.
Jika satu `tweet_id` muncul di beberapa program, laporan mencatatnya.
Untuk data awal yang dibuat oleh `src/collect_training_data.py`, gunakan
`--input-dir data/processed/training_initial/v4/x` agar hasil replay LK-04
tidak tercampur.
Ketika nanti membagi data latih dan uji, kelompokkan berdasarkan `tweet_id`
agar teks unggahan yang sama tidak bocor ke dua bagian.

Kami belum menghapus stopword atau memecah teks menjadi token pada tahap
ini. Kata seperti *tidak* penting bagi sentimen; tokenisasi dan pembobotan
lebih tepat ditentukan bersama metode ekstraksi fitur. Hasil kandidat juga
belum punya label `positive`, `neutral`, atau `negative`. Pemeriksaan bahasa,
relevansi, privasi teks, dan label manual masih diperlukan sebelum model
dilatih.
