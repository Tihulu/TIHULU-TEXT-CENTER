import test from "node:test";
import assert from "node:assert/strict";
import {GNSS,rtlSignalClass} from "../core/gnss.mjs";

test("NavIC includes newer L1, L5 and S-band signals", () => {
  const navic=GNSS.find(s=>s.id==="I");
  assert.ok(navic, "NavIC must be present in the GNSS registry");
  assert.ok(navic.signals.some(([name,mhz])=>name.startsWith("L1")&&mhz===1575.42));
  assert.ok(navic.signals.some(([name,mhz])=>name==="L5"&&mhz===1176.45));
  assert.ok(navic.signals.some(([name,mhz])=>name==="S"&&mhz===2498.028));
  assert.match(rtlSignalClass(2498.028),/Outside approximate tuner range/);
});
