# Live FM RadioText setup — Pop!_OS / Linux

This receiver is available in TIHULU TEXT CENTER v0.2, but the app does **not**
install or run a third-party decoder automatically. It will claim the RTL-SDR USB
device when **you click Start**. No background scanning; FM frequency range
is limited to 87.5–108.0 MHz and each capture to 10–90 seconds. It is
receive-only and never transmits.

## 1. Prepare redsea

Your existing system has `rtl_fm` and `rtl_test`, but **redsea was not found**
in the November 6, 2026 check. First see if your Pop!_OS apt sources offer it:

```bash
apt-cache policy redsea
```

If a package candidate exists, `sudo apt install redsea` is a reasonable
package-managed choice. Otherwise follow the **official upstream** Meson build:

```bash
sudo apt update
sudo apt install git build-essential meson ninja-build libsndfile1-dev libliquid-dev nlohmann-json3-dev
mkdir -p ~/src
git clone https://github.com/windytan/redsea.git ~/src/redsea
cd ~/src/redsea
meson setup build
meson compile -C build
sudo meson install -C build
hash -r
command -v redsea
redsea --help
```

This builds from current upstream source; review the repository, license and
dependencies before installation. Avoid `curl | bash` and random binaries.
Do not install redsea or run a radio process if you do not want to.

Upstream README: https://github.com/windytan/redsea

## 2. Start the Text Center

```bash
cd ~/TIHULU-TEXT-CENTER
git pull --ff-only
python3 -m unittest discover -s tests -q
python3 -m textcenter receivers
python3 -m textcenter serve
```

Open **http://127.0.0.1:8787/**, go to **Radio Data (400)**, and look for
**Tune & decode FM RDS**. Enter a known, actually receivable FM frequency
(e.g. 98.6 MHz is a **published candidate** for WDR 2 around Köln, not a
guaranteed reception claim); select 30–60 seconds.

Close Gqrx, welle.io, readsb, rtl_433 and other SDR applications before
checking the consent box. Only one physical Nooelec dongle can tune one
independent center frequency at a time. The backend requires exactly one
RTL2832U-compatible USB candidate and starts:

```text
rtl_fm -d 0 -M fm -l 0 -A std -p 0 -s 171k -g 20 -F 9 -f <validated Hz>
    | redsea --input mpx -r 171k
```

This is the upstream-supported MPX → JSON pipeline. It is launched as
**two fixed argument-vector subprocesses without a shell**. The actual path is
resolved from installed binaries. JSON groups with PS or RadioText are stored
as `fm_rds` events in the existing local SQLite archive.

RDS may take several seconds to decode; poor reception or missing RDS can
yield zero items. The interface must never fabricate signal quality, station
identities, track metadata or official emergency alerts.

### Stop / lifetime

- **Stop Capture** requests subprocess termination. Captures also end on
  the selected 10–90 second timeout.
- If the Radio Data page stops polling (e.g. you close it), the session is
  automatically stopped after approximately 12 seconds.
- The cooperative local lock rejects a second Text Center session or
  another client honoring this particular lock. **Gqrx and other third-party
  apps do not have to honor this lock.** If they are already using the SDR,
  the decoder may fail with a busy-device error.
- Captures save the **original decoded text** in the local archive.
  They do not modify TV/Radio master recordings or transmit any signals.

## 3. Troubleshooting

```bash
cd ~/TIHULU-TEXT-CENTER
python3 -m textcenter receivers
command -v rtl_fm
command -v redsea
```

A detected USB device does not certify driver access, RF signal strength,
stereo/RDS MPX quality or station service. If the decoder exits without
data, select a strong broadcaster, verify antenna placement, and check that
no other application holds the USB receiver.

Do **not** run `rtl_test` or a manual `rtl_fm | redsea` pipeline in parallel
with a Text Center capture; both would compete for the USB receiver.

## Hardware/QA status

GitHub Actions runs **mock-only** parser/API/supervisor tests and checks
browser JavaScript syntax. The real Nooelec dongle, real RDS reception, Pi5
resource budgets, USB ownership across noncooperating programs, and live
mobile/portal use require separate user-provided acceptance evidence.
