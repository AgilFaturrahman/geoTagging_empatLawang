# Peta Geotagging — Kabupaten Empat Lawang

Web app peta sederhana untuk menampilkan hasil geotagging di atas basemap satelit,
dengan sidebar filter berjenjang: **Kecamatan → Desa → SLS → Sub-SLS**.

## Isi folder

```
index.html          <- halaman utama (buka file ini)
data/
  sls.geojson        <- batas wilayah SLS (dari QGIS, sudah dipangkas kolomnya)
  points.json         <- titik hasil geotagging (dipadatkan dari CSV, 70.513 titik)
vendor/
  leaflet/            <- library peta Leaflet (di-bundle lokal, tidak perlu internet ke CDN)
  markercluster/       <- plugin pengelompokan titik (Leaflet.markercluster)
etl.py               <- script Python untuk membangun ulang data/ dari file sumber
daftar_petugas.csv   <- daftar nama PML/PPL per wilayah (dipakai etl.py, lihat bagian di bawah)
```

## Cara menjalankan / hosting

File ini adalah **static site murni** (HTML + JS + JSON), tidak butuh backend/server khusus.

1. **Paling gampang — hosting gratis:**
   Upload seluruh folder ini ke GitHub Pages, Netlify, Vercel, atau Cloudflare Pages.
   Setelah online, tinggal bagikan link-nya ke siapa saja yang perlu lihat hasil geotagging.

2. **Coba lokal dulu di komputer sendiri:**
   Membuka `index.html` langsung dengan cara double-click **tidak akan memuat data**
   (browser modern memblokir `fetch()` ke file lokal karena alasan keamanan/CORS).
   Jalankan local server sederhana dulu dari folder ini, misalnya:
   ```
   python -m http.server 8000
   ```
   lalu buka `http://localhost:8000` di browser.

## Fitur

- Basemap **Google Satellite** (default), plus pilihan Hybrid (satelit+label jalan) dan peta jalan OSM biasa — bisa ganti lewat ikon layer di pojok kanan atas peta.
- Filter wilayah berjenjang di sidebar kiri: pilih Kecamatan → pilihan Desa otomatis menyesuaikan → lalu SLS → lalu Sub-SLS. Peta otomatis zoom ke area terpilih.
- Toggle tampilkan/sembunyikan titik **Keluarga** vs **Usaha** (beda warna: biru = Keluarga, oranye = Usaha).
- Toggle tampil/sembunyikan batas polygon SLS.
- Klik titik → detail (nama, status keberadaan, jumlah anggota/usaha, penggunaan bangunan, link buka di FASIH).
- Klik polygon SLS → info wilayah (kecamatan/desa/SLS/sub-SLS, nama gedung, luas, nama PML & PPL yang bertugas di wilayah itu).
- Ringkasan jumlah titik yang sedang ditampilkan vs total.
- Toggle tampilkan/sembunyikan titik **Bangunan Kosong** (abu-abu) — dideteksi otomatis dari titik ber-jenis Usaha yang nama usahanya mengandung kata "kosong" (mis. "BANGUNAN KOSONG", "RUMAH KOSONG"), terpisah dari Usaha yang beneran ada isinya.
- Info "Data kondisi per" dan "Terakhir diproses" di sidebar kiri bawah.

## Info "Data kondisi per" & "Terakhir diproses"

CSV geotagging sumber tidak punya kolom tanggal per baris, jadi dua info ini dihitung otomatis oleh `etl.py`:
- **Data kondisi per** — diambil dari tanggal-jam terakhir file CSV itu sendiri diubah (file modified time), sebagai perkiraan kapan data ini di-export dari FASIH. Ini otomatis ikut berubah setiap kali Anda menjalankan `etl.py` dengan file CSV baru yang berbeda tanggalnya.
- **Terakhir diproses** — tanggal-jam saat `etl.py` terakhir dijalankan (kapan `data/points.json` ini dibuat).

Kalau Anda tahu persis kapan data ini ditarik dari FASIH (misalnya dari catatan tim lapangan) dan itu beda dari tanggal file CSV-nya, buka `etl.py`, cari baris:
```python
DATA_AS_OF_OVERRIDE = None
```
lalu isi manual, contoh:
```python
DATA_AS_OF_OVERRIDE = "20 Agustus 2026 14:00 WIB"
```
Nilai ini akan dipakai apa adanya dan mengabaikan tanggal file CSV.

## Info Nama PML & PPL

Popup saat klik polygon SLS menampilkan nama **PML** (Pengawas/pemeriksa Lapangan) dan **PPL**
(Petugas Pendataan Lapangan) yang ditugaskan di wilayah itu. Data ini diambil dari file
`daftar_petugas.csv` yang dibaca oleh `etl.py` lewat variabel `PETUGAS_IN` di bagian atas script.

Kalau kantor memberi daftar petugas dalam format Excel (`.xlsx`):
1. Buka file-nya di Excel.
2. **File → Save As** → pilih format **CSV UTF-8 (Comma delimited) (*.csv)**.
3. Taruh file CSV hasilnya di folder yang sama dengan `etl.py`, beri nama `daftar_petugas.csv`
   (atau ganti nama filenya di variabel `PETUGAS_IN`).

Kolom yang wajib ada di CSV ini (nama kolom harus persis sama):
- `KODE WILAYAH` — kode 16 digit yang sama persis dengan `KODE SUB-SLS` di CSV geotagging.
- `Nama PML`
- `Nama PPL`

Kalau belum ada datanya, boleh dikosongkan dengan mengubah baris berikut di `etl.py` jadi:
```python
PETUGAS_IN = None
```
Popup SLS akan tetap muncul seperti biasa, hanya baris Nama PML/Nama PPL-nya jadi "-".

Kalau ada wilayah SLS yang kodenya tidak ditemukan di `daftar_petugas.csv` (misalnya wilayah
non-pemukiman seperti hutan/perkebunan yang memang tidak ada petugasnya), `etl.py` akan
mencetak catatan berapa banyak wilayah yang tidak cocok, dan baris Nama PML/PPL-nya otomatis
tampil "-" tanpa error.

## Catatan penting

- **Tile Google Satellite yang dipakai di sini bukan lewat Google Maps API resmi** (tidak pakai API key, cara umum yang dipakai banyak proyek open-source). Cocok untuk pemakaian internal/terbatas. Untuk pemakaian publik skala besar/jangka panjang sebaiknya pertimbangkan ganti ke Esri World Imagery (gratis & resmi) atau Google Maps Platform resmi (berbayar, perlu API key).


## Update data di kemudian hari

Kalau ada file GeoJSON SLS, geotagging, atau daftar petugas yang baru:
1. Taruh file sumber baru, sesuaikan path di bagian atas `etl.py`.
2. Jalankan `python3 etl.py` — ini akan menulis ulang `data/sls.geojson` dan `data/points.json`.
3. Upload ulang (atau `git push` kalau pakai GitHub Pages) — situs otomatis pakai data terbaru.
