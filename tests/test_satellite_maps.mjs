import test from 'node:test';
import assert from 'node:assert/strict';
import { mapSkyPoint, mapFootprintKm, mapValidCoordinates, mapSplitDateline } from '../satellite_center/browser/satellite_maps.mjs';

test('sky polar chart orientation: N up, E right, zenith at center', () => {
  const north=mapSkyPoint(0,0,300,300,200);
  const east=mapSkyPoint(90,0,300,300,200);
  const zenith=mapSkyPoint(90,90,300,300,200);
  assert.ok(Math.abs(north[0]-300)<1e-6 && Math.abs(north[1]-100)<1e-6);
  assert.ok(Math.abs(east[0]-500)<1e-6 && Math.abs(east[1]-300)<1e-6);
  assert.ok(Math.abs(zenith[0]-300)<1e-6 && Math.abs(zenith[1]-300)<1e-6);
});

test('radio geometry footprint shrinks for higher minimum elevation', () => {
  const atHorizon=mapFootprintKm(400,0),at30=mapFootprintKm(400,30);
  assert.ok(atHorizon>1500 && atHorizon<2600);
  assert.ok(at30>100 && at30<atHorizon);
  assert.equal(mapFootprintKm(-100,0),0);
});

test('ground track splits across longitude discontinuity', () => {
  assert.equal(mapSplitDateline([[5,175],[6,179],[7,-179],[8,-175]]).length,2);
  assert.equal(mapSplitDateline([[5,10],[6,12],[7,14]]).length,1);
});

test('observer latitude longitude validation rejects impossible positions', () => {
  assert.equal(mapValidCoordinates(50.938,6.96),true);
  assert.equal(mapValidCoordinates(38.423,27.14),true);
  assert.equal(mapValidCoordinates(100,0),false);
  assert.equal(mapValidCoordinates(0,181),false);
});
