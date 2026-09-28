# Sampel sumber untuk LK-04

Folder ini berisi **20 baris dari hasil ingestion X yang benar-benar dilakukan
pada 21 September 2026**: lima baris pertama untuk masing-masing MBG, CKG,
Kopdes Merah Putih, dan Sekolah Rakyat. Dataset lokal asal berisi 60 baris per
program. Sampel ini bukan data sintetis dan bukan hasil pengambilan terbaru.

Untuk publikasi tugas, profil akun dihilangkan, ID posting/percakapan diganti
dengan ID sampel, permalink dikosongkan, dan mention, URL, email, serta nomor
panjang dalam teks disamarkan. Tanggal publikasi, bahasa, dan engagement tetap
berasal dari sumber. CSV mempertahankan kolom yang dibutuhkan adapter
preprocessing, tetapi merupakan **subset sumber yang telah dianonimkan**, bukan
salinan mentah utuh. Provenance, checksum, jumlah baris, dan transformasi tercatat
di `provenance.json`. Dataset mentah lengkap tetap berada di `data/raw/x/`
secara lokal dan tidak masuk Git.

Jalankan dari root repo setelah `uv sync --frozen --extra dev`:

```bash
uv run --frozen python src/preprocess.py --input-dir data/raw/samples/x --skip-existing
uv run --frozen python src/ingest_data.py --replay-dir data/raw/samples/x --preprocess --cycles 2 --interval-seconds 1
```

Perintah kedua adalah simulasi periodik **offline**. Ia menyalin sampel ke dua
run baru dan menjalankan preprocessing; ia tidak mengambil posting baru dari X.
Semua hasil run disimpan secara lokal dan tidak menimpa sampel ini.
