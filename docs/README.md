# Dokumentasi Kuping Negara

Mulai dari [README](../README.md) untuk menjalankan fitur yang tersedia.
Dokumentasi operasional menjelaskan kode di `main`; proposal dan roadmap
menjelaskan pekerjaan yang belum tersedia.

## Penggunaan

| Dokumen | Isi |
| --- | --- |
| [Codespaces Setup](codespaces-setup.md) | Setup Python/uv, Dev Container, dan troubleshooting |
| [X Data Collection](x-data-collection.md) | Pengumpulan interaktif, keyword, browser, dan raw storage |
| [X Data Preprocessing](x-data-preprocessing.md) | Transformasi CSV, flag kualitas, dan lineage |
| [Airflow Docker](airflow-docker.md) | Jadwal 23.59 WIB, Docker, token lokal, retry, dan operasi |
| [Annotation Guidelines](annotation-guidelines.md) | Definisi sentimen dan prosedur review manual |

## Pengembangan

| Dokumen | Isi |
| --- | --- |
| [Project Structure](project-structure.md) | Struktur aktual dan batas tanggung jawab modul |
| [Development Guidelines](development-guidelines.md) | Gaya kode, dependensi, pengujian, dan dokumentasi |
| [Git Workflow](git-workflow.md) | Branch, commit, Pull Request, dan rilis |
| [Keyword Configuration](../configs/keywords/README.md) | Konfigurasi program bersama untuk dua pipeline |
| [Data Contract](../configs/schemas/README.md) | Rancangan JSON Schema dan status validasinya |

## Perencanaan dan riwayat

- [Project Proposal](project-proposal.md): konteks riset, arsitektur target, dan metrik.
- [Roadmap](roadmap.md): status implementasi dan urutan pekerjaan berikutnya.
- [Archive](archive/README.md): proposal infrastruktur terdahulu.

Perubahan perilaku, kontrak, atau cara menjalankan proyek harus memperbarui
dokumen terkait dalam Pull Request yang sama.
