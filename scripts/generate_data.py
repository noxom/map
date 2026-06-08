#!/usr/bin/env python3
"""Генерирует data/places.json и data/countries.json по списку городов
из scripts/input/cities.txt, используя локальный дамп GeoNames.

Запуск: python3 scripts/generate_data.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES_DUMP = Path(__file__).parent / "data" / "cities15000.txt"
INPUT_FILE = Path(__file__).parent / "input" / "cities.txt"
PLACES_DATA_JS = ROOT / "assets" / "js" / "places-data.js"
COUNTRIES_DATA_JS = ROOT / "assets" / "js" / "countries-data.js"

# Колонки cities*.txt (tab-separated), см. http://download.geonames.org/export/dump/readme.txt
COL_GEONAMEID = 0
COL_NAME = 1
COL_ASCIINAME = 2
COL_ALTERNATENAMES = 3
COL_LATITUDE = 4
COL_LONGITUDE = 5
COL_COUNTRY_CODE = 8
COL_POPULATION = 14


def load_index():
    index = {}  # lowercase name -> list of rows
    with open(CITIES_DUMP, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) <= COL_POPULATION:
                continue
            names = {cols[COL_NAME], cols[COL_ASCIINAME]}
            for alt in cols[COL_ALTERNATENAMES].split(","):
                if alt:
                    names.add(alt)
            for name in names:
                key = name.strip().lower()
                if not key:
                    continue
                index.setdefault(key, []).append(cols)
    return index


def read_input_cities():
    cities = []
    with open(INPUT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                cities.append(line)
    return cities


def read_existing_places():
    """Читает уже сгенерированный places-data.js (если есть), чтобы не дублировать записи."""
    if not PLACES_DATA_JS.exists():
        return []
    text = PLACES_DATA_JS.read_text(encoding="utf-8")
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(text[start:end + 1])


def write_js_array(file, var_name, value):
    body = json.dumps(value, ensure_ascii=False, indent=2)
    file.write_text(f"export const {var_name} = {body};\n", encoding="utf-8")


def main():
    index = load_index()
    cities = read_input_cities()

    places = read_existing_places()
    known_ids = {p["geonameid"] for p in places if p.get("geonameid")}

    for city in cities:
        matches = index.get(city.lower())
        if not matches:
            print(f'[!] Город не найден: "{city}" — пропущен, добавьте вручную')
            continue

        best = max(matches, key=lambda c: int(c[COL_POPULATION] or 0))

        geonameid = int(best[COL_GEONAMEID])
        if geonameid in known_ids:
            print(f'[=] "{city}" уже есть в places.json (geonameid {geonameid}) — пропущен')
            continue

        places.append({
            "name": best[COL_NAME],
            "country": best[COL_COUNTRY_CODE],
            "lat": float(best[COL_LATITUDE]),
            "lng": float(best[COL_LONGITUDE]),
            "geonameid": geonameid,
        })
        known_ids.add(geonameid)
        print(f'[+] "{city}" -> {best[COL_NAME]}, {best[COL_COUNTRY_CODE]} (geonameid {geonameid})')

    write_js_array(PLACES_DATA_JS, "places", places)

    visited = sorted({p["country"] for p in places})
    write_js_array(COUNTRIES_DATA_JS, "visitedCountries", visited)

    print(f"\nГотово: {len(places)} мест, {len(visited)} стран.")
    print(f"-> {PLACES_DATA_JS.relative_to(ROOT)}")
    print(f"-> {COUNTRIES_DATA_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
