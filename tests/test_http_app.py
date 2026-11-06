import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from textcenter.core import Store
from textcenter.http_app import LocalServer, run_server


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=LocalServer(("127.0.0.1",0),Store(Path(self.tmp.name)/"app.db"))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self,method,path,data=None,csrf=None,origin=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        headers={}
        body=None
        if data is not None:
            headers["Content-Type"]="application/json"
            body=json.dumps(data).encode()
        if csrf:
            headers["X-Tihulu-CSRF"]=csrf
        if origin:
            headers["Origin"]=origin
        conn.request(method,path,body=body,headers=headers)
        res=conn.getresponse()
        data=res.read()
        result=(res.status,dict(res.getheaders()),data)
        conn.close()
        return result

    def test_ui_and_local_navigation(self):
        code,headers,data=self.request("GET","/")
        self.assertEqual(code,200)
        self.assertIn(b"TIHULU TEXT CENTER",data)
        self.assertEqual(headers["X-Content-Type-Options"],"nosniff")
        code,_,payload=self.request("GET","/api/page?number=100")
        result=json.loads(payload)
        self.assertEqual(result["kind"],"local_index")
        self.assertEqual(result["title"],"INDEX")
        self.assertEqual(self.request("GET","/api/page?number=999")[0],400)
        self.assertEqual(self.request("GET","/api/page?number=102")[0],404)
        self.assertEqual(self.request("GET","/../README.md")[0],404)

    def test_favicon_is_local_and_served(self):
        code,headers,payload=self.request("GET","/favicon.svg")
        self.assertEqual(code,200)
        self.assertEqual(headers["Content-Type"],"image/svg+xml; charset=utf-8")
        self.assertIn(b"<svg",payload)

    def test_no_forged_source(self):
        code,_,raw=self.request("GET","/api/page?source_id=ard_text&number=100")
        self.assertEqual(code,404)
        self.assertIn(b"No imported page",raw)
        code,_,raw=self.request("GET","/api/bootstrap")
        self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)["radio_receiver"],"not_connected")

    def test_csrf_and_same_origin_for_local_post(self):
        _,_,raw=self.request("GET","/api/bootstrap")
        csrf=json.loads(raw)["csrf"]
        post={"title":"Test","body":"Body","author":"Local"}
        self.assertEqual(self.request("POST","/api/bulletins",post)[0],403)
        bad="http://evil.example"
        self.assertEqual(self.request("POST","/api/bulletins",post,csrf,origin=bad)[0],403)
        right="http://127.0.0.1:"+str(self.server.server_port)
        self.assertEqual(self.request("POST","/api/bulletins",post,csrf,origin=right)[0],201)
        code,_,raw=self.request("GET","/api/bulletins")
        self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)[0]["title"],"Test")

    def test_feed_registration_without_auto_fetch(self):
        _,_,raw=self.request("GET","/api/bootstrap")
        csrf=json.loads(raw)["csrf"]
        code,_,data=self.request("POST","/api/feeds/add",
            {"title":"Local feed","url":"https://example.org/rss"},csrf)
        self.assertEqual(code,201)
        code,_,data=self.request("GET","/api/feeds")
        self.assertEqual(len(json.loads(data)),1)
        self.assertIsNone(json.loads(data)[0]["last_fetched"])

    def test_server_will_not_bind_lan(self):
        with self.assertRaises(ValueError):
            run_server(Store(Path(self.tmp.name)/"another.db"),host="0.0.0.0",port=0)


if __name__=="__main__":
    unittest.main()
