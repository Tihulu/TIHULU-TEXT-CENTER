"""Localhost-only HTTP regressions for paired TIHULU remote media hub."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from tv_center.remote_hub import RemoteHub,create_handler


class PairedRemoteHubTests(unittest.TestCase):
    def test_media_catalog_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"media"
            root.mkdir()
            (root/"track.mp3").write_bytes(b"fake")
            outside=Path(d)/"outside.mp4"
            outside.write_bytes(b"fake")
            (root/"escape.mp4").symlink_to(outside)
            hub=RemoteHub(root)
            try:
                names=[str(v.name) for v in hub.files.values()]
                self.assertIn("track.mp3",names)
                self.assertNotIn("escape.mp4",names)
                self.assertFalse(hub.sessions)
                self.assertFalse(hub.cache.exists() is False)
            finally:
                hub.close()
            self.assertFalse(hub.cache.exists())

    def test_cookie_pairing_and_csrf_required_for_control(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            hub=RemoteHub(root)
            srv=ThreadingHTTPServer(("127.0.0.1",0),create_handler(hub))
            thread=threading.Thread(target=srv.serve_forever,daemon=True)
            thread.start()
            url=f"http://127.0.0.1:{srv.server_port}"
            def post(path,payload,cookie="",csrf=""):
                return Request(url+path,data=json.dumps(payload).encode(),
                    headers={"Content-Type":"application/json",
                             **({"Cookie":cookie} if cookie else {}),
                             **({"X-CSRF-Token":csrf} if csrf else {})},
                    method="POST")
            try:
                with self.assertRaises(HTTPError) as auth:
                    urlopen(url+"/api/catalog",timeout=3)
                self.assertEqual(auth.exception.code,401)
                with self.assertRaises(HTTPError) as wrong:
                    urlopen(post("/api/pair",{"pin":"000000"}),timeout=3)
                self.assertEqual(wrong.exception.code,403)
                with urlopen(post("/api/pair",{"pin":hub.pin}),timeout=3) as answer:
                    body=json.loads(answer.read())
                    cookie=answer.headers.get("Set-Cookie").split(";",1)[0]
                self.assertIn("csrf",body)
                with self.assertRaises(HTTPError) as no_csrf:
                    urlopen(post("/api/stop",{},cookie),timeout=3)
                self.assertEqual(no_csrf.exception.code,403)
                with urlopen(post("/api/stop",{},cookie,body["csrf"]),timeout=3) as ok:
                    self.assertEqual(ok.status,200)
                with urlopen(Request(url+"/api/status",headers={
                        "Cookie":cookie}),timeout=3) as status:
                    self.assertEqual(json.loads(status.read())["state"],"idle")
            finally:
                srv.shutdown()
                srv.server_close()
                thread.join(timeout=4)
                hub.close()


if __name__=="__main__":
    unittest.main()
