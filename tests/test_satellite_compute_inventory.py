"""CPU/GPU/NPU discovery must not imply a working decoder or fake accelerator."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from satellite_center.compute_backends import detect_compute_inventory

class NativeComputeInventoryTests(unittest.TestCase):
    def test_media_center_style_physical_hardware_vs_runnable_kernels(self):
        gpu={"detected":True,"devices":["NVIDIA GeForce RTX 5080"],
             "driver":"595.104","source":"nvidia-smi"}
        npu={"available":False,"reason":"No Intel OpenVINO NPU kernel"}
        # Even a physical Hailo node is NOT an OpenVINO Robot36 kernel.
        fake_dev=SimpleNamespace(glob=lambda pattern:[SimpleNamespace(name="hailo0")])
        with patch("satellite_center.compute_backends.platform.system",return_value="Linux"), patch(
             "satellite_center.compute_backends.Path",return_value=fake_dev):
            inventory=detect_compute_inventory(gpu,npu)
        self.assertTrue(inventory["cpu"]["detected"])
        self.assertGreaterEqual(inventory["cpu"]["logical_cores"],1)
        self.assertEqual(inventory["gpu"]["names"],["NVIDIA GeForce RTX 5080"])
        self.assertFalse(inventory["gpu"]["runtime_ready"])
        self.assertTrue(inventory["npu"]["detected"])
        self.assertFalse(inventory["npu"]["runtime_ready"])
        self.assertIn("Hailo hailo0",inventory["npu"]["names"])
    def test_no_hardware_does_not_generate_devices(self):
        gpu={"detected":False,"devices":[],"driver":None,
             "source":"no working OS GPU inventory"}
        npu={"available":False}
        with patch("satellite_center.compute_backends.platform.system",return_value="Windows"):
            inventory=detect_compute_inventory(gpu,npu)
        self.assertFalse(inventory["gpu"]["detected"])
        self.assertFalse(inventory["npu"]["detected"])
        self.assertFalse(inventory["gpu"]["runtime_ready"])
        self.assertFalse(inventory["npu"]["runtime_ready"])
