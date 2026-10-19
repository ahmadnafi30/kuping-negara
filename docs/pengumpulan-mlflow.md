# Berkas pengumpulan dan sumber kode

Paket pengumpulan menggunakan kelanjutan proyek Kuping Negara yang sama.
Implementasi training tetap berada pada `train.py` dan
`src/kuping_negara/training/`. File dalam folder `kode/` pada paket pengumpulan
merupakan salinan sumber dari satu commit repositori untuk keperluan review.
Pengembangan berikutnya tetap dilakukan di repositori utama.

## Isi paket lokal

```text
folder-pengumpulan/
  <laporan-yang-diekspor-pemilik-proyek>.pdf
  model_metadata.md
  experiment_summary.json
  README_PENGUMPULAN.md
  kode/
    README.md
    ASAL_KODE.json
    train.py
    src/kuping_negara/...
    configs/...
    docker/...
    data/...                  # penunjuk dan manifest DVC
    ...                       # dependensi dan modul pendukung terkait
  img/
    01-mlflow-daftar-run.jpg
    02-mlflow-perbandingan-metrik.jpg
    03-mlflow-model-registry.jpg
    04-mlflow-hasil-test-terbaik.jpg
```

`kode/README.md` menjelaskan fungsi setiap berkas yang disertakan, path asal
pada repositori, dan tautan GitHub ke versi commit sumber. `ASAL_KODE.json`
mencatat commit, path, dan checksum SHA-256 agar salinan dapat dibandingkan
dengan repositori. Struktur subfolder source tetap mengikuti path aslinya.

PDF yang dibuat pemilik proyek tetap menjadi laporan utama. Metadata Markdown
menjelaskan model terbaik, sedangkan JSON menyediakan detail eksperimen yang
bisa dibaca program. Gambar merupakan bukti pendukung laporan.

## Sumber yang perlu dirujuk

- [Repositori utama](https://github.com/ahmadnafi30/kuping-negara).
- [Peta alur dan file](kode-mlflow.md).
- [Penjelasan modul dalam folder training](../src/kuping_negara/training/README.md).
- [Metadata model terbaik](../reports/training/expanded_20261019_docker/model_metadata.md).
- [Ringkasan JSON](../reports/training/expanded_20261019_docker/experiment_summary.json).
- [Panduan screenshot](../img/README.md).

Untuk reproduksi, gunakan clone Git dari repositori agar tag dan riwayat
versioning tersedia. Pulihkan dataset menggunakan DVC sesuai
[panduan remote](dvc-data-versioning.md), lalu ikuti
[panduan training Docker](mlflow-docker.md). Salinan source pengumpulan tidak
membawa direktori `.git`, dataset CSV, cache, token, atau database MLflow.

## Melanjutkan pekerjaan

Tambahkan perubahan pada modul yang sudah memiliki tanggung jawab tersebut;
lihat [peta kode](kode-mlflow.md) sebelum membuat modul baru. Perubahan model,
konfigurasi eksperimen, dan dokumentasi dibuat dalam commit yang menjelaskan
perubahan sebenarnya. Hasil eksperimen lama dipertahankan dan run berikutnya
menggunakan folder laporan baru. Setelah CI lulus, rilis perubahan melalui
[alur Git proyek](git-workflow.md) dan sinkronkan `main` serta `develop`.

Label eksperimen saat ini masih hasil AI. Pendaftaran ke Registry tidak
mengubah status review manusia maupun persetujuan deployment.
