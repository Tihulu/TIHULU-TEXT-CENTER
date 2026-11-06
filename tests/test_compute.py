import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from textcenter.compute import inventory_compute,resolve_device,LANG_PAIRS


class ComputeTest(unittest.TestCase):
    def test_cpu_gpu_hailo_detection_without_claiming_npu_support(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cpu=root/"cpuinfo";cpu.write_text("model name : Test CPU 42\n")
            card=root/"drm"/"card0"/"device"
            card.mkdir(parents=True)
            (card/"vendor").write_text("0x10de")
            (card/"device").write_text("0x2684")
            dev=root/"dev";dev.mkdir()
            (dev/"hailo0").touch()
            data=inventory_compute(cpuinfo=cpu,drm_root=root/"drm",dev_root=dev,
                 lookup=lambda name:None,include_driver_query=False,
                 package_lookup=lambda name:name in ("faster_whisper","ctranslate2"))
            self.assertEqual(data["devices"][0]["name"],"Test CPU 42")
            self.assertEqual(len(data["devices"]),3)
            self.assertFalse(data["devices"][2]["inference_compatible"])
            self.assertFalse(data["npu_asr_adapter_integrated"])
            self.assertEqual(len(data["translation_pairs"]),6)
            with self.assertRaises(ValueError):
                resolve_device("hailo:hailo0",data)

    def test_model_directory_and_manual_cpu_cuda_validation(self):
        with tempfile.TemporaryDirectory() as td:
            model=Path(td)/"model"
            model.mkdir()
            (model/"model.bin").write_bytes(b"fixture")
            with patch.dict("os.environ",{"TIHULU_WHISPER_MODEL":str(model)}):
                info=inventory_compute(
                    cpuinfo=Path(td)/"cpu",drm_root=Path(td)/"empty",
                    dev_root=Path(td)/"dev",
                    lookup=lambda _:None,include_driver_query=False,
                    package_lookup=lambda pkg:pkg=="faster_whisper")
            info["devices"].append({"id":"cuda:0","name":"Synthetic RTX","kind":"gpu"})
            info["runtimes"]["ctranslate2"]=True
            self.assertEqual(resolve_device("cpu",info)["backend"],"cpu")
            self.assertEqual(resolve_device("auto",info,validate_cuda=lambda _:False)["selected"],"cpu")
            self.assertEqual(resolve_device("auto",info,validate_cuda=lambda _:True)["selected"],"cuda:0")
            self.assertEqual(resolve_device("cuda:0",info,validate_cuda=lambda _:True)["device_name"],"Synthetic RTX")
            with self.assertRaises(ValueError):
                resolve_device("cuda:999",info,validate_cuda=lambda _:True)


if __name__=="__main__":
    unittest.main()
