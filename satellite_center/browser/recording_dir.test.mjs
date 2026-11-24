import test from "node:test";
import assert from "node:assert/strict";

const { normalizeOutputDir, dropPlanFor, acceptsAnalysisDrop,
        droppedFileSuffix, DROP_SUFFIXES, OUTPUT_DIR_MAX } =
  await import("./recording_dir.mjs");

test("an empty recording folder means the default captures folder", () => {
  assert.equal(normalizeOutputDir(""), null);
  assert.equal(normalizeOutputDir("   "), null);
  assert.equal(normalizeOutputDir(null), null);
  assert.equal(normalizeOutputDir(undefined), null);
});

test("a plain subdirectory name is accepted", () => {
  assert.equal(normalizeOutputDir("ISS-SSTV-2026-11"), "ISS-SSTV-2026-11");
  assert.equal(normalizeOutputDir(" iss_sstv.01 "), "iss_sstv.01");
});

test("traversal, separators and absolute paths are refused", () => {
  for (const bad of ["..", ".", "../etc", "a/b", "a\\b", "/etc", "/home/x",
                     "~/x", "..%2fetc", "sub/../../home"]) {
    assert.throws(() => normalizeOutputDir(bad), /Recording folder/, bad);
  }
});

test("hidden control characters and overlong names are refused", () => {
  assert.throws(() => normalizeOutputDir("x".repeat(OUTPUT_DIR_MAX + 1)), /at most/);
  assert.throws(() => normalizeOutputDir("bad\x00name"), /Recording folder/);
  assert.throws(() => normalizeOutputDir("name with spaces"), /Recording folder/);
  assert.throws(() => normalizeOutputDir("-leading-dash"), /Recording folder/);
  assert.throws(() => normalizeOutputDir("_leading"), /Recording folder/);
  assert.throws(() => normalizeOutputDir(42), /Recording folder/);
});

test("the CU8 analyzer accepts only raw IQ recordings", () => {
  for (const suffix of [".cu8", ".iq", ".u8"]) {
    const plan = dropPlanFor("iq-analysis", suffix);
    assert.equal(plan.inputId, "iq-file", suffix);
    assert.equal(plan.startId, "iq-analyze-file", suffix);
    assert.equal(acceptsAnalysisDrop("iq-analysis", suffix), true, suffix);
  }
  for (const suffix of [".wav", ".png", ".txt", ""]) {
    assert.equal(dropPlanFor("iq-analysis", suffix), null, suffix);
    assert.equal(acceptsAnalysisDrop("iq-analysis", suffix), false, suffix);
  }
});

test("the image section routes WAV, CU8 and images to their own inputs", () => {
  const wav = dropPlanFor("satellite-images", ".wav");
  assert.equal(wav.inputId, "image-sstv-file");
  assert.equal(wav.startId, "image-decode-sstv");
  const cu8 = dropPlanFor("satellite-images", ".cu8");
  assert.equal(cu8.inputId, "image-cuiq-file");
  assert.equal(cu8.startId, "image-decode-cuiq");
  const png = dropPlanFor("satellite-images", ".png");
  assert.equal(png.inputId, "image-import");
  assert.equal(png.startId, null);
  assert.equal(dropPlanFor("satellite-images", ".txt"), null);
});

test("suffix extraction is case-insensitive and rejects odd names", () => {
  assert.equal(droppedFileSuffix("TIHULU_ISS_20261123T120000Z_137900000Hz_IQ.cu8"), ".cu8");
  assert.equal(droppedFileSuffix("clip.WAV"), ".wav");
  assert.equal(droppedFileSuffix("noextension"), "");
  assert.equal(droppedFileSuffix(null), "");
  assert.equal(droppedFileSuffix(7), "");
});

test("every advertised drop suffix has a concrete plan in at least one zone", () => {
  for (const suffix of DROP_SUFFIXES) {
    const supported = ["iq-analysis", "satellite-images"]
      .some(zone => acceptsAnalysisDrop(zone, suffix));
    assert.equal(supported, true, suffix);
  }
});
