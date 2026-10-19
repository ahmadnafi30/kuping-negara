# Perluasan data dan perbaikan eksperimen sentimen

Untuk training dan dashboard menggunakan container, ikuti [panduan MLflow Docker](mlflow-docker.md).

Pembaruan 19 Oktober 2026 menambah data nyata, memeriksa konteks label AI,
dan melatih ulang tiga variasi model. Data lama tetap tersedia untuk audit.

## Hasil data

| Tahap | Jumlah |
| --- | ---: |
| Snapshot raw sebelumnya | 200 pasangan program/post |
| Baris yang dibaca dari tujuh koleksi baru | 493 |
| Pasangan program/post baru setelah deduplikasi | 466 |
| Snapshot raw baru | 666 baris; 651 ID post unik |
| Kandidat baru yang lolos preprocessing dan diperiksa konteksnya oleh AI | 413 |
| Kandidat baru yang dipakai untuk eksperimen | 324 |
| Development lama yang digunakan kembali | 72 |
| Snapshot training/evaluasi baru | 396 |
| Test eksperimen awal yang tetap dipisahkan | 19 |

Satu post dapat membahas beberapa program. Karena itu jumlah pasangan
program/post berbeda dari jumlah ID post unik. Label per target disimpan
terpisah; post/percakapan terkait tetap masuk kelompok split yang sama.

| Program | Negatif | Netral | Positif | Total |
| --- | ---: | ---: | ---: | ---: |
| MBG | 68 | 49 | 16 | 133 |
| CKG | 1 | 14 | 7 | 22 |
| Kopdes Merah Putih | 84 | 39 | 21 | 144 |
| Sekolah Rakyat | 7 | 46 | 44 | 97 |
| **Total** | **160** | **148** | **88** | **396** |

Dari 466 baris baru, 53 belum lolos preprocessing, sedangkan 89 yang lolos
masih tidak relevan atau tidak cukup jelas saat pemeriksaan konteks. Baris-baris
tersebut tetap tersimpan untuk audit dan tidak dipaksakan menjadi target
pelatihan. Snapshot lama menyumbang 72 development; 19 test lama tetap di luar
snapshot baru, sementara 109 baris awal lainnya tidak memenuhi seleksi lama.

## Pengambilan yang diperbaiki

- Query memakai filter bahasa Indonesia. CKG juga memakai konteks kesehatan
  agar singkatannya tidak didominasi penggunaan di luar program kesehatan.
- Pencarian nama lengkap melengkapi pencarian singkatan. Kedua konfigurasi
  tetap dicatat; pencarian nama lengkap cenderung lebih banyak berisi berita/promosi.
- Respons pencarian ditampung sebelum form dikirim, termasuk respons awal yang
  cepat. Pembacaan halaman lanjutan menerima instruksi cursor dan daftar tweet
  pada posisi yang berbeda. ID berulang tidak menambah hitungan limit.
- Tanggal publikasi diperiksa terhadap rentang WIB, hasil tidak boleh melebihi
  limit, dan CSV parsial dari proses gagal tidak dipublikasikan.
- Salinan YAML per koleksi menjaga query dan aturan historis dapat diperiksa
  meskipun konfigurasi saat ini sudah berubah.

Koleksi baru yang berhasil mencakup 12-18 Oktober 2026 WIB. Rencana backfill
minggu lebih lama tidak seluruhnya selesai: beberapa pencarian tidak
menghasilkan CSV valid dan satu koneksi terputus. Kejadian tersebut tidak
dianggap bukti bahwa tidak ada unggahan pada periode itu. Tidak ada data
sintetis atau pengulangan baris untuk memenuhi target jumlah.

Batas Airflow sekarang 200 unggahan per program setiap run. Hari dan jam tetap
Senin MBG, Selasa CKG, Rabu Kopdes, Kamis Sekolah Rakyat, pukul 23.59 WIB.
Status aktif/paused mengikuti pengaturan yang sudah ada; pembaruan image tidak
mengaktifkan DAG yang sebelumnya paused. Docker dan internet perlu aktif.

## Preprocessing dan pelabelan

Preprocessing tetap versi 3: simpan teks asli, bersihkan URL/mention pada teks
model, dan pertahankan negasi, emoji, tanda baca, kapitalisasi serta ejaan
informal. Kata seperti `tidak`, `nggak`, atau `bukan` tidak dihapus/stemming.

Usulan awal dibuat lokal dengan model
[taufiqdp/indonesian-sentiment](https://huggingface.co/taufiqdp/indonesian-sentiment)
pada revisi tetap `7b102f732bbce270807db57cde99c8c202bb2ad7`.
Bobot SafeTensors dimuat lokal tanpa menjalankan kode model pihak ketiga;
teks unggahan tidak dikirim ke layanan pelabelan eksternal. Skor model tidak
terkalibrasi, dan model tersebut bukan penilai khusus empat program pemerintah.

Usulan otomatis tidak diberi izin training. Pemeriksaan konteks AI menilai
413 kandidat baru sesuai pedoman proyek: pisahkan sikap terhadap program dari
emosi umum, julukan dalam fandom/gim, pertanyaan, serta berita/kutipan. Contoh
berisi kritik tidak diterima sebagai positif hanya karena skor model tinggi.
Keputusan dikunci ke checksum teks dan disimpan bersama alasan serta metode.

Semua 396 label tetap **AI provisional**, termasuk 72 contoh lama. Tidak ada
review manusia atau agreement antarmanusia yang diklaim. Flag
`human_reviewed` dan `approved_for_training` tetap False. Pemeriksaan ini tidak
menjamin semua label benar dan belum menggantikan anotasi manusia independen.

## Pembagian dan fitur model

Pembagian menyatukan ID post, conversation ID, teks identik, kelompok kemiripan,
dan kelompok kasus/kampanye yang ditandai saat review. Misalnya variasi cerita
Arlan di Sekolah Rakyat disatukan untuk mengurangi salinan cerita yang tersebar
ke train/test. Kelompok kampanye merupakan petunjuk AI yang juga perlu audit;
deteksi semua duplikat semantik belum dijamin.

Snapshot baru memakai 316 development dan 80 test, tanpa overlap kelompok.
Development dipakai untuk CV tiga fold. Vocabulary TF-IDF hanya dipelajari dari
partisi latihan. Teks dengan label berbeda antartarget memerlukan model yang
mengondisikan prediksi pada target dan ditahan dari model teks ini.

Representasi baru menggabungkan TF-IDF kata 1-2 gram (termasuk emoji/tanda baca)
dan karakter 3-5 gram untuk variasi ejaan. Fitur one-hot program tidak dipakai
agar model tidak hanya mengandalkan distribusi kelas per program. Tiga nilai
C ialah 0,5; 2; dan 10, dengan class weight balanced, max_iter 2.000, seed 42.
Model dipilih melalui rerata CV Macro-F1, lalu hanya pemenang diuji pada holdout.

## Menjalankan kembali

Dari root repo dengan remote Drive yang sudah dikonfigurasi:

```bash
uv sync --locked --extra dev --extra data-versioning --extra google-drive --extra training
uv run --locked --no-sync dvc pull --remote gdrive data/raw/expanded_20261019.csv.dvc data/training/sentiment_expanded_20261019.csv.dvc
uv run --locked --no-sync python train.py run --dataset data/training/sentiment_expanded_20261019.csv --config configs/training/expanded.json --output reports/training/expanded-rerun --allow-provisional
```

Gunakan direktori laporan baru setiap eksekusi. Skrip menolak menimpa laporan
sebelumnya. `--allow-provisional` membuka eksperimen AI dan tidak mengubah
persetujuan manusia. Lihat [panduan MLflow](mlflow.md) untuk membuka port 5000.

Untuk menyiapkan snapshot dari berkas review privat yang tersedia lokal:

```bash
uv run --locked --no-sync python train.py prepare --labels data/labeled/batch=expansion-20261019-reviewed/reviewed.csv --raw data/raw/expanded_20261019.csv --raw-revision raw-expanded-20261019-v1 --output data/training/sentiment_expanded_20261019.csv --allow-provisional
```

Usulan dan review berada pada `src/kuping_negara/labeling/`. Extra `annotation`
(Torch CPU dan Transformers) hanya diperlukan untuk usulan model lokal, bukan
untuk mengambil snapshot DVC atau melatih model TF-IDF. Cache model berada di
`models/` dan cache dependensi di `.cache/`, keduanya diabaikan Git. Menjalankan
modul usulan saja tidak membuat labelnya boleh dipakai untuk training.

## Hasil dan batas kesimpulan

Pemenang `word-char-c10`: CV Macro-F1 **0,7901**, test Macro-F1 **0,7476**,
accuracy **0,7375**. Test berisi 32 negatif, 30 netral, dan 18 positif; model
mengenali 25, 18, dan 16 contoh pada kelas masing-masing. Dummy mayoritas
mencapai accuracy 0,4000 dan Macro-F1 0,1905.

Eksperimen awal 91 baris mempunyai test berbeda. Jangan menyebut perubahan
skor sebagai perbaikan pada benchmark yang sama. Skor mengukur kesesuaian
terhadap label AI, belum penilaian manusia. Kelas positif bertambah, tetapi
berita dan kampanye promosi juga memengaruhi distribusi data.

CKG masih sangat terbatas: 22 contoh dengan hanya satu negatif; test CKG hanya
2 contoh. Test Kopdes tidak mengandung positif. Penilaian per-program belum
merata. Split ini juga belum menguji generalisasi ke waktu mendatang.

Model tercatat sebagai `kuping-negara-sentiment-expanded-pilot` versi 1, alias
`experimental`, `deployment_approved=false`. Dataset baru sudah disimpan di
remote lokal dan Drive, lalu dipulihkan dengan cache kosong dan SHA-256 identik.
Git hanya menyimpan penunjuk DVC, manifest, kode serta laporan agregat.

## Bukti yang tersedia

- [Metrik raw dan sumbernya](../reports/data/expansion_20261019.json).
- [Audit pengambilan](../reports/data/collection_20261019.json).
- [Ringkasan anotasi](../reports/annotation/expansion_20261019.json).
- [Manifest training](../data/training/sentiment_expanded_20261019.manifest.json).
- [Tiga run dan rincian split](../reports/training/expanded_20261019/experiment_summary.json).
- [Parameter terbaik dan keterbatasan](../reports/training/expanded_20261019/model_metadata.md).
- [Bukti pemulihan Drive](../reports/training/expanded_20261019/storage_verification.json).
