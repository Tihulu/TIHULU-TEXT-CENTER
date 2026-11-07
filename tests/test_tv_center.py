import tempfile
from pathlib import Path
import unittest
from tv_center.core import read_channels, zap_argv, player_argv, Channel, parse_signal_log
from tv_center.captions import ass_text, decode_segment
from tv_center.bridge import TVBridge
from tv_center.ts import ServiceFilter

class NativeTVTests(unittest.TestCase):
    def test_dvbv5_channels_and_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "channels.conf"
            conf.write_text("[arte HD]\nFREQUENCY = 538000000\nSERVICE_ID = 100\n\n"
                            "[KiKA HD]\nFREQUENCY = 538000000\nSERVICE_ID = 101\n")
            channels = read_channels([conf, conf])
            self.assertEqual([c.name for c in channels], ["arte HD", "KiKA HD"])
            self.assertEqual(channels[0].service_id, 100)
            self.assertEqual(zap_argv(channels[0])[-1], "arte HD")
            self.assertNotIn("--program=100", player_argv(channels[0], 42))
            self.assertIn("--input-ipc-server=/tmp/tv.sock",
                          player_argv(channels[0], 42, ipc_path="/tmp/tv.sock"))
            self.assertIn("--hwdec=no", player_argv(channels[0], 42))
            self.assertIn("--gpu-context=x11", player_argv(channels[0], 42))
            self.assertIn("--vo=x11", player_argv(channels[0], 42, renderer="x11-compat"))
            with self.assertRaises(ValueError):
                player_argv(channels[0], 0)

    def test_ass_parser_uses_only_real_dialogue(self):
        raw = "Header\nDialogue: 0,0:00:01,0:00:05,Default,,0,0,0,,{\\i1}Guten Tag\\Nzusammen\n"
        self.assertEqual(ass_text(raw), "Guten Tag zusammen")

    def test_missing_stream_is_not_fabricated(self):
        result = decode_segment(b"", mode="auto", page=150)
        self.assertEqual(result["original"], "")

    def test_real_signal_parser(self):
        text = ("Lock   (0x1f) Signal= -64.00dBm C/N= 18.50dB UCB= 900 postBER= 1e-6\n"
                "Carrier(0x03) Signal= -64.00dBm\n"
                "Lock   (0x1f) Signal= -64.00dBm C/N= 21.50dB UCB= 915 postBER= 0\n")
        result = parse_signal_log(text)
        self.assertEqual(result["ucb_delta"], 15)
        self.assertEqual(result["loss_indications"], 1)
        self.assertEqual(result["cn_max_db"], 21.5)

    def test_selected_program_transport_filter(self):
        # Complete PAT: service 100 -> PMT PID 0x100; service 101 -> 0x101
        pat = bytes.fromhex("00 b0 11 00 01 c1 00 00 00 64 e1 00 00 65 e1 01 00 00 00 00")
        # Program 100 PMT: PCR/video PID 0x200, audio 0x201, Teletext 0x202
        pmt = bytes.fromhex("02 b0 1c 00 64 c1 00 00 e2 00 f0 00"
                            " 24 e2 00 f0 00 0f e2 01 f0 00 06 e2 02 f0 00 00 00 00 00")
        def packet(pid, payload, start=False):
            if len(payload) > 184:
                raise ValueError("test payload too big")
            head = bytes([0x47, ((pid >> 8) & 0x1f) | (0x40 if start else 0),
                          pid & 0xff, 0x10])
            return head + payload + bytes([0xff]) * (184-len(payload))
        chunks = [packet(0, b"\\x00"+pat, True),
                  packet(0x100, b"\\x00"+pmt, True),
                  packet(0x200, b"video"),
                  packet(0x201, b"audio"),
                  packet(0x202, b"teletext"),
                  packet(0x300, b"other program")]
        filt = ServiceFilter(100)
        output = filt.feed(b"".join(chunks))
        result = [((output[n+1]&0x1f)<<8)|output[n+2]
                  for n in range(0, len(output), 188)]
        self.assertEqual(result, [0, 0x100, 0x200, 0x201, 0x202])
        self.assertTrue(filt.ready)
        self.assertEqual(filt.filtered_packets, 1)

    def test_bridge_refuses_lan_listener(self):
        with self.assertRaises(ValueError):
            TVBridge(lambda: {}, lambda p: None, host="0.0.0.0")

if __name__ == "__main__":
    unittest.main()
