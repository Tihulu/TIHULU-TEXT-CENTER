"""No-hardware tests for authorized remote TV commands and web bundles."""
from pathlib import Path
import threading
import unittest
from tv_center.web_control import WebCommandQueue
from tv_center.lan import MobileLAN
from tv_center.bridge import TVBridge

class BrowserTVTests(unittest.TestCase):
    def test_web_command_queued_for_gui_thread(self):
        bridge=WebCommandQueue()
        result=[]
        def client():
            result.append(bridge.submit("channels",{}))
        worker=threading.Thread(target=client)
        worker.start()
        self.assertTrue(bridge.queue.not_empty or worker.is_alive())
        bridge.drain(lambda action,params: {"action":action,"params":params})
        worker.join(timeout=2)
        self.assertEqual(result,[{"action":"channels","params":{}}])
        bridge.close()
        with self.assertRaises(RuntimeError):
            bridge.submit("channels",{})

    def test_reject_unlisted_web_action(self):
        controller=WebCommandQueue()
        with self.assertRaises(ValueError):
            controller.submit("arbitrary_shell",{"cmd":"rm"})
        controller.close()

    def test_lan_pairing_uses_cookie_and_commands_opt_in(self):
        controller=MobileLAN(lambda:{},lambda p:None,lambda:None,
                             commands=lambda name,args:{"requested":name})
        self.assertIsNotNone(controller.commands)
        ticket,err=controller.accept_pin("192.168.1.50",controller.pin)
        self.assertIsNone(err)
        self.assertTrue(controller.authorized("tihulu_tv="+ticket))
        self.assertFalse(controller.authorized(""))

    def test_tokenless_companion_is_loopback_and_same_origin(self):
        import json
        import urllib.request
        import urllib.error
        bridge=TVBridge(lambda:{"source":"offline","channel":None}, lambda p:None,
                        port=0,commands=lambda action,args:{"action":action,"params":args})
        info=bridge.start()
        url=info["url"].rstrip("/")
        self.assertEqual(info["mode"],"tokenless_loopback")
        self.assertNotIn("token",info)
        try:
            def get(path, headers=None):
                req=urllib.request.Request(url+path,headers=headers or {})
                return urllib.request.urlopen(req,timeout=5)
            with get("/api/health") as resp:
                health=json.load(resp)
                self.assertEqual(health["mode"],"tokenless_loopback")
            with get("/") as resp:
                body=resp.read().decode("utf-8")
                self.assertIn("Open Local TV",body)
                self.assertNotIn('id="token"',body)
            with get("/api/status") as resp:
                self.assertEqual(json.load(resp)["source"],"offline")
            with get("/api/channels") as resp:
                self.assertEqual(json.load(resp)["action"],"channels")
            request=urllib.request.Request(url+"/api/command",
                data=json.dumps({"action":"channels","params":{}}).encode("utf-8"),
                method="POST",headers={"Content-Type":"application/json",
                "Origin":url})
            with urllib.request.urlopen(request,timeout=5) as resp:
                self.assertTrue(json.load(resp)["ok"])
            # Pages may only do a non-sensitive health check.
            with get("/api/health",{"Origin":"https://tihulu.github.io"}) as resp:
                self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"),
                                 "https://tihulu.github.io")
            with self.assertRaises(urllib.error.HTTPError) as err:
                get("/api/channels",{"Origin":"https://tihulu.github.io"})
            self.assertEqual(err.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError) as err:
                get("/api/channels",{"Host":"evil.example:1234"})
            self.assertEqual(err.exception.code,403)
            request=urllib.request.Request(url+"/api/command",
                data=b'{"action":"stop","params":{}}',method="POST",
                headers={"Content-Type":"application/json",
                         "Origin":"https://tihulu.github.io"})
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(request,timeout=5)
            self.assertEqual(err.exception.code,403)
            req=urllib.request.Request(url+"/api/command",
                headers={"Origin":"https://tihulu.github.io",
                         "Access-Control-Request-Method":"POST"},method="OPTIONS")
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.urlopen(req,timeout=5)
            self.assertEqual(err.exception.code,403)
            req=urllib.request.Request(url+"/api/health",
                headers={"Origin":"https://tihulu.github.io",
                         "Access-Control-Request-Private-Network":"true"},method="OPTIONS")
            with urllib.request.urlopen(req,timeout=5) as resp:
                self.assertEqual(resp.status,204)
                self.assertEqual(resp.headers.get("Access-Control-Allow-Private-Network"),"true")
        finally:
            bridge.stop()

    def test_local_hls_serves_only_own_playlist_not_arbitrary_files(self):
        import tempfile
        import urllib.request
        import urllib.error
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/"index.m3u8").write_text("#EXTM3U\n",encoding="utf-8")
            bridge=TVBridge(lambda:{},lambda p:None,port=0,
                stream_dir=lambda: path,commands=lambda action,args:{})
            address=bridge.start()["url"].rstrip("/")
            try:
                with urllib.request.urlopen(address+"/hls/index.m3u8",timeout=5) as response:
                    self.assertEqual(response.read(),b"#EXTM3U\n")
                for target in ("/hls/secrets.txt","/hls/../../etc/passwd"):
                    with self.assertRaises(urllib.error.HTTPError):
                        urllib.request.urlopen(address+target,timeout=5)
            finally:
                bridge.stop()

    def test_local_loopback_only_and_lan_pin_still_required(self):
        bridge=TVBridge(lambda:{},lambda p:None,commands=lambda name,args:{})
        self.assertIsNotNone(bridge.commands)
        with self.assertRaises(ValueError):
            TVBridge(lambda:{},lambda p:None,host="0.0.0.0")

    def test_mobile_serves_shared_scan_ui_module(self):
        from tv_center.lan import STATIC
        self.assertEqual(STATIC["web-controls.js"], "web-controls.js")
        self.assertEqual(STATIC["scan-ui-state.js"], "scan-ui-state.js")
        module=Path(__file__).parents[1]/"tv_center/web/scan-ui-state.js"
        self.assertTrue(module.is_file())

    def test_browser_assets_link_to_real_controls(self):
        root=Path(__file__).parents[1]/"tv_center/web"
        pages=(root/"index.html").read_text()
        mobile=(root/"mobile.html").read_text()
        for page in (pages,mobile):
            self.assertIn('id="web-control-root"',page)
            self.assertIn("web-controls.js",page)
        self.assertIn("browser-ai-ui.js",pages)
        for name in ("browser-ai-ui.js","browser-ai-worker.js","web-controls.js"):
            self.assertTrue((root/name).is_file())
        self.assertIn("Open Local TV",pages)
        self.assertIn("BROWSER ONLY", (root/"app.js").read_text(encoding="utf-8"))
        self.assertIn("GitHub Pages", (root/"web-controls.js").read_text(encoding="utf-8"))
        self.assertNotIn('id="token"',pages)
        controls=(root/"app.js").read_text(encoding="utf-8")
        self.assertIn('tokenless_loopback',controls)
        self.assertNotIn('"Authorization"',controls)

if __name__=="__main__":
    unittest.main()
