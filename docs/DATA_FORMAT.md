# Decoder export format

This JSON is consumed only through the **explicit** local CLI import command; the standalone app does not poll receivers or open a listening network ingest API.

Example (replace with data **actually received** from a decoder; this document is only a schema example and is NOT reception evidence):

```json
{
  "schema_version": 1,
  "pages": [
    {
      "source_id": "example-dvb-source",
      "page": 100,
      "subpage": 0,
      "title": "Example Teletext page",
      "body": "Actual decoder output goes here.",
      "language": "de",
      "received_at": "2026-11-06T10:00:00+01:00",
      "station": "Example channel (not measured)",
      "frequency_hz": 514000000,
      "medium": "dvb_teletext",
      "provenance": "Decoder name, version and local capture ID"
    }
  ],
  "events": [
    {
      "source_id": "example-fm-source",
      "title": "Example radio text",
      "body": "Actual decoded RadioText goes here.",
      "language": "en",
      "received_at": "2026-11-06T10:00:00+01:00",
      "station": "Example FM station (not measured)",
      "frequency_hz": 98600000,
      "medium": "fm_rds",
      "provenance": "Decoder name, version and local capture ID"
    }
  ]
}
```

Run: `python3 -m textcenter import-text --file decoded-pages.json` using the default persistent database. Use `python3 -m textcenter make-template` to generate an **empty** local template (0 RF records). There is no bundled decoder capture file.

Accepted numbered page media: `dvb_teletext`, `journaline`; pages 100–899, subpages 0–99.

Accepted event media: `dvb_teletext`, `dab_dls`, `journaline`, `fm_rds`, `drm`, `navtex`, `hf_weather`, `aprs`, `other_receiver`. Event timestamps must include a UTC offset.

The input is **never automatically an authenticated alert**, even if it contains warning-like words. Preserve the original text and timestamp; do not label tuner candidates as decoded.

## Radio/Tuner integration constraints

- TV Teletext requires an actual DVB transport-stream teletext PID and decoding; Nooelec RTL-SDR's narrow instantaneous bandwidth does not substitute for a DVB-T2 HDTV USB tuner.
- FM RDS/DAB DLS/Journaline require compatible SDR receivers and decoder services; the present app cannot demodulate RF.
- NAVTEX/HF text requires antenna, signal, schedule and an external decoder.
- APRS reception is not permission to transmit; Meshtastic/packet-radio TX requires separate compliant hardware, where relevant authorization, and explicit opt-in.
- A single SDR cannot independently tune FM, DAB and ADS-B across separate RF bands simultaneously.
- A verified official emergency-warning service has a distinct provenance and trust pipeline. No alert is promoted from user-imported RF text without external authentication.

## Storage policy

SQLite records persist across restarts. Source timestamps are retained, and receiving new data with the same (source_id, page, subpage) updates that entry; original RF recordings are not managed, modified or deleted by this app. Import size max 4 MB, 2000 combined records per invocation. For a full evidence archive, save raw decoder data separately under the owner's Files/Recorder policy.
