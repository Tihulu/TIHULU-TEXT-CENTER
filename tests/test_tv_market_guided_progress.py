"""AI Model Market quick-open, guided download progress and Custom-mode tests.

The Qt UI can run without PyQt in CI by parsing its AST; no runtime probe,
network, or model installation is performed by this test module.
"""
import ast
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center.ai_profiles import (
    PROFILES, COMPONENT_DOWNLOADS, component_estimate,
    progress_fraction, install_components)
from tv_center.model_market import ModelLibrary


class ProfileDownloadTests(unittest.TestCase):
    def test_release_profiles_use_hardware_minimums_not_a_specific_pc(self):
        self.assertIn("NVIDIA CUDA",PROFILES["performance"]["name"])
        self.assertIn("min 12 GB VRAM",PROFILES["performance"]["name"])
        self.assertNotIn("RTX 5080",PROFILES["performance"]["name"])
        self.assertEqual(PROFILES["performance"]["min_vram_mib"],12000)
        self.assertEqual(PROFILES["performance"]["min_ram_mib"],16000)
        for key,p in PROFILES.items():
            for code in p["components"]:
                self.assertIn(code,COMPONENT_DOWNLOADS)
                self.assertTrue(component_estimate(code))

    def test_progress_requires_true_known_positive_content_length(self):
        self.assertEqual(progress_fraction(25,100),250)
        self.assertEqual(progress_fraction(200,100),1000)
        for received,total in ((15,None),(-2,10),(0,0),(0,-1),
                               ("10",100),(1.2,5)):
            self.assertIsNone(progress_fraction(received,total))

    def test_install_all_emits_real_component_status_without_auto_select(self):
        with tempfile.TemporaryDirectory() as root:
            library=type("FakeLibrary",(),{
                "root":Path(root),
                "_path":lambda self,key:Path(root)/(key+".bin")})()
            installed={"whisper_cpu"}
            events=[]
            calls=[]
            def status(code,**kwargs):
                return code in installed
            def installer(code):
                calls.append(code)
                installed.add(code)
            with patch("tv_center.ai_profiles.local_status",side_effect=status):
                result=install_components("normal",library=library,
                    events=events.append,installer=installer)
            self.assertEqual(calls,["small","argos","resemblyzer","sound_labels"])
            self.assertEqual(result[0],("whisper_cpu","already installed"))
            self.assertEqual([(e["component"],e["state"]) for e in events],[
                ("whisper_cpu","checking"),
                ("whisper_cpu","already installed"),
                ("small","checking"),("small","installing"),
                ("small","verifying"),("small","installed"),
                ("argos","checking"),("argos","installing"),
                ("argos","verifying"),("argos","installed"),
                ("resemblyzer","checking"),("resemblyzer","installing"),
                ("resemblyzer","verifying"),("resemblyzer","installed"),
                ("sound_labels","checking"),("sound_labels","installing"),
                ("sound_labels","verifying"),("sound_labels","installed"),
            ])
            self.assertNotIn("active_profile",events[-1])

    def test_real_http_content_length_not_safety_limit_used_for_progress(self):
        class Response(io.BytesIO):
            def __init__(self,data,length):
                super().__init__(data)
                self.url="https://huggingface.co/weights"
                self.headers=({} if length is None else
                              {"Content-Length":str(length)})
        payload=b"A"*8192
        digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as root:
            market=ModelLibrary(root)
            market.catalog["tiny"]={
                "filename":"ggml-tiny.bin", "sha256":digest,
                "url":"https://huggingface.co/weights",
                "max_bytes":1000000,"size_mb":1,"name":"test"}
            for size in (len(payload),None):
                (Path(root)/"ggml-tiny.bin").unlink(missing_ok=True)
                result=[]
                with patch("tv_center.model_market.urllib.request.urlopen",
                           return_value=Response(payload,size)):
                    market.download("tiny",progress=lambda got,total:
                                    result.append((got,total)))
                self.assertEqual(result[-1],(len(payload),size))
                self.assertEqual(
                    (Path(root)/"ggml-tiny.bin").read_bytes(),payload)


class ModelMarketFastStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui=(Path(__file__).resolve().parent.parent/
                "tv_center/settings_ui.py").read_text(encoding="utf-8")
        tree=ast.parse(cls.ui)
        factory=next(node for node in tree.body
                     if isinstance(node,ast.FunctionDef)
                     and node.name=="open_ai_settings")
        cls.manager=next(node for node in factory.body
                         if isinstance(node,ast.ClassDef)
                         and node.name=="Manager")

    def method(self,name):
        return next(node for node in self.manager.body
                    if isinstance(node,ast.FunctionDef) and node.name==name)

    def test_first_paint_does_not_call_heavy_inventory(self):
        init=self.method("__init__")
        direct_calls=[]
        for node in ast.walk(init):
            if (isinstance(node,ast.Call) and
                    isinstance(node.func,ast.Attribute) and
                    isinstance(node.func.value,ast.Name) and
                    node.func.value.id=="self"):
                direct_calls.append(node.func.attr)
        for name in ("inspect_nllb","inspect_speaker","inspect_compute",
                     "inspect_starter","inspect_argos","inspect_all_status"):
            self.assertNotIn(name,direct_calls)
        self.assertIn("QTimer.singleShot(180, self.inspect_profile)",self.ui)

    def test_profile_widgets_have_status_and_progress_for_every_component(self):
        present=self.ui
        self.assertIn("self.profile_rows_layout.addWidget(widget)",present)
        self.assertIn("QProgressBar()",present)
        self.assertIn("component_estimate(code)",present)
        self.assertIn('elif kind == "model_event":',present)
        self.assertIn("events=lambda event:self.work.put((",present)
        self.assertIn("self._set_component_state(",present)

    def test_custom_is_live_and_apply_does_not_trigger_custom(self):
        text=self.ui
        self.assertIn('self.profile_choice.addItem("Custom · manually adjusted", "custom")',text)
        self.assertIn("self.mark_manual_custom",text)
        self.assertIn("self.preview_profile_controls(key)",text)
        self.assertIn("self.populate_models()",text)
        self.assertIn("PREVIEW ONLY",text)
        self.assertIn("no downloads or settings changes were saved",text)
        self.assertIn("self.profile_choice.blockSignals(True)",text)
        self.assertIn("self._applying_profile=True",text)
        self.assertIn("self._manual_custom=False",text)
        self.assertIn("not self._manual_custom and spec",text)
        self.assertIn("self.model_path.setText(data[\"patch\"][\"model_path\"])",text)
        self.assertIn("self.translation_choice.setCurrentIndex(",text)

    def test_profile_details_render_real_linebreaks(self):
        source=ast.get_source_segment(self.ui,self.method("show_profile_description"))
        self.assertNotIn('\\\\nEstimated',source)
        self.assertIn('\\nEstimated disk',source)


if __name__=="__main__":
    unittest.main()
