# Arsip Branch pada 11 Oktober 2026

Pembersihan repositori mempertahankan `main` dan `develop` sebagai branch aktif.
Dari 15 branch pekerjaan terdahulu, lima sudah tercakup pada `main` dan sepuluh
berasal dari satu rangkaian eksperimen lama. Tidak ada Pull Request terbuka saat
audit dilakukan.

Riwayat 33 commit eksperimen yang belum masuk `main` dipertahankan pada tag
`archive/legacy-mlops-2026-10-11`, dengan commit puncak
`3a2e28ad144787a04d84b50d87fc0b9d0cd54c16`. Semua commit dari sepuluh branch
eksperimen merupakan ancestor commit tersebut. Kode di tag ini adalah snapshot
historis dan belum dinyatakan kompatibel dengan pipeline aktif.

## Referensi branch sebelum pembersihan

| Branch lama | Commit terakhir | Penyimpanan riwayat |
| --- | --- | --- |
| `feat/collection-date-validation` | `0c05ba81962da814f7cd765f3f80dc55fd79e41a` | Tag arsip eksperimen |
| `feat/dvc-data-versioning` | `fe96c86e8edffc50f5e1e9260d9ed7b08b93ccc2` | Tag arsip eksperimen |
| `feat/initial-data-eda` | `57ee528a53ce73c0c08232129af9787f3373cf09` | Tag arsip eksperimen |
| `feat/initial-training-pilot` | `3a2e28ad144787a04d84b50d87fc0b9d0cd54c16` | Tag arsip eksperimen |
| `feat/lk04-ingestion-preprocessing` | `256705c4c7d33f5a5785196f4a2d1e89fc369d79` | Tag arsip eksperimen |
| `feat/lk05-google-drive-remote` | `ecb4f5320bc3608b9ca6ebe0b5139f491acfe4fb` | `main` |
| `feat/lk05-raw-data-versions` | `7dce924b3cb6c7ce517f35718d6179e6f61a1289` | `main` |
| `feat/mlops-integration` | `3a2e28ad144787a04d84b50d87fc0b9d0cd54c16` | Tag arsip eksperimen |
| `feat/preprocessing-training-candidates` | `23f3ccd6f7267b30005bc237c2df75eddbc786cb` | Tag arsip eksperimen |
| `feat/sentiment-preprocessing` | `6bc6b99ed9358ed7e0f6338a4768f0d1843128cf` | `main` |
| `feat/training-data-bootstrap` | `a7b1cede75e58dd20ed79110e2efb633caa6278d` | Tag arsip eksperimen |
| `feat/training-source-isolation` | `abf64328736fde6773f2c286f47fad0916a7f380` | Tag arsip eksperimen |
| `feat/weekly-airflow-scheduling` | `161e67a04bb2cc41e3ac2fafcf9ccb9606b1ea00` | Tag arsip eksperimen |
| `fix/jakarta-search-time-window` | `9441876826ab9558689a4576e51a23188c85e0f1` | `main` |
| `hotfix/data-quality-gates` | `bafea6100956199c38e157eb9979e024a08179bf` | `main` |

## Memulihkan kode eksperimen

Gunakan checkout terpisah agar pipeline aktif tidak terganti:

```bash
git fetch origin --tags
git worktree add --detach ../kuping-negara-legacy archive/legacy-mlops-2026-10-11
```

Untuk melihat titik branch tertentu, gunakan commit pada tabel di atas dengan
`git show <commit>` atau checkout terpisah. Metadata DVC dalam arsip dapat
merujuk objek yang berbeda dari dua versi dataset aktif; keberadaan riwayat Git
saja tidak menjamin objek dataset historis tersedia pada remote saat ini.

Tag `lk05-data-v1` dan `lk05-data-v2` tetap dipertahankan untuk audit dataset
aktif. Hindari `dvc push --all-tags` pada repo ini karena tag arsip kode bukan
bagian dari migrasi dua versi dataset tersebut.
