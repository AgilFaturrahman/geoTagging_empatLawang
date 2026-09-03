import json, csv, os, datetime

# ============================================================================
# HANYA DUA BARIS INI YANG PERLU DIUBAH kalau ada file GeoJSON/CSV baru.
# Paling gampang: taruh file barunya di folder yang sama dengan etl.py ini,
# lalu ganti nama filenya di bawah. Boleh juga isi path lengkap kalau filenya
# ada di lokasi lain, misalnya "C:/Users/Nama/Downloads/geotagging_baru.csv".
# ============================================================================
GEOJSON_IN = "data\peta_sls_202511611.geojson"
CSV_IN = "data\geotagging_all_3september.csv"

# Daftar nama petugas (PML/PPL) per wilayah. Ini file CSV (bukan .xlsx) --
# kalau file dari kantor masih .xlsx, buka di Excel lalu "Save As" > CSV UTF-8
# dulu. Kolom yang wajib ada: "KODE WILAYAH" (16 digit, sama seperti KODE
# SUB-SLS), "Nama PML", "Nama PPL". Boleh dikosongkan (PETUGAS_IN = None) kalau
# belum ada datanya -- popup SLS tetap jalan, cuma baris PML/PPL-nya kosong.
PETUGAS_IN = "data\DAFTAR WILAYAH & NAMA PETUGAS.csv"

# --- Di bawah ini TIDAK PERLU diubah ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.isabs(GEOJSON_IN):
    GEOJSON_IN = os.path.join(SCRIPT_DIR, GEOJSON_IN)
if not os.path.isabs(CSV_IN):
    CSV_IN = os.path.join(SCRIPT_DIR, CSV_IN)
if PETUGAS_IN and not os.path.isabs(PETUGAS_IN):
    PETUGAS_IN = os.path.join(SCRIPT_DIR, PETUGAS_IN)

OUT_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- "Data per kapan?" ----------
# CSV sumber tidak punya kolom tanggal per baris, jadi sebagai gantinya kita
# pakai tanggal-jam terakhir file CSV itu diubah/di-export sebagai perkiraan
# "data kondisi kapan". Kalau Anda tahu persis kapan data ini ditarik dari
# FASIH (mis. dari nama file atau info dari tim lapangan), isi manual di
# DATA_AS_OF_OVERRIDE di bawah ini (format bebas, contoh: "20 Agustus 2026 14:00 WIB")
# -- itu akan dipakai apa adanya dan mengabaikan tanggal file.
DATA_AS_OF_OVERRIDE = None

BULAN_ID = ["Januari","Februari","Maret","April","Mei","Juni","Juli",
            "Agustus","September","Oktober","November","Desember"]
WIB = datetime.timezone(datetime.timedelta(hours=7))

def format_wib(ts):
    d = datetime.datetime.fromtimestamp(ts, WIB)
    return f"{d.day} {BULAN_ID[d.month-1]} {d.year} {d.hour:02d}:{d.minute:02d} WIB"

if DATA_AS_OF_OVERRIDE:
    data_as_of = DATA_AS_OF_OVERRIDE
else:
    data_as_of = format_wib(os.path.getmtime(CSV_IN))

generated_at = format_wib(datetime.datetime.now(WIB).timestamp())

print("data per (dari tanggal file CSV):", data_as_of)
print("data diproses pada:", generated_at)

# ---------- 1. Baca daftar petugas (PML/PPL), kalau ada ----------
petugas_by_id = {}
if PETUGAS_IN and os.path.isfile(PETUGAS_IN):
    with open(PETUGAS_IN, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kode = (row.get("KODE WILAYAH") or "").strip()
            if not kode:
                continue
            petugas_by_id[kode] = {
                "nm_pml": (row.get("Nama PML") or "").strip() or None,
                "nm_ppl": (row.get("Nama PPL") or "").strip() or None,
            }
    print("daftar petugas dimuat:", len(petugas_by_id), "wilayah")
elif PETUGAS_IN:
    print("PERINGATAN: file daftar petugas tidak ditemukan:", PETUGAS_IN)
    print("Baris Nama PML/PPL di popup SLS akan kosong ('-').")

# ---------- 2. Process SLS boundary geojson ----------
with open(GEOJSON_IN, encoding="utf-8") as f:
    gj = json.load(f)

trimmed_features = []
for feat in gj["features"]:
    p = feat["properties"]
    petugas = petugas_by_id.get(p.get("idsubsls"), {})
    new_p = {
        "idsls": p.get("idsls"),
        "idsubsls": p.get("idsubsls"),
        "kdkec": p.get("kdkec"),
        "nmkec": p.get("nmkec"),
        "kddesa": p.get("kddesa"),
        "nmdesa": p.get("nmdesa"),
        "kdsls": p.get("kdsls"),
        "nmsls": p.get("nmsls"),
        "kdsubsls": p.get("kdsubsls"),
        "subsls": p.get("subsls"),
        "nm_gedung": p.get("nm_gedung"),
        "nm_pml": petugas.get("nm_pml"),
        "nm_ppl": petugas.get("nm_ppl"),
        "luas": round(p["luas"], 1) if p.get("luas") is not None else None,
    }
    trimmed_features.append({
        "type": "Feature",
        "properties": new_p,
        "geometry": feat["geometry"],
    })

if petugas_by_id:
    n_no_petugas = sum(1 for f in trimmed_features if not f["properties"]["nm_pml"])
    if n_no_petugas:
        print(f"catatan: {n_no_petugas} wilayah SLS tidak ada di daftar petugas (Nama PML/PPL akan '-').")

out_gj = {"type": "FeatureCollection", "features": trimmed_features}
with open(os.path.join(OUT_DIR, "sls.geojson"), "w", encoding="utf-8") as f:
    json.dump(out_gj, f, ensure_ascii=False, separators=(",", ":"))

print("sls.geojson features:", len(trimmed_features))

valid_idsubsls = {f["properties"]["idsubsls"] for f in trimmed_features}

# ---------- 3. Process geotagging CSV into compact points.json ----------
jenis_legend = ["Keluarga", "Usaha"]

status_legend = ["-"]  # index 0 = blank
status_index = {"": 0}

bangunan_legend = ["-"]
bangunan_index = {"": 0}

def get_status_idx(val):
    val = (val or "").strip()
    if val not in status_index:
        status_index[val] = len(status_legend)
        status_legend.append(val)
    return status_index[val]

def get_bangunan_idx(val):
    val = (val or "").strip()
    if val not in bangunan_index:
        bangunan_index[val] = len(bangunan_legend)
        bangunan_legend.append(val)
    return bangunan_index[val]

ASSIGNMENT_BASE = "https://fasih-sm.bps.go.id/app/assignment/fd68e454-ba45-4b85-8205-f3bf777ded24/"

points = []
bad_code_examples = []
n = 0
n_bad_code = 0
with open(CSV_IN, encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)
    if reader.fieldnames and "NOMOR BANGUNAN" not in reader.fieldnames:
        print("catatan: kolom 'NOMOR BANGUNAN' tidak ada di CSV ini -- baris Nomor")
        print("bangunan di popup titik akan tampil '-' untuk semua titik.")
    for row in reader:
        n += 1

        kode_subsls = row["KODE SUB-SLS"].strip()
        if kode_subsls not in valid_idsubsls:
            n_bad_code += 1
            if len(bad_code_examples) < 5:
                bad_code_examples.append(kode_subsls)

        jenis = row["JENIS ASSIGNMENT"].strip()
        jenis_idx = 0 if jenis == "Keluarga" else 1

        if jenis_idx == 0:
            status_raw = row["STATUS KEBERADAAN KELUARGA"]
            nama = row["NAMA KELUARGA"].strip() or row["NAMA USAHA"].strip()
            jml = row["JUMLAH ANGGOTA KELUARGA YANG TINGGAL BERSAMA"].strip()
        else:
            status_raw = row["STATUS KEBERADAAN USAHA"]
            nama = row["NAMA USAHA"].strip() or row["NAMA KELUARGA"].strip()
            jml = row["JUMLAH USAHA DITEMUKAN"].strip()

        jml_int = int(jml) if jml.isdigit() else None

        try:
            lat = round(float(row["LATITUDE"]), 6)
            lon = round(float(row["LONGITUDE"]), 6)
        except ValueError:
            continue  # skip rows without valid coordinates

        nobangunan = (row.get("NOMOR BANGUNAN") or "").strip() or None

        rec = [
            row["KODE SUB-SLS"].strip(),      # 0 idsubsls (join key to boundary polygons)
            lat,                                # 1
            lon,                                # 2
            jenis_idx,                          # 3
            get_status_idx(status_raw),         # 4
            nama,                                # 5
            jml_int,                            # 6
            get_bangunan_idx(row["KODE PENGGUNAAN BANGUNAN"]),  # 7
            row["ID"].strip(),                  # 8 (record id -> link)
            nobangunan,                          # 9 nomor bangunan
        ]
        points.append(rec)

print("total csv rows:", n, "-> points exported:", len(points))

if n_bad_code:
    pct = n_bad_code / n * 100
    print()
    print("=" * 70)
    print(f"PERINGATAN: {n_bad_code} dari {n} baris ({pct:.1f}%) punya KODE SUB-SLS")
    print("yang TIDAK cocok dengan kode manapun di sls.geojson.")
    print("Contoh kode bermasalah:", bad_code_examples)
    print()
    print("Titik-titik ini TETAP muncul kalau 'Semua Kecamatan' dipilih,")
    print("tapi akan HILANG begitu difilter per Kecamatan/Desa/SLS/Sub-SLS,")
    print("karena kodenya tidak cocok untuk pencarian wilayah.")
    print()
    print("Penyebab paling umum: CSV ini sempat dibuka/disimpan lewat Excel,")
    print("sehingga kolom KODE SLS / KODE SUB-SLS (harusnya teks panjang)")
    print("berubah jadi notasi ilmiah (mis. 1.61107E+15) dan sebagian digit")
    print("terakhirnya hilang/berubah. Solusi: export ulang CSV dari sumber")
    print("aslinya tanpa dibuka lewat Excel, lalu jalankan etl.py ini lagi.")
    print("=" * 70)
    print()

out = {
    "assignmentBase": ASSIGNMENT_BASE,
    "dataAsOf": data_as_of,
    "generatedAt": generated_at,
    "jenisLegend": jenis_legend,
    "statusLegend": status_legend,
    "bangunanLegend": bangunan_legend,
    "fields": ["idsubsls", "lat", "lon", "jenis", "status", "nama", "jml", "bangunan", "id", "nobangunan"],
    "points": points,
}
with open(os.path.join(OUT_DIR, "points.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print("status legend:", status_legend)
print("bangunan legend:", bangunan_legend)

for fn in ["sls.geojson", "points.json"]:
    p = os.path.join(OUT_DIR, fn)
    print(fn, os.path.getsize(p) / 1024 / 1024, "MB")
