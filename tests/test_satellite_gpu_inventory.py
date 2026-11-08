"""Native GPU inventory is not the same as usable CUDA/CuPy DSP."""
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from satellite_center.compute_backends import detect_gpu_hardware, compute_capabilities


class GPUInventoryTests(unittest.TestCase):
    def tearDown(self):
        detect_gpu_hardware.cache_clear()
        compute_capabilities.cache_clear()

    def test_nvidia_smi_detects_physical_gpu_without_cuda_claim(self):
        detect_gpu_hardware.cache_clear()
        output=SimpleNamespace(returncode=0,
            stdout="NVIDIA GeForce RTX 5080, 595.104.02\n",stderr="")
        with patch("satellite_center.compute_backends.shutil.which",
                   side_effect=lambda name:"/usr/bin/nvidia-smi" if name=="nvidia-smi" else None), patch(
                   "satellite_center.compute_backends.subprocess.run",
                   return_value=output) as run:
            found=detect_gpu_hardware()
        self.assertTrue(found["detected"])
        self.assertEqual(found["devices"],["NVIDIA GeForce RTX 5080"])
        self.assertEqual(found["source"],"nvidia-smi")
        self.assertEqual(found["driver"],"595.104.02")
        run.assert_called_once()

    def test_no_vendor_executable_is_not_assumed_present(self):
        detect_gpu_hardware.cache_clear()
        with patch("satellite_center.compute_backends.shutil.which",return_value=None):
            found=detect_gpu_hardware()
        self.assertFalse(found["detected"])

    def test_browser_native_ui_distinguishes_webgpu_and_cuda(self):
        root=Path(__file__).resolve().parents[1]/"satellite_center"
        compute=(root/"browser"/"compute_selector.mjs").read_text()
        bridge=(root/"native_desktop_bridge.js").read_text()
        html=(root/"browser"/"index.html").read_text()
        self.assertIn("nativeGpu",compute)
        self.assertIn("Native OS GPU detected",compute)
        self.assertIn("window.nativeComputeStatus=()=>",bridge)
        self.assertIn('id="native-gpu-discovery"',html)


if __name__=="__main__":
    unittest.main()
