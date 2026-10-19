# Eksperimen Sentimen dengan MLflow

Pipeline ini menjalankan klasifikasi `negative`, `neutral`, dan `positive`
menggunakan TF-IDF dan Logistic Regression. `train.py` menjadi entry point;
validasi data, pembagian dataset, dan pencatatan eksperimen berada dalam
`src/kuping_negara/training/`.

## Data yang digunakan

Sumbernya snapshot raw LK-05 pada tag `lk05-data-v2` (200 baris). Label AI
batch 11 Oktober digabungkan berdasarkan pasangan program/post. Checksum raw,
checksum label, conversation ID, dan hasil preprocessing diperiksa sebelum
snapshot training dibuat. Teks input harus sama dengan hasil preprocessing raw
versi tersebut.

Mode bawaan hanya menerima label yang `human_reviewed=True` serta
`approved_for_training=True`. Eksperimen awal ini memakai `--allow-provisional`
atas persetujuan pemilik proyek. Flag persetujuan manusia tidak diubah.

Dari 92 kandidat anotasi AI, satu masih memiliki flag review relevansi sehingga
91 baris masuk snapshot: 41 negatif, 44 netral, dan 6 positif. Data berasal dari
MBG, Kopdes Merah Putih, dan Sekolah Rakyat; CKG belum menyumbang contoh yang
memenuhi syarat. Label kosong, uncertain, tidak relevan, dan flag kualitas yang
belum selesai tidak menjadi target latihan.

## Lingkungan Codespaces atau lokal

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv pip check
```

Dev Container memasang extra `training` dan meneruskan port 5000. Saat pertama
kali memakai konfigurasi baru, rebuild Dev Container. MLflow dan model berjalan
pada environment pengembangan; penjadwalan Airflow tetap menangani collect dan
preprocess.

## Menyiapkan snapshot training

Jalankan dari root repo pada mesin yang memiliki hasil anotasi privat:

```bash
uv run --locked --no-sync python train.py prepare --labels "data/labeled/batch=20261011T143700+0700/all_programs_ai_labeled.csv" --allow-provisional
uv run --locked --no-sync dvc add data/training/sentiment_dataset.csv
```

Hasilnya CSV training privat, `sentiment_dataset.csv.dvc`, dan
`sentiment_dataset.manifest.json`. Penunjuk serta manifest masuk Git; isi CSV
diabaikan Git. Manifest mencatat versi raw, checksum, distribusi kelas, versi
preprocessing, dan status label. Jika snapshot yang ada berbeda, gunakan path
output baru agar versi sebelumnya tidak tertimpa.

Pada clone lain yang remote-nya sudah disiapkan dan memiliki objek training:

```bash
uv run --locked --no-sync dvc pull --remote gdrive data/raw/lk05_dataset.csv.dvc data/training/sentiment_dataset.csv.dvc
```

Token dan file anotasi tidak ikut clone. Lihat [konfigurasi DVC](dvc-data-versioning.md)
untuk setup remote. Ketersediaan objek training pada remote harus dicek setelah
upload; cache lokal saja tidak membuatnya tersedia pada mesin lain.

## Menjalankan tiga variasi

```bash
uv run --locked --no-sync python train.py run --allow-provisional
```

`train-sentiment run --allow-provisional` menyediakan entry point yang sama.
Konfigurasi tersimpan dalam `configs/training/sentiment.json`:

| Run | C | N-gram teks | Class weight |
| --- | ---: | --- | --- |
| lr-c01-unigram | 0.1 | 1 | balanced |
| lr-c1-bigram | 1.0 | 1-2 | balanced |
| lr-c10-bigram | 10.0 | 1-2 | balanced |

Semakin kecil C, regularisasi semakin kuat. Seluruh trial memakai seed 42,
max_features 10.000 dan max_iter 2.000. Representasi program memakai one-hot
encoding sebagai fitur tambahan. TF-IDF dan encoder dipasang dalam satu
scikit-learn Pipeline agar fit hanya memakai partisi latihan.

## Pembagian dan pemilihan model

Post yang sama, percakapan yang sama, teks identik, dan kelompok kemiripan dari
preprocessing digabung secara transitif menjadi satu kelompok. Kelompok tidak
boleh melintasi partisi. Pembagian bersifat grouped-stratified, belum pengujian
masa depan berdasarkan waktu.

- 72 baris development dipakai pada cross-validation tiga fold.
- 19 baris menjadi test holdout tetap.
- Ketiga parameter dibandingkan berdasarkan rerata `cv_macro_f1`.
- Jika skor sama, trial pertama dalam konfigurasi dipilih secara deterministik.
- Hanya pemenang cross-validation dievaluasi pada test holdout, satu kali.
- Dummy classifier kelas mayoritas menjadi pembanding pada holdout.

Test holdout tidak dipakai memilih parameter. Pada sampel saat ini, test hanya
memiliki satu contoh positif; recall kelas tersebut sangat tidak stabil.
Indeks split, jumlah kelas, seed, dan pemeriksaan overlap tersimpan sebagai
artefak sehingga pembagian dapat diaudit.

## Apa yang tercatat di MLflow

`mlflow.log_param()` mencatat C, n-gram, class weight, seed, versi raw, dan hash
dataset. Metrik mencakup accuracy, Macro-F1, weighted-F1, recall per kelas,
serta simpangan baku Macro-F1 antar-fold. Skor per fold dicatat dengan step
sehingga dapat ditampilkan sebagai grafik.

`mlflow.sklearn.log_model()` menyimpan Pipeline lengkap, signature input,
contoh input sintetis, serta dependensi model. Tidak ada contoh unggahan asli
yang ditambahkan sebagai input example. Teks dan vocabulary masih berada pada
artefak lokal model, sehingga folder MLflow tidak diunggah ke Git.

Setiap run juga mencatat konfigurasi, lineage, commit kode dan status working
tree. Run pemenang mendapat laporan klasifikasi, confusion matrix, grafik
perbandingan, dan ringkasan eksperimen. Semua hasil berasal dari eksekusi,
bukan nilai yang diisi manual.

## Membuka dashboard

Pada terminal baru dari root repo lokal:

```bash
uv run --locked --no-sync mlflow server --backend-store-uri sqlite:///mlruns/tracking.db --host 127.0.0.1 --port 5000
```

Buka <http://localhost:5000>. Database SQLite dan artefak berada di `mlruns/`,
di luar Git. Server UI harus memakai database yang sama dengan training.

Pada Codespaces gunakan:

```bash
uv run --locked --no-sync mlflow server --backend-store-uri sqlite:///mlruns/tracking.db --host 0.0.0.0 --port 5000 --allowed-hosts "localhost:*,127.0.0.1:*,${CODESPACE_NAME}-5000.app.github.dev" --cors-allowed-origins "https://${CODESPACE_NAME}-5000.app.github.dev"
```

Buka port 5000 dari tab Ports dan pertahankan visibility Private. Lingkungan
Codespaces memiliki database lokal sendiri; jalankan eksperimen di sana agar
run muncul pada dashboard Codespaces.

## Model Registry dan metadata

Pemenang didaftarkan sebagai `kuping-negara-sentiment-pilot` dengan alias
`experimental`. Tag `label_status=provisional_ai` dan
`deployment_approved=false` menyertai model. Registry ini mencatat kandidat
latihan; deployment membutuhkan review label, evaluasi independen, slice per
program, dan persetujuan terpisah.

Artefak Git yang bisa dibaca tanpa database lokal:

- [Ringkasan eksperimen](../reports/training/initial/experiment_summary.json).
- [Metadata model terpilih](../reports/training/initial/model_metadata.md).
- [Manifest dataset](../data/training/sentiment_dataset.manifest.json).

Model binary, database, dan CSV disimpan di luar Git. Untuk memulihkan model
Registry di lingkungan lain, jalankan ulang eksperimen dengan data DVC yang
sama; backup database lokal saja perlu disertai direktori artefaknya.

## Bukti untuk laporan

Ambil screenshot asli dari UI berikut:

1. Halaman eksperimen yang menampilkan tiga run beserta parameter C dan skor
   `cv_macro_f1` / `cv_accuracy`.
2. Pilih tiga run lalu Compare untuk grafik metrik. Gunakan metrik CV agar
   ketiga run dibandingkan pada prosedur yang sama.
3. Detail run terbaik: parameter, skor cross-validation, dan skor test akhir.
4. Halaman model Registry: nama, versi, run sumber, alias, dan tag kualitas.

Laporan menjelaskan dataset LK-05, status label AI, filter kualitas, split,
variasi parameter, pencatatan MLflow, hasil perbandingan, alasan pemilihan,
dan keterbatasan. Accuracy terhadap label AI tidak dapat disebut akurasi
terhadap penilaian manusia. Skor tinggi pada sampel kecil juga belum membuktikan
kesiapan deployment.

Referensi: [logging model scikit-learn](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.sklearn.html)
dan [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/).
