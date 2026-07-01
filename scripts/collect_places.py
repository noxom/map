#!/usr/bin/env python3
"""Recursively finds place.csv and city.csv files under BASE_DIR, merges them into
scripts/input/mega-places.csv and scripts/input/mega-cities.csv,
and copies resized photos to assets/img/.

Usage:
    python scripts/collect_places.py <base_dir> [--max-px N] [--force]

place.csv format (same as extra-places.csv):
    name,country,lat,lng,photo
    photo is a filename relative to the place.csv file itself.

city.csv format (same as cities.csv):
    name,geonameid,photo
    photo is a filename relative to the city.csv file itself.
"""

import argparse
import csv
import re
import sys
import warnings
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_DIR = Path(r"D:\backup_google_drive_2024_12_04\Photos")
MEGA_PLACES_FILE = ROOT / "scripts" / "input" / "mega-places.csv"
MEGA_CITIES_FILE = ROOT / "scripts" / "input" / "mega-cities.csv"
IMG_DIR = ROOT / "assets" / "img"
CITIES_DUMP = ROOT / ".cache" / "cities500.txt"

COL_GEONAMEID = 0
COL_NAME = 1
COL_ASCIINAME = 2
COL_ALTERNATENAMES = 3
COL_COUNTRY_CODE = 8
COL_POPULATION = 14
LOGS_DIR = ROOT / "scripts" / "logs"
LOG_FILE = LOGS_DIR / "collect.log"
ERROR_LOG_FILE = LOGS_DIR / "collect-errors.log"


def load_geonames_index():
    """Loads GeoNames dump into name→rows and id→row indexes. Returns (by_name, by_id) or (None, None) if dump missing."""
    if not CITIES_DUMP.exists():
        print(f"[!] GeoNames cache not found at {CITIES_DUMP} — city photos will be placed flat in assets/img/")
        print(f"    Run 'make generate' once to download the cache.")
        return None, None
    by_name = {}
    by_id = {}
    with open(CITIES_DUMP, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) <= COL_POPULATION:
                continue
            by_id[int(cols[COL_GEONAMEID])] = cols
            names = {cols[COL_NAME], cols[COL_ASCIINAME]}
            for alt in cols[COL_ALTERNATENAMES].split(","):
                if alt:
                    names.add(alt)
            for name in names:
                key = name.strip().lower()
                if key:
                    by_name.setdefault(key, []).append(cols)
    return by_name, by_id


def resolve_country(by_name, by_id, name, geonameid):
    """Returns ISO country code for a city, or empty string if not found."""
    if by_name is None:
        return ""
    if geonameid:
        row = by_id.get(int(geonameid))
        return row[COL_COUNTRY_CODE] if row else ""
    matches = by_name.get(name.lower())
    if not matches:
        return ""
    row = max(matches, key=lambda c: int(c[COL_POPULATION] or 0))
    return row[COL_COUNTRY_CODE]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base_dir", nargs="?", default=str(DEFAULT_BASE_DIR),
                   help=f"Base directory to search recursively (default: {DEFAULT_BASE_DIR})")
    p.add_argument("--max-px", type=int, default=1024, metavar="N",
                   help="Max pixels on longest side for resized photos (default: 1024)")
    p.add_argument("--force", action="store_true",
                   help="Re-process and overwrite already copied photos")
    return p.parse_args()


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return s


def unique_dest(img_dir: Path, slug: str, suffix: str, force: bool) -> Path:
    candidate = img_dir / f"{slug}{suffix}"
    if not candidate.exists() or force:
        return candidate
    i = 2
    while True:
        candidate = img_dir / f"{slug}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def resize_and_copy(src: Path, dest: Path, max_px: int):
    if not HAS_PIL:
        print(f"  [!] Pillow not installed — copying {src.name} without resizing")
        import shutil
        shutil.copy2(src, dest)
        return

    with Image.open(src) as img:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        if max(w, h) > max_px:
            scale = max_px / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.LANCZOS)
            print(f"  [~] Resized {src.name}: {w}x{h} -> {new_size[0]}x{new_size[1]}")
        else:
            print(f"  [=] {src.name} already within {max_px}px ({w}x{h}), copying as-is")
        img.save(dest, optimize=True, quality=85)


def process_photo(name: str, photo_filename: str, source_dir: Path, args, errors: list, country: str = "") -> str:
    """Copies and resizes a photo into assets/img/{country}/ (or flat if no country).
    Returns the relative path from assets/img/ (e.g. 'JP/tokyo.jpg' or 'almaty.jpg')."""
    if not photo_filename:
        return ""
    src = source_dir / photo_filename
    if not src.exists():
        msg = f"Photo not found for {name!r}: {src}"
        print(f"  [!] {msg}")
        errors.append(msg)
        return ""
    slug = slugify(name)
    suffix = src.suffix.lower()
    dest_dir = (IMG_DIR / country.upper()) if country else IMG_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_dest(dest_dir, slug, suffix, args.force)
    if dest.exists() and not args.force:
        print(f"  [=] {dest.relative_to(IMG_DIR)} already in assets/img/, skipping copy")
    else:
        try:
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("ignore")
                resize_and_copy(src, dest, args.max_px)
        except Exception as e:
            msg = f"Failed to process photo for {name!r} ({src}): {e}"
            print(f"  [!] {msg}")
            errors.append(msg)
            return ""
    return dest.relative_to(IMG_DIR).as_posix()


# --- place.csv handling ---

def collect_places(base_dir: Path, args, errors: list):
    csv_files = sorted(p for p in base_dir.rglob("*.csv") if p.name.lower() in ("place.csv", "places.csv"))
    if not csv_files:
        print("No place.csv files found.")
        return []

    print(f"\nFound {len(csv_files)} place.csv file(s):")
    for f in csv_files:
        print(f"  {f.relative_to(base_dir)}")

    all_entries = []
    seen = set()

    for path in csv_files:
        with open(path, encoding="utf-8", newline="") as f:
            lines = (line for line in f if not line.lstrip().startswith("#"))
            for row in csv.DictReader(lines):
                name = (row.get("name") or "").strip()
                lat_s = (row.get("lat") or "").strip()
                lng_s = (row.get("lng") or "").strip()
                if not name or not lat_s or not lng_s:
                    if name:
                        msg = f"Skipping row without lat/lng: {name!r} in {path}"
                        print(f"  [!] {msg}")
                        errors.append(msg)
                    continue
                key = (name, lat_s, lng_s)
                if key in seen:
                    print(f"  [=] Duplicate skipped: {name!r} ({lat_s}, {lng_s})")
                    continue
                seen.add(key)
                all_entries.append({
                    "name": name,
                    "country": (row.get("country") or "").strip(),
                    "lat": lat_s,
                    "lng": lng_s,
                    "photo": (row.get("photo") or "").strip(),
                    "_source_dir": path.parent,
                    "_source_file": str(path),
                })

    print(f"\nProcessing {len(all_entries)} unique place(s)...")
    output_rows = []
    for entry in all_entries:
        photo_out = process_photo(entry["name"], entry["photo"], entry["_source_dir"], args, errors, country=entry["country"])
        output_rows.append({
            "name": entry["name"],
            "country": entry["country"],
            "lat": entry["lat"],
            "lng": entry["lng"],
            "photo": photo_out,
            "_source_file": entry["_source_file"],
        })

    return output_rows


# --- city.csv handling ---

def collect_cities(base_dir: Path, args, errors: list, by_name=None, by_id=None):
    csv_files = sorted(p for p in base_dir.rglob("*.csv") if p.name.lower() in ("city.csv", "cities.csv"))
    if not csv_files:
        print("No city.csv files found.")
        return []

    print(f"\nFound {len(csv_files)} city.csv file(s):")
    for f in csv_files:
        print(f"  {f.relative_to(base_dir)}")

    all_entries = []
    seen = set()

    for path in csv_files:
        with open(path, encoding="utf-8", newline="") as f:
            lines = (line for line in f if not line.lstrip().startswith("#"))
            for row in csv.DictReader(lines):
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                raw_id = (row.get("geonameid") or "").strip()
                geonameid = int(raw_id) if raw_id else None
                key = (name, geonameid)
                if key in seen:
                    print(f"  [=] Duplicate skipped: {name!r}")
                    continue
                seen.add(key)
                all_entries.append({
                    "name": name,
                    "geonameid": raw_id,
                    "photo": (row.get("photo") or "").strip(),
                    "_source_dir": path.parent,
                    "_source_file": str(path),
                })

    print(f"\nProcessing {len(all_entries)} unique city/cities...")
    output_rows = []
    for entry in all_entries:
        country = resolve_country(by_name, by_id, entry["name"], entry["geonameid"])
        photo_out = process_photo(entry["name"], entry["photo"], entry["_source_dir"], args, errors, country=country)
        output_rows.append({
            "name": entry["name"],
            "geonameid": entry["geonameid"],
            "photo": photo_out,
            "_source_file": entry["_source_file"],
        })

    return output_rows


def main():
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()
    if not base_dir.is_dir():
        sys.exit(f"[ERROR] Not a directory: {base_dir}")

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ERROR_LOG_FILE.write_text("", encoding="utf-8")  # clear on each run

    errors = []
    print("Loading GeoNames index...")
    by_name, by_id = load_geonames_index()
    place_rows = collect_places(base_dir, args, errors)
    city_rows = collect_cities(base_dir, args, errors, by_name=by_name, by_id=by_id)

    MEGA_PLACES_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(MEGA_PLACES_FILE, "w", encoding="utf-8", newline="") as f:
        f.write("# Auto-generated by collect_places.py — do not edit manually\n")
        writer = csv.DictWriter(f, fieldnames=["name", "country", "lat", "lng", "photo"])
        writer.writeheader()
        writer.writerows({k: v for k, v in r.items() if not k.startswith("_")} for r in place_rows)

    with open(MEGA_CITIES_FILE, "w", encoding="utf-8", newline="") as f:
        f.write("# Auto-generated by collect_places.py — do not edit manually\n")
        writer = csv.DictWriter(f, fieldnames=["name", "geonameid", "photo"])
        writer.writeheader()
        writer.writerows({k: v for k, v in r.items() if not k.startswith("_")} for r in city_rows)

    import datetime
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"collect_places.py run at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"base_dir: {base_dir}\n\n")
        f.write(f"=== places ({len(place_rows)}) ===\n")
        for r in place_rows:
            f.write(f"  {r['name']}\n    {r['_source_file']}\n")
        f.write(f"\n=== cities ({len(city_rows)}) ===\n")
        for r in city_rows:
            f.write(f"  {r['name']}\n    {r['_source_file']}\n")

    if errors:
        with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"Errors from run at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for i, e in enumerate(errors, 1):
                f.write(f"{i}. {e}\n")

    print(f"\nDone:")
    print(f"  {len(place_rows)} places -> {MEGA_PLACES_FILE.relative_to(ROOT)}")
    print(f"  {len(city_rows)} cities  -> {MEGA_CITIES_FILE.relative_to(ROOT)}")
    print(f"  log -> {LOG_FILE.relative_to(ROOT)}")
    if errors:
        print(f"  {len(errors)} error(s) -> {ERROR_LOG_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
