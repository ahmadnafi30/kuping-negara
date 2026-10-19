# Alur Git dan Sinkronisasi Branch

Repositori mempertahankan dua branch utama. Branch pekerjaan dibuat untuk satu
tujuan, diperbarui mengikuti `main`, lalu dihapus setelah selesai.

| Branch | Peran |
| --- | --- |
| `main` | Versi stabil yang telah lulus pemeriksaan |
| `develop` | Basis integrasi pekerjaan berikutnya; mengikuti perubahan `main` |
| `feat/<nama>` | Fitur baru |
| `fix/<nama>` atau `hotfix/<nama>` | Perbaikan biasa atau mendesak |
| `refactor/<nama>` | Perubahan struktur kode |
| `docs/<nama>` | Dokumentasi |
| `chore/<nama>` atau `test/<nama>` | Pemeliharaan atau pengujian |

Nama branch memakai lower-case kebab-case. Pemeliharaan yang secara khusus
menyasar `main` dapat dibuat dari `main`; fitur biasa dibuat dari `develop`.

## Memulai pekerjaan

Sinkronkan branch dasar sebelum membuat branch baru:

```bash
git fetch origin --prune
git switch develop
git pull --ff-only origin develop
git merge --ff-only origin/main
git switch -c feat/short-description
```

Jika `develop` memiliki pekerjaan yang belum dirilis dan tidak bisa
fast-forward, integrasikan `origin/main` menggunakan merge biasa pada branch
sinkronisasi, selesaikan konflik, dan jalankan pemeriksaan sebelum push.
Jangan memakai reset atau force push untuk menghilangkan pekerjaan tersebut.

## Menjaga branch tetap mengikuti main

Pada branch pekerjaan yang masih diperlukan:

```bash
git fetch origin
git merge origin/main
```

Selesaikan konflik sesuai kontrak terbaru, lalu jalankan pemeriksaan. Menghapus
branch yang telah selesai mengurangi daftar branch tertinggal tanpa membuat
commit sinkronisasi yang tidak diperlukan.

## Commit dan verifikasi

Gunakan Conventional Commits seperti `feat(ingestion): ...`,
`fix(preprocessing): ...`, atau `docs: ...`. Pilih file staging secara eksplisit.

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv pip check
uv run --locked --no-sync python -m kuping_negara.healthcheck
uv run --locked --no-sync ruff check src tests dags docker/airflow docker/mlflow train.py
uv run --locked --no-sync ruff format --check src tests dags docker/airflow docker/mlflow train.py
uv run --locked --no-sync pytest
git diff --check
git status --short
```

Data, cache, model, token, dan konfigurasi rahasia tetap di luar Git.
Untuk perubahan dokumentasi, periksa tautan, contoh perintah, dan konsistensi
hasil yang dijelaskan. Jangan membuat pengujian yang hanya menyalin isi dokumen.

## Publikasi dan merge

1. Push branch pekerjaan dan ajukan Pull Request ke `develop`, atau ke `main`
   untuk pemeliharaan yang langsung ditujukan ke versi stabil.
2. Jelaskan perubahan, pemeriksaan, dan dampak yang relevan.
3. Tunggu CI Windows/Linux, Airflow, dan MLflow Docker lulus sebelum merge.
4. Setelah rilis masuk `main`, sinkronkan `develop` dengan `main`.
5. Hapus branch pekerjaan yang telah selesai, lalu prune referensi lokal.

Untuk pemeliharaan oleh satu maintainer tanpa Pull Request, commit yang sama
harus lulus CI pada branch pekerjaan sebelum fast-forward ke branch utama.
Perlindungan branch yang aktif tetap berlaku. `main` dan `develop` tidak di-force-push.

Sinkronisasi `develop` setelah rilis, saat tidak ada commit unik di sana:

```bash
git switch develop
git merge --ff-only main
git push origin develop
```

Periksa hasilnya:

```bash
git fetch origin --prune
git rev-list --left-right --count origin/develop...origin/main
```

Hasil `0 0` berarti keduanya menunjuk riwayat yang sama. Jika `develop` masih
memiliki perubahan yang belum dirilis, angka pertama boleh lebih besar dari
nol; angka kedua harus nol setelah sinkronisasi.

## Arsip pekerjaan lama

Branch eksperimen yang tidak menjadi implementasi aktif dipertahankan melalui
tag arsip sebelum branch dihapus. [Catatan arsip](archive/2026-10-11-branch-cleanup.md)
memuat commit setiap branch dan cara memulihkan pekerjaan tersebut.
Tag `lk05-data-v1` dan `lk05-data-v2` tetap menjadi penanda dataset; tag
`archive/legacy-mlops-2026-10-11` menyimpan riwayat kode eksperimen.
