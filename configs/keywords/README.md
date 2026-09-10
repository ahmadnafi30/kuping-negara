# Konfigurasi kata kunci

Direktori ini menyimpan kata kunci pengambilan data per program. Berkas
`programs.example.yaml` adalah contoh awal, bukan daftar final untuk produksi.

Setiap perubahan kata kunci harus:

1. ditinjau agar tidak terlalu luas atau bias;
2. diberi `schema_version` atau versi konfigurasi yang baru;
3. dicatat pada commit dan pull request;
4. diuji pada sampel data sebelum dipakai oleh pipeline terjadwal.

