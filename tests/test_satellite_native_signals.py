import tempfile,unittest,wave
from pathlib import Path
from satellite_center.native_signal_tools import discover_channels,fm_to_wav
class TestNativeSignals(unittest.TestCase):
 def test_spectral_candidates_provenance(self):
  report={"source":"test.cu8","source_bytes":10000,"complete_time_coverage":False,
          "frequencies_hz":[137890000,137895000,137900000,137905000,137910000],
          "relative_spectrum_db":[-30,-30,-8,-30,-30]}
  data=discover_channels(report)
  self.assertEqual(len(data["candidates"]),1)
  self.assertEqual(data["candidates"][0]["status"],"UNCLASSIFIED_RF_ENERGY_ONLY")
  self.assertTrue(data["candidates"][0]["possible_protocols_not_verified"])
 def test_real_pcm_wav_from_synthetic_fm_iq(self):
  try:import numpy as np
  except ImportError:self.skipTest("NumPy unavailable")
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);sr=1024000;n=sr//5
   t=np.arange(n);audio=np.sin(2*np.pi*440*t/sr)
   ph=np.cumsum(2*np.pi*2500*audio/sr)
   iq=(np.exp(1j*ph)*80)
   pairs=np.column_stack([np.clip(127.5+iq.real,0,255),
                           np.clip(127.5+iq.imag,0,255)]).astype("uint8")
   p=root/"synthetic.cu8";p.write_bytes(pairs.tobytes())
   result=fm_to_wav(p,root,1024000,145800000)
   with wave.open(result["output_wav"],"rb") as w:
    self.assertEqual(w.getframerate(),32000)
    self.assertEqual(w.getnchannels(),1)
    self.assertEqual(w.getnframes(),6400)
   self.assertEqual(result["confidence"],"UNVERIFIED_FM_DEMODULATION")
 def test_unsupported_audio_rate_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"signal.cu8";p.write_bytes(b"\x7f"*8192)
   self.assertRaises(ValueError,fm_to_wav,p,td,44100)
