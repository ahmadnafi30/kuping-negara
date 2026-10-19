# Peta kode dan kelanjutan proyek

Training sentimen merupakan kelanjutan pipeline Kuping Negara. Kode tetap
menggunakan paket `src/kuping_negara/`, konfigurasi, dan metadata dataset yang
sama. `train.py` memanggil paket tersebut, sehingga pengembangan berikutnya
dapat memakai kembali modul yang sudah tersedia.

## Alur data sampai model

```text
X -> ingestion -> raw CSV + manifest
  -> preprocessing -> review label AI/manusia
  -> snapshot training dan penunjuk DVC
  -> train.py -> training.cli -> training.experiments
  -> training.data + training.evaluation
  -> metrik dan artefak MLflow -> Model Registry
```

Pengumpulan dan preprocessing dijadwalkan oleh Airflow. Review label,
publikasi snapshot DVC, dan training merupakan langkah terpisah yang dijalankan
secara eksplisit. DAG Airflow saat ini belum melakukan pelabelan, training,
atau deployment otomatis.

## File yang perlu dibaca

Semua tautan berikut menuju file asli pada branch `main` repositori yang sama.

| Path dalam repo | Fungsi | GitHub |
| --- | --- | --- |
| `train.py` | Entry point training; memanggil CLI paket | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/train.py) |
| `src/kuping_negara/training/README.md` | Penjelasan tiap modul training | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/README.md) |
| `src/kuping_negara/training/cli.py` | Perintah persiapan dataset dan eksperimen | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/cli.py) |
| `src/kuping_negara/training/data.py` | Validasi dataset, lineage DVC dan kelompok data | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/data.py) |
| `src/kuping_negara/training/evaluation.py` | TF-IDF, Logistic Regression, grouped split/CV dan metrik | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/evaluation.py) |
| `src/kuping_negara/training/experiments.py` | Tiga trial, logging MLflow, pemilihan model dan Registry | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/experiments.py) |
| `configs/training/expanded.json` | Tiga variasi C, seed dan nama eksperimen/Registry | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/configs/training/expanded.json) |
| `src/kuping_negara/ingestion/tweet_harvest.py` | Entry point pengumpulan data X | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/ingestion/tweet_harvest.py) |
| `src/kuping_negara/preprocessing/x_pipeline.py` | Validasi raw, preprocessing dan publikasi hasil | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/preprocessing/x_pipeline.py) |
| `src/kuping_negara/labeling/batches.py` | Menggabungkan keputusan review dan melindungi kelompok test lama | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/labeling/batches.py) |
| `src/kuping_negara/data_versioning/snapshots.py` | Membuat dan menambah snapshot raw tervalidasi | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/data_versioning/snapshots.py) |
| `data/raw/expanded_20261019.csv.dvc` | Penunjuk snapshot raw 666 baris | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/data/raw/expanded_20261019.csv.dvc) |
| `data/training/sentiment_expanded_20261019.csv.dvc` | Penunjuk snapshot eksperimen 396 contoh | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/data/training/sentiment_expanded_20261019.csv.dvc) |
| `compose.yaml` | Layanan Airflow/PostgreSQL serta profil MLflow/trainer | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/compose.yaml) |
| `docker/mlflow/Dockerfile` | Image dengan dependensi training dan server MLflow | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/docker/mlflow/Dockerfile) |
| `docker/mlflow/train.py` | Memeriksa kesesuaian source image dengan Git sebelum menjalankan entry point root | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/docker/mlflow/train.py) |
| `pyproject.toml` dan `uv.lock` | Dependensi dan versi lingkungan yang dikunci | [Proyek](https://github.com/ahmadnafi30/kuping-negara/blob/main/pyproject.toml), [Lockfile](https://github.com/ahmadnafi30/kuping-negara/blob/main/uv.lock) |
| `.devcontainer/devcontainer.json` | Lingkungan Codespaces, termasuk extra training dan port MLflow | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/.devcontainer/devcontainer.json) |

## Berkas hasil

| Path | Isi | GitHub |
| --- | --- | --- |
| `reports/training/expanded_20261019_docker/model_metadata.md` | Parameter terbaik, metrik dan batas penggunaan | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/reports/training/expanded_20261019_docker/model_metadata.md) |
| `reports/training/expanded_20261019_docker/experiment_summary.json` | Tiga run, lineage, pembagian data, model terpilih dan Registry | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/reports/training/expanded_20261019_docker/experiment_summary.json) |
| `reports/training/expanded_20261019_docker/runtime_verification.json` | Bukti runtime container, pemuatan model dan pemisahan kelompok | [Buka](https://github.com/ahmadnafi30/kuping-negara/blob/main/reports/training/expanded_20261019_docker/runtime_verification.json) |

Snapshot 396 contoh menggunakan label AI provisional. Model terbaik dipilih
melalui CV pada 316 contoh development, kemudian dievaluasi pada 80 contoh
test. Registry masih berstatus `experimental`, tanpa persetujuan deployment.

## Melanjutkan pengembangan

Gunakan clone repositori agar riwayat dan tag DVC tersedia:

```bash
git clone https://github.com/ahmadnafi30/kuping-negara.git
cd kuping-negara
git fetch --tags
```

Pulihkan dataset melalui DVC mengikuti
[panduan remote](dvc-data-versioning.md), kemudian jalankan training di Docker
mengikuti [panduan runtime](mlflow-docker.md). Pilih folder laporan baru setiap
run agar hasil sebelumnya tetap tersimpan.

Perubahan CLI dilakukan di `training/cli.py`, perubahan validasi data di
`training/data.py`, dan perubahan model/evaluasi di `training/evaluation.py`.
Pencatatan atau pemilihan eksperimen berada di `training/experiments.py`.
Pengembangan dilakukan melalui [alur Git proyek](git-workflow.md), lalu
`main` dan `develop` disinkronkan setelah rilis.
