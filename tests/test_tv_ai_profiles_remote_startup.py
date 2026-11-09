"""Offline regressions for preset selection, remote TLS opt-in, fast startup."""
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center import ai_profiles
from tv_center.ai_settings import AISettings
from tv_center.hardware_market import quick_hardware
from tv_center.remote_gpu import (
    validate_endpoint, save_token, read_token, delete_token, transcribe)


def hardware(*, pi5=False, ram=65536, vram=16303, hailo=False):
    return {"ram_mib":ram,"raspberry_pi_5":pi5,
            "gpu":{"detected":vram>0,"vram_mib":vram},
            "npu":{"devices":["hailo0"] if hailo else [],
                   "hailo_arch":"HAILO10H" if hailo else ""}}


class ProfileTests(unittest.TestCase):
    def test_five_profiles_have_real_curated_components_only(self):
        self.assertEqual(tuple(ai_profiles.PROFILES),(
            "pi5","pi5_hat2","normal","performance","experimental"))
        for key,profile in ai_profiles.PROFILES.items():
            self.assertTrue(all(name in ai_profiles.COMPONENTS
                                for name in profile["components"]))
            self.assertIn(profile["backend"],("cpu","gpu"))
            self.assertNotIn("hailo_whisper",profile["components"])
        self.assertEqual(ai_profiles.PROFILES["pi5_hat2"]["backend"],"cpu")

    def test_pi_hat_does_not_add_npu_memory_to_host_ram(self):
        self.assertIn("RAM",ai_profiles.hardware_issue(
            "pi5_hat2",hardware(pi5=True,ram=3800,hailo=True)))
        self.assertIn("Hailo",ai_profiles.hardware_issue(
            "pi5_hat2",hardware(pi5=True,ram=8000,hailo=False)))
        self.assertIsNone(ai_profiles.hardware_issue(
            "pi5_hat2",hardware(pi5=True,ram=8000,hailo=True)))

    def test_performance_5080_is_ok_but_experimental_requires_more_vram(self):
        self.assertIsNone(ai_profiles.hardware_issue(
            "performance",hardware(vram=16303)))
        self.assertIn("VRAM",ai_profiles.hardware_issue(
            "experimental",hardware(vram=16303)))
        self.assertIsNone(ai_profiles.hardware_issue(
            "experimental",hardware(vram=32768)))

    def test_install_all_does_not_auto_activate_and_is_resumable(self):
        calls=[]
        with tempfile.TemporaryDirectory() as root:
            lib=type("FakeLibrary",(),{"root":Path(root),
                  "_path":lambda self,key:Path(root)/("ggml-"+key+".bin")})()
            installed={"whisper_cpu"}
            def status(key,**kwargs):
                return key in installed
            def install(key):
                calls.append(key)
                installed.add(key)
            with patch("tv_center.ai_profiles.local_status",side_effect=status):
                result=ai_profiles.install_components(
                    "normal",library=lib,installer=install)
            self.assertEqual(calls,["small","argos"])
            self.assertEqual(result[0],("whisper_cpu","already installed"))
            self.assertEqual(ai_profiles.missing_components(
                "normal",{key:True for key,_ in result}),())

    def test_select_only_complete_models(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"ggml-small.bin"
            p.touch()
            lib=type("FakeLibrary",(),{"root":Path(root),
                 "_path":lambda self,key:p})()
            with self.assertRaisesRegex(RuntimeError,"missing"):
                ai_profiles.selection_patch("normal",library=lib,
                    hardware=hardware(),
                    status={"whisper_cpu":True,"small":True,"argos":False})
            chosen=ai_profiles.selection_patch("normal",library=lib,
                hardware=hardware(),
                status={"whisper_cpu":True,"small":True,"argos":True})
            self.assertEqual(chosen["active_profile"],"normal")
            self.assertEqual(chosen["backend"],"cpu")

    def test_settings_reject_remote_without_owner_opt_in(self):
        with tempfile.TemporaryDirectory() as home:
            s=AISettings(Path(home)/"ai.json")
            self.assertEqual(s.values["active_profile"],"")
            with self.assertRaises(ValueError):
                s.update({"backend":"remote"})
            s.update({"remote_gpu_enabled":True,"backend":"remote",
                      "remote_gpu_url":"https://gpu.example:8443"})
            self.assertEqual(AISettings(Path(home)/"ai.json").values[
                "remote_gpu_enabled"],True)

    def test_quick_hardware_no_subprocess(self):
        with patch("subprocess.run",side_effect=AssertionError("Must not probe")):
            snapshot=quick_hardware()
        self.assertIsNone(snapshot["gpu"]["vram_mib"])


class RemoteGPUTests(unittest.TestCase):
    def test_only_fixed_tls_endpoint_no_userinfo_no_redirects(self):
        self.assertEqual(validate_endpoint("https://gpu.example:8443"),
                         "https://gpu.example:8443/v1/transcribe")
        for url in ("http://gpu.example", "https://user:pass@gpu.example",
                    "https://gpu.example/redirect", "https://gpu.example?q=1",
                    "file:///etc/passwd", "https://gpu.example#fragment"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                validate_endpoint(url)

    def test_token_is_private_and_removable(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"private-token"
            save_token("ThisIsASecretToken1234",path=path)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(read_token(path=path),"ThisIsASecretToken1234")
            os.chmod(path,0o644)
            with self.assertRaises(ValueError):
                read_token(path=path)
            os.chmod(path,0o600)
            delete_token(path=path)
            self.assertFalse(path.exists())

    def test_remote_audio_sent_only_when_explicitly_called(self):
        with patch("tv_center.remote_gpu._request",return_value={
                "text":"Guten Tag","words":[
                    {"text":"Guten","start":0.1,"end":0.3}],
                "language":"de"}) as request,patch(
                    "tv_center.remote_gpu.read_token",return_value="Secret"):
            result=transcribe(b"\\0\\0"*32000,"de","https://gpu.example")
        self.assertEqual(result["text"],"Guten Tag")
        self.assertEqual(request.call_count,1)
        self.assertEqual(request.call_args.args[0],"https://gpu.example")


class DeferredStartupTests(unittest.TestCase):
    def test_model_market_and_native_tv_window_avoid_synchronous_ai_startup(self):
        # CI deliberately runs headless without PyQt5; inspect source
        # rather than importing desktop.py's eagerly imported Qt scan UI.
        source=Path(__file__).resolve().parent.parent/"tv_center"
        ui=(source/"settings_ui.py").read_text(encoding="utf-8")
        desktop=(source/"desktop.py").read_text(encoding="utf-8")
        self.assertIn("quick_hardware()",ui)
        # GPU/Argos scans now occur only on the corresponding tab; the
        # selected preset gets one worker inventory after first paint.
        self.assertIn("QTimer.singleShot(180, self.inspect_profile)",ui)
        self.assertIn("self.model_tabs.currentChanged.connect(",ui)
        self.assertIn("def on_model_tab_changed",ui)
        self.assertIn("threading.Thread(target=scan",ui)
        self.assertIn("def _show_argos",ui)
        self.assertIn("def _show_starter",ui)
        self.assertIn("def show_ai_inventory",desktop)
        self.assertIn("self._ai_inventory_results.put(info)",desktop)
        self.assertIn("self._ai_inventory_results.get_nowait()",desktop)


if __name__=="__main__":
    unittest.main()
