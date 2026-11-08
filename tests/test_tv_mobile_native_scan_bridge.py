"""Actual native DVB web dispatch and conditional satellite UI regression tests.

No tuner or Qt display is needed; these tests never claim hardware scan success.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
from tv_center.web_desktop import TVWebMixin


class FakeChoice:
    def __init__(self, choices, selected=0):
        self.options=list(choices)
        self.selected=selected
    def findData(self, value):
        return self.options.index(value) if value in self.options else -1
    def setCurrentIndex(self, value):
        self.selected=value
    def currentData(self):
        return self.options[self.selected]


class NativeRemoteHost(TVWebMixin):
    def __init__(self):
        self.country=FakeChoice(["DE","TR"])
        self.delivery=FakeChoice(["t","c","s"])
        self.satellite=FakeChoice(["S42E0","S13E0"])
        self.diseqc=FakeChoice([None,0,1,2,3])
        self.scanner=SimpleNamespace(running=False)
        self.capture=SimpleNamespace(adapter=0,thread=None)
        self.web_scan_events=[]
        self.web_scan_requested=False
        self.web_scan_remote=False
        self.scan_calls=[]
        self.signal_result=SimpleNamespace(text=lambda:"C/N: 12 dB (last measured)")
        self.statusbar=SimpleNamespace(text=lambda:"Receiver idle")
    def current_profile(self):
        return self.country.currentData()+"-"+self.delivery.currentData()
    def scan_channels(self, confirmed=False):
        self.scan_calls.append(confirmed)
        self.web_scan_requested=True
        return True


class NativePairedScanTests(TestCase):
    def test_remote_terrestrial_scan_starts_real_native_method_once(self):
        host=NativeRemoteHost()
        result=host.web_action("scan_start",{"country":"DE","medium":"t"})
        self.assertEqual(result["backend"],"native_tv_center")
        self.assertTrue(result["scan_requested"])
        self.assertEqual(host.scan_calls,[True])
        self.assertTrue(host.web_scan_requested)
        self.assertEqual(host.diseqc.currentData(),None)
        self.assertTrue(host.web_scan_events)
        with self.assertRaises(RuntimeError):
            host.web_action("scan_start",{"country":"DE","medium":"t"})
        self.assertEqual(host.scan_calls,[True])

    def test_satellite_position_and_diseqc_only_apply_to_satellite(self):
        host=NativeRemoteHost()
        result=host.web_action("scan_start",{"country":"DE","medium":"s",
                             "satellite":"S13E0","diseqc_port":1})
        self.assertTrue(result["scan_requested"])
        self.assertEqual(host.satellite.currentData(),"S13E0")
        self.assertEqual(host.diseqc.currentData(),1)
        host.web_scan_requested=False
        with self.assertRaisesRegex(ValueError,"DiSEqC"):
            host.web_action("scan_start",{"country":"DE","medium":"s",
                                            "diseqc_port":5})
        self.assertEqual(len(host.scan_calls),1)

    def test_real_scan_state_never_invents_cn_ucb_signal(self):
        host=NativeRemoteHost()
        host.web_scan_events=[
          {"stage":1,"kind":"frequency","frequency":"538.000 MHz"},
          {"stage":2,"kind":"found","channel":"Real Test","count":1},
          {"stage":2,"kind":"signal",
           "metrics":{"available":False,"reason":"Scanner owns the frontend"}}]
        host.web_scan_requested=True
        with mock.patch("tv_center.web_desktop.receiver_status",
                        return_value={"adapter":0,"frontend_present":True,
                                      "frontend":"/dev/dvb/adapter0/frontend0"}), \
             mock.patch("tv_center.web_desktop.check_dependencies",
                        return_value={"w_scan_cpp":True,"dvbv5-scan":True,"fuser":True}), \
             mock.patch("tv_center.web_desktop.Path.glob",
                        return_value=[]):
            result=host.web_action("scan_status",{})
        self.assertTrue(result["running"])
        self.assertEqual(result["backend"],"native_tv_center")
        self.assertEqual(result["discovered_services"],1)
        self.assertFalse(result["signal_is_live"])
        self.assertFalse(result["signal_metrics"]["available"])
        self.assertIn("scanner",result["signal"].lower())
        self.assertEqual(result["events"][0]["frequency"],"538.000 MHz")

    def test_browser_and_qt_integration_guardrails(self):
        root=Path(__file__).resolve().parents[1]
        desktop=(root/"tv_center/desktop.py").read_text()
        script=(root/"tv_center/web/web-controls.js").read_text()
        style=(root/"tv_center/web/style.css").read_text()
        self.assertIn("class Window(QMainWindow, TVWebMixin)",desktop)
        self.assertIn("self.setup_mobile_ui(form)",desktop)
        self.assertIn("self.web_commands.drain(self.web_action",desktop)
        self.assertIn("def scan_channels(self, confirmed=False)",desktop)
        self.assertIn("self.web_scan_events.append(dict(info))",desktop)
        self.assertIn("if ok and not was_remote:",desktop)
        self.assertIn("web-satellite-field",script)
        self.assertIn('medium==="s"',script)
        self.assertIn("web-diseqc-field",script)
        self.assertIn("data.frontend_present===true",script)
        self.assertIn('data.backend!=="native_tv_center"',script)
        self.assertIn("#web-control-root [hidden]{display:none!important}",style)
        self.assertNotIn("signal.toFixed",script)
