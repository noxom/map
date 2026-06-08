#!/usr/bin/env python3
"""Генерирует data/places.json и data/countries.json по списку городов
из scripts/input/cities.txt, используя локальный дамп GeoNames.

Запуск: python3 scripts/generate_data.py
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
    """CSV-файл с колонками name,geonameid. geonameid опционален — указывается
    только для устранения неоднозначности (если городов с таким именем несколько,
    например небольшие города в разных странах)."""
    cities = []
    with open(INPUT_FILE, encoding="utf-8", newline="") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        for row in csv.DictReader(lines):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            raw_id = (row.get("geonameid") or "").strip()
            cities.append((name, int(raw_id) if raw_id else None))
    return cities


def read_extra_places():
    """CSV с произвольными точками, не привязанными к городам из GeoNames
    (острова, достопримечательности и т.п.). Колонки: name,country,lat,lng.
    `country` нужен только для группировки в легенде на странице с пинами —
    на закраску карты стран эти записи не влияют (у них нет geonameid)."""
    if not EXTRA_PLACES_FILE.exists():
        return []
    extra = []
    with open(EXTRA_PLACES_FILE, encoding="utf-8", newline="") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        for row in csv.DictReader(lines):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            extra.append({
                "name": name,
                "country": (row.get("country") or "").strip(),
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
            })
    return extra


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


def write_js_array_atomic(file, var_name, value):
    """Пишет во временный файл и атомарно заменяет целевой — успешная предыдущая
    генерация не будет испорчена, если что-то пойдёт не так на полпути."""
    body = json.dumps(value, ensure_ascii=False, indent=2)
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(f"export const {var_name} = {body};\n", encoding="utf-8")
    os.replace(tmp, file)


def resolve_city(by_name, by_id, name, geonameid):
    """Возвращает строку GeoNames для города или None, если не найдена.
    Если указан geonameid — ищем сразу по нему, поиск по названию не используется."""
    if geonameid is not None:
        return by_id.get(geonameid)

    matches = by_name.get(name.lower())
    if not matches:
        return None
    return max(matches, key=lambda c: int(c[COL_POPULATION] or 0))


def main():
    by_name, by_id = load_index()
    cities = read_input_cities()

    places = read_existing_places()
    known_ids = {p["geonameid"] for p in places if p.get("geonameid")}

    for name, geonameid in cities:
        row = resolve_city(by_name, by_id, name, geonameid)
        if row is None:
            if geonameid is not None:
                sys.exit(
                    f'[ОШИБКА] Город "{name}" с geonameid={geonameid} не найден в базе GeoNames.\n'
                    f'Проверьте значение geonameid в строке "{name},{geonameid}" файла {INPUT_FILE.name}.\n'
                    f'Генерация прервана, файлы не изменены.'
                )
            sys.exit(
                f'[ОШИБКА] Город "{name}" не найден в базе GeoNames.\n'
                f'Если это маленький город и название неуникально (например, есть тёзки в разных странах),\n'
                f'укажите его geonameid явно вторым столбцом: "{name},<geonameid>" в {INPUT_FILE.name}\n'
                f'(найти id можно на https://www.geonames.org/ через поиск по названию).\n'
                f'Генерация прервана, файлы не изменены.'
            )

        found_id = int(row[COL_GEONAMEID])
        if found_id in known_ids:
            print(f'[=] "{name}" уже есть в places-data.js (geonameid {found_id}) — пропущен')
            continue

        places.append({
            "name": row[COL_NAME],
            "country": row[COL_COUNTRY_CODE],
            "lat": float(row[COL_LATITUDE]),
            "lng": float(row[COL_LONGITUDE]),
            "geonameid": found_id,
        })
        known_ids.add(found_id)
        print(f'[+] "{name}" -> {row[COL_NAME]}, {row[COL_COUNTRY_CODE]} (geonameid {found_id})')

    # Карта стран красится только по городам из GeoNames (у них есть geonameid).
    visited = sorted({p["country"] for p in places if p.get("geonameid")})
    write_js_array_atomic(COUNTRIES_DATA_JS, "visitedCountries", visited)

    # Произвольные точки (острова, достопримечательности и т.п.) добавляются в список
    # мест для отображения и легенды, но не влияют на закраску карты стран.
    existing_extra = {(p["name"], p["lat"], p["lng"]) for p in places if not p.get("geonameid")}
    extra_count = 0
    for extra in read_extra_places():
        key = (extra["name"], extra["lat"], extra["lng"])
        if key in existing_extra:
            continue
        places.append(extra)
        existing_extra.add(key)
        extra_count += 1
        print(f'[+] "{extra["name"]}" -> произвольная точка, {extra["country"] or "без страны"}')

    write_js_array_atomic(PLACES_DATA_JS, "places", places)

    print(f"\nГотово: {len(places)} мест ({extra_count} произвольных точек), {len(visited)} стран.")
    print(f"-> {PLACES_DATA_JS.relative_to(ROOT)}")
    print(f"-> {COUNTRIES_DATA_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
