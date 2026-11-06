"""Native Qt Earth & polar-sky maps; NO embedded browser/WebView.

OSM tiles only when the user enables the layer. No bulk downloads or prefetch.
The bundled Natural Earth outline remains usable entirely offline.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QUrl, QStandardPaths
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath, QPolygonF, QPixmap
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkDiskCache
from PyQt5.QtWidgets import QWidget

from .native_tracking import mercator_pixel,mercator_unproject,sky_project

WORLD_JSON=Path(__file__).parent/"browser"/"natural-earth-land-110m.geojson"
OSM_TILE="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION="© OpenStreetMap contributors"
OSM_UA="TIHULU-Satellite-Center-NativeQt/0.3 (+https://github.com/Tihulu/TIHULU-TEXT-CENTER)"
MAX_CONCURRENT_TILES=6
MAX_TILES_PER_VIEW=36
FALLBACK_TILE_SECONDS=7*86400

def world_rings(path=WORLD_JSON):
    """Small static Natural Earth GeoJSON land outlines (public domain)."""
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("type")!="FeatureCollection":
        raise ValueError("Invalid bundled land GeoJSON")
    rings=[]
    for feature in payload["features"]:
        geometry=feature.get("geometry") or {}
        typ=geometry.get("type")
        polys=geometry.get("coordinates") or []
        if typ=="Polygon":polys=[polys]
        if typ not in ("Polygon","MultiPolygon"):continue
        for poly in polys:
            if not poly:continue
            # Outer rings only to avoid incorrect holes on global drawing.
            ring=[]
            for pair in poly[0][:12000]:
                if isinstance(pair,(list,tuple)) and len(pair)>1:
                    lon,lat=pair[:2]
                    if all(isinstance(v,(int,float)) and math.isfinite(v) for v in (lat,lon)):
                        ring.append((float(lat),float(lon)))
            if len(ring)>2:rings.append(ring)
    return rings

def _shortest_world_x(x,cx,world):
    return x + round((cx-x)/world)*world

class MapCanvas(QWidget):
    """Interactive native Qt painter map with tiles, tracks and clickable markers."""
    def __init__(self,mode="earth",parent=None):
        super().__init__(parent)
        if mode not in ("earth","sky"):raise ValueError("Invalid map mode")
        self.mode=mode
        self.setMinimumHeight(340)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.rows=[]
        self.station_lat=50.938
        self.station_lon=6.960
        self.center_lat=25.0
        self.center_lon=0.0
        self.zoom=2
        self.selected=None
        self.tracks=[]
        self.show_tracks=True
        self.show_coverage=True
        self.show_only_above=False
        self.use_osm=False
        self._drag=None
        self._hits=[]
        self.on_select=None
        self._rings=None
        self._tiles={}
        self._pending=set()
        self._failures=0
        self._net=QNetworkAccessManager(self)
        cache=QNetworkDiskCache(self._net)
        base=QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        if not base:
            base=str(Path.home()/".cache"/"tihulu-satellite-center")
        cache.setCacheDirectory(str(Path(base)/"osm-tiles"))
        cache.setMaximumCacheSize(96*1024*1024)
        self._net.setCache(cache)
        self._cache=cache
        self.setToolTip("Mouse drag to pan; wheel to zoom; click orbital dot to inspect. No RF inference.")

    def set_state(self,rows,station_lat,station_lon,selected=None,tracks=None):
        self.rows=list(rows)
        self.station_lat=float(station_lat)
        self.station_lon=float(station_lon)
        self.selected=selected
        if tracks is not None:self.tracks=list(tracks)
        self.update()

    def enable_osm(self,enabled):
        self.use_osm=bool(enabled) and self.mode=="earth"
        if self.use_osm:self.load_visible_tiles()
        self.update()

    def recenter(self):
        self.center_lat=self.station_lat
        self.center_lon=self.station_lon
        self.zoom=max(self.zoom,4)
        if self.use_osm:self.load_visible_tiles()
        self.update()

    def _world(self):
        return 256*(2**self.zoom)

    def _center(self):
        return mercator_pixel(self.center_lat,self.center_lon,self.zoom)

    def _point(self,lat,lon):
        if self.mode=="sky":
            raise ValueError("Use sky projection")
        x,y=mercator_pixel(lat,lon,self.zoom)
        cx,cy=self._center()
        x=_shortest_world_x(x,cx,self._world())
        return QPointF(self.width()/2+(x-cx),self.height()/2+(y-cy))

    def _visible_tiles(self):
        world=self._world()
        cx,cy=self._center()
        min_x=int(math.floor((cx-self.width()/2)/256))
        max_x=int(math.floor((cx+self.width()/2)/256))
        min_y=int(math.floor((cy-self.height()/2)/256))
        max_y=int(math.floor((cy+self.height()/2)/256))
        out=[]
        count=2**self.zoom
        for iy in range(max(0,min_y),min(count-1,max_y)+1):
            for ix in range(min_x,max_x+1):
                if len(out)>=MAX_TILES_PER_VIEW:return out
                out.append((self.zoom,ix%count,iy,ix))
        return out

    def load_visible_tiles(self):
        """Demand-load only tiles actually on screen, never orbit/time-driven."""
        if not self.use_osm or self.mode!="earth":return
        for z,x,y,_ in self._visible_tiles():
            key=(z,x,y)
            if key in self._tiles or key in self._pending:continue
            if len(self._pending)>=MAX_CONCURRENT_TILES:break
            self._pending.add(key)
            url=QUrl(OSM_TILE.format(z=z,x=x,y=y))
            request=QNetworkRequest(url)
            request.setRawHeader(b"User-Agent",OSM_UA.encode("ascii"))
            request.setAttribute(QNetworkRequest.CacheLoadControlAttribute,
                                 QNetworkRequest.PreferCache)
            reply=self._net.get(request)
            reply.finished.connect(lambda k=key, rep=reply:self._tile_done(k,rep))

    def _tile_done(self,key,reply):
        self._pending.discard(key)
        try:
            payload=bytes(reply.readAll())
            if reply.error()!=reply.NoError or len(payload)>800_000:
                self._failures+=1
            else:
                pixmap=QPixmap()
                if pixmap.loadFromData(payload,"PNG"):
                    self._tiles[key]=pixmap
                    # Trim process-local tile images; HTTP disk cache remains policy-aware.
                    if len(self._tiles)>84:self._tiles.pop(next(iter(self._tiles)))
                else:self._failures+=1
        finally:
            reply.deleteLater()
            self.update()
            # A single viewport may need >6 tiles; remaining are requested
            # only when this enabled layer is still visible to the user.
            if self.isVisible() and self.use_osm:self.load_visible_tiles()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(),QColor("#0c1d31"))
        if self.mode=="earth":
            self._earth(painter)
        else:
            self._sky(painter)
        painter.end()

    def _earth(self,p):
        self._hits=[]
        w,h=self.width(),self.height()
        if self.use_osm:
            cx,cy=self._center()
            for z,x,y,ix in self._visible_tiles():
                tile=self._tiles.get((z,x,y))
                if tile is None:continue
                X=int(round(w/2+ix*256-cx))
                Y=int(round(h/2+y*256-cy))
                p.drawPixmap(X,Y,256,256,tile)
        if not self.use_osm or not self._tiles:
            if self._rings is None:
                try:self._rings=world_rings()
                except (OSError,ValueError,KeyError,TypeError):self._rings=[]
            p.setPen(QPen(QColor("#4c8ca0"),.7))
            p.setBrush(QBrush(QColor("#194c59")))
            for ring in self._rings:
                points=[]
                last=None
                for lat,lon in ring:
                    point=self._point(lat,lon)
                    if last is not None and abs(point.x()-last.x())>self._world()/2:
                        if len(points)>2:
                            p.drawPolygon(QPolygonF(points))
                        points=[]
                    points.append(point);last=point
                if len(points)>2:p.drawPolygon(QPolygonF(points))
        # Geographic graticule.
        p.setPen(QPen(QColor("#35607b"),.6,Qt.DotLine))
        for lat in (-60,-30,0,30,60):
            a=self._point(lat,-179);b=self._point(lat,179)
            if abs(a.x()-b.x())<w*2:p.drawLine(a,b)
        # Actual observer location, fixed independent of satellite visibility.
        station=self._point(self.station_lat,self.station_lon)
        p.setPen(QPen(QColor("#ffffff"),2))
        p.setBrush(QBrush(QColor("#52dfaa")))
        p.drawEllipse(station,6,6)
        p.drawText(station+QPointF(9,-9),"Station")
        if self.show_tracks:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#e5b55c"),1.5,Qt.DashLine))
            for segment in self.tracks:
                points=[self._point(lat,lon) for lat,lon in segment]
                for first,second in zip(points,points[1:]):
                    if abs(first.x()-second.x())<self._world()/2:
                        p.drawLine(first,second)
        # Each satellite dot is a TLE-derived subpoint only.
        colors={"iss":"#58d3aa","meteor":"#e0ab58","iridium":"#bd9bff",
                "cubesat":"#70b4ef","unknown":"#9cb1c8"}
        for row in self.rows:
            if self.show_only_above and row["elevation_deg"]<0:continue
            pos=self._point(row["lat"],row["lon"])
            if pos.x()<-15 or pos.x()>w+15 or pos.y()<-15 or pos.y()>h+15:continue
            col=QColor(colors.get(row["family"],colors["unknown"]))
            selected=str(row["id"])==str(self.selected)
            p.setBrush(QBrush(col));p.setPen(QPen(QColor("#ffffff") if selected else QColor("#182c43"),2))
            p.drawEllipse(pos,8 if selected else 5,8 if selected else 5)
            self._hits.append((pos,row))
            if selected:p.drawText(pos+QPointF(12,-8),row["name"][:35])
        p.setPen(QColor("#d1e2f0"))
        p.drawText(12,22,f"TLE predicted positions · {len(self.rows)} objects · no RF reception implied")
        p.drawText(12,h-12,"Offline Natural Earth" if not self.use_osm else OSM_ATTRIBUTION)
        if self.use_osm and not self._tiles:
            p.drawText(12,h-33,"Loading visible OSM tiles; offline outline remains available.")

    def _sky(self,p):
        self._hits=[]
        w,h=self.width(),self.height()
        radius=min(w,h)*.45
        center=QPointF(w/2,h/2)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#345b76"),1))
        for elev in (0,30,60):
            p.drawEllipse(center,radius*(1-elev/90),radius*(1-elev/90))
        for az in (0,90,180,270):
            x,y=sky_project(az,0,w,h)
            p.drawLine(center,QPointF(x,y))
        p.setPen(QColor("#c3dced"))
        for az,label in [(0,"N"),(90,"E"),(180,"S"),(270,"W")]:
            x,y=sky_project(az,0,w,h)
            p.drawText(QPointF(x+5,y-5),label)
        for row in self.rows:
            if row["elevation_deg"]<0:continue
            x,y=sky_project(row["azimuth_deg"],row["elevation_deg"],w,h)
            point=QPointF(x,y)
            selected=str(row["id"])==str(self.selected)
            color=QColor("#e7b45f" if row["family"]=="meteor" else "#63cbdd")
            p.setPen(QPen(QColor("#fff") if selected else color,1))
            p.setBrush(QBrush(color))
            p.drawEllipse(point,8 if selected else 5,8 if selected else 5)
            self._hits.append((point,row))
            if selected:p.drawText(point+QPointF(13,-10),row["name"][:35])
        p.setPen(QColor("#d1e2f0"))
        p.drawText(12,22,"Polar sky · zenith center, horizon edge · geometric TLE positions")
        p.drawText(12,h-12,"North up · East right · RF unverified")

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._drag=event.pos()
            self._drag_origin=(self.center_lat,self.center_lon)
            self._dragged=False

    def mouseMoveEvent(self,event):
        if self._drag is None or self.mode!="earth":return
        dx=event.pos().x()-self._drag.x()
        dy=event.pos().y()-self._drag.y()
        if abs(dx)+abs(dy)>4:self._dragged=True
        cx,cy=mercator_pixel(*self._drag_origin,self.zoom)
        lat,lon=mercator_unproject(cx-dx,cy-dy,self.zoom)
        self.center_lat=lat;self.center_lon=lon
        self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        pos=event.pos();moved=getattr(self,"_dragged",False)
        self._drag=None
        if self.mode=="earth" and moved and self.use_osm:
            self.load_visible_tiles()
        if not moved and self._hits:
            hit=min(self._hits,key=lambda p:(p[0].x()-pos.x())**2+(p[0].y()-pos.y())**2)
            distance=math.hypot(hit[0].x()-pos.x(),hit[0].y()-pos.y())
            if distance<15 and callable(self.on_select):
                self.on_select(hit[1])
        self.update()

    def wheelEvent(self,event):
        if self.mode!="earth":return
        delta=event.angleDelta().y()
        if not delta:return
        self.zoom=max(1,min(12,self.zoom+(1 if delta>0 else -1)))
        if self.use_osm:self.load_visible_tiles()
        self.update()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.use_osm:self.load_visible_tiles()
