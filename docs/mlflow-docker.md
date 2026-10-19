# Training dan MLflow di Docker

Alur ini menjalankan `train.py` di container sekali jalan. MLflow menyimpan
riwayat eksperimen, model, dan Registry dalam volume `mlflow-data`. Airflow
menangani jadwal collect dan preprocess, sedangkan PostgreSQL menyimpan metadata
Airflow. Seluruh komponen Airflow tetap berada dalam satu container.

## Menjalankan layanan

Jalankan Docker Desktop, lalu buka terminal di root repositori. Siapkan secret
Airflow mengikuti [panduan scheduler](airflow-docker.md) bila belum tersedia. Dataset
harus sudah dipulihkan melalui DVC pada mesin yang memiliki akses Drive:

```bash
uv run --locked --no-sync dvc pull --remote gdrive data/raw/expanded_20261019.csv.dvc data/training/sentiment_expanded_20261019.csv.dvc
docker compose --profile training build mlflow
docker compose --profile training up -d --wait postgres airflow mlflow
```

Buka Airflow di <http://localhost:8080> dan MLflow di <http://localhost:5000>.
Port keduanya hanya dipublikasikan ke komputer lokal. Profil `training`
bersifat opsional: perintah Compose biasa tetap menjalankan Airflow dan
PostgreSQL saja. Sebutkan nama layanan saat `up` agar trainer tidak ikut
berjalan sebelum Anda siap.

## Menjalankan tiga eksperimen

```bash
docker compose --profile training run --rm trainer
```

Perintah tersebut menjalankan 396 contoh pada snapshot
`sentiment_expanded_20261019.csv`, dengan tiga nilai C: 0,5, 2, dan 10.
Konfigurasi berada di `configs/training/expanded.json`. Label masih hasil AI;
`--allow-provisional` mengizinkan eksperimen awal tanpa mengubah status review
manusia atau persetujuan deployment.

Hasil tersimpan di `reports/training/expanded_20261019_docker/`. Folder output
yang sudah berisi hasil tidak ditimpa. Untuk mengulang dengan nama laporan baru:

```bash
docker compose --profile training run --rm trainer run --dataset data/training/sentiment_expanded_20261019.csv --config configs/training/expanded.json --output reports/training/docker-rerun --allow-provisional --tracking-uri http://mlflow:5000
```

Trainer berhenti dan dihapus setelah selesai. Layanan yang tetap berjalan
adalah Airflow, PostgreSQL, dan MLflow. Hasil di dashboard dapat dibuka setelah
trainer selesai. Pilih eksperimen `kuping-negara-sentiment-expanded`, bandingkan
`cv_macro_f1` pada tiga run, lalu lihat model dengan alias `experimental` di
Registry. Pemilihan model memakai CV; hanya pemenang yang dievaluasi pada test.

## Penyimpanan dan reproduksi

- Dataset dipasang ke trainer sebagai volume baca saja. Isi CSV tidak dimasukkan
  ke image.
- Laporan dipasang ke folder `reports` di workspace; pada mesin pengembangan ini
  lokasinya berada di drive D:.
- Model dan database MLflow disimpan di volume Docker `mlflow-data`. Riwayat
  eksperimen lokal lama dalam `mlruns/` tetap disimpan terpisah.
- Trainer mengirim artefak lewat server MLflow. Path file Windows tidak dipakai
  sebagai alamat model antar-container.
- Image tidak membawa token X, OAuth Drive, cache DVC, atau database lokal.
  Pengambilan data tetap memakai secret khusus container Airflow.
- Git dipasang baca saja untuk memeriksa versi dataset dan commit sumber.
  Setelah kode berubah, commit perubahan lalu build ulang image sebelum training.

Jangan menghapus volume ketika ingin mempertahankan riwayat MLflow. Untuk
menghentikan layanan tanpa menghapus volume:

```bash
docker compose --profile training stop
```

Dataset DVC di Google Drive tidak mencadangkan database atau artefak MLflow.
Cadangkan volume `mlflow-data` secara terpisah sebelum memindahkan layanan ke
mesin lain. Jangan menjalankan `down -v` pada stack yang masih diperlukan.

CI membangun image dan menjalankan tiga eksperimen dengan data sintetis pada
server MLflow sementara. Pengujian memastikan logging HTTP, penyimpanan
artefak, Registry, dan pemuatan ulang model bekerja antar-container.
