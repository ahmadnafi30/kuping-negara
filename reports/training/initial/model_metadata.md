# Metadata Model Sentimen Terpilih

Model ini adalah hasil eksperimen awal menggunakan label AI yang belum divalidasi manusia.
Pemilihan memakai rerata Macro-F1 cross-validation, lalu model terpilih diuji satu kali pada holdout.

| Informasi | Nilai |
| --- | --- |
| Run terpilih | `eb5bf7dec2944eb08546bcbefd50f48b` |
| Algoritme | TF-IDF + One-hot program + Logistic Regression |
| C | 10.0 |
| N-gram | 1-2 |
| Class weight | balanced |
| Max features / max iter | 10.000 / 2.000 |
| Seed | 42 |
| Data | 91 baris; raw `lk05-data-v2` |
| SHA-256 data training | `1c073b14fd28d7dd7302544f7f936e587726076743b3baf708e3ec6327a580a4` |
| Registry | `kuping-negara-sentiment-pilot`, versi 1, alias `experimental` |
| Commit kode latihan | `fac6e86c56b6052cfea107b0e1fa15a8e9f17192` |
| Deployment approved | **False** |

## Perbandingan eksperimen

| Variasi | CV accuracy | CV Macro-F1 | Simpangan baku F1 |
| --- | ---: | ---: | ---: |
| lr-c01-unigram | 0.6667 | 0.5714 | 0.2422 |
| lr-c1-bigram | 0.7222 | 0.5992 | 0.2225 |
| lr-c10-bigram | 0.7361 | 0.6079 | 0.2170 |

Variasi `lr-c10-bigram` dipilih karena rerata CV Macro-F1 tertinggi (0.6079).

## Tes akhir dan batas hasil

Accuracy holdout: **0.7895**; Macro-F1: **0.5412**.
Dummy kelas mayoritas: accuracy 0.4737, Macro-F1 0.2143.
Test berisi 9 negatif, 9 netral, dan 1 positif. Recall positif bernilai 0;
model belum berhasil mengenali contoh positif pada test ini. Nilai tersebut
mengukur kesesuaian dengan label AI, belum ketepatan terhadap anotasi manusia.
Target Macro-F1 proposal 0,75 pada data independen belum terpenuhi.

Model tetap disimpan sebagai kandidat eksperimen untuk memenuhi alur Registry.
Sebelum deployment, perlu review manusia, tambahan data terutama kelas positif,
evaluasi per program dan periode, evaluasi temporal, serta pemeriksaan kalibrasi.
CKG belum terwakili pada training; jangan menganggap model sudah tervalidasi untuk CKG.

## Kontrak input model

Model MLflow menerima pandas DataFrame dengan kolom `model_text` dan
`target_program`; output berupa salah satu dari tiga label sentimen.
`model_text` harus dihasilkan dengan preprocessing versi 3. Vocabulary TF-IDF
dan encoder dipaketkan dalam Pipeline; jangan melakukan fit ulang pada input inferensi.

Dataset CSV, model binary, SQLite dan artefak tersimpan lokal, di luar Git.
Ringkasan terstruktur: [experiment_summary.json](experiment_summary.json).

Snapshot training sudah diunggah ke Google Drive dan dipulihkan dengan jumlah
baris serta SHA-256 yang sama; lihat [bukti storage](storage_verification.json).
