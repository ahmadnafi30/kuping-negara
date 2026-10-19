# Metadata model hasil perluasan data

Model ini memakai 396 contoh dengan label AI provisional. Pemilihan parameter
menggunakan rerata Macro-F1 cross-validation pada development; test dievaluasi
setelah pemenang dipilih. Tidak ada klaim validasi manusia atau kesiapan deployment.

| Informasi | Nilai |
| --- | --- |
| Run terbaik | `2a32d8a89e6f49b5b63b9e30d08ec4b4` |
| Model | TF-IDF kata 1-2 gram + karakter 3-5 gram, Logistic Regression |
| C / class weight | 10 / balanced |
| Batas fitur kata / karakter | 10.000 / 20.000 |
| Max iter / seed | 2.000 / 42 |
| Program one-hot | Tidak digunakan |
| Data | 396 baris: 160 negatif, 148 netral, 88 positif |
| Development / test | 316 / 80; overlap kelompok 0 |
| Raw DVC | `raw-expanded-20261019-v1`, 666 pasangan program/post |
| SHA-256 training | `29d088b126a6462a3ac48af22f08b5608a0ef0bd9626b065bddfc1525a8f369f` |
| Commit sumber | `bac2d24d9c05920bede514eb4304453802b3b0cc`; working tree bersih saat training |
| Registry | `kuping-negara-sentiment-expanded-pilot`, versi 1, alias `experimental` |
| Deployment approved | **False** |

## Pemilihan parameter

| Run | C | CV accuracy | CV Macro-F1 | Std Macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| word-char-c05 | 0.5 | 0.7723 | 0.7479 | 0.0412 |
| word-char-c2 | 2.0 | 0.7881 | 0.7660 | 0.0619 |
| word-char-c10 | 10.0 | 0.8102 | 0.7901 | 0.0446 |

`word-char-c10` dipilih berdasarkan CV Macro-F1 0,7901. Skor test tidak dipakai
untuk mengganti parameter atau memilih run.

## Test holdout baru

- Accuracy: **0,7375** (59/80).
- Macro-F1: **0,7476**; weighted-F1: **0,7340**.
- Recall negatif: 25/32; netral: 18/30; positif: 16/18.
- Dummy kelas mayoritas: accuracy 0,4000; Macro-F1 0,1905.

Ini ukuran kesesuaian terhadap label AI. Hasil awal 91 baris memakai test lain
(19 baris); perubahan skor tidak membuktikan peningkatan pada benchmark yang
sama. Ke-19 contoh test lama dan semua kelompok terhubungnya tidak masuk
snapshot baru. Snapshot lama, eksperimen lama, dan Registry lama tetap tersedia.

CKG memiliki 22 contoh (1 negatif, 14 netral, 7 positif), dengan hanya 2 contoh
pada test baru. Model benar pada 1/2 contoh CKG dan gagal pada 1 contoh positifnya.
Kopdes tidak memiliki contoh positif pada slice test ini. Jangan menarik
kesimpulan per-program/per-kelas yang tidak didukung sampelnya. Rincian slice
beserta ukuran sampel tersedia di ringkasan JSON.

## Kontrak dan batas penggunaan

Input berupa DataFrame dengan `model_text` hasil preprocessing versi 3 dan
`target_program`; keluaran salah satu dari tiga kelas sentimen. Representasi
baru hanya memakai teks. Teks yang sama dengan sentimen berbeda antartarget
memerlukan model yang mengondisikan prediksi pada target; kandidat konflik
seperti itu ditahan dari pelatihan model ini.

Label baru melalui pemeriksaan konteks oleh AI setelah usulan model lokal;
`human_reviewed=False` dan `approved_for_training=False` dipertahankan. Sampel
berisi opini, berita, dan promosi; hasilnya bukan ukuran dukungan masyarakat.
Review manusia, data lebih beragam terutama CKG, evaluasi temporal, dan uji
independen tetap diperlukan untuk tahap deployment berikutnya.

- [Ringkasan lengkap](experiment_summary.json).
- [Pemulihan dari Drive dengan cache kosong](storage_verification.json).
- [Verifikasi model dan pembagian data](runtime_verification.json).
