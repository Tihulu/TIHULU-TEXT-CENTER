/* Pure UI policy for the native DVB scan panel; tested independently of the DOM.
 * Country frequency plans apply to terrestrial/cable. Satellite is selected
 * by orbital position. Neither GitHub Pages nor WebUSB lab is an RF backend.
 */
export const SATELLITES = Object.freeze({
  S42E0: "Türksat 42°E", S13E0: "Hot Bird 13°E",
  S19E2: "Astra 19.2°E", S7E0: "Eutelsat 7°E"
});
export const DELIVERY = Object.freeze({
  t: "Antenna DVB-T/T2", c: "Cable DVB-C", s: "Satellite DVB-S/S2"
});
const NATIVE_ONLY = "Full scan requires a connected native Linux/Pi DVB receiver. WebUSB diagnostics cannot tune channels yet.";

export function scanFields(medium) {
  if (!(medium in DELIVERY)) throw new RangeError("Unsupported DVB delivery");
  return Object.freeze({
    showCountry: medium !== "s", showSatellite: medium === "s",
    countryUsedForFrequencies: medium !== "s",
    deliveryLabel: DELIVERY[medium]
  });
}

export function scanRequest({country, medium, satellite}) {
  const fields = scanFields(medium);
  if (fields.showSatellite) {
    if (!(satellite in SATELLITES)) throw new RangeError("Unknown satellite");
    // Satellite orbital position determines RF scan, not country.
    // Native channel profiles still use a region for saved-list naming.
    return {
      country: satellite === "S42E0" ? "TR" : "DE",
      medium: "s", satellite
    };
  }
  if (!["DE", "TR"].includes(country)) throw new RangeError("Unknown country");
  return {country, medium};
}

export function scanTitle(request) {
  if (request.medium === "s")
    return (SATELLITES[request.satellite] || "Satellite") + " · DVB-S/S2";
  return (request.country === "TR" ? "Türkiye" : "Germany") +
         " · " + DELIVERY[request.medium];
}

export function scanControls({connected=false, medium="t", scanning=false,
    playing=false, pending=false, signal="", scanMessage=""} = {}) {
  const fields = scanFields(medium);
  const nativeReady = Boolean(connected);
  const isScanning = nativeReady && Boolean(scanning);
  const isPlaying = nativeReady && Boolean(playing);
  return {
    ...fields,
    connected:nativeReady,
    scanEnabled:nativeReady && !isScanning && !isPlaying && !pending,
    cancelEnabled:nativeReady && isScanning && !pending,
    stopEnabled:nativeReady && isPlaying && !pending,
    refreshEnabled:nativeReady && !pending,
    captionEnabled:nativeReady && !pending,
    countryEnabled:!isScanning && !pending && fields.showCountry,
    satelliteEnabled:!isScanning && !pending && fields.showSatellite,
    deliveryEnabled:!isScanning && !pending,
    backendText:nativeReady
      ? "Native Linux/Pi DVB connected · real RF scanning available when tuner is idle"
      : "No native DVB receiver connected · WebUSB diagnostics do not enable RF scanning",
    statusText:!nativeReady ? "Connect or pair with native TV Center to scan."
      : isScanning ? "Scanning actual DVB frequencies · " + (scanMessage || "waiting for receiver")
      : isPlaying ? "TV is playing. Stop the tuner before starting a full scan."
      : (scanMessage || "Receiver connected · ready to scan"),
    signalText:!nativeReady ? "No RF readings — receiver disconnected."
      : signal || "No RF readings yet (driver may not expose them).",
    explanation:nativeReady ? "Scan controls use your native DVB tuner, not browser WebUSB."
      : NATIVE_ONLY
  };
}
