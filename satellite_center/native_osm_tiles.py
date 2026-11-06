"""Opt-in OSM raster tiles for a *native* Qt desktop map (no WebView).

Never auto-start, prefetch, bulk-download, or save tiles for offline areas.
Requests use one visible viewport, a named app User-Agent, HTTPS and disk cache.
"""
from __future__ import annotations
import math,time
from pathlib import Path
from PyQt5.QtCore import QObject,QUrl,pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from .native_orbit import mercator_xy

OSM_URL="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
IDENTITY=b"TIHULU-Satellite-Center/0.3 (+https://github.com/Tihulu/TIHULU-TEXT-CENTER)"
CACHE=Path.home()/".cache"/"tihulu-satellite-center"/"osm"
TTL=7*86400
MAX_BYTES=800_000

def tile_url(z,x,y):
    if not all(type(q) is int for q in (z,x,y)) or not 0<=z<=13 or not 0<=x<2**z or not 0<=y<2**z:
        raise ValueError("Invalid OSM tile index")
    return OSM_URL.format(z=z,x=x,y=y)

def visible_tiles(lat,lon,zoom,width,height):
    if width<=0 or height<=0:return []
    cx,cy=mercator_xy(lat,lon,zoom)
    n=2**zoom
    x0=math.floor((cx-width/2)/256);x1=math.floor((cx+width/2)/256)
    y0=max(0,math.floor((cy-height/2)/256))
    y1=min(n-1,math.floor((cy+height/2)/256))
    result=[]
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
            key=(zoom,x%n,y)
            if key not in result:result.append(key)
            if len(result)>=48:return result
    return result

class VisibleTileCache(QObject):
    updated=pyqtSignal()
    def __init__(self,parent=None,root=CACHE):
        super().__init__(parent)
        self.root=Path(root)
        self.manager=QNetworkAccessManager(self)
        self.memory={}
        self.queue=[]
        self.pending=set()
        self.viewport=set()
        self.enabled=False
        self.failures=0
    def path(self,key):
        z,x,y=key
        return self.root/str(z)/str(x)/(str(y)+".png")
    def image(self,key):
        if key in self.memory:return self.memory[key]
        p=self.path(key)
        if not p.exists():return None
        image=QPixmap(str(p))
        if image.isNull():return None
        if len(self.memory)>=120:self.memory.pop(next(iter(self.memory)))
        self.memory[key]=image
        return image
    def set_view(self,lat,lon,zoom,width,height,enabled):
        self.enabled=bool(enabled)
        self.viewport=(set(visible_tiles(lat,lon,zoom,width,height))
                       if self.enabled else set())
        self.queue=[]
        if not self.enabled:return
        for key in sorted(self.viewport):
            file=self.path(key)
            if file.exists() and time.time()-file.stat().st_mtime<TTL:
                continue
            if key not in self.pending:self.queue.append(key)
        self._pump()
    def _pump(self):
        if not self.enabled:return
        while self.queue and len(self.pending)<2:
            key=self.queue.pop(0)
            if key not in self.viewport or key in self.pending:continue
            z,x,y=key
            request=QNetworkRequest(QUrl(tile_url(z,x,y)))
            request.setRawHeader(b"User-Agent",IDENTITY)
            request.setAttribute(QNetworkRequest.FollowRedirectsAttribute,False)
            path=self.path(key)
            if path.exists():
                etag=path.with_suffix(".etag")
                if etag.exists():
                    value=etag.read_bytes()[:240]
                    if value:request.setRawHeader(b"If-None-Match",value)
            reply=self.manager.get(request)
            self.pending.add(key)
            reply.finished.connect(lambda k=key,q=reply:self._completed(k,q))
    def _completed(self,key,reply):
        self.pending.discard(key)
        try:
            status=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            path=self.path(key)
            if status==304 and path.exists():
                path.touch()
            elif status==200 and reply.error()==QNetworkReply.NoError:
                data=bytes(reply.readAll())
                if data.startswith(b"\x89PNG\r\n\x1a\n") and 0<len(data)<=MAX_BYTES:
                    picture=QPixmap()
                    if picture.loadFromData(data,"PNG") and picture.width()<=512 and picture.height()<=512:
                        path.parent.mkdir(parents=True,exist_ok=True)
                        path.write_bytes(data)
                        etag=bytes(reply.rawHeader(b"ETag"))[:240]
                        if etag:path.with_suffix(".etag").write_bytes(etag)
                        self.memory[key]=picture
                    else:self.failures+=1
                else:self.failures+=1
            else:self.failures+=1
        except OSError:
            self.failures+=1
        finally:
            reply.deleteLater()
            self.updated.emit()
            self._pump()
