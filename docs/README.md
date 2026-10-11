# Dokumentasi Kuping Negara

[README proyek](../README.md) menyediakan mulai cepat dan status fitur.
Panduan berikut menjelaskan implementasi yang tersedia pada `main`.

## Menjalankan pipeline

| Panduan | Isi |
| --- | --- |
| [Setup Codespaces](codespaces-setup.md) | Python, uv, Dev Container, dan troubleshooting |
| [Pengumpulan data X](x-data-collection.md) | Keyword, CLI, browser, rentang WIB, dan raw storage |
| [Preprocessing data X](x-data-preprocessing.md) | Transformasi, flag kualitas, duplikat, dan lineage |
| [Airflow di Docker](airflow-docker.md) | Stack dua container, jadwal 23.59 WIB, dan operasi |
| [Alur penambahan versi data](dvc.md) | Collect, append, pelacakan DVC, upload, commit/tag, dan pemulihan |
| [Konfigurasi DVC dan remote](dvc-data-versioning.md) | Cache, remote lokal, OAuth Drive, dan audit dataset |
| [Pedoman anotasi](annotation-guidelines.md) | Relevansi, kelas sentimen, review, dan adjudication |

## Mengembangkan proyek

| Panduan | Isi |
| --- | --- |
| [Struktur proyek](project-structure.md) | Kepemilikan modul dan batas dependensi |
| [Standar pengembangan](development-guidelines.md) | Konvensi kode, dependensi, dan pemeriksaan kualitas |
| [Alur Git](git-workflow.md) | Main/develop, branch sementara, merge, dan sinkronisasi |
| [Konfigurasi keyword](../configs/keywords/README.md) | Konfigurasi bersama pengumpulan dan preprocessing |
| [Kontrak data](../configs/schemas/README.md) | Rancangan JSON Schema dan status validasinya |

## Perencanaan dan arsip

- [Proposal proyek](project-proposal.md): tujuan riset dan arsitektur target.
- [Roadmap](roadmap.md): fitur tersedia dan pekerjaan berikutnya.
- [Arsip](archive/README.md): desain historis dan riwayat branch eksperimen.

Perbarui panduan terkait ketika perilaku, konfigurasi, atau alur penggunaan
berubah. Proposal dan arsip tidak menjadi petunjuk menjalankan stack saat ini.
