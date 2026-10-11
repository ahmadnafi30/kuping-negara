# Git Workflow

`main` menyimpan versi stabil. `develop` mengintegrasikan pekerjaan sebelum
rilis. Gunakan branch pendek dan Pull Request dengan tujuan yang jelas.

## Branch

| Branch | Basis | Tujuan |
| --- | --- | --- |
| `main` | — | Versi stabil yang lulus CI |
| `develop` | `main` | Integrasi fitur yang sudah direview |
| `feat/<nama>` | `develop` | Fitur baru |
| `fix/<nama>` | `develop` | Perbaikan bug |
| `refactor/<nama>` | `develop` | Perubahan struktur kode |
| `docs/<nama>` | `develop` | Dokumentasi |
| `chore/<nama>` | `develop` | Tooling atau pemeliharaan |
| `test/<nama>` | `develop` | Pengujian |
| `hotfix/<nama>` | `main` | Perbaikan mendesak pada versi stabil |

Nama branch memakai lower-case kebab-case, misalnya `refactor/data-pipeline`.
Pemeliharaan yang secara khusus ditujukan ke `main` dapat dibuat dari `main`
dan diajukan langsung ke `main`; sebutkan alasan tersebut pada Pull Request.

## Mulai bekerja

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feat/short-description
```

Untuk pekerjaan yang ditujukan langsung ke `main`, ganti basis pada contoh
dengan `main`. Jangan menimpa perubahan lokal ketika berganti branch.

## Commit dan pemeriksaan

Gunakan format `<type>(optional-scope): <summary>`. Contoh:

```text
feat(ingestion): add program selection
fix(preprocessing): reject empty datasets
refactor: separate collection and storage responsibilities
docs: clarify supported workflows
```

Setiap commit membawa satu tujuan yang dapat dipahami. Sebelum push:

```bash
uv sync --locked --extra dev
uv pip check
uv run --locked --extra dev ruff check src tests
uv run --locked --extra dev ruff format --check src tests
uv run --locked --extra dev pytest
git diff --check
git status --short
```

Pilih file dengan sengaja saat staging. Kredensial, dataset, model binary,
virtual environment, dan cache tidak boleh masuk commit.

## Pull Request

1. Push branch pekerjaan dengan `git push -u origin <branch>`.
2. Pilih target `develop` untuk fitur biasa atau `main` untuk rilis/pemeliharaan langsung.
3. Jelaskan masalah, perilaku setelah perubahan, hasil pemeriksaan, dan risiko.
4. Perbarui dokumentasi serta kontrak/dependensi yang ikut berubah.
5. Tunggu seluruh CI selesai dan tangani feedback sebelum merge.

CI menjalankan pengujian, pemeriksaan dependensi, health check, lint, dan format
pada Linux dan Windows. Review independen dianjurkan ketika ada contributor
lain. Jangan melewati perlindungan branch yang sudah diterapkan.

## Merge dan sinkronisasi

- Topic branch ke `develop`: squash merge untuk perubahan yang koheren.
- `develop` ke `main`: Pull Request rilis.
- Pemeliharaan langsung ke `main`: merge setelah pemeriksaan lulus, lalu
  sinkronkan perubahan ke `develop` melalui Pull Request bila diperlukan.
- Hapus topic branch setelah memastikan pekerjaan sudah digabungkan.
- Pertahankan `main` dan `develop`; jangan force push kedua branch tersebut.

Label *ahead*/*behind* menunjukkan perbedaan riwayat commit, bukan kualitas
branch. Branch yang selesai dapat dihapus; tidak perlu membuat commit kosong
untuk mengubah angka pembanding.

Jika branch bersama sudah divergen, periksa riwayat dan gunakan merge yang
direview. Jangan menghapus riwayat dengan reset atau force push.
