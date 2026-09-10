# Kontrak data

`tweet_record.schema.json` adalah kontrak awal untuk rekaman data Kuping Negara.
Kontrak ini mencakup identitas data, program sasaran, teks, waktu, engagement,
label/prediksi sentimen, probabilitas, serta versi pipeline.

Aturan perubahan:

- perubahan kompatibel ke belakang menaikkan versi minor;
- perubahan yang menghapus atau mengubah arti field menaikkan versi mayor;
- raw zone tetap append-only dan tidak boleh ditimpa;
- validasi kontrak dilakukan sebelum data berpindah ke processed zone;
- field identitas personal harus diminimalkan atau dianonimkan.
