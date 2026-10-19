# Modul training sentimen

Modul ini meneruskan alur Kuping Negara: pengumpulan data, preprocessing,
review label, versioning DVC, lalu eksperimen MLflow. Entry point tetap
`train.py` pada root repositori. Pelatihan dijalankan di container trainer;
server MLflow menyimpan metrik, artefak, dan Model Registry.

## Fungsi file

| File | Fungsi | Lokasi GitHub |
| --- | --- | --- |
| `train.py` pada root | Memanggil CLI training; menjadi perintah utama dari terminal dan Docker | [train.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/train.py) |
| `cli.py` | Membaca argumen `prepare`/`run`, memilih dataset dan konfigurasi, lalu memanggil proses terkait | [cli.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/cli.py) |
| `data.py` | Memvalidasi sumber DVC dan label, menyiapkan snapshot training, serta membentuk kelompok pencegah leakage | [data.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/data.py) |
| `evaluation.py` | Membuat Pipeline TF-IDF/Logistic Regression, split berkelompok, cross-validation dan metrik | [evaluation.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/evaluation.py) |
| `experiments.py` | Menjalankan tiga variasi, mencatat parameter/metrik/model ke MLflow, mengevaluasi pemenang dan mendaftarkannya ke Registry | [experiments.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/experiments.py) |
| `__init__.py` | Menandai namespace paket training | [__init__.py](https://github.com/ahmadnafi30/kuping-negara/blob/main/src/kuping_negara/training/__init__.py) |

`mlflow.log_param()`, `mlflow.log_metric()`, `mlflow.log_metrics()`,
`mlflow.sklearn.log_model()`, dan pendaftaran Registry berada di `experiments.py`.
Konfigurasi tiga nilai C berada di `configs/training/expanded.json`.

Baca [peta alur dan file proyek](../../../docs/kode-mlflow.md) untuk hubungan
modul ini dengan pengumpulan, preprocessing, DVC, Docker dan berkas hasil.
Cara menjalankan ada di [panduan MLflow Docker](../../../docs/mlflow-docker.md).
