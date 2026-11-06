# Receiver status and actual decoder connection

## Why the previous UI said "RF adapters not connected"

Version 0.1 used a static placeholder string even when a compatible RTL-SDR USB device was present. That was **not** a failed hardware test.

This version performs a **passive on-demand Linux USB inventory** at launch and when the user explicitly selects **Refresh device status**. It reads Linux sysfs for USB vendor/product ID `0bda:2838` and looks for `/dev/dvb/adapter*/frontend*`. It also checks whether `rtl_fm`, `redsea`, `welle-cli`, `rtl_test` and `rtl_433` executables exist.

This is only a discovery step. **No RF hardware is opened, scanned or retuned; no signal is claimed; USB permissions are not tested.** The ID `0bda:2838` identifies a shared RTL2832U-type USB receiver, and does not uniquely establish that the device is Nooelec-branded.

## Pop!_OS local diagnosis

From the checked-out repository:

```bash
cd ~/TIHULU-TEXT-CENTER
git pull --ff-only
python3 -m textcenter receivers
python3 -m textcenter serve
```

Refresh the browser at `http://127.0.0.1:8787/`, visit **Radio Data (400)**, then select **REFRESH DEVICE STATUS**. The sidebar distinguishes detected USB hardware from a decoder that is actually connected.

For low-level checks outside the application, where no other RTL-SDR program is using the device:

```bash
lsusb -d 0bda:2838
command -v rtl_fm
command -v redsea
command -v welle-cli
```

`rtl_test` is intentionally not run automatically: it opens the device and can conflict with Gqrx, welle.io, an ADS-B receiver or a protected recording.

## Decoder plans

- **FM RadioText:** An explicitly authorized future integration will use `rtl_fm` to produce FM multiplex PCM, then `redsea --input mpx -r 171k` to decode genuine JSON RadioText. Recording protection and process-level lock must be designed and tested before enabling any GUI-controlled retune.
- **DAB+:** `welle-cli` can provide DAB metadata where installed and configured. Do not assume it has a functioning local web API just because the binary is installed.
- **DVB-T2 Teletext:** A separate real DVB frontend and transport stream decoder is required; RTL-SDR detection is not DVB-T2 reception.
- **Other modes:** NAVTEX, Journaline, APRS, packet radio and LoRa have distinct receiver/decoder/legal requirements. They are not implied by detection.

The source-based JSON `import-text` path is still supported and remains the only supported broadcast data import in this milestone.

Relevant upstream reference for future FM adapter: https://github.com/windytan/redsea . Example source-supplied pipeline: `rtl_fm -M fm -l 0 -A std -p 0 -s 171k -g 20 -F 9 -f 98.6M | redsea --input mpx -r 171k`. This **will attempt to claim and retune the RTL-SDR** and is shown only as documentation, not executed by Tihulu. Check existing receiver ownership first.
