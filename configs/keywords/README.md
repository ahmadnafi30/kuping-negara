# Konfigurasi keyword

`programs.example.yaml` digunakan bersama oleh kolektor dan preprocessing.
Salin dan sesuaikan keyword, lalu arahkan kedua CLI ke file yang sama melalui
`--config`.

```yaml
schema_version: 1
programs:
  mbg:
    display_name: Makan Bergizi Gratis
    collection_day: monday
    keywords:
      - mbg
      - makan bergizi gratis
```

- `schema_version` wajib bernilai integer `1`.
- ID program memakai lower-case snake_case, dimulai huruf, tanpa pemisah path.
- `display_name` wajib berupa string tidak kosong.
- `keywords` wajib berupa daftar string tidak kosong; spasi tepi dibersihkan.
- `collection_day` opsional: `monday` sampai `sunday`. Scheduler menggunakan cron
  di `dags/x_collection.py`; jaga metadata ini konsisten dengan hari pada DAG.
- Urutan program dan keyword dipertahankan: kolektor mengikuti urutan program,
  sedangkan preprocessing merekam keyword pertama yang cocok.

Konfigurasi tidak berisi kredensial. Perubahan keyword dapat mengubah relevansi
dan hasil quality report; commit perubahan bersama penjelasan di Pull Request.
