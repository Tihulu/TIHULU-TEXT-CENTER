"""Incremental MPEG transport-stream service filter for direct DVBv5 capture.

A DVB-T2 frequency carries multiple services. dvbv5-zap -P forwards the
entire multiplex, which needlessly saturates a player stdin pipe.
This parser retains PAT, the selected service's PMT, PCR and *all* elementary
PIDs listed by that PMT (video, audio, Teletext, subtitles, private data).

No transport payload is rewritten, and no fake signal health is inferred.
This is an experimental MPEG-TS parser; unusual multi-section PSI, encrypted
channels, PID changes, and severely corrupted captures need hardware testing.
"""
from __future__ import annotations


PACKET_SIZE = 188


class ServiceFilter:
    def __init__(self, service_id: int | None):
        self.service_id = service_id
        self.pmt_pid: int | None = None
        self.allowed = {0}
        self.pending = b""
        self.sections: dict[int, bytearray] = {}
        self.ready = service_id is None
        self.invalid_packets = 0
        self.filtered_packets = 0
        self.seen_packets = 0

    def _section(self, pid: int, payload: bytes, start: bool) -> bytes | None:
        if start:
            if not payload:
                return None
            pointer = payload[0]
            if 1 + pointer >= len(payload):
                self.sections.pop(pid, None)
                return None
            self.sections[pid] = bytearray(payload[1 + pointer:])
        elif pid in self.sections:
            self.sections[pid].extend(payload)
        else:
            return None
        section = self.sections[pid]
        if len(section) < 3:
            return None
        length = ((section[1] & 0x0f) << 8) | section[2]
        if length < 4 or length > 1021:
            self.sections.pop(pid, None)
            return None
        total = 3 + length
        if len(section) < total:
            return None
        self.sections.pop(pid, None)
        return bytes(section[:total])

    def _parse_pat(self, section: bytes):
        if section[0] != 0x00 or len(section) < 12:
            return
        # PAT section: table header 8 bytes, entries 4 bytes, CRC32 4 bytes.
        for pos in range(8, len(section) - 7, 4):
            prog = (section[pos] << 8) | section[pos + 1]
            pid = ((section[pos + 2] & 0x1f) << 8) | section[pos + 3]
            if prog == self.service_id:
                if pid != self.pmt_pid:
                    self.pmt_pid = pid
                    self.allowed = {0, pid}
                    self.ready = False
                return

    def _parse_pmt(self, section: bytes):
        if section[0] != 0x02 or len(section) < 16:
            return
        prog = (section[3] << 8) | section[4]
        if prog != self.service_id:
            return
        end = len(section) - 4
        pcr = ((section[8] & 0x1f) << 8) | section[9]
        info_len = ((section[10] & 0x0f) << 8) | section[11]
        pos = 12 + info_len
        if pos > end:
            return
        chosen = {0, self.pmt_pid}
        if pcr != 0x1fff:
            chosen.add(pcr)
        while pos + 5 <= end:
            pid = ((section[pos + 1] & 0x1f) << 8) | section[pos + 2]
            dlen = ((section[pos + 3] & 0x0f) << 8) | section[pos + 4]
            if pos + 5 + dlen > end:
                return
            chosen.add(pid)
            pos += 5 + dlen
        self.allowed = chosen
        self.ready = True

    def _packet(self, pkt: bytes) -> bool:
        if self.service_id is None:
            return True
        pid = ((pkt[1] & 0x1f) << 8) | pkt[2]
        if pid == 0 or pid == self.pmt_pid:
            adaptation = (pkt[3] >> 4) & 0x03
            if adaptation & 0x01:
                off = 4
                if adaptation & 0x02:
                    off += 1 + pkt[4]
                if off < PACKET_SIZE:
                    section = self._section(pid, pkt[off:], bool(pkt[1] & 0x40))
                    if section is not None:
                        if pid == 0:
                            self._parse_pat(section)
                        elif pid == self.pmt_pid:
                            self._parse_pmt(section)
        return pid in self.allowed

    def feed(self, data: bytes) -> bytes:
        if not data:
            return b""
        buf = self.pending + data
        offset = 0
        retained = []
        while len(buf) - offset >= PACKET_SIZE:
            if buf[offset] != 0x47:
                # Search for a synchronized packet boundary, never guess.
                at = buf.find(b"\x47", offset + 1)
                if at < 0:
                    offset = max(offset, len(buf) - PACKET_SIZE + 1)
                    break
                offset = at
                self.invalid_packets += 1
                continue
            pkt = buf[offset:offset + PACKET_SIZE]
            self.seen_packets += 1
            if self._packet(pkt):
                retained.append(pkt)
            else:
                self.filtered_packets += 1
            offset += PACKET_SIZE
        self.pending = buf[offset:]
        return b"".join(retained)
