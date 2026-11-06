"""Synthetic loopback auth + portability tests; no RTL-SDR or network downloads."""
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest

from satellite_center.bridge import (
    PAGES_ORIGIN, allowed_origin, local_host_allowed, pairing_secret,
)
from satellite_center.__main__ import Server, Station


class BridgeTests(unittest.TestCase):
    def test_pairing_file_persists_privately(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            a, b = pairing_secret(folder), pairing_secret(folder)
            self.assertEqual(a, b)
            self.assertEqual(len(a), 64)
            self.assertEqual((folder / "pages-pairing.key").read_text().strip(), a)
            self.assertFalse(allowed_origin('https://evil.example', '127.0.0.1:8791'))
            self.assertTrue(allowed_origin(PAGES_ORIGIN, '127.0.0.1:8791'))
            self.assertFalse(local_host_allowed('station.example:8791', 8791))

    def test_pages_cross_origin_requires_bearer_and_local_pairing(self):
        with tempfile.TemporaryDirectory() as td:
            server = Server(('127.0.0.1', 0), Station(Path(td)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_port
            host = f'127.0.0.1:{port}'

            def request(method, path, body=None, headers=None):
                conn = HTTPConnection('127.0.0.1', port, timeout=3)
                conn.request(method, path, body=body, headers=headers or {})
                response = conn.getresponse()
                raw = response.read()
                result = (response.status, dict(response.getheaders()),
                          json.loads(raw) if raw else None)
                conn.close()
                return result

            try:
                status, _, d = request('GET','/api/status')
                self.assertEqual(status, 200)
                csrf = d['csrf']
                self.assertNotIn('pairing_token', d)
                status, _, _ = request('GET','/api/status',headers={'Host':f'example.org:{port}'})
                self.assertEqual(status,403)
                status, _, _ = request('GET','/api/status',headers={'Origin':'https://attacker.example'})
                self.assertEqual(status,403)
                status, hdr, _ = request('OPTIONS','/api/status',headers={'Origin':PAGES_ORIGIN,
                    'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'Authorization'})
                self.assertEqual(status,204)
                self.assertEqual(hdr.get('Access-Control-Allow-Origin'),PAGES_ORIGIN)
                status,_,_ = request('GET','/api/status',headers={'Origin':PAGES_ORIGIN})
                self.assertEqual(status,401)
                status,_,d = request('POST','/api/pair',body=json.dumps({'csrf':csrf}),
                    headers={'Content-Type':'application/json','Origin':f'http://{host}'})
                self.assertEqual(status,200,d)
                token=d['token']
                status,_,d = request('GET','/api/status',headers={
                    'Origin':PAGES_ORIGIN,'Authorization':'Bearer '+token})
                self.assertEqual(status,200,d)
                status,_,d = request('POST','/api/pair',body=json.dumps({'csrf':csrf}),
                    headers={'Origin':PAGES_ORIGIN,'Authorization':'Bearer '+token})
                self.assertEqual(status,403,d)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
