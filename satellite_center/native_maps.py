"""Real Qt QPainter Earth + polar-sky satellite map canvases; NO WebView."""
from __future__ import annotations
import json,math
from pathlib import Path
from PyQt5.QtCore import Qt,QPointF,QRectF,pyqtSignal,QTimer
from PyQt5.QtGui import QColor,QPen,QPainter,QPolygonF
from PyQt5.QtWidgets import QWidget
from .native_orbit import mercator_xy,mercator_reverse,sky_xy,footprint_deg
from .native_osm_tiles import VisibleTileCache,visible_tiles

LAND=Path(__file__).parent/"browser"/"natural-earth-land-110m.geojson"
COLORS={"iss":"#61e5fa","meteor":"#72eea3","cubesat":"#f9c679","iridium":"#c29aff"}

def land_polygons(path=LAND):
    geo=json.loads(Path(path).read_text(encoding="utf-8"))
    if geo.get("type")!="FeatureCollection":raise ValueError("Invalid offline world map")
    rings=[]
    for f in geo.get("features",[]):
        g=f.get("geometry") or {}
        if g.get("type")=="Polygon":parts=[g.get("coordinates",[])]
        elif g.get("type")=="MultiPolygon":parts=g.get("coordinates",[])
        else:continue
        for poly in parts:
            if poly and len(poly[0])>=3:rings.append(poly[0])
    return rings

def coverage_ring(lat,lon,alt_km,min_el=10):
    """Approximate min-elevation coverage circle from TLE altitude, not RF."""
    lat1=math.radians(lat);lon1=math.radians(lon)
    d=math.radians(footprint_deg(alt_km,min_el))
    points=[]
    for i in range(97):
        az=2*math.pi*i/96
        lat2=math.asin(max(-1,min(1,
            math.sin(lat1)*math.cos(d)+math.cos(lat1)*math.sin(d)*math.cos(az))))
        lon2=lon1+math.atan2(math.sin(az)*math.sin(d)*math.cos(lat1),
                            math.cos(d)-math.sin(lat1)*math.sin(lat2))
        points.append((math.degrees(lat2),(math.degrees(lon2)+180)%360-180))
    return points

class OrbitCanvas(QWidget):
    selected=pyqtSignal(int)
    def __init__(self,mode="earth",parent=None):
        super().__init__(parent)
        if mode not in ("sky","earth"):raise ValueError("Map mode")
        self.mode=mode
        self.data={"satellites":[],"observer":{"lat":50.87,"lon":6.87},"track_segments":[]}
        self.selected_norad=None
        self.above_only=False
        self.coverage_scope="selected"
        self.tracks_visible=True
        self.center_lat=49.;self.center_lon=12.
        self.zoom=2
        self._land=land_polygons() if mode=="earth" else []
        self._hits=[]
        self._press=None;self._dragged=False
        self._street=False
        self.tiles=VisibleTileCache(self) if mode=="earth" else None
        if self.tiles:self.tiles.updated.connect(self.update)
        self.setMouseTracking(True)
        self.setMinimumHeight(310)
    def set_snapshot(self,data):
        self.data=data;self.update()
    def set_selected(self,norad):
        self.selected_norad=int(norad) if norad is not None else None
        self.update()
    def set_street(self,enable):
        self._street=bool(enable)
        self._sync_tiles();self.update()
    def center_station(self):
        self.center_lat=self.data["observer"]["lat"]
        self.center_lon=self.data["observer"]["lon"]
        self.zoom=5
        self._sync_tiles();self.update()
    def _sync_tiles(self):
        if self.tiles:
            self.tiles.set_view(self.center_lat,self.center_lon,self.zoom,
                                self.width(),self.height(),
                                self._street and self.isVisible())
    def _project(self,lat,lon):
        # Natural Earth polygons legitimately contain 180.00000000000014
        # or out-of-range pole vertices from floating point rounding.
        # Normalize map DRAWING only; observer/SDR coordinates stay strict.
        latitude=max(-90.,min(90.,float(lat)))
        longitude=(float(lon)+180.)%360.-180.
        cx,cy=mercator_xy(self.center_lat,self.center_lon,self.zoom)
        x,y=mercator_xy(latitude,longitude,self.zoom)
        world=256*2**self.zoom
        return QPointF(self.width()/2+(x-cx+world/2)%world-world/2,
                       self.height()/2+y-cy)
    def _line_segments(self,coords):
        """Never draw false long lines across antimeridian."""
        chunks=[];batch=[];oldlon=None
        for lat,lon in coords:
            if oldlon is not None and abs(lon-oldlon)>180:
                if len(batch)>=2:chunks.append(batch)
                batch=[]
            batch.append(self._project(lat,lon));oldlon=lon
        if len(batch)>=2:chunks.append(batch)
        return chunks
    def _draw_path(self,p,coords):
        for points in self._line_segments(coords):
            for a,b in zip(points,points[1:]):
                if abs(a.x()-b.x())<256*2**self.zoom/2:p.drawLine(a,b)
    def _offline_earth(self,p):
        p.fillRect(self.rect(),QColor("#0d2439"))
        p.setPen(QPen(QColor("#284963"),1))
        for longitude in range(-180,181,30):
            self._draw_path(p,[(lat,longitude) for lat in range(-85,86,5)])
        for latitude in range(-60,81,30):
            self._draw_path(p,[(latitude,lon) for lon in range(-180,181,5)])
        p.setPen(QPen(QColor("#658d95"),.7))
        p.setBrush(QColor("#294d58"))
        for ring in self._land:
            for segment in self._line_segments([(lat,lon) for lon,lat in ring]):
                if len(segment)>=3:p.drawPolygon(QPolygonF(segment))
    def _street_tiles(self,p):
        if not self._street:return
        cx,cy=mercator_xy(self.center_lat,self.center_lon,self.zoom)
        world=256*2**self.zoom
        for z,x,y in visible_tiles(self.center_lat,self.center_lon,self.zoom,
                                   self.width(),self.height()):
            image=self.tiles.image((z,x,y))
            if image is None:continue
            px=self.width()/2+(x*256-cx+world/2)%world-world/2
            py=self.height()/2+y*256-cy
            p.drawPixmap(QRectF(px,py,256,256),image,
                         QRectF(0,0,image.width(),image.height()))
    def _earth(self,p):
        self._offline_earth(p)
        self._street_tiles(p)
        if self.tracks_visible:
            p.setPen(QPen(QColor("#6ae2d2"),2,Qt.DashLine))
            for segment in self.data.get("track_segments",[]):
                self._draw_path(p,[(pt["lat"],pt["lon"]) for pt in segment])
        if self.coverage_scope!="none":
            rows=self.data["satellites"]
            coverage=rows[:30] if self.coverage_scope=="all" else [
                row for row in rows if row["norad"]==self.selected_norad]
            for row in coverage:
                p.setPen(QPen(QColor("#63c7bc"),1,Qt.DashLine))
                self._draw_path(p,coverage_ring(row["lat"],row["lon"],row["alt_km"]))
        o=self.data["observer"]
        q=self._project(o["lat"],o["lon"])
        p.setPen(QPen(QColor("#111d2d"),2));p.setBrush(QColor("#ffde80"))
        p.drawEllipse(q,6,6)
        p.setPen(QColor("#ffefa9"));p.drawText(q+QPointF(9,-10),"GROUND STATION")
        self._hits=[]
        for row in self.data.get("satellites",[]):
            if self.above_only and row["el"]<0:continue
            q=self._project(row["lat"],row["lon"])
            if not (-20<=q.x()<=self.width()+20 and -20<=q.y()<=self.height()+20):
                continue
            selected=row["norad"]==self.selected_norad
            p.setPen(QPen(QColor("#ffffff") if selected else QColor("#0c1b2d"),2))
            p.setBrush(QColor(COLORS.get(row["family"],"#eeeeee")))
            p.drawEllipse(q,8 if selected else 5,8 if selected else 5)
            if selected:
                p.setPen(QColor("#f2faff"))
                p.drawText(q+QPointF(10,-10),row["name"])
            self._hits.append((q,row))
        p.setPen(QColor("#daebfb"))
        p.setBrush(QColor(12,22,37,215))
        p.drawRect(QRectF(0,self.height()-25,self.width(),25))
        p.drawText(10,self.height()-8,(
            "© OpenStreetMap contributors · optional viewport-only tiles" if self._street
            else "Offline Natural Earth 110m land outlines · no network")+
            " · TLE geometry ≠ RF")

    def _sky(self,p):
        p.fillRect(self.rect(),QColor("#112035"))
        cx=self.width()/2;cy=self.height()/2
        radius=max(45,min(self.width()-75,self.height()-65)/2)
        p.setPen(QPen(QColor("#476583"),1))
        for elevation in (0,30,60):
            rr=radius*(90-elevation)/90
            p.drawEllipse(QPointF(cx,cy),rr,rr)
        for label,az in (("N",0),("E",90),("S",180),("W",270)):
            x,y=sky_xy(az,0)
            p.drawLine(QPointF(cx,cy),QPointF(cx+x*radius,cy+y*radius))
            p.setPen(QColor("#c1dbee"))
            p.drawText(QPointF(cx+x*(radius+18)-5,cy+y*(radius+18)+4),label)
            p.setPen(QPen(QColor("#476583"),1))
        self._hits=[]
        for row in self.data.get("satellites",[]):
            if row["el"]<0:continue
            x,y=sky_xy(row["az"],row["el"])
            q=QPointF(cx+x*radius,cy+y*radius)
            selected=row["norad"]==self.selected_norad
            p.setPen(QPen(QColor("#ffffff") if selected else QColor("#091525"),2))
            p.setBrush(QColor(COLORS.get(row["family"],"#ffffff")))
            p.drawEllipse(q,8 if selected else 5,8 if selected else 5)
            if selected:
                p.setPen(QColor("#ffffff"));p.drawText(q+QPointF(12,-10),row["name"])
            self._hits.append((q,row))
        p.setPen(QColor("#93b1cb"))
        p.drawText(10,self.height()-9,"Sky · North up, East right, horizon rim · predicted angles, not RF")
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if self.mode=="earth":self._earth(p)
        else:self._sky(p)
        p.end()
    def _nearest(self,point):
        closest=None;distance=15
        for q,row in self._hits:
            value=math.hypot(q.x()-point.x(),q.y()-point.y())
            if value<distance:closest=row;distance=value
        return closest
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._press=event.pos();self._dragged=False
    def mouseMoveEvent(self,event):
        if self.mode=="earth" and self._press is not None and event.buttons()&Qt.LeftButton:
            dx=event.pos().x()-self._press.x()
            dy=event.pos().y()-self._press.y()
            if abs(dx)+abs(dy)>2:
                self._dragged=True
                cx,cy=mercator_xy(self.center_lat,self.center_lon,self.zoom)
                self.center_lat,self.center_lon=mercator_reverse(cx-dx,cy-dy,self.zoom)
                self._press=event.pos()
                self.update()
        else:
            row=self._nearest(event.pos())
            self.setToolTip(row["name"]+" · "+str(row["el"])+"° above horizon · TLE only"
                            if row else "TLE positions; no radio detection")
    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        if self._dragged:self._sync_tiles()
        else:
            row=self._nearest(event.pos())
            if row:self.selected.emit(row["norad"])
        self._press=None;self._dragged=False
    def wheelEvent(self,event):
        if self.mode=="earth":
            self.zoom=max(2,min(11,self.zoom+(1 if event.angleDelta().y()>0 else -1)))
            self._sync_tiles();self.update()
    def resizeEvent(self,event):
        if self.tiles:QTimer.singleShot(220,self._sync_tiles)
