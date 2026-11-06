# Optional Survival Kit integration

This is an **independent** repository. No change was made to Tihulu Survival Kit branches, its Stage 8 release status, or the standalone flight-radar repository.

The app is deliberately loopback-only and uses SQLite. A deployment to a Raspberry Pi should:

1. Run \`python3 -m textcenter serve --host 127.0.0.1 --port 8787\` only on user request or when the owner explicitly enables its service.
2. Place an **authenticated TLS reverse proxy** in front, using the existing Survival Kit \`tihulu.lan\` local host and user session / per-owner access controls. Its browser route must forward API and assets safely; the MVP currently assumes root path \`/\` and should be mounted at a dedicated authenticated hostname or revised with a configured prefix before use under \`/text-center/\`.
3. Do not expose the private server directly to local or public networks. No public unrestricted proxy, no anonymous remote API, no automatic radio transmission.
4. Use the existing Stage 4 hardware lease broker for any future SDR/DVB adapter, preserve all protected recordings, and allow multiple viewers of the **same** tuned stream only if demonstrated by backend tests. Do not schedule hidden scans.
5. Reuse Stage 6 Translator/ASR and Stage 5 Local AI only on explicit user action with retained originals and correct worker admissions. No bundled LLM, telemetry or background inference.
6. Reuse the existing verified Emergency Center alerts only through a dedicated trusted integration; imported RDS/Teletext/NAVTEX alone is not a valid official warning.
7. Implement actual multi-user authentication/ACL and persistent partitioning before offering the local board to multiple phones/users. The current board is a local owner notebook with labels, not an open chat.

This is an integration **contract**, not a report that any of these services is installed or tested on Raspberry Pi 5 hardware.

## QA gates before a public network release

Test RPi 5 8GB power/RAM, Pop!_OS desktop, mobile Safari/Chrome, multi-tab behavior, account/session authentication, CSRF, HTTPS/mDNS setup, real RTL-SDR/TV decoder imports, frequency/time provenance, bounded RSS requests, protected media storage, tuner conflict handling and explicit refresh disabled in Background OFF. Record real hardware evidence separately.
