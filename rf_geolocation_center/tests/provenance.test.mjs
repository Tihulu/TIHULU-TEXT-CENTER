import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

test("untrusted imported aircraft flag does not determine observer/map fallback",()=>{
 const app=readFileSync(new URL("../web/app.mjs",import.meta.url),"utf8");
 const start=app.indexOf("function source(){");
 const end=app.indexOf("\nfunction distanceRef(",start);
 assert.ok(start>=0&&end>start,"Locate source arbitration policy");
 const chooser=app.slice(start,end);
 assert.match(chooser,/state\.serialFix/);
 assert.match(chooser,/state\.browser/);
 assert.match(chooser,/DEFAULT_CENTER/);
 assert.doesNotMatch(chooser,/state\.references/,"JSON imports cannot authenticate actual ADS-B reception");
 assert.match(app,/sourceClaimsObservation/,"Untrusted source flag is classified as metadata only");
 assert.doesNotMatch(app,/imported observed references/);
});
