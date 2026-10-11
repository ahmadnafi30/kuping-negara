# Rancangan kontrak data

`tweet_record.schema.json` adalah rancangan kontrak rekaman Kuping Negara,
mencakup identitas, program, teks, waktu, engagement, label, prediksi, dan lineage.
Field prediksi merupakan rencana untuk fase modeling/serving.

Pipeline saat ini memvalidasi kolom sumber, timestamp, teks, dan engagement
melalui kode preprocessing. JSON Schema ini belum digunakan sebagai validator
runtime; integrasinya tercatat dalam [roadmap](../../docs/roadmap.md).
Field kualitas tambahan di output dijelaskan dalam
[panduan preprocessing](../../docs/x-data-preprocessing.md).

Aturan perubahan:

- perubahan kontrak harus menaikkan versi dan menyertakan catatan migrasi;
- raw zone tetap immutable; perbaikan menghasilkan versi baru;
- personal identifier diminimalkan sebelum pemakaian downstream;
- `raw_text` dan permalink masih dapat mengandung informasi personal.
