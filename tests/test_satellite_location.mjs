import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
 foldCityName, validStationCoordinates, offlineCityMatches,
 onlineCityMatches
} from '../satellite_center/browser/location_search.mjs';
const catalog = JSON.parse(fs.readFileSync(
 new URL('../satellite_center/browser/cities-de-tr.json', import.meta.url), 'utf8'));
const rows=catalog.places;

test('bundled Germany/Türkiye data is real and large, not invented placeholders',()=>{
 assert.ok(rows.length>=8000);
 assert.equal(rows.filter(r=>r[0]==='DE').length,7104);
 assert.equal(rows.filter(r=>r[0]==='TR').length,980);
 assert.ok(rows.some(r=>r[1]==='Karaburun'&&r[2]==='İzmir'));
 assert.ok(rows.some(r=>r[1]==='Hürth'));
});
test('Turkish/German accent folding and known English aliases',()=>{
 for(const [typed,normalized] of [
  ['İzmir','izmir'],['ıSPARTA','isparta'],['Eskişehir','eskisehir'],
  ['Köln','koln'],['Düsseldorf','dusseldorf'],['Şanlıurfa','sanliurfa'],
  ['MÜNCHEN','munchen']])assert.equal(foldCityName(typed),normalized);
 const izmir=offlineCityMatches(rows,'izmir','TR');
 assert.ok(izmir.some(r=>r.name==='İzmir'||r.name==='Izmir'));
 assert.ok(offlineCityMatches(rows,'hürth','DE').some(r=>r.name==='Hürth'));
 assert.ok(offlineCityMatches(rows,'karaburun','TR').some(r=>r.region==='İzmir'));
 assert.ok(offlineCityMatches(rows,'cologne','DE').some(r=>r.name==='Köln'||r.name==='Cologne'));
});
test('suggestions are bounded, do not silently match all 8k without a query',()=>{
 assert.equal(offlineCityMatches(rows,'').length,0);
 assert.equal(offlineCityMatches(rows,'a').length,0);
 assert.ok(offlineCityMatches(rows,'ber','all').length<=12);
 assert.ok(offlineCityMatches(rows,'ber','TR').every(r=>r.country==='TR'));
});
test('custom location validation supports world coordinates including poles and dateline',()=>{
 assert.equal(validStationCoordinates(90,180),true);
 assert.equal(validStationCoordinates(-90,-180),true);
 assert.equal(validStationCoordinates(51.0,6.9),true);
 assert.equal(validStationCoordinates(91,6),false);
 assert.equal(validStationCoordinates(0,-181),false);
 assert.equal(validStationCoordinates(NaN,0),false);
});
test('online results are validated and never blindly used',()=>{
 const p={results:[
  {name:'Tokyo',country:'Japan',country_code:'JP',admin1:'Tokyo',latitude:35.6895,longitude:139.69},
  {name:'Bad',country_code:'DE',latitude:100,longitude:25},
  {name:'Berlin',country:'Germany',country_code:'DE',admin1:'Berlin',latitude:52.52,longitude:13.405}
 ]};
 const all=onlineCityMatches(p);
 assert.equal(all.length,2);
 assert.equal(onlineCityMatches(p,'DE').length,1);
 assert.equal(onlineCityMatches({},'all').length,0);
});
test('UI static contract: browser GPS only on button, manual coords not overwritten',()=>{
 const html=fs.readFileSync(new URL('../satellite_center/browser/index.html',import.meta.url),'utf8');
 const js=fs.readFileSync(new URL('../satellite_center/browser/location_search.mjs',import.meta.url),'utf8');
 for(const id of ['city-query','city-suggestions','city-country','city-online-search',
  'city-online-toggle','location-gps','location-status','lat','lon']){
  assert.ok(html.includes('id="'+id+'"'),id+' missing');
 }
 assert.ok(js.includes('gpsBtn.addEventListener("click"'));
 assert.ok(js.includes('navigator.geolocation.getCurrentPosition('));
 assert.ok(js.includes('getCurrentPosition(pos=>'));
 assert.ok(js.includes('latitude,longitude,accuracy'));
 assert.ok(js.includes('select.value="Custom"'));
 assert.ok(js.includes('if(automatic&&!onlineToggle.checked)return'));
});
