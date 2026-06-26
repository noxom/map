import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { countryName, countryFlag, styleFeature, groupByCountry, popupHtml } from '../assets/js/utils.js';

describe('countryName', () => {
  it('returns full name for known code', () => {
    assert.equal(countryName('JP'), 'Japan');
    assert.equal(countryName('RU'), 'Russia');
  });

  it('returns code as fallback for unknown code', () => {
    assert.equal(countryName('XX'), 'XX');
  });
});

describe('countryFlag', () => {
  it('returns flag emoji for country code', () => {
    assert.equal(countryFlag('JP'), '🇯🇵');
    assert.equal(countryFlag('RU'), '🇷🇺');
  });

  it('handles lowercase input', () => {
    assert.equal(countryFlag('jp'), countryFlag('JP'));
  });
});

describe('styleFeature', () => {
  const visited = new Set(['JP', 'RU']);

  it('returns visited style for visited country', () => {
    const style = styleFeature(visited, { properties: { 'ISO3166-1-Alpha-2': 'JP' } });
    assert.equal(style.fillColor, '#2e7d32');
  });

  it('returns other style for non-visited country', () => {
    const style = styleFeature(visited, { properties: { 'ISO3166-1-Alpha-2': 'DE' } });
    assert.equal(style.fillColor, '#cccccc');
  });
});

describe('groupByCountry', () => {
  const places = [
    { name: 'Tokyo', country: 'JP', lat: 35.68, lng: 139.69, geonameid: 1, type: 'city' },
    { name: 'Osaka', country: 'JP', lat: 34.69, lng: 135.50, geonameid: 2, type: 'city' },
    { name: 'Moscow', country: 'RU', lat: 55.75, lng: 37.61, geonameid: 3, type: 'city' },
  ];

  it('groups places by country', () => {
    const result = groupByCountry(places);
    assert.equal(result.get('JP').length, 2);
    assert.equal(result.get('RU').length, 1);
  });

  it('assigns geonameid as id', () => {
    const result = groupByCountry(places);
    assert.equal(result.get('JP')[0].id, 1);
  });

  it('uses index as id when geonameid is missing', () => {
    const result = groupByCountry([{ name: 'X', country: 'JP', lat: 0, lng: 0, type: 'city' }]);
    assert.equal(result.get('JP')[0].id, 0);
  });
});

describe('popupHtml', () => {
  it('renders name only', () => {
    assert.equal(popupHtml({ name: 'Tokyo' }), '<b>Tokyo</b>');
  });

  it('includes year when present', () => {
    assert.ok(popupHtml({ name: 'Tokyo', year: 2023 }).includes('2023'));
  });

  it('includes img tag when photo present', () => {
    assert.ok(popupHtml({ name: 'Tokyo', photo: 'photo.jpg' }).includes('<img'));
  });
});
