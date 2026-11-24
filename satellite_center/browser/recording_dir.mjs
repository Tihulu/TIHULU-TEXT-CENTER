// Per-job recording folder (native companion) and analysis-section drag & drop.
// Pure helpers only: the DOM wiring lives in browser.js and this module's own
// unit test imports it directly. Never upload or transmit a dropped file.

// A web client may only name ONE subdirectory under the companion's captures
// folder. Absolute paths, separators and '..' are refused here AND again,
// strictly, by the companion server (see Station.resolve_recording_dir).
export const OUTPUT_DIR_MAX = 41;
const OUTPUT_DIR_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,40}$/;

export function normalizeOutputDir(value) {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") throw Error("Recording folder must be a name");
  const text = value.trim();
  if (!text) return null;
  if (text.length > OUTPUT_DIR_MAX)
    throw Error("Recording folder name must be at most " + OUTPUT_DIR_MAX + " characters");
  if (text === "." || text === ".." || !OUTPUT_DIR_PATTERN.test(text))
    throw Error("Recording folder must be a single name: letters, digits, dot, underscore or dash");
  return text;
}

export const DROP_SUFFIXES = [".cu8", ".iq", ".u8", ".wav", ".png", ".jpg", ".jpeg"];

export function droppedFileSuffix(name) {
  if (typeof name !== "string") return "";
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot).toLowerCase() : "";
}

// Each analysis section accepts only the recordings it can actually open, and
// a dropped file behaves exactly like the same file chosen with the picker.
export function dropPlanFor(zoneId, suffix) {
  const ext = String(suffix || "").toLowerCase();
  if (zoneId === "iq-analysis") {
    if ([".cu8", ".iq", ".u8"].includes(ext))
      return { inputId: "iq-file", startId: "iq-analyze-file", label: "CU8 analyzer" };
    return null;
  }
  if (zoneId === "satellite-images") {
    if (ext === ".wav")
      return { inputId: "image-sstv-file", startId: "image-decode-sstv", label: "Robot36 SSTV decoder" };
    if ([".cu8", ".iq", ".u8"].includes(ext))
      return { inputId: "image-cuiq-file", startId: "image-decode-cuiq", label: "CU8 to Robot36 decoder" };
    if ([".png", ".jpg", ".jpeg"].includes(ext))
      return { inputId: "image-import", startId: null, label: "local image import" };
    return null;
  }
  return null;
}

export function acceptsAnalysisDrop(zoneId, suffix) {
  return dropPlanFor(zoneId, suffix) !== null;
}
