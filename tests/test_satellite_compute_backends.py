"""Compute capability selection tests: no synthetic hardware or claimed RF."""
import math
import struct
import unittest

from satellite_center.compute_backends import (
    compute_capabilities, resolve_compute_backend, vectorized_frequency_trace,
)
from satellite_center.sstv_series35 import _trace


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
