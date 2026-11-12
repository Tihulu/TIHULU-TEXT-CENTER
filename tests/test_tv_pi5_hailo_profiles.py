"""Pi 5 CPU budget and real Hailo-10H Whisper preflight regressions.

No USB, network, Hailo hardware or PyQt required in this CI suite.
"""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tv_center.pi_hailo import (
    parse_architecture, model_files_ready, readiness, environment)
from tv_center.ai_profiles import hardware_issue, selection_patch
from tv_center.ai_settings import AISettings
from tv_center.media_backend.speech import transcribe_pcm, SpeechError


def pi_hardware(*, arch="HAILO10H", ram=7900, with_hat=True):
    return {
        "ram_mib":ram,"raspberry_pi_5":True,
        "gpu":{"detected":False,"vram_mib":None},
        "npu":{"devices":["hailo0"] if with_hat else [],
               "hailo_arch":arch if with_hat else ""},
    }


def paths(root):
    root=Path(root)
    encoder=root/"whisper-encoder.hef"
    decoder=root/"whisper-decoder.hef"
    npy=root/"decoder-assets"
    npy.mkdir()
    encoder.write_bytes(b"H"*8192)
    decoder.write_bytes(b"D"*8192)
    (npy/"embeddings.npy").write_bytes(b"N"*4096)
    return {"hailo_encoder_hef":str(encoder),
            "hailo_decoder_hef":str(decoder),
            "hailo_npy_dir":str(npy)}


class RaspberryPiModeTests(unittest.TestCase):
    def test_hailo_identity_does_not_confuse_hailo8_with_hailo10h(self):
        self.assertEqual(parse_architecture(
            "Device Architecture: HAILO10H\n"),"HAILO10H")
        self.assertEqual(parse_architecture(
            "Device Architecture: HAILO8L\n"),"HAILO8L")
        self.assertEqual(parse_architecture("Board: Generic PCI accelerator"),"")
        self.assertIn("Hailo-10H",hardware_issue(
            "pi5_hat2",pi_hardware(arch="HAILO8L")))
        self.assertIsNone(hardware_issue("pi5_hat2",pi_hardware()))
        self.assertIn("RAM",hardware_issue(
            "pi5_hat2",pi_hardware(ram=4000)))

    def test_local_assets_are_explicit_and_do_not_download(self):
        with tempfile.TemporaryDirectory() as root:
            values=paths(root)
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("Network forbidden")):
                self.assertTrue(model_files_ready(values))
            self.assertEqual(environment(values)["TIHULU_HAILO_ENCODER_HEF"],
                             values["hailo_encoder_hef"])
            Path(values["hailo_decoder_hef"]).unlink()
            self.assertFalse(model_files_ready(values))

    def test_hailo_status_requires_runtime_arch_and_real_model_files(self):
        with tempfile.TemporaryDirectory() as root:
            values=paths(root)
            hardware=pi_hardware()
            self.assertTrue(readiness(values,hardware=hardware,runtime=True)["ready"])
            self.assertFalse(readiness(values,hardware=hardware,runtime=False)["ready"])
            self.assertFalse(readiness(
                values,hardware=pi_hardware(arch="HAILO8"),runtime=True)["ready"])
            self.assertFalse(readiness(
                values,hardware=pi_hardware(with_hat=False),runtime=True)["ready"])
            Path(values["hailo_encoder_hef"]).unlink()
            self.assertFalse(readiness(values,hardware=hardware,runtime=True)["ready"])

    def test_hat_profile_keeps_cpu_fallback_and_promotes_only_when_ready(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            (root/"ggml-tiny.bin").write_bytes(b"x")
            library=type("Library",(),{
                "root":root,
                "_path":lambda self,key:root/("ggml-"+key+".bin")})()
            installed={"tiny":True,"whisper_cpu":True,"argos":True}
            cpu=selection_patch("pi5_hat2",library=library,
                                hardware=pi_hardware(),status=installed)
            self.assertEqual(cpu["backend"],"cpu")
            accelerated=selection_patch(
                "pi5_hat2",library=library,
                hardware=pi_hardware(),status=installed,hailo_ready=True)
            self.assertEqual(accelerated["backend"],"npu")
            self.assertEqual(accelerated["model_path"],cpu["model_path"])
            self.assertEqual(accelerated["pi_cpu_threads"],3)

    def test_vanilla_pi_cpu_budget_set_without_preset_selection(self):
        with tempfile.TemporaryDirectory() as root:
            s=AISettings(Path(root)/"ai.json")
            self.assertEqual(s.values["active_profile"],"")
            with patch("pathlib.Path.read_text",
                       return_value="Raspberry Pi 5 Model B Rev 1.0"):
                s.configure_environment()
            self.assertEqual(os.environ.get("TIHULU_PI_CPU_THREADS"),"3")
            os.environ.pop("TIHULU_PI_CPU_THREADS",None)
            with self.assertRaises(ValueError):
                s.update({"pi_cpu_threads":8})

    def test_whisper_cli_uses_pi_threads_only_when_configured(self):
        commands=[]
        def fake_run(argv,**kwargs):
            commands.append(argv)
            output=Path(argv[argv.index("-of")+1]+".txt")
            output.write_text("Guten Tag",encoding="utf-8")
            return SimpleNamespace(returncode=0)
        profile={"speech":{"model_path":"/model/ggml-tiny.bin",
                           "executable":"/usr/local/bin/whisper-cli"}}
        with patch.dict(os.environ,{"TIHULU_PI_CPU_THREADS":"3"}):
            with patch("tv_center.media_backend.speech.subprocess.run",side_effect=fake_run):
                answer=transcribe_pcm(bytes(64000),"de","cpu",profile)
        self.assertEqual(answer,"Guten Tag")
        self.assertEqual(commands[0][-2:],["-t","3"])
        commands.clear()
        with patch.dict(os.environ,{"TIHULU_PI_CPU_THREADS":""}):
            with patch("tv_center.media_backend.speech.subprocess.run",side_effect=fake_run):
                transcribe_pcm(bytes(64000),"de","cpu",profile)
        self.assertNotIn("-t",commands[0])

    def test_npu_error_falls_back_only_for_hat_profile_when_enabled(self):
        from tv_center.captions import asr_from_clip
        streams=[{"codec_type":"audio","index":0,"tags":{"language":"de"}}]
        def speech(pcm,lang,backend,profile):
            if backend=="npu":
                raise SpeechError("Hailo hardware busy")
            return "Hallo Welt"
        dummy={"speech":{"model_path":"/models/tiny.bin",
                         "ready_cpu":True,"ready_npu":True,
                         "npu_engine":"hailo_whisper",
                         "executable":"/usr/bin/whisper-cli"}}
        def backend(_,requested):
            return {"selected":requested,"ready":True}
        diagnostics={}
        with patch.dict(os.environ,{"TIHULU_TV_ASR_BACKEND":"npu"}):
            with (patch("tv_center.captions._program_streams",return_value=streams),
                  patch("tv_center.captions._run",
                        return_value=SimpleNamespace(returncode=0,
                                                     stdout=bytes(64000))),
                  patch("tv_center.media_backend.compute.detect_devices",return_value=dummy),
                  patch("tv_center.media_backend.compute.choose_backend",side_effect=backend),
                  patch("tv_center.media_backend.speech.transcribe_pcm",side_effect=speech),
                  patch("tv_center.ai_settings.AISettings") as ai):
                ai.return_value.values={
                    "active_profile":"pi5_hat2","hailo_cpu_fallback":True}
                result=asr_from_clip(Path("/fake/recording.ts"),
                     "de","/fake/tiny.bin",diagnostics=diagnostics)
        self.assertEqual(result,"Hallo Welt")
        self.assertEqual(diagnostics["backend"],"cpu")
        self.assertEqual(diagnostics["npu_fallback"],"Whisper Tiny CPU")


if __name__=="__main__":
    unittest.main()
