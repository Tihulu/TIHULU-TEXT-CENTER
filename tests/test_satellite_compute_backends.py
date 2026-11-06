"""Compute capability selection tests: no synthetic hardware or claimed RF."""
import math
import struct
import unittest

from satellite_center.compute_backends import (
    compute_capabilities, resolve_compute_backend, vectorized_frequency_trace,
)
from satellite_center.sstv_series35 import _trace
from satellite_center.npu_sstv import scan_real_npu_tones, probe_real_sstv_npu
from unittest.mock import patch



class BackendTests(unittest.TestCase):
    def setUp(self):
        self.caps = {
            "cpu": {"available": True, "implementation": "NumPy vectorization"},
            "gpu": {"available": True, "name": "Mock capability only"},
            "npu": {"available": False, "reason": "No real Robot36 NPU kernel"},
        }

    def test_auto_optimizes_length_only_when_gpu_kernel_is_available(self):
        self.assertEqual(resolve_compute_backend(seconds=36, capabilities=self.caps)["selected_targets"], ["cpu"])
        self.assertEqual(resolve_compute_backend(seconds=240, capabilities=self.caps)["selected_targets"], ["cpu", "gpu"])
        self.caps["gpu"]["available"] = False
        self.assertEqual(resolve_compute_backend(seconds=240, capabilities=self.caps)["selected_targets"], ["cpu"])

    def test_custom_multi_devices_and_npu_are_not_faked(self):
        plan = resolve_compute_backend("custom", ["cpu", "gpu"], seconds=500, capabilities=self.caps)
        self.assertEqual(plan["trace_backend"], "cupy-cuda")
        self.assertIn("pixel assembly", plan["cpu_mandatory_stages"])
        with self.assertRaisesRegex(ValueError, "unavailable"):
            resolve_compute_backend("custom", ["cpu", "npu"], capabilities=self.caps)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            resolve_compute_backend("custom", ["cpu", "cpu"], capabilities=self.caps)
        with self.assertRaisesRegex(ValueError, "Select"):
            resolve_compute_backend("custom", [], capabilities=self.caps)

    def test_probes_do_not_infer_npu_from_chips(self):
        caps = compute_capabilities()
        self.assertTrue(caps["cpu"]["available"])
        self.assertFalse(caps["npu"]["available"])
        self.assertIn("kernel", caps["npu"]["reason"])

    def test_available_real_npu_supports_cpu_npu_and_cpu_gpu_npu(self):
        self.caps["npu"] = {"available": True, "auto_beneficial": True,
                             "name": "test hardware status only"}
        plan = resolve_compute_backend("custom", ["cpu", "gpu", "npu"],
                                       capabilities=self.caps, seconds=180)
        self.assertEqual(plan["selected_targets"], ["cpu", "gpu", "npu"])
        self.assertEqual(len(plan["npu_stages"]), 1)
        self.assertEqual(resolve_compute_backend(seconds=180, capabilities=self.caps)["selected_targets"],
                         ["cpu", "gpu", "npu"])
        self.caps["npu"]["auto_beneficial"] = False
        self.assertEqual(resolve_compute_backend(seconds=180, capabilities=self.caps)["selected_targets"],
                         ["cpu", "gpu"])

    def test_npu_pcm_is_processed_by_real_matrix_inference_api(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy optional")
        rate = 8000
        width = 64
        bins = np.zeros((width, 16), dtype=np.float32)
        for i in range(width):
            for j, hz in enumerate((1000, 1100, 1200, 1300, 1450, 1600, 1900, 2300)):
                bins[i, 2*j] = np.cos(2*math.pi*hz*i/rate)
                bins[i, 2*j+1] = np.sin(2*math.pi*hz*i/rate)
        class FakeCompiled:
            def input(self, n): return "pcm"
            def output(self, n): return "dft"
            def __call__(self, inp):
                return {"dft": inp["pcm"] @ bins}
        kernel = {"compiled": FakeCompiled(), "np": np,
                  "window_samples": width, "sample_rate": rate}
        samples = [int(12000*math.sin(2*math.pi*1200*i/rate))
                   for i in range(rate)]
        raw = struct.pack("<"+"h"*len(samples), *samples)
        # Stub verifies numerical dataflow only: NOT evidence of physical NPU.
        with patch("satellite_center.npu_sstv._build_npu_kernel", return_value=kernel):
            report = scan_real_npu_tones(raw, rate)
        self.assertEqual(report["windows_processed"], 497)
        self.assertGreater(report["sync_tone_1200_window_count"], 0)
        self.assertFalse(report["image_or_iss_verified"])

    def test_openvino_npu_never_reports_hardware_when_probe_fails(self):
        with patch("satellite_center.npu_sstv._build_npu_kernel",
                   side_effect=RuntimeError("No real NPU")):
            info = probe_real_sstv_npu()
        self.assertFalse(info["available"])
        self.assertIn("No real NPU", info["reason"])

    def test_numpy_trace_agrees_with_portable_real_pcm_math(self):
        try:
            import numpy  # noqa
        except ImportError:
            self.skipTest("NumPy optional and not installed")
        rate = 8000
        values = [int(10000 * math.sin(2 * math.pi * 1200 * i / rate))
                  for i in range(rate * 2)]
        raw = struct.pack("<" + "h" * len(values), *values)
        portable = _trace(raw, rate)
        accelerated = vectorized_frequency_trace(raw, rate)
        self.assertEqual(len(portable), len(accelerated))
        self.assertLess(max(abs(a - b) for a, b in zip(portable[100:-100],
                                                        accelerated[100:-100])), 10.0)


if __name__ == "__main__":
    unittest.main()
