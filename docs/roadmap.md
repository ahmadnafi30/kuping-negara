# Roadmap

Status ini merujuk pada kode yang tersedia di `main`. Target performa dan
arsitektur lengkap ada dalam [proposal](project-proposal.md).

## Sudah tersedia

- Package Python dengan entry point CLI, uv lockfile, dan Dev Container.
- Konfigurasi keyword bersama dengan validasi input.
- Pengumpulan X interaktif menggunakan Tweet Harvest, dry run, dan raw partition.
- Preprocessing deterministik, pemetaan field, flag review, dan lineage SHA-256.
- Pedoman anotasi manual serta rancangan JSON Schema.
- Pengujian unit/integrasi, pemeriksaan format dan lint, serta CI.

## Berikutnya

| Tahap | Pekerjaan | Bukti selesai |
| --- | --- | --- |
| Kualitas data | Integrasikan JSON Schema dan tentukan penanganan invalid/empty cleaned text | Tes kontrak, laporan kualitas, dan aturan review |
| Dataset berlabel | Anotasi, adjudication, dan split berbasis waktu/conversation | Dataset version dan laporan agreement |
| Baseline model | Training/evaluation scikit-learn | Macro-F1 dan recall per kelas dengan split terdokumentasi |
| Eksperimen model | Bandingkan kandidat model Bahasa Indonesia | Metrik, biaya inference, calibration, dan lineage |
| Infrastruktur | Pilih serta implementasikan DVC, MLflow, dan Airflow sesuai kebutuhan | Instalasi reproducible, health check, dan runbook |
| Serving | API prediksi dan dashboard | Tes kontrak dan tampilan uncertainty |
| Operasi | Monitoring, alerting, retraining, dan rollback | Metrik, prosedur recovery, dan review kesiapan |

Jadwal dalam YAML adalah metadata proposal; kolektor belum otomatis berjalan
menurut `collection_day`. DVC, model registry, dan layanan penjadwalan belum
diaktifkan. Tambahkan dependensi dan folder saat implementasi memerlukannya.
