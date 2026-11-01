# Model Registry dan kesiapan inferensi

LK-7 melanjutkan eksperimen LK-6 tanpa mengulang pengumpulan atau pelabelan data.
Registry `kuping-negara-sentiment-lk07-simulation` dipisahkan dari registry pilot
agar latihan perpindahan stage tidak mengubah model penelitian sebelumnya.
Status Production di sini adalah simulasi tugas. Label masih hasil AI dan
`deployment_approved=false`; model belum disetujui untuk layanan publik.

## Alur kode

- `src/kuping_negara/training/registry.py`: registrasi, seleksi, transisi stage,
  penerbitan referensi, serta verifikasi inferensi.
- `src/kuping_negara/training/evaluation.py`: pipeline TF-IDF dan Logistic
  Regression, pembagian grup dan cross-validation yang sama dengan LK-6.
- `registry/active_model.yaml.dvc`: penunjuk DVC metadata model aktif.
- `reports/registry/lk07/workflow.json`: versi, skor CV, lineage dan urutan stage.
- `reports/registry/lk07/inference.json`: bukti pemanggilan model Production.
- `img/lk07/`: tangkapan layar MLflow yang diambil saat pengerjaan.

## Menjalankan di Docker

```powershell
docker compose --profile training build mlflow
docker compose --profile training up -d --no-deps --wait mlflow
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry register
```

Perintah `register` mendaftarkan artefak C=10 dari LK-6 sebagai versi 1.
Versi 2 memakai C=5, dilatih pada 316 baris development dan dinilai dengan
3-fold cross-validation berbasis grup. Delapan puluh baris test sebelumnya
tidak dipakai lagi untuk pemilihan. Versi dengan CV Macro-F1 tertinggi dipindah
ke Staging. Registrasi menolak nama yang sudah memiliki versi agar riwayat
lama tidak tertimpa; perintah ini bukan perintah yang perlu diulang tiap startup.

Ambil bukti Staging terlebih dahulu, kemudian:

```powershell
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry promote
docker compose --profile training run --rm --no-deps --entrypoint python trainer -m kuping_negara.training.registry infer
```

`promote` menguji model Staging sebelum memindahkannya ke Production dan
memasang alias `champion`. Metadata menyimpan versi numerik, run ID, checksum
artefak, checksum dataset, revisi raw DVC dan commit kode. `infer` memastikan
versi Production sesuai metadata dan checksum artefaknya cocok, lalu memanggil
`mlflow.pyfunc.load_model` menggunakan URI Production. Contoh masukan bersifat
sintetis, bukan bukti akurasi atau pengganti evaluasi test.

MLflow masih mendukung stage yang diminta tugas walaupun API tersebut sudah
deprecated. Alias `champion` juga disimpan sebagai rujukan untuk migrasi.

## Pelacakan metadata dengan DVC

```powershell
dvc add registry/active_model.yaml
dvc push -r localstore registry/active_model.yaml.dvc
dvc status registry/active_model.yaml.dvc
```

Git menyimpan penunjuk `.dvc`; isi YAML disimpan melalui cache dan remote DVC.
Di komputer lain, atur remote yang dapat diakses lalu jalankan `dvc pull`.
Remote `localstore` pada pengerjaan ini berada di disk D:, bukan Google Drive.
YAML saja tidak memindahkan artefak model: volume MLflow `mlflow-data` juga
harus dicadangkan agar model tetap dapat dimuat. DVC menyimpan referensi dan
lineage, sedangkan MLflow menyimpan artefak dan riwayat versi model.

## Model aktif

Hasil aktual tercatat di metadata dan laporan workflow; alasan pemilihan adalah
CV Macro-F1 tertinggi pada development, bukan nomor versi paling baru.
Lihat ringkasan hasil di bagian berikut setelah workflow selesai.

| Versi | Parameter C | CV Macro-F1 | Status akhir |
| --- | --- | --- | --- |
| 1 | 10 | 0,7901 | Production; alias champion |
| 2 | 5 | 0,7830 | None; disimpan sebagai alternatif |

Versi 1 aktif karena skor development lebih tinggi. Versi 2 tetap disimpan
agar perubahan parameter dan riwayat model dapat ditelusuri. Uji Docker
mengonfirmasi pemuatan URI Production dan checksum artefak sesuai metadata.
Prediksi sintetis: positif, netral, negatif untuk tiga contoh pada laporan.
Dua prediksi terakhir tidak sesuai interpretasi umum kalimat; keberhasilan
pemanggilan model tidak sama dengan kelayakan kualitas prediksi. Review label
manusia serta evaluasi baru diperlukan sebelum deployment sebenarnya.
