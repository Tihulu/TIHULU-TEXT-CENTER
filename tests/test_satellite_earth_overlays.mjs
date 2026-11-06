import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mapSplitDateline, mapFootprintKm, mapValidCoordinates } from '../satellite_center/browser/satellite_maps.mjs';

const map = readFileSync(new URL('../satellite_center/browser/satellite_maps.mjs',import.meta.url),'utf8');
const html = readFileSync(new URL('../satellite_center/browser/index.html',import.meta.url),'utf8');

test('user-visible Earth overlay controls are real wired handlers',()=>{
 for(const id of ['map-track-scope','map-coverage-scope','map-focus-selected','map-fit-all','map-overlay-count']){
   assert.ok(html.includes('id="'+id+'"'),id+' missing in HTML');
   assert.ok(map.includes('$("'+id+'")'),id+' not used by map module');
 }
 assert.match(map,/\$\("map-focus-selected"\)\.addEventListener\("click"/);
 assert.match(map,/\$\("map-fit-all"\)\.addEventListener\("click"/);
 assert.match(map,/earthMap\.fitBounds\(/);
 assert.match(map,/earthMap\.setView\(\[sat\.lat,sat\.lon\]/);
});

test('satellite and orbit overlays have explicit correct Leaflet z-order',()=>{
 const definition=[['sat-coverage',380],['sat-tracks',420],['sat-markers',450],['sat-station',470]];
 for(const [name,z] of definition){
   assert.ok(map.includes('["'+name+'",'+z+']'));
   assert.ok(map.includes('pane:"'+name+'"'));
 }
 assert.ok(map.includes('worldPane.style.zIndex="350"'));
 assert.ok(map.includes('leaflet.circleMarker([s.lat,s.lon]'));
 assert.ok(map.includes('leaflet.polyline(segment'));
 assert.ok(map.includes('leaflet.polygon(segment'));
});

test('both all-satellite tracks and selected coverage are actually rendered',()=>{
 assert.ok(html.includes('<option value="all" selected>All tracked satellites (±45 min)</option>'));
 assert.ok(html.includes('<option value="selected" selected>Selected satellite</option>'));
 assert.match(map,/scope==="all"\|\|\(scope==="selected"&&active\)/);
 assert.match(map,/coverage==="all"\|\|\(coverage==="selected"&&active\)/);
 assert.ok(map.includes('for(let m=-45;m<=45;m+=3)'));
 assert.ok(map.includes('if(showCoverage)'));
 assert.ok(map.includes('if(showTrack)'));
});

test('global camera fit and selected focus do not change TLE positions',()=>{
 assert.ok(map.includes('fitTrackedEarth()'));
 assert.ok(map.includes('initialCatalogFitDone'));
 assert.ok(map.includes('mapValidCoordinates(row.lat,row.lon)'));
 assert.ok(map.includes('minZoom:0'));
 assert.ok(map.includes('earthMap.fitBounds(bounds.pad(0.12)'));
 assert.match(map,/updateEarthViewportCount\(\)/);
 assert.ok(map.includes('bounds.contains([row.lat,row.lon])'));
});

test('dateline split and contact radius remain geometric and bounded',()=>{
 const segments=mapSplitDateline([[60,177],[60,179],[61,-178],[61,-175]]);
 assert.equal(segments.length,2);
 const radius=mapFootprintKm(2116,15);
 assert.ok(radius>0 && radius<6500);
 assert.ok(mapFootprintKm(2116,30)<radius);
 assert.equal(mapValidCoordinates(59.631,42.899),true);
});

test('map display cannot be confused with detected RF signal',()=>{
 assert.match(map,/Predictions, not radio reception/);
 assert.match(html,/not received RF detections/);
});
