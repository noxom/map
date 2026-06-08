// Сгенерировано scripts/generate_data.py из scripts/input/cities.txt
import { places } from './places-data.js';

const map = L.map('map').setView([50, 15], 4);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 18,
}).addTo(map);

const legendList = document.getElementById('legend-list');
let activeId = null;
const markersById = new Map();

function setActive(id) {
  if (activeId === id) return;

  if (activeId !== null) {
    markersById.get(activeId).marker._icon?.classList.remove('pin-highlight');
    legendList.querySelector(`[data-id="${activeId}"]`)?.classList.remove('active');
  }

  activeId = id;

  if (activeId !== null) {
    markersById.get(activeId).marker._icon?.classList.add('pin-highlight');
    const item = legendList.querySelector(`[data-id="${activeId}"]`);
    item?.classList.add('active');
    item?.scrollIntoView({ block: 'nearest' });
  }
}

const COUNTRY_NAMES = new Intl.DisplayNames(['ru'], { type: 'region' });

function countryName(code) {
  try {
    return COUNTRY_NAMES.of(code) ?? code;
  } catch {
    return code;
  }
}

const byCountry = new Map();
places.forEach((p, index) => {
  const id = p.geonameid ?? index;
  markersById.set(id, { place: p });
  if (!byCountry.has(p.country)) byCountry.set(p.country, []);
  byCountry.get(p.country).push({ ...p, id });
});

const countryEntries = [...byCountry.entries()].sort((a, b) =>
  countryName(a[0]).localeCompare(countryName(b[0]))
);

for (const [code, cities] of countryEntries) {
  const countryItem = document.createElement('li');
  countryItem.className = 'country';
  countryItem.textContent = countryName(code);
  legendList.appendChild(countryItem);

  const cityList = document.createElement('ul');
  cityList.className = 'cities';

  cities
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach(({ id, name }) => {
      const cityItem = document.createElement('li');
      cityItem.textContent = name;
      cityItem.dataset.id = id;
      cityItem.addEventListener('mouseenter', () => setActive(id));
      cityItem.addEventListener('mouseleave', () => setActive(null));
      cityList.appendChild(cityItem);
    });

  legendList.appendChild(cityList);
}

places.forEach((p, index) => {
  const id = p.geonameid ?? index;
  const marker = L.marker([p.lat, p.lng])
    .addTo(map)
    .bindPopup(`<b>${p.name}</b>${p.year ? `<br>${p.year}` : ''}`)
    .bindTooltip(`${p.name}, ${countryName(p.country)}`, { direction: 'top', offset: [0, -32] });

  marker.on('mouseover', () => setActive(id));
  marker.on('mouseout', () => setActive(null));

  markersById.get(id).marker = marker;
});
