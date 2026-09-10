# Panduan Anotasi Sentimen

Dokumen ini adalah versi awal pedoman anotasi manual untuk proyek Kuping Negara.
Pedoman wajib diberi versi setiap kali definisi atau contoh keputusan berubah.

## Ruang lingkup

Anotasi menilai sentimen sebuah unggahan terhadap program yang sedang menjadi
target pengumpulan: Makan Bergizi Gratis (MBG), Cek Kesehatan Gratis (CKG),
Koperasi Desa Merah Putih, atau Sekolah Rakyat. Label bukan penilaian terhadap
penulis unggahan dan bukan kesimpulan mengenai seluruh masyarakat Indonesia.

## Definisi label

| Label | Definisi operasional |
| --- | --- |
| `positive` | Unggahan mendukung, memuji, menyatakan manfaat, atau menunjukkan pengalaman positif terhadap program target. |
| `neutral` | Unggahan menyampaikan fakta, pertanyaan, pengumuman, atau informasi tanpa evaluasi dominan yang jelas. |
| `negative` | Unggahan mengkritik, menolak, mengeluhkan dampak, atau menunjukkan pengalaman negatif terhadap program target. |
| `uncertain` | Konteks tidak cukup, target sentimen ambigu, sarkasme tidak dapat dipastikan, atau annotator tidak dapat memilih salah satu dari tiga kelas utama secara andal. |

## Aturan keputusan

1. Nilai sentimen terhadap `target_program`, bukan emosi umum unggahan.
2. Gunakan konteks percakapan hanya jika konteks tersebut tersedia pada dataset.
3. Jika terdapat sentimen campuran, pilih sentimen yang paling dominan terhadap
   program; gunakan `uncertain` bila kekuatannya seimbang.
4. Berita atau kutipan yang hanya melaporkan pernyataan diberi `neutral`, kecuali
   penulis menambahkan sikapnya sendiri secara jelas.
5. Sarkasme diberi label sesuai maksud yang cukup meyakinkan; jika tidak,
   gunakan `uncertain`.
6. Unggahan yang tidak relevan dengan program target ditandai untuk pemeriksaan
   kualitas dan tidak dipaksakan menjadi kelas sentimen.
7. Jangan menyalin nama akun, nomor telepon, alamat, atau identitas personal ke
   catatan anotasi.

## Proses kualitas label

- Sampel awal dianotasi oleh minimal dua annotator.
- Perbedaan diselesaikan melalui adjudikasi dan dicatat sebagai contoh batas.
- Agreement dilaporkan sebelum dataset dijadikan versi pelatihan.
- Label `uncertain` tidak dipakai sebagai target pelatihan tiga kelas, tetapi
  disimpan untuk audit dan perbaikan pedoman.
- Setiap baris label menyimpan versi pedoman, waktu anotasi, dan identitas
  annotator dalam bentuk pseudonim internal.

## Versi

- Versi pedoman: `0.1.0`
- Status: draft awal
- Tanggal: 2026-09-10
