# Roadmap

Status ini merujuk pada kode yang tersedia di `main`. Target performa dan
arsitektur lengkap ada dalam [proposal](project-proposal.md).

## Sudah tersedia

- Package Python dengan entry point CLI, uv lockfile, dan Dev Container.
- Konfigurasi keyword bersama dengan validasi input.
- Pengumpulan X interaktif menggunakan Tweet Harvest, dry run, dan raw partition.
- Preprocessing deterministik, pemetaan field, flag review, dan lineage SHA-256.
- Validasi periode WIB dan batas hasil; teks kosong diblokir, duplikat lintas run,
  dan audit karantina output lama.
- Teks model yang mempertahankan makna sentimen, relevansi hashtag, duplikat
  per target program, serta flag kemiripan dan petunjuk grup dataset.
- Pedoman anotasi manual serta rancangan JSON Schema.
- Pengujian unit/integrasi, pemeriksaan format dan lint, serta CI.
- Airflow Docker lokal: empat jadwal mingguan 23.59 WIB, collect → preprocess,
  token via secret, publikasi atomik, dan verifikasi checksum pada retry.

## Berikutnya

| Tahap | Pekerjaan | Bukti selesai |
| --- | --- | --- |
| Kualitas data | Integrasikan JSON Schema dan perluas deteksi perubahan bahasa/relevansi | Tes kontrak, laporan kualitas, dan aturan review |
| Dataset berlabel | Anotasi, adjudication, dan split berbasis waktu/conversation | Dataset version dan laporan agreement |
| Baseline model | Training/evaluation scikit-learn | Macro-F1 dan recall per kelas dengan split terdokumentasi |
| Eksperimen model | Bandingkan kandidat model Bahasa Indonesia | Metrik, biaya inference, calibration, dan lineage |
| Infrastruktur | Implementasikan DVC/MLflow dan persiapkan deployment Airflow produksi | Backup, autentikasi, secret management, dan runbook produksi |
| Serving | API prediksi dan dashboard | Tes kontrak dan tampilan uncertainty |
| Operasi | Monitoring, alerting, retraining, dan rollback | Metrik, prosedur recovery, dan review kesiapan |

Jadwal operasional didefinisikan di `dags/x_collection.py`; `collection_day`
dalam YAML tetap metadata dan harus konsisten dengan DAG. DAG dibuat pause;
aktivasi membutuhkan secret akun X lokal. DVC dan model registry belum tersedia.
Panduan penggunaan serta batas stack lokal ada di [Airflow Docker](airflow-docker.md).
