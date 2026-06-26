const COUNTRY_NAMES = new Intl.DisplayNames(['en'], { type: 'region' });

export function countryName(code) {
  try {
    return COUNTRY_NAMES.of(code) ?? code;
  } catch {
    return code;
  }
}

export function countryFlag(code) {
  return [...code.toUpperCase()].map(c => String.fromCodePoint(0x1F1E6 - 65 + c.charCodeAt(0))).join('');
}

export function styleFeature(visitedSet, feature) {
  const VISITED_STYLE = { fillColor: '#2e7d32', fillOpacity: 0.6, color: '#1b5e20', weight: 1 };
  const OTHER_STYLE = { fillColor: '#cccccc', fillOpacity: 0.15, color: '#999999', weight: 0.5 };
  const code = feature.properties['ISO3166-1-Alpha-2'];
  return visitedSet.has(code) ? VISITED_STYLE : OTHER_STYLE;
}

export function groupByCountry(places) {
  const byCountry = new Map();
  places.forEach((p, index) => {
    const id = p.geonameid ?? index;
    if (!byCountry.has(p.country)) byCountry.set(p.country, []);
    byCountry.get(p.country).push({ ...p, id });
  });
  return byCountry;
}

export function popupHtml(place) {
  let html = `<b>${place.name}</b>`;
  if (place.year) html += `<br>${place.year}`;
  if (place.photo) html += `<br><img src="${place.photo}" style="width:200px;margin-top:6px;border-radius:4px;display:block">`;
  return html;
}
