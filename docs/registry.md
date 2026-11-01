# Pengelolaan Versi Model dan Inferensi dengan MLflow

Proyek **Kuping Negara** menggunakan MLflow Model Registry untuk mencatat
riwayat model analisis sentimen dan menentukan versi yang digunakan saat
inferensi. Setiap versi menyimpan sumber eksperimen, parameter, hasil evaluasi,
dan referensi dataset. Metadata model aktif dilacak dengan DVC, sedangkan
artefak dan database model disimpan pada volume MLflow.

Alur pengelolaan model:

```text
Artefak eksperimen terpilih
        ↓
Registrasi model → pencatatan versi baru
        ↓
Perbandingan CV Macro-F1 pada data development
        ↓
None → Staging → uji pemanggilan → Production
        ↓
Alias champion + metadata model aktif yang dilacak DVC
        ↓
Pemeriksaan versi, checksum, dan inferensi melalui Docker
```

## Model yang aktif

| Informasi | Nilai |
| --- | --- |
| Nama Registry | `kuping-negara-sentiment-lk07-simulation` |
| Versi aktif | **1** |
| Stage | **Production** |
| Alias | `champion` |
| Algoritma | Logistic Regression, `class_weight=balanced` |
| Representasi teks | TF-IDF kata 1-2 gram dan karakter 3-5 gram |
| Parameter terpilih | `C=10`, `max_iter=2000`, `random_seed=42` |
| Sumber eksperimen | `b24847e7c86040acbeada6bc373861d2` (`word-char-c10`) |
| URI inferensi | `models:/kuping-negara-sentiment-lk07-simulation/Production` |
| URI versi tetap | `models:/kuping-negara-sentiment-lk07-simulation/1` |
| Status label | Hasil AI, belum divalidasi manusia |
| Persetujuan deployment | `false`; Production hanya simulasi pengelolaan model |

Versi 1 dipilih berdasarkan **CV Macro-F1 tertinggi pada data development**.
Versi terbaru tidak otomatis menjadi versi aktif.

| Versi | Parameter C | CV Macro-F1 | Status akhir | Alasan |
| --- | --- | --- | --- | --- |
| 1 | 10 | 0,790114 | Production / champion | Skor CV lebih tinggi |
| 2 | 5 | 0,783011 | None | Disimpan sebagai riwayat perubahan parameter |

## Dataset dan pemilihan model

Dataset training berisi **396 contoh**: 316 development dan 80 test. Versi 2
menggunakan pembagian grup dan 3-fold cross-validation yang sama dengan
eksperimen sebelumnya. Delapan puluh contoh test tidak digunakan ulang untuk
memilih versi model aktif.

- Dataset: `data/training/sentiment_expanded_20261019.csv`.
- Tag training DVC/Git: `sentiment-data-expanded-20261019-v1`.
- Tag raw: `raw-expanded-20261019-v1`.
- SHA-256 training: `29d088b126a6462a3ac48af22f08b5608a0ef0bd9626b065bddfc1525a8f369f`.

Detail versi dan lineage tersedia pada [workflow.json](../reports/registry/lk07/workflow.json).

## Membuka dashboard dan menguji model yang sudah tersedia

Jalankan perintah dari folder utama repositori dengan Docker Desktop aktif.
Model dan database MLflow hasil eksperimen harus masih tersedia di volume
`mlflow-data`. Build image saja tidak memulihkan model ke database kosong.

```powershell
docker compose --profile training build mlflow
docker compose --profile training up -d --no-deps --wait mlflow
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry infer
```

- Dashboard: [http://localhost:5000](http://localhost:5000).
- Model: [Model Registry](http://localhost:5000/#/models/kuping-negara-sentiment-lk07-simulation).
- Modul implementasi: [registry.py](../src/kuping_negara/training/registry.py).

`infer` memastikan versi Production cocok dengan metadata dan checksum artefak,
lalu memanggil `mlflow.pyfunc.load_model`. Model dimuat sekali untuk menguji
prediksi berulang. Input menggunakan kolom `model_text` dan `target_program`;
keluaran berupa `negative`, `neutral`, atau `positive`. Input kosong, kolom yang
hilang, dan nilai teks yang tidak valid ditolak sebelum prediksi.

Hasil pengukuran disimpan ke `reports/registry/lk07/inference_benchmark.json`.
Menjalankan ulang `infer` memperbarui berkas pengukuran tersebut dan bisa
menghasilkan waktu respons yang berbeda.

## Registrasi versi dan transisi stage

Alur registrasi dan pemilihan versi:

1. Mendaftarkan artefak eksperimen C=10 sebagai versi 1.
2. Melatih variasi C=5 dan mendaftarkannya sebagai versi 2.
3. Membandingkan CV Macro-F1 dan memindahkan versi 1 dari None ke Staging.
4. Menguji pemanggilan model Staging sebelum memindahkannya ke Production.
5. Memasang alias `champion`, menerbitkan metadata, dan menguji inferensi.
6. Melengkapi deskripsi model dan setiap versi beserta tag parameter dan lineage.

Perintah untuk urutan awal tersebut adalah:

```powershell
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry register
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry promote
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry annotate
```

**Jangan menjalankan `register` dan `promote` ulang pada kondisi sekarang.**
`register` hanya untuk Registry baru dengan artefak eksperimen dan dataset yang sudah
tersedia; perintah ini menolak riwayat yang telah ada. `promote` memerlukan
model terpilih berada di Staging. Keduanya bukan perintah startup harian.
`annotate` dapat digunakan untuk memperbarui deskripsi dan tag tanpa membuat versi baru.

MLflow yang digunakan masih mendukung stage None, Staging, dan Production,
walaupun API stage sudah deprecated. Alias `champion` juga dicatat untuk rujukan model aktif.

## Metadata model dan DVC

[active_model.yaml.dvc](../registry/active_model.yaml.dvc) melacak isi
`registry/active_model.yaml`. YAML menyimpan nama dan versi model, stage, alias,
run ID, checksum artefak dan dataset, revisi raw DVC, serta commit kode lifecycle.

```powershell
dvc add registry/active_model.yaml
dvc push -r localstore registry/active_model.yaml.dvc
dvc status registry/active_model.yaml.dvc
```

Metadata pada pengerjaan ini dicadangkan ke remote **lokal**
`D:/MLOPS/dvc-storage/kuping-negara`, bukan ke Google Drive. Perintah DVC di atas
dijalankan pada lingkungan host yang sudah memasang DVC. Training dan inferensi
tetap berjalan di container.

Untuk memulihkan YAML, konfigurasi remote yang dapat diakses terlebih dahulu,
lalu jalankan `dvc pull -r localstore registry/active_model.yaml.dvc`.
Git menyimpan penunjuk `.dvc`; isi YAML disimpan di cache/remote DVC.
**Metadata DVC tidak mencadangkan artefak model.** Database dan artefak pada
volume MLflow juga harus dipulihkan agar inferensi berjalan di komputer lain.

## Bukti hasil pengujian

| Berkas | Isi |
| --- | --- |
| [workflow.json](../reports/registry/lk07/workflow.json) | Dua versi, skor CV, lineage, dan urutan transisi awal |
| [metadata_audit.json](../reports/registry/lk07/metadata_audit.json) | Deskripsi dan tag yang dibaca kembali dari Registry |
| [inference.json](../reports/registry/lk07/inference.json) | Hasil inferensi awal dari Production |
| [inference_benchmark.json](../reports/registry/lk07/inference_benchmark.json) | Waktu muat, prediksi berulang, dan validasi input |
| [screenshot_recapture.json](../reports/registry/lk07/screenshot_recapture.json) | Catatan pengambilan ulang screenshot Staging dan verifikasi setelah Production dipulihkan |

Pengukuran pada `inference_benchmark.json` mencatat waktu memuat model sekitar
**5,18 detik**. Setelah dimuat, median prediksi **satu batch berisi tiga teks**
adalah **5,60 ms**, dengan p95 **6,40 ms**, dari 30 pengulangan. Empat kasus
input tidak valid berhasil ditolak. Angka tersebut berasal dari container
lokal dan tidak menyatakan jaminan waktu respons layanan dengan banyak pengguna.

## Bukti dan tangkapan layar

| Bukti | Gambar |
| --- | --- |
| Deskripsi Registry, daftar versi, dan Production | [01-registry-production.jpg](../img/lk07/dark/01-registry-production.jpg) |
| Metadata versi 1 | [02-versi1-metadata.jpg](../img/lk07/dark/02-versi1-metadata.jpg) |
| Metadata versi 2 | [03-versi2-metadata.jpg](../img/lk07/dark/03-versi2-metadata.jpg) |
| Model pada Staging | [04-staging.jpg](../img/lk07/dark/04-staging.jpg) |
| Penunjuk DVC di GitHub | [09-penunjuk-dvc.jpg](../img/lk07/09-penunjuk-dvc.jpg) |
| JSON hasil inferensi di GitHub | [08-hasil-inferensi-json.jpg](../img/lk07/08-hasil-inferensi-json.jpg) |

Screenshot Staging mode gelap diambil ulang melalui transisi nyata model
simulasi dari Production ke Staging, kemudian dikembalikan ke Production.
Status akhir dan inferensinya diperiksa kembali; catatannya tersedia pada
`screenshot_recapture.json`. Screenshot DVC dan inferensi menampilkan berkas
hasil tersimpan di GitHub, bukan keluaran terminal.

## Batasan penggunaan

Label masih berasal dari AI dan belum divalidasi manusia. Beberapa prediksi
contoh masih kurang sesuai dengan makna kalimatnya. Keberhasilan pemuatan
model membuktikan jalur inferensi berjalan, bukan bahwa kualitas prediksi
sudah layak produksi. Review label dan evaluasi lanjutan diperlukan sebelum
penggunaan sebenarnya; `simulation_only=true` dan `deployment_approved=false`
tetap berlaku.
