import json, csv, os, datetime

GEOJSON_IN = "data/sls.geojson"
CSV_IN = "data/geotagging_all_27agustus.csv"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.isabs(GEOJSON_IN):
    GEOJSON_IN = os.path.join(SCRIPT_DIR, GEOJSON_IN)
if not os.path.isabs(CSV_IN):
    CSV_IN = os.path.join(SCRIPT_DIR, CSV_IN)

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

# ---------- 1. Process SLS boundary geojson ----------
with open(GEOJSON_IN, encoding="utf-8") as f:
    gj = json.load(f)

trimmed_features = []
for feat in gj["features"]:
    p = feat["properties"]
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
        "nm_ketua": p.get("nm_ketua"),
        "luas": round(p["luas"], 1) if p.get("luas") is not None else None,
    }
    trimmed_features.append({
        "type": "Feature",
        "properties": new_p,
        "geometry": feat["geometry"],
    })

out_gj = {"type": "FeatureCollection", "features": trimmed_features}
with open(os.path.join(OUT_DIR, "sls.geojson"), "w", encoding="utf-8") as f:
    json.dump(out_gj, f, ensure_ascii=False, separators=(",", ":"))

print("sls.geojson features:", len(trimmed_features))

# ---------- 2. Process geotagging CSV into compact points.json ----------
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
missing_subsls_match = 0
n = 0
with open(CSV_IN, encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)
    for row in reader:
        n += 1
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
        ]
        points.append(rec)

print("total csv rows:", n, "-> points exported:", len(points))

out = {
    "assignmentBase": ASSIGNMENT_BASE,
    "dataAsOf": data_as_of,
    "generatedAt": generated_at,
    "jenisLegend": jenis_legend,
    "statusLegend": status_legend,
    "bangunanLegend": bangunan_legend,
    "fields": ["idsubsls", "lat", "lon", "jenis", "status", "nama", "jml", "bangunan", "id"],
    "points": points,
}
with open(os.path.join(OUT_DIR, "points.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print("status legend:", status_legend)
print("bangunan legend:", bangunan_legend)

for fn in ["sls.geojson", "points.json"]:
    p = os.path.join(OUT_DIR, fn)
    print(fn, os.path.getsize(p) / 1024 / 1024, "MB")
