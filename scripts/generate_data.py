#!/usr/bin/env python3
"""Generates assets/js/places-data.js and assets/js/countries-data.js
from scripts/input/cities.csv using a local GeoNames dump.

Usage: python3 scripts/generate_data.py
"""

import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES_DUMP = Path(__file__).parent / "data" / "cities500.txt"
INPUT_FILE = Path(__file__).parent / "input" / "cities.csv"
EXTRA_PLACES_FILE = Path(__file__).parent / "input" / "extra-places.csv"
PLACES_DATA_JS = ROOT / "assets" / "js" / "places-data.js"
COUNTRIES_DATA_JS = ROOT / "assets" / "js" / "countries-data.js"
PHOTO_DIR = "assets/img"

# Columns of cities*.txt (tab-separated), see http://download.geonames.org/export/dump/readme.txt
COL_GEONAMEID = 0
COL_NAME = 1
COL_ASCIINAME = 2
COL_ALTERNATENAMES = 3
COL_LATITUDE = 4
COL_LONGITUDE = 5
COL_COUNTRY_CODE = 8
COL_POPULATION = 14


def load_index():
    by_name = {}  # lowercase name -> list of rows
    by_id = {}  # geonameid -> row
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
                if not key:
                    continue
                by_name.setdefault(key, []).append(cols)
    return by_name, by_id


def read_input_cities():
    """CSV file with columns name,geonameid,photo. geonameid and photo are optional."""
    cities = []
    with open(INPUT_FILE, encoding="utf-8", newline="") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        for row in csv.DictReader(lines):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            raw_id = (row.get("geonameid") or "").strip()
            photo = (row.get("photo") or "").strip()
            cities.append((name, int(raw_id) if raw_id else None, f"{PHOTO_DIR}/{photo}" if photo else None))
    return cities


def read_extra_places():
    """CSV with arbitrary points not tied to GeoNames cities
    (islands, landmarks, etc.). Columns: name,country,lat,lng,photo.
    `country` is used only for legend grouping - these entries do not
    affect country map coloring (they have no geonameid)."""
    if not EXTRA_PLACES_FILE.exists():
        return []
    extra = []
    with open(EXTRA_PLACES_FILE, encoding="utf-8", newline="") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        for row in csv.DictReader(lines):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            entry = {
                "name": name,
                "country": (row.get("country") or "").strip(),
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
                "type": "place",
            }
            photo = (row.get("photo") or "").strip()
            if photo:
                entry["photo"] = f"{PHOTO_DIR}/{photo}"
            extra.append(entry)
    return extra


def read_existing_places():
    """Reads the already-generated places-data.js (if present) to avoid duplicates."""
    if not PLACES_DATA_JS.exists():
        return []
    text = PLACES_DATA_JS.read_text(encoding="utf-8")
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(text[start:end + 1])


def write_js_array_atomic(file, var_name, value):
    """Writes to a temp file then atomically replaces the target - a previously
    successful generation is not corrupted if something fails midway."""
    body = json.dumps(value, ensure_ascii=False, indent=2)
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(f"export const {var_name} = {body};\n", encoding="utf-8")
    os.replace(tmp, file)


def resolve_city(by_name, by_id, name, geonameid):
    """Returns the GeoNames row for a city, or None if not found.
    If geonameid is given, looks it up directly without name search."""
    if geonameid is not None:
        return by_id.get(geonameid)

    matches = by_name.get(name.lower())
    if not matches:
        return None
    return max(matches, key=lambda c: int(c[COL_POPULATION] or 0))


def main():
    force = "--force" in sys.argv
    by_name, by_id = load_index()
    cities = read_input_cities()

    places = [] if force else read_existing_places()
    known_ids = {p["geonameid"] for p in places if p.get("geonameid")}

    for name, geonameid, photo in cities:
        row = resolve_city(by_name, by_id, name, geonameid)
        if row is None:
            if geonameid is not None:
                sys.exit(
                    f'[ERROR] City "{name}" with geonameid={geonameid} not found in GeoNames.\n'
                    f'Check the geonameid in line "{name},{geonameid}" of {INPUT_FILE.name}.\n'
                    f'Generation aborted, files unchanged.'
                )
            sys.exit(
                f'[ERROR] City "{name}" not found in GeoNames.\n'
                f'If this is a small city with a non-unique name, specify its geonameid explicitly\n'
                f'as the second column: "{name},<geonameid>" in {INPUT_FILE.name}\n'
                f'(find the id at https://www.geonames.org/ via name search).\n'
                f'Generation aborted, files unchanged.'
            )

        found_id = int(row[COL_GEONAMEID])
        if found_id in known_ids:
            if photo:
                for p in places:
                    if p.get("geonameid") == found_id and p.get("photo") != photo:
                        p["photo"] = photo
                        print(f'[~] "{name}" photo updated (geonameid {found_id})')
            else:
                print(f'[=] "{name}" already in places-data.js (geonameid {found_id}) - skipped')
            continue

        entry = {
            "name": row[COL_NAME],
            "country": row[COL_COUNTRY_CODE],
            "lat": float(row[COL_LATITUDE]),
            "lng": float(row[COL_LONGITUDE]),
            "geonameid": found_id,
            "type": "city",
        }
        if photo:
            entry["photo"] = photo
        places.append(entry)
        known_ids.add(found_id)
        print(f'[+] "{name}" -> {row[COL_NAME]}, {row[COL_COUNTRY_CODE]} (geonameid {found_id})')

    # Country map is colored only by GeoNames cities (those have geonameid).
    visited = sorted({p["country"] for p in places if p.get("geonameid")})
    write_js_array_atomic(COUNTRIES_DATA_JS, "visitedCountries", visited)

    # Arbitrary points (islands, landmarks, etc.) are added to the places list
    # for display and legend, but do not affect country map coloring.
    existing_extra = {(p["name"], p["lat"], p["lng"]) for p in places if not p.get("geonameid")}
    extra_count = 0
    for extra in read_extra_places():
        key = (extra["name"], extra["lat"], extra["lng"])
        if key in existing_extra:
            continue
        places.append(extra)
        existing_extra.add(key)
        extra_count += 1
        print(f'[+] "{extra["name"]}" -> custom point, {extra["country"] or "no country"}')

    write_js_array_atomic(PLACES_DATA_JS, "places", places)

    print(f"\nDone: {len(places)} places ({extra_count} custom points), {len(visited)} countries.")
    print(f"-> {PLACES_DATA_JS.relative_to(ROOT)}")
    print(f"-> {COUNTRIES_DATA_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
