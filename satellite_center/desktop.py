"""TIHULU Satellite Center: real native Qt Widgets desktop application.

No browser, localhost HTTP server, WebView, HTML renderer or WebUSB is
started. Satellite RF uses the existing receive-only Station/rtl_sdr backend.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import csv
import json
import math
import os
import re
import shutil
from pathlib import Path
import sys
import time
import wave
import uuid

from PyQt5.QtCore import Qt, QDate, QDateTime, QPointF, QRectF, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, QUrl, QSize, QStringListModel
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QPixmap, QDesktopServices, QImage, QIcon
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QLineEdit, QFrame, QHeaderView, QSizePolicy, QCompleter, QScrollArea, QSlider,
    QDialog, QDialogButtonBox, QToolButton, QMenu, QListWidget, QListWidgetItem
)

from .__main__ import Station, PROFILES, LOCATIONS, AUTO_DOWNLINK_PROFILES, allowed_mode
from .capture_budget import MAX_IQ_BYTES
from .native_analysis import analyze_cu8, save_spectrum_report, export_results_zip
from .native_data_labels import describe_local_file
from .media_catalog import (MEDIA_COLORS, MEDIA_SYMBOLS, kinds_for_pass, filter_passes,
                            media_summary, capabilities_for_pass)
from .native_locations import load_locations, search_locations, city_label, regions_for
from .native_geocoding import search_worldwide
from .native_pass_filters import sort_filter_passes
from .native_orbit import OrbitEngine
from .native_maps import OrbitCanvas
from .native_map_parity import (
    map_satellite_capabilities, map_satellite_protocols,
    filter_orbit_snapshot, export_orbit_geojson)
from .native_signal_tools import discover_channels, fm_to_wav
from .sstv_series35 import extract_robot36_wav
from .native_imagery import list_official_images, fetch_official_image
from .native_protocols import (load_profiles, save_profiles, import_profiles,
                               export_profiles, parse_user_protocol, match_user_hints)


def local_time(value):
    try:
        return datetime.fromisoformat(str(value)).astimezone().strftime("%d %b %Y · %H:%M:%S")
    except (TypeError, ValueError):
        return "—"


def native_datetime(value):
    return QDateTime.fromSecsSinceEpoch(int(datetime.fromisoformat(value).timestamp()))


def small_bytes(count):
    return f"{count / 1048576:.1f} MiB"


class TaskSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class BackgroundTask(QRunnable):
    def __init__(self, job):
        super().__init__()
        self.job = job
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.result.emit(self.job())
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class SpectrumView(QWidget):
    """Relative RF evidence only. Not a fake satellite image or decoded packet."""
    def __init__(self):
        super().__init__()
        self.report = None
        self.setMinimumHeight(255)
        self.setAccessibleName("Measured CU8 spectrum and representative waterfall")

    def set_report(self, report):
        self.report = report
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0c1729"))
        painter.setPen(QColor("#a6bfdc"))
        if not self.report:
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "No IQ evidence loaded. Import a .cu8 and select Analyze.")
            painter.end()
            return
        values = self.report["relative_spectrum_db"]
        if not values:
            painter.end()
            return
        w, h = max(1, self.width()-45), max(1, self.height()-55)
        top, height = 25, max(45, int(h*.55))
        low, high = min(values), max(values)
        if abs(high-low) < .001:
            high += 1
        painter.setPen(QPen(QColor("#25405b"), 1))
        for i in range(5):
            y=top+i*height/4
            painter.drawLine(38,int(y),38+w,int(y))
        painter.setPen(QColor("#bed4ea"))
        painter.drawText(9,17,"Relative RF spectrum (dB-like; uncalibrated)")
        polygon = QPolygonF([QPointF(38+i*w/max(1,len(values)-1),
                                    top+(high-v)/(high-low)*height)
                             for i,v in enumerate(values)])
        painter.setPen(QPen(QColor("#52d6cc"),1.5))
        painter.drawPolyline(polygon)
        rows=self.report.get("waterfall_db") or []
        if rows:
            # Bounded <=96 x <=512; no external GPU/WebGL/browser dependency.
            image=QImage(len(rows[0]),len(rows),QImage.Format_RGB32)
            for y,row in enumerate(rows):
                for x,v in enumerate(row):
                    z=max(0,min(1,(v-low)/(high-low)))
                    image.setPixel(x,y,QColor(int(12+z*230),int(45+z*163),int(92+z*75)).rgb())
            painter.drawImage(QRectF(38,top+height+10,w,max(30,self.height()-top-height-42)),image)
        painter.setPen(QColor("#91aaca"))
        painter.drawText(38,self.height()-5,
                         "Window coverage: "+self.report["analysis_mode"]+
                         " · strongest bin "+f'{self.report["strongest_spectrum_bin_hz"]/1e6:.6f}'+" MHz")
        painter.end()


class NativeIqLevelView(QWidget):
    """Read-only chart of actual locally captured CU8 sample bytes."""

    def __init__(self,parent=None):
        super().__init__(parent)
        self.levels=[]
        self.setMinimumHeight(125)
        self.setAccessibleName("Actual relative CU8 receiver sample power history")

    def push(self,dbfs):
        if not math.isfinite(dbfs):
            return
        self.levels.append(max(-80.,min(0.,float(dbfs))))
        self.levels=self.levels[-120:]
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing,True)
        rect=self.rect()
        painter.fillRect(rect,QColor("#091523"))
        painter.setPen(QColor("#a9c6e0"))
        painter.drawText(12,20,"Real IQ sample level · relative digital dBFS (NOT calibrated dBm)")
        left,right=47,max(56,rect.width()-12)
        top,bottom=31,max(40,rect.height()-17)
        for db in (-80,-60,-40,-20,0):
            y=top+int((db+80)/80*(bottom-top))
            y=bottom-(y-top)
            painter.setPen(QColor("#294863"))
            painter.drawLine(left,y,right,y)
            painter.setPen(QColor("#93b4d2"))
            painter.drawText(7,y+4,str(db))
        if len(self.levels)<2:
            painter.setPen(QColor("#a6bdd6"))
            painter.drawText(left+12,top+30,"No real CU8 sample measurements yet")
            return
        count=len(self.levels)
        coords=[]
        for i,level in enumerate(self.levels):
            x=left+(right-left)*i/max(1,count-1)
            y=bottom-(bottom-top)*(level+80)/80.
            coords.append(QPointF(x,y))
        painter.setPen(QPen(QColor("#55d6c9"),2))
        painter.drawPolyline(QPolygonF(coords))
        painter.setPen(QColor("#f2f7ff"))
        painter.drawText(max(left,right-95),top+14,f"{self.levels[-1]:.1f} dBFS")


class SatelliteWindow(QMainWindow):
    """Only native Qt5 controls; controls are not replaced during timed updates."""
    def __init__(self, station=None, auto_poll=True):
        super().__init__()
        self.station = station if station is not None else Station()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.tasks = {}
        self.passes = {}
        self.last_jobs_key = None
        self.last_archive_key = None
        self.last_analysis = None
        self.last_report_path = None
        self.last_candidate_report = None
        self.preview_wav = None
        self.media_player = None
        self.decoded_paths = []
        self.robot36_report = None
        self.robot36_source_wav = None
        self.extra_visual_outputs=[]
        self.imported_path = None
        self.selected_path = None
        self.active = True
        self.orbit_engine=OrbitEngine(self.station)
        self.map_selected_norad=None
        self.map_live=True
        self.map_paused_at=None
        self.map_last_track_at=0
        self.map_track_segments=[]
        self.map_last_snapshot=None
        self.setWindowTitle("TIHULU Satellite Center · Native SDR")
        self.setWindowIcon(QIcon(str(Path(__file__).parent/"assets"/"tihulu-satellite.png")))
        self.resize(1320,850)
        self.setMinimumSize(900,650)
        self._build()
        self._style()
        self.map_timer=QTimer(self)
        self.map_timer.setInterval(1000)
        self.map_timer.timeout.connect(self.refresh_orbit_map)
        self.tabs.currentChanged.connect(self._on_tab_change)
        self.tabs.currentChanged.connect(self._update_nav_selection)
        self._update_nav_selection(self.tabs.currentIndex())
        if auto_poll:self.map_timer.start()
        self.statusBar().showMessage("Native Qt window. No browser, WebUSB or HTTP server.")
        self.level_timer=QTimer(self)
        self.level_timer.setInterval(1000)
        self.level_timer.timeout.connect(self._refresh_live_iq_level)
        if auto_poll:self.level_timer.start()
        self.timer=QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_status)
        if auto_poll:
            self.timer.start()
            self.refresh_status()

    def _style(self):
        self.setStyleSheet("""
          QMainWindow,QWidget{background:#080f1b;color:#e7effa;font-size:13px;font-family:"Noto Sans"}
          QFrame#passDetail{background:#112038;border:1px solid #324966;border-radius:14px}
          QLabel#passTitle{font-size:17px;font-weight:700;color:#f1f9ff}
          QLabel#passSubtitle{font-size:12px;color:#a9c5dd}
          QLabel#passSectionTitle{font-size:13px;font-weight:650;color:#c8e3f9}
          QLabel#dataHint{color:#9cb8d2;font-size:11px}
          QLineEdit{background:#162d49;color:#f3f7ff;border:1px solid #436080;border-radius:8px;padding:9px}
          QLineEdit:focus,QComboBox:focus{border:1px solid #65c9e5}
          QGroupBox{border:1px solid #324966;border-radius:14px;margin-top:14px;
                     padding:20px 12px 12px;background:#112038;font-weight:650}
          QGroupBox::title{subcontrol-origin:margin;left:17px;padding:0 7px;color:#dcecff}
          QTabWidget::pane{border:1px solid #31526f;border-radius:10px}
          QPushButton#primaryNav{background:transparent;border:0;border-bottom:3px solid transparent;
                   color:#b4d1e5;border-radius:0;font-size:13px;font-weight:650;padding:10px 12px}
          QPushButton#primaryNav:checked{color:#ffffff;background:#183752;border-bottom-color:#55d6c9}
          QPushButton#primaryNav:hover{background:#1a3a55}
          QToolButton#moreNav{background:#193b59;border:1px solid #3c6282;border-radius:8px;
                   color:#d4eafa;font-size:12px;font-weight:650;padding:9px 13px}
          QMenu{background:#11263e;border:1px solid #3b607d;color:#e6f3ff}
          QMenu::item{padding:10px 24px}
          QMenu::item:selected{background:#26547b}
          QFrame#workflowCard{border:1px solid #324966;border-radius:14px;background:#1b2a43}
          QFrame#workflowCard QLabel{background:transparent;border:0}
          QGroupBox QLabel{background:transparent;border:0}
          QScrollArea QLabel{background:transparent;border:0}
          QLabel#fileBanner{background:#122e45;border:1px solid #345c79}
          QLabel#workflowStep{font-size:14px;font-weight:750;color:#e9f6ff}
          QLabel#workflowDescription{color:#afc9e2;font-size:12px}
          QLabel#homeTagline{font-size:15px;color:#b8d8ea}
          QLabel#fileBanner{padding:10px;border:1px solid #345c79;border-radius:8px;
                            background:#122e45;color:#c5efff}
          QTabWidget#resultSteps::pane{border:1px solid #385b7c;border-radius:9px}

          QTabBar::tab{padding:10px 18px;background:#172c46;border:1px solid #2a4865}
          QTabBar::tab:selected{background:#24547d;color:#fff}
          QComboBox,QSpinBox,QDoubleSpinBox,QDateTimeEdit,QDateEdit,QPlainTextEdit,
          QTreeWidget,QTableWidget{background:#162d49;color:#f3f7ff;border:1px solid #436080;
                                 border-radius:8px;padding:8px;selection-background-color:#2873cf}
          QComboBox QAbstractItemView{background:#132843;color:#eff7ff;selection-background-color:#376c9d}
          QPushButton{background:#2873cf;color:#ffffff;border:1px solid #3b84dc;
                      border-radius:9px;padding:10px 14px;font-weight:600}
          QPushButton:hover{background:#3583e1}
          QPushButton#secondaryAction{background:#253b57;border-color:#54749d}
          QPushButton#dangerAction{background:#502e3e;border-color:#ac6378}
          QPushButton#dangerAction:hover{background:#704254}
          QPushButton:disabled{color:#6f88a3;background:#17283b}
          QHeaderView::section{background:#1a344f;color:#d9ebff;padding:9px;border:0;border-bottom:1px solid #34536e;font-weight:600}
          QTreeWidget::item{padding:6px}
          QTreeWidget::item:selected{background:#294c70;color:#ffffff}
          QScrollBar:vertical{width:11px;background:#101f34}
          QScrollBar::handle:vertical{background:#345d80;min-height:26px;border-radius:5px}
          QLabel#headline{font-size:26px;font-weight:750;color:#f1faff}
          QLabel#eyebrow{font-size:11px;font-weight:700;color:#87bdef}
          QLabel#hint{color:#a7bfd7}
        """)


    def _build(self):
        root=QWidget()
        layout=QVBoxLayout(root)
        layout.setContentsMargins(15,12,15,10)
        layout.setSpacing(10)
        header=QHBoxLayout()
        brand=QVBoxLayout()
        eyebrow=QLabel("TIHULU SATELLITE CENTER  ·  DIRECT NATIVE USB")
        eyebrow.setObjectName("eyebrow")
        brand.addWidget(eyebrow)
        title=QLabel("Satellite Center")
        title.setObjectName("headline")
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch(1)
        self.top_status=QLabel("Receive-only · SDR not acquired")
        header.addWidget(self.top_status)
        layout.addLayout(header)

        # Web-like primary navigation. Keep all original native pages and controls,
        # but present only the five common tasks; no browser/WebView is involved.
        self.tabs=QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.setDocumentMode(True)
        self.nav_buttons={}
        nav=QHBoxLayout()
        nav.setSpacing(3)
        for label,target in (
            ("Receiver & planner","Overview"),
            ("Hardware / USB","Hardware"),
            ("Satellite Images & Data","Satellite Images & Data"),
            ("Earth / Sky","Maps & Live"),
            ("Signal analysis","Recordings & results"),
            ("Pass planner","Passes & Data"),
        ):
            button=QPushButton(label.replace("&","&&"))
            button.setObjectName("primaryNav")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, destination=target: self._open_native_tab(destination))
            button.setAccessibleName("Open "+label)
            self.nav_buttons[target]=button
            nav.addWidget(button)
        self.more_button=QToolButton()
        self.more_button.setObjectName("moreNav")
        self.more_button.setText("More tools  ▾")
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        tools=QMenu(self.more_button)
        for label,target in (
            ("Auto reception","Auto reception"),
            ("Reception calendar","Reception calendar"),
            ("Manual RF capture","Manual RF capture"),
            ("Saved protocols","Saved protocols"),
        ):
            action=tools.addAction(label)
            action.triggered.connect(
                lambda checked=False, destination=target: self._open_native_tab(destination))
        self.more_button.setMenu(tools)
        nav.addWidget(self.more_button)
        nav.addStretch(1)
        layout.addLayout(nav)
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)

        self._dashboard_tab()
        self._hardware_tab()
        self._passes_tab()
        self._maps_tab()
        self._auto_tab()
        self._calendar_tab()
        self._capture_tab()
        self._results_tab()
        self._images_tab()
        self._protocols_tab()

    def _update_nav_selection(self,index):
        name=self.tabs.tabText(index) if 0<=index<self.tabs.count() else ""
        for key,button in self.nav_buttons.items():
            button.setChecked(key==name)
        self.more_button.setText("More tools  ▾" if name in self.nav_buttons
                                 else "More: "+name+"  ▾")

    def _panel(self, title, parent):
        group=QGroupBox(title.replace("&","&&"))
        group.setLayout(QVBoxLayout())
        parent.addWidget(group)
        return group.layout()

    def _row(self, layout, *widgets):
        row=QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget)
        layout.addLayout(row)

    def _button(self, label, callback, tooltip=None):
        button=QPushButton(label.replace("&","&&"))
        button.clicked.connect(callback)
        if tooltip: button.setToolTip(tooltip)
        return button

    def _hint(self, value):
        item=QLabel(value)
        item.setObjectName("hint")
        item.setWordWrap(True)
        return item

    def _new_tab(self, title):
        pane=QWidget()
        body=QVBoxLayout(pane)
        body.setSpacing(9)
        self.tabs.addTab(pane,title)
        return body


    def _dashboard_tab(self):
        """Same seven-section receiver-to-results information architecture as web.

        All controls are native Qt Widgets; never embed HTML or WebUSB.
        """
        host=self._new_tab("Overview")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.home_scroll=scroll
        host.addWidget(scroll)
        page=QWidget()
        body=QVBoxLayout(page)
        body.setSpacing(14)
        body.setContentsMargins(12,11,12,16)
        scroll.setWidget(page)

        heading=QLabel("Satellite Center  ·  Native desktop")
        heading.setObjectName("passTitle")
        body.addWidget(heading)
        body.addWidget(self._hint(
            "The same receiver & planner workflow as the web edition. "
            "All radio access uses native rtl_sdr/rtl_fm tools and your attached USB SDR. "
            "No WebUSB, browser, server or embedded website."))

        workflow=QGroupBox("Satellite Auto-Capture && Decode — three steps")
        w=QVBoxLayout(workflow)
        w.addWidget(self._hint(
            "Select a published image, text or voice target and schedule real local RF acquisition. "
            "Then inspect saved files and decode only what the signal actually contains."))
        top=QHBoxLayout()
        self.home_auto_mode=QComboBox()
        for name,ids in (
            ("ISS SSTV · event only",["iss-sstv"]),
            ("Earth weather images + ISS SSTV",["meteor-m2-3","meteor-m2-4","iss-sstv"]),
            ("ISS APRS · public packet text",["iss-aprs"]),
            ("ISS voice · FM audio candidate",["iss-voice"]),
            ("Images + text + voice",list(AUTO_DOWNLINK_PROFILES)),
        ):
            self.home_auto_mode.addItem(name,ids)
        self.home_auto_length=QSpinBox()
        self.home_auto_length.setRange(0,900)
        self.home_auto_length.setSpecialValueText("Auto · fit pass")
        self.home_auto_goal=QComboBox()
        self.home_auto_goal.addItem("Prefer full predicted pass","full")
        self.home_auto_goal.addItem("Quick sample","sample")
        top.addWidget(QLabel("Auto target"))
        top.addWidget(self.home_auto_mode,3)
        top.addWidget(QLabel("Seconds"))
        top.addWidget(self.home_auto_length,1)
        top.addWidget(self.home_auto_goal,2)
        w.addLayout(top)
        self.home_iss_format=QComboBox()
        self.home_iss_format.addItem("WAV · actual FM/SSTV audio","wav")
        self.home_iss_format.addItem("CU8 · original raw RF","cu8")
        self.home_iss_format.addItem("CU8 + WAV · from same native RF capture","both")
        form_formats=QFormLayout()
        form_formats.addRow("ISS recording format",self.home_iss_format)
        w.addLayout(form_formats)
        steps=QHBoxLayout()
        self.home_auto=self._button("2   Auto schedule & capture",self._home_auto)
        self.home_analyze=self._button("3   Open & analyze a recording",self._home_analyze)
        self.home_extract=self._button("View decoded results",self._home_extract)
        steps.addWidget(self._button("1 · Auto Schedule & Capture",self._home_schedule_now))
        steps.addWidget(self.home_analyze)
        steps.addWidget(self.home_extract)
        w.addLayout(steps)
        self.home_auto_status=self._hint(
            "No RF capture scheduled here. Native scheduling needs a confirmed receiver.")
        w.addWidget(self.home_auto_status)
        body.addWidget(workflow)

        columns=QHBoxLayout()
        columns.setSpacing(14)
        left_widget=QWidget()
        right_widget=QWidget()
        left=QVBoxLayout(left_widget)
        right=QVBoxLayout(right_widget)
        left.setContentsMargins(0,0,0,0)
        right.setContentsMargins(0,0,0,0)
        left.setSpacing(13)
        right.setSpacing(13)
        columns.addWidget(left_widget,1)
        columns.addWidget(right_widget,1)
        body.addLayout(columns)

        usb=QGroupBox("1 · Choose USB receiver")
        ul=QVBoxLayout(usb)
        self.device_label=self._hint("Checking physical RTL-SDR USB presence…")
        self.session_label=QLabel("Idle · no receiver in use")
        self.disk_label=self._hint("Local recordings directory not yet checked")
        self.cache_label=self._hint("No TLE data fetched automatically")
        for label in (self.device_label,self.session_label):
            label.setWordWrap(True)
            ul.addWidget(label)
        self.home_usb_state=self._hint(
            "USB identity is not the same as a physical IQ sample test.")
        ul.addWidget(self.home_usb_state)
        buttonrow=QHBoxLayout()
        buttonrow.addWidget(self._button("Connect & verify",self.connect_receiver))
        buttonrow.addWidget(self._button("Release USB / RF",self.disconnect_receiver))
        ul.addLayout(buttonrow)
        ul.addWidget(self._button(
            "Hardware diagnostics · USB tests, model, process and lock status",
            lambda:self._open_native_tab("Hardware")))
        left.addWidget(usb)

        manual=QGroupBox("2 · Receive satellite-band samples")
        ml=QVBoxLayout(manual)
        manual_form=QFormLayout()
        self.home_capture_profile=QComboBox()
        for key,info in PROFILES.items():
            self.home_capture_profile.addItem(info["label"],key)
        self.home_capture_profile.currentIndexChanged.connect(self._home_capture_modes)
        self.home_capture_mode=QComboBox()
        self.home_capture_rate=QComboBox()
        self.home_capture_rate.addItem("1.024 MS/s",1024000)
        self.home_capture_rate.addItem("2.048 MS/s",2048000)
        self.home_capture_rate.currentIndexChanged.connect(self._home_capture_budget)
        self.home_capture_length=QSpinBox()
        self.home_capture_length.setRange(8,900)
        self.home_capture_length.setValue(60)
        self.home_capture_mode.currentIndexChanged.connect(self._home_capture_budget)
        self.home_capture_length.valueChanged.connect(self._home_capture_budget)
        manual_form.addRow("Receive profile",self.home_capture_profile)
        manual_form.addRow("Save format",self.home_capture_mode)
        manual_form.addRow("IQ sample rate",self.home_capture_rate)
        manual_form.addRow("Recording length · seconds",self.home_capture_length)
        ml.addLayout(manual_form)
        self.home_capture_cost=self._hint("Local disk recording · estimated space")
        ml.addWidget(self.home_capture_cost)
        buttons=QHBoxLayout()
        buttons.addWidget(self._button("Start native RF capture",self._home_capture_now))
        buttons.addWidget(self._button("Stop recording",self.stop_capture))
        ml.addLayout(buttons)
        self.home_sample_state=self._hint("No live CU8 file is being recorded.")
        ml.addWidget(self.home_sample_state)
        self.home_level_chart=NativeIqLevelView()
        ml.addWidget(self.home_level_chart)
        ml.addWidget(self._hint(
            "CU8 stores original IQ, WAV stores actual FM-demodulated audio. "
            "CU8+WAV captures the same RF data once and derives the WAV afterward. "
            "No image/speech or satellite identity is assumed."))
        left.addWidget(manual)
        left.addStretch(1)

        planner=QGroupBox("3 · Satellite pass planner")
        pl=QVBoxLayout(planner)
        pl.setSpacing(9)
        pl.addWidget(self._hint(
            "Find a ground station locally (Germany / Türkiye), anywhere online, "
            "or enter coordinates. Orbit predictions are TLE geometry, not radio signals."))
        self.home_station=QComboBox()
        for city in ("Cologne","Berlin","Hamburg","Izmir","Istanbul","Ankara"):
            if city in LOCATIONS:self.home_station.addItem(city,city)
        self.home_station.addItem("Custom coordinates (anywhere)","custom")
        self.home_station.addItem("Search offline city / district / town","offline")
        self.home_station.addItem("Search any city worldwide (online)","online")
        self.home_station.currentIndexChanged.connect(self._home_select_station)
        self.home_search_timer=QTimer(self)
        self.home_search_timer.setSingleShot(True)
        self.home_search_timer.setInterval(850)
        self.home_search_timer.timeout.connect(self._home_online_auto_search)
        self.home_geocode_generation=0
        self.home_geocode_cache={}
        pl.addWidget(self.home_station)

        # Identical interaction model to website: query first, optional remote
        # suggestions while typing, country/state and GPS in expandable options.
        self.home_advanced_button=QPushButton("Advanced location options  ▸")
        self.home_advanced_button.setCheckable(True)
        self.home_location_options=QWidget()
        adv=QVBoxLayout(self.home_location_options)
        adv.setContentsMargins(0,0,0,0)
        location_filters=QHBoxLayout()
        self.home_country=QComboBox()
        for title,key in (("Germany + Türkiye","all"),("Germany","DE"),
                          ("Türkiye","TR")):
            self.home_country.addItem(title,key)
        self.home_region=QComboBox()
        self.home_region.addItem("All states / provinces",None)
        self.home_country.currentIndexChanged.connect(self._home_update_regions)
        self.home_region.currentIndexChanged.connect(self._home_find_city)
        location_filters.addWidget(self.home_country,1)
        location_filters.addWidget(self.home_region,2)
        adv.addLayout(location_filters)

        self.home_city_search=QLineEdit()
        self.home_city_search.setPlaceholderText(
            "Search city, district or town · Hürth, Köln, İzmir, Karaburun…")
        self.home_city_search.setClearButtonEnabled(True)
        self.home_city_search.textChanged.connect(self._home_find_city)
        self.home_city_search.returnPressed.connect(self._home_apply_first_city)
        pl.addWidget(self.home_city_search)
        self.home_auto_online=QCheckBox("Include worldwide online suggestions while typing")
        self.home_auto_online.setToolTip(
            "Opt-in: city search terms are sent to Open-Meteo after an 850 ms pause.")
        self.home_auto_online.toggled.connect(self._home_online_option_changed)
        pl.addWidget(self.home_auto_online)
        self.home_city_results=QListWidget()
        self.home_city_results.setMaximumHeight(110)
        self.home_city_results.setMinimumHeight(0)
        self.home_city_results.setVisible(False)
        self.home_city_results.itemClicked.connect(self._home_apply_city_item)
        self.home_city_results.itemActivated.connect(self._home_apply_city_item)
        pl.addWidget(self.home_city_results)
        self.home_city_info=self._hint(
            "8,084 bundled DE/TR places · choose country/state and type a name. "
            "No internet or GPS access occurs while typing.")
        pl.addWidget(self.home_city_info)
        online_actions=QHBoxLayout()
        online_actions.addWidget(self._button(
            "Search worldwide online",self._home_worldwide_lookup))
        online_actions.addWidget(self._button(
            "Use OS location (ask permission)",self._request_system_location))
        adv.addLayout(online_actions)

        coordinates=QHBoxLayout()
        self.home_lat=QDoubleSpinBox()
        self.home_lat.setDecimals(5);self.home_lat.setRange(-90,90)
        self.home_lat.setValue(50.938)
        self.home_lon=QDoubleSpinBox()
        self.home_lon.setDecimals(5);self.home_lon.setRange(-180,180)
        self.home_lon.setValue(6.960)
        self.home_lat.valueChanged.connect(self._home_coordinates_changed)
        self.home_lon.valueChanged.connect(self._home_coordinates_changed)
        coordinates.addWidget(QLabel("Latitude"))
        coordinates.addWidget(self.home_lat,1)
        coordinates.addWidget(QLabel("Longitude"))
        coordinates.addWidget(self.home_lon,1)
        adv.addLayout(coordinates)

        lookahead=QHBoxLayout()
        self.home_hours=QSpinBox()
        self.home_hours.setRange(1,72);self.home_hours.setValue(24)
        self.home_elev=QDoubleSpinBox()
        self.home_elev.setRange(5,75);self.home_elev.setValue(15)
        self.home_hours.valueChanged.connect(self._home_planning_range_changed)
        self.home_elev.valueChanged.connect(self._home_planning_range_changed)
        lookahead.addWidget(QLabel("Lookahead · h"))
        lookahead.addWidget(self.home_hours,1)
        lookahead.addWidget(QLabel("Min elevation · °"))
        lookahead.addWidget(self.home_elev,1)
        adv.addLayout(lookahead)
        self.home_location_options.setVisible(False)
        self.home_advanced_button.toggled.connect(self.home_location_options.setVisible)
        self.home_advanced_button.toggled.connect(
            lambda open_:self.home_advanced_button.setText(
                "Advanced location options  ▾" if open_ else
                "Advanced location options  ▸"))
        pl.addWidget(self.home_advanced_button)
        pl.addWidget(self.home_location_options)

        stationrow=QHBoxLayout()
        stationrow.addWidget(self._button("Refresh orbit data",self.refresh_tles))
        stationrow.addWidget(self._button("Calculate passes",self.calculate_passes))
        pl.addLayout(stationrow)
        self.home_pass_summary=self._hint(
            "No passes calculated. On the first calculation the app requests "
            "public TLEs if no usable local orbit files exist.")
        pl.addWidget(self.home_pass_summary)

        self.home_pass_search=QLineEdit()
        self.home_pass_search.setPlaceholderText("Filter satellite name or NORAD ID…")
        self.home_pass_search.setClearButtonEnabled(True)
        self.home_pass_search.textChanged.connect(self._render_home_passes)
        pl.addWidget(self.home_pass_search)
        filters=QHBoxLayout()
        self.home_pass_family=QComboBox()
        for label,value in (("All satellite families","all"),("ISS","iss"),
                            ("Meteor","meteor"),("CubeSat","cubesat"),
                            ("Iridium","iridium")):
            self.home_pass_family.addItem(label,value)
        self.home_pass_media=QComboBox()
        for label,value in (("All formats","All"),("Image","Image"),
                            ("Audio","Audio"),("Text/packets","Text"),
                            ("RF data","RF data"),("RF only","RF only")):
            self.home_pass_media.addItem(label,value)
        self.home_pass_family.currentIndexChanged.connect(self._render_home_passes)
        self.home_pass_media.currentIndexChanged.connect(self._render_home_passes)
        filters.addWidget(self.home_pass_family)
        filters.addWidget(self.home_pass_media)
        pl.addLayout(filters)

        self.home_pass_sort=QComboBox()
        for label,value in (("Soonest","soonest"),("Latest","latest"),
                            ("Highest elevation","high"),("Lowest elevation","low"),
                            ("Longest duration","duration-long"),
                            ("Shortest duration","duration-short"),
                            ("Name A–Z","name")):
            self.home_pass_sort.addItem(label,value)
        self.home_pass_sort.currentIndexChanged.connect(self._render_home_passes)
        sorter=QHBoxLayout()
        sorter.addWidget(QLabel("Sort satellite passes"))
        sorter.addWidget(self.home_pass_sort,1)
        pl.addLayout(sorter)

        self.home_pass_results=QTreeWidget()
        self.home_pass_results.setHeaderLabels(
            ["Satellite · NORAD","AOS · local","Peak","Formats"])
        self.home_pass_results.setRootIsDecorated(False)
        self.home_pass_results.setMaximumHeight(225)
        self.home_pass_results.setMinimumHeight(120)
        self.home_pass_results.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.home_pass_results.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        for col in (2,3):
            self.home_pass_results.header().setSectionResizeMode(
                col,QHeaderView.ResizeToContents)
        self.home_pass_results.itemSelectionChanged.connect(self._home_pass_selected)
        pl.addWidget(self.home_pass_results)
        self.home_pass_detail=self._hint(
            "Select a predicted pass to see its timing and open the editable schedule.")
        pl.addWidget(self.home_pass_detail)
        pass_actions=QHBoxLayout()
        self.home_plan_button=self._button(
            "Plan selected pass",self._home_open_selected_pass)
        self.home_plan_button.setEnabled(False)
        pass_actions.addWidget(self.home_plan_button)
        pass_actions.addWidget(self._button(
            "Full pass planner / calendar",
            lambda:self._open_native_tab("Passes & Data")))
        pl.addLayout(pass_actions)
        right.addWidget(planner)

        calendar=QGroupBox("4 · Scheduled reception && recorded data")
        cl=QVBoxLayout(calendar)
        self.home_jobs_status=self._hint("No native RF jobs checked yet.")
        cl.addWidget(self.home_jobs_status)
        cl.addWidget(self.disk_label)
        cl.addWidget(self.cache_label)
        calbuttons=QHBoxLayout()
        calbuttons.addWidget(self._button("Open 24-hour calendar",
                                         lambda:self._open_native_tab("Reception calendar")))
        calbuttons.addWidget(self._button("Open saved data",self._home_analyze))
        cl.addLayout(calbuttons)
        right.addWidget(calendar)
        right.addStretch(1)

        for title,description,action in (
            ("5 · Satellite maps · Earth & sky",
             "Live TLE ground tracks, selectable satellites, native Earth/Sky, "
             "optional OpenStreetMap and PNG/GeoJSON exports.",
             lambda:self._open_native_tab("Maps & Live")),
            ("6 · Signal Intelligence · CU8 I/Q analysis",
             "Whole-file FFT, time-frequency waterfall, candidate signals, "
             "real FM audio previews and independent local file analysis.",
             self._home_analyze),
            ("7 · Satellite Images & Data",
             "Real Robot36 PNG / Meteor LRPT decoding, local WAV/text previews, "
             "protocol profiles, results ZIP and original online imagery.",
             lambda:self._open_native_tab("Satellite Images & Data")),
        ):
            card=QGroupBox(title)
            layout=QHBoxLayout(card)
            caption=QLabel(description)
            caption.setObjectName("hint")
            caption.setWordWrap(True)
            layout.addWidget(caption,3)
            layout.addWidget(self._button("Open section  →",action),1)
            body.addWidget(card)
        body.addWidget(self._hint(
            "Native application: receiver ownership is explicit. Disconnect keeps RF "
            "disabled until the next successful physical USB + IQ verification. "
            "USB hardware remains electrically connected until unplugged."))
        self._home_capture_modes()

    def _hardware_tab(self):
        """Native USB panel: physical presence != RF lease != app enable."""
        host=self._new_tab("Hardware")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host.addWidget(scroll)
        page=QWidget()
        body=QVBoxLayout(page)
        body.setSpacing(12)
        scroll.setWidget(page)
        heading=QLabel("USB receivers · connect, test and release")
        heading.setObjectName("passTitle")
        body.addWidget(heading)
        body.addWidget(self._hint(
            "1. Plug in the physical USB device and antenna. "
            "2. Refresh to see it on this computer. "
            "3. Connect & verify to actually open it briefly with rtl_test. "
            "4. Disconnect to stop this app's RF processes and disable future captures."))

        card=QFrame()
        card.setObjectName("workflowCard")
        state=QVBoxLayout(card)
        self.hardware_presence=QLabel("USB presence: not checked yet")
        self.hardware_presence.setObjectName("passTitle")
        self.hardware_access=self._hint("Physical USB-open test has not been run.")
        self.hardware_mode=self._hint("Application RF state: checking…")
        self.hardware_lease=self._hint("Receiver release: checking…")
        self.hardware_busy=self._hint("External receiver programs: checking…")
        self.hardware_schedules=self._hint("Pending RF jobs: checking…")
        for item in (self.hardware_presence,self.hardware_access,self.hardware_mode,
                     self.hardware_lease,self.hardware_busy,self.hardware_schedules):
            item.setWordWrap(True)
            state.addWidget(item)
        body.addWidget(card)

        actions=QHBoxLayout()
        self.hardware_refresh_button=self._button("↻  Refresh devices",self.refresh_status)
        self.hardware_test_button=self._button("Test USB only",self.usb_test)
        self.hardware_test_button.setObjectName("secondaryAction")
        sample_actions=QHBoxLayout()
        self.hardware_test_frequency=QComboBox()
        for name,hz in (
            ("Meteor 137.900 MHz",137900000),
            ("Meteor 137.100 MHz",137100000),
            ("ISS VHF 145.800 MHz",145800000),
            ("ISS SSTV 437.550 MHz",437550000),
            ("ISS APRS 145.825 MHz",145825000),
            ("Iridium RF 1620 MHz",1620000000)):
            self.hardware_test_frequency.addItem(name,hz)
        self.hardware_sample_button=self._button(
            "Test real RF / IQ samples (0.5 sec)",self.sample_receiver)
        self.hardware_connect_button=self._button("Connect & enable RF",self.connect_receiver)
        self.hardware_disconnect_button=self._button("Stop & disconnect RF",self.disconnect_receiver)
        self.hardware_disconnect_button.setObjectName("dangerAction")
        for button in (self.hardware_refresh_button,self.hardware_test_button,
                       self.hardware_connect_button,self.hardware_disconnect_button):
            actions.addWidget(button)
        body.addLayout(actions)
        sample_actions.addWidget(QLabel("Test frequency"))
        sample_actions.addWidget(self.hardware_test_frequency)
        sample_actions.addWidget(self.hardware_sample_button)
        body.addLayout(sample_actions)
        self.hardware_feedback=self._hint(
            "No test yet. 'Detected' means a USB ID was seen; it does not prove the receiver can be opened.")
        self.hardware_feedback.setObjectName("fileBanner")
        body.addWidget(self.hardware_feedback)

        body.addWidget(QLabel("USB hardware discovered on this computer"))
        self.hardware_devices=QTreeWidget()
        self.hardware_devices.setHeaderLabels(["Hardware / model","Receiver type","USB ID","System path"])
        self.hardware_devices.setRootIsDecorated(False)
        self.hardware_devices.setMaximumHeight(170)
        self.hardware_devices.header().setSectionResizeMode(0,QHeaderView.Stretch)
        for col in (1,2,3):
            self.hardware_devices.header().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        body.addWidget(self.hardware_devices)
        self.hardware_inventory_key=None
        self.hardware_log=QPlainTextEdit()
        self.hardware_log.setReadOnly(True)
        self.hardware_log.setMaximumHeight(110)
        self.hardware_log.setPlainText(
            "No USB diagnostics yet. Only explicit Test or Connect opens an SDR.")
        body.addWidget(self.hardware_log)
        body.addWidget(self._hint(
            "Disconnect is a software RF safety control: it stops only Satellite Center's "
            "owned processes, releases its SDR lock, and remembers RF disabled after restart. "
            "Future scheduled recordings are paused until you explicitly Connect again. "
            "It cannot electrically power off, physically eject or unplug USB hardware, "
            "and it never terminates readsb, Gqrx or another application's receiver. "
            "Hauppauge DVB-T2 hardware is listed separately; it is not a general IQ SDR."))
        body.addStretch(1)

    def sample_receiver(self):
        frequency=self.hardware_test_frequency.currentData()
        self.hardware_feedback.setText(
            "Reading actual CU8 I/Q samples from the connected receiver…")
        self._task("Real RF sample test",
                   lambda:self.station.sample_test(int(frequency)),
                   self._sample_receiver_done)

    def _sample_receiver_done(self,report):
        self.hardware_log.setPlainText(json.dumps(report,indent=2,default=str))
        self.hardware_feedback.setText(
            "PASS: "+str(report["complex_samples"])+" real complex I/Q samples received "
            "at "+str(report["frequency_hz"]/1e6)+" MHz. "
            "Test process and lock released. Signal identity remains unknown.")
        self.refresh_status()

    def connect_receiver(self):
        self.hardware_feedback.setText("Checking USB with rtl_test and reading real IQ bytes…")
        self._task("Connect SDR",self.station.connect_receiver,
                   self._connected_receiver)

    def _connected_receiver(self,result):
        self.hardware_feedback.setText(
            "USB OPEN + ACTUAL IQ SAMPLES PASS. RTL-SDR is ready for explicit "
            "recordings. Both test handles and lock were released while idle.")
        self.hardware_log.setPlainText(json.dumps(result,indent=2,default=str))
        self.refresh_status()

    def disconnect_receiver(self):
        with self.station.lock:
            active=bool(self.station.session.get("active") or self.station.launching)
            pending=sum(j.get("state")=="pending" for j in self.station.jobs)
        if active or pending:
            warning=("Stop only this application's RF capture and keep RF disabled "
                     "until the next verified Connect?\n\n")
            if pending:
                warning+=f"{pending} pending recording(s) will be PAUSED, not deleted.\n"
            warning+="The USB device itself will remain physically plugged in."
            if QMessageBox.question(self,"Disconnect and disarm SDR",warning,
                                    QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:
                return
        self.hardware_feedback.setText(
            "Disabling RF and stopping owned receiver processes. Confirming release…")
        self._task("Disconnect SDR",self.station.disconnect_receiver,
                   self._disconnected_receiver)

    def _disconnected_receiver(self,result):
        if result.get("app_released"):
            message=("RF DISABLED · Satellite Center owns no live SDR process or receiver lock. "
                     f"{result.get('pending_jobs_paused',0)} pending job(s) paused.")
        else:
            message=("RF DISABLED · stop requested, but release is not yet verified. "
                     "Refresh and check for remaining owned processes.")
        self.hardware_feedback.setText(message)
        self.hardware_log.setPlainText(json.dumps(result,indent=2,default=str))
        self.refresh_status()

    def _open_native_tab(self,name):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index)==name:
                self.tabs.setCurrentIndex(index)
                return True
        self.statusBar().showMessage("Native section unavailable: "+name,10000)
        return False

    def _home_capture_modes(self,*_):
        key=self.home_capture_profile.currentData()
        previous=self.home_capture_mode.currentData()
        self.home_capture_mode.blockSignals(True)
        self.home_capture_mode.clear()
        for mode,label in (
            ("iq","CU8 · original RF/IQ"),
            ("iq_and_fm_wav","CU8 + WAV · same physical RF samples"),
            ("sstv_audio","WAV · FM/SSTV"),
            ("fm_audio","WAV · FM voice"),
            ("aprs","TXT · AX.25 / APRS"),
            ("survey","JSON · RF spectrum survey"),
        ):
            if key and allowed_mode(key,mode):
                self.home_capture_mode.addItem(label,mode)
        old=self.home_capture_mode.findData(previous)
        if old>=0:self.home_capture_mode.setCurrentIndex(old)
        self.home_capture_mode.blockSignals(False)
        self._home_capture_budget()

    def _home_capture_budget(self,*_):
        mode=self.home_capture_mode.currentData()
        rate=int(self.home_capture_rate.currentData() or 1024000)
        is_iq=mode in ("iq","iq_and_fm_wav")
        cap=(min(900,MAX_IQ_BYTES//(2*rate+(64000 if mode=="iq_and_fm_wav" else 0)))
             if is_iq else 180 if mode=="survey" else 900)
        self.home_capture_length.setMaximum(max(8,cap))
        self.home_capture_rate.setEnabled(is_iq)
        seconds=self.home_capture_length.value()
        estimate=(2*rate/1e6+(.064 if mode=="iq_and_fm_wav" else 0)
                  if is_iq else .096)
        self.home_capture_cost.setText(
            "Estimated local disk: ~"+f"{seconds*estimate:.1f}"+" MB. "
            "Native RTL-SDR receiver, no WebUSB. Source identity unverified.")

    def _home_capture_now(self):
        profile=self.home_capture_profile.currentData()
        mode=self.home_capture_mode.currentData()
        if not profile or not mode:return
        self.capture_profile.setCurrentIndex(
            self.capture_profile.findData(profile))
        mode_index=self.capture_mode.findData(mode)
        if mode_index>=0:self.capture_mode.setCurrentIndex(mode_index)
        self.capture_sample_rate.setCurrentIndex(
            self.capture_sample_rate.findData(self.home_capture_rate.currentData()))
        self.capture_seconds.setValue(self.home_capture_length.value())
        self.start_capture()

    def _home_schedule_now(self):
        targets=self.home_auto_mode.currentData() or []
        for mid,box in self.mission_boxes.items():
            box.setChecked(mid in targets)
        self.coverage.setCurrentIndex(self.coverage.findData(
            self.home_auto_goal.currentData()))
        self.auto_seconds.setValue(self.home_auto_length.value())
        self.auto_iss_format.setCurrentIndex(
            self.auto_iss_format.findData(self.home_iss_format.currentData()))
        self.auto_schedule()


    def _home_select_station(self,*_):
        selected=self.home_station.currentData()
        if not hasattr(self,"city"):
            return
        if selected in LOCATIONS:
            self.home_search_timer.stop()
            self.city.setCurrentText(selected)
            self.home_city_info.setText(
                "Preset: "+selected+" · change station any time, then recalculate passes.")
        elif selected=="offline":
            self.home_auto_online.setChecked(False)
            self.home_city_search.setFocus()
            self._home_find_city()
        elif selected=="online":
            # Worldwide is a deliberate search preference and user permission
            # to send the current query through Open-Meteo after debounce.
            self.home_auto_online.setChecked(True)
            self.home_country.setCurrentIndex(self.home_country.findData("all"))
            self.home_city_search.setFocus()
            self.home_city_info.setText(
                "Worldwide online search selected. Type Sydney or another city; "
                "suggestions will appear below without a second button.")
            self._home_find_city()
        else:
            self.home_search_timer.stop()
            self.city.setCurrentText("Custom coordinates")
            self.home_advanced_button.setChecked(True)
            self.home_lat.setFocus()
            self.home_city_info.setText(
                "Custom coordinates can describe any location on Earth.")

    def _home_update_regions(self,*_):
        if not hasattr(self,"_offline_cities"):
            return
        selected_country=self.home_country.currentData() or "all"
        self.home_region.blockSignals(True)
        self.home_region.clear()
        self.home_region.addItem("All states / provinces",None)
        for region in regions_for(self._offline_cities,selected_country):
            self.home_region.addItem(region,region)
        self.home_region.blockSignals(False)
        self._home_find_city()
        self._sync_home_region_to_detail()

    def _sync_home_region_to_detail(self):
        """One country/region filter state, not two contradictory selectors."""
        if not hasattr(self,"city_country") or not hasattr(self,"city_region"):
            return
        cc=self.home_country.currentData() or "all"
        if self.city_country.currentData()!=cc:
            self.city_country.blockSignals(True)
            self.city_country.setCurrentIndex(self.city_country.findData(cc))
            self.city_country.blockSignals(False)
            self._refresh_city_regions()
        region=self.home_region.currentData()
        index=self.city_region.findData(region)
        if index>=0 and self.city_region.currentIndex()!=index:
            self.city_region.blockSignals(True)
            self.city_region.setCurrentIndex(index)
            self.city_region.blockSignals(False)
        self._refresh_city_search()

    def _sync_detail_region_to_home(self,*_):
        if not hasattr(self,"home_country") or not hasattr(self,"home_region"):
            return
        cc=self.city_country.currentData() or "all"
        if self.home_country.currentData()!=cc:
            self.home_country.blockSignals(True)
            self.home_country.setCurrentIndex(self.home_country.findData(cc))
            self.home_country.blockSignals(False)
            self._home_update_regions()
        index=self.home_region.findData(self.city_region.currentData())
        if index>=0 and self.home_region.currentIndex()!=index:
            self.home_region.blockSignals(True)
            self.home_region.setCurrentIndex(index)
            self.home_region.blockSignals(False)
        self._home_find_city()


    def _home_find_city(self,*_):
        if not hasattr(self,"_offline_cities"):
            return
        self.home_geocode_generation += 1
        self.home_search_timer.stop()
        query=self.home_city_search.text().strip()
        cc=self.home_country.currentData() or "all"
        region=self.home_region.currentData()
        online_mode=self.home_station.currentData()=="online"
        self.home_offline_results=[] if online_mode else search_locations(
            self._offline_cities,query,cc,limit=12,region=region)
        self.home_remote_results=[]
        if hasattr(self,"city_country") and hasattr(self,"city_region"):
            self._sync_home_region_to_detail()
        self._home_render_location_results()
        if len(query)<2:
            self.home_city_info.setText(
                "Type a city or town. Offline DE/TR results work without internet.")
            return
        automatic=online_mode or self.home_auto_online.isChecked()
        if automatic and len(query)>=3:
            self.home_city_info.setText(
                "Searching worldwide after a short pause (Open-Meteo opt-in)…")
            self.home_search_timer.start()
        elif self.home_offline_results:
            self.home_city_info.setText(
                f"{len(self.home_offline_results)} local match(es) · select a location.")
        else:
            self.home_city_info.setText(
                "No offline match. Use worldwide online search or custom coordinates.")

    def _home_render_location_results(self):
        choices=list(self.home_offline_results)[:12]+list(self.home_remote_results)[:10]
        self.home_city_results.blockSignals(True)
        self.home_city_results.clear()
        for row in choices:
            online=isinstance(row,dict)
            label=row["label"] if online else city_label(row)+" · Offline"
            item=QListWidgetItem(label)
            item.setData(Qt.UserRole,row)
            self.home_city_results.addItem(item)
        self.home_city_results.blockSignals(False)
        self.home_city_results.setVisible(bool(choices))

    def _home_online_option_changed(self,enabled):
        if not enabled:
            self.home_search_timer.stop()
            self.home_remote_results=[]
            self.home_geocode_generation+=1
        self._home_find_city()

    def _home_online_auto_search(self):
        query=self.home_city_search.text().strip()
        if len(query)<3 or not (
            self.home_auto_online.isChecked() or self.home_station.currentData()=="online"):
            return
        self._home_request_online(query)

    def _home_request_online(self,query):
        if "Home worldwide geocoding" in self.tasks:
            # In-flight remote query may be stale; retry with newest query after
            # it has completed rather than returning a mismatched old city.
            self.home_search_timer.start(350)
            return
        cc="all" if self.home_station.currentData()=="online" else (
            self.home_country.currentData() or "all")
        cache_key=(query.casefold(),cc)
        if cache_key in self.home_geocode_cache:
            self._home_online_results(query,cc,self.home_geocode_cache[cache_key])
            return
        self.home_city_info.setText(
            "Looking up "+query+" worldwide… Only this search term is sent.")
        self._task(
            "Home worldwide geocoding",
            lambda:search_worldwide(query,cc),
            lambda rows:self._home_online_results(query,cc,rows))

    def _home_online_results(self,query,country,rows):
        key=(query.casefold(),country)
        if len(self.home_geocode_cache)>=25:
            self.home_geocode_cache.pop(next(iter(self.home_geocode_cache)))
        self.home_geocode_cache[key]=rows
        if query!=self.home_city_search.text().strip():
            self.home_search_timer.start(100)
            return
        self.home_remote_results=rows
        self._home_render_location_results()
        self.home_city_info.setText(
            f"{len(rows)} worldwide city match(es). "
            "Select the correct name, region and country to update the station."
            if rows else
            "Worldwide geocoder returned no matches. Check spelling or use custom coordinates.")


    def _home_apply_first_city(self):
        item=self.home_city_results.currentItem()
        if item is None and self.home_city_results.count():
            item=self.home_city_results.item(0)
        if item is not None:
            return self._home_apply_city_item(item)
        if len(self.home_city_search.text().strip())>=2:
            return self._home_worldwide_lookup()

    def _home_apply_city_item(self,item):
        row=item.data(Qt.UserRole)
        online=isinstance(row,dict)
        if online:
            lat,lon=float(row["lat"]),float(row["lon"])
            label=row["label"]
            mode="online"
            query=row["name"]
        elif isinstance(row,(tuple,list)) and len(row)==5:
            lat,lon=float(row[3]),float(row[4])
            label=city_label(row)
            mode="offline"
            query=row[1]
        else:
            return
        if not -90<=lat<=90 or not -180<=lon<=180:return
        self.home_search_timer.stop()
        self.home_station.blockSignals(True)
        self.home_station.setCurrentIndex(self.home_station.findData(mode))
        self.home_station.blockSignals(False)
        self.home_city_search.blockSignals(True)
        self.home_city_search.setText(query)
        self.home_city_search.blockSignals(False)
        self.home_city_results.setVisible(False)
        self.home_offline_results=[]
        self.home_remote_results=[]
        self.city.setCurrentText("Custom coordinates")
        self.lat.setValue(lat)
        self.lon.setValue(lon)
        self.city_search.setText(label)
        self.home_city_info.setText(
            "Selected: "+label+f" · {lat:.5f}°, {lon:.5f}°. "
            "Ready for Calculate passes. Typing alone never changes coordinates.")

    def _home_coordinates_changed(self,*_):
        if not hasattr(self,"lat"):
            return
        if self.home_station.currentData()!="custom":
            self.home_station.blockSignals(True)
            self.home_station.setCurrentIndex(self.home_station.findData("custom"))
            self.home_station.blockSignals(False)
        self.city.setCurrentText("Custom coordinates")
        self.lat.setValue(self.home_lat.value())
        self.lon.setValue(self.home_lon.value())
        self.home_city_info.setText(
            "Custom coordinates applied to the shared pass planner and native maps. "
            "Recalculate passes after edits.")

    def _home_planning_range_changed(self,*_):
        if hasattr(self,"hours"):
            self.hours.setValue(self.home_hours.value())
            self.elev.setValue(self.home_elev.value())

    def _sync_home_from_planner(self,*_):
        if not hasattr(self,"lat") or not hasattr(self,"home_lat"):
            return
        for home,target in (
            (self.home_lat,self.lat.value()),
            (self.home_lon,self.lon.value()),
            (self.home_hours,self.hours.value()),
            (self.home_elev,self.elev.value()),
        ):
            home.blockSignals(True)
            home.setValue(target)
            home.blockSignals(False)


    def _home_worldwide_lookup(self):
        query=self.home_city_search.text().strip()
        if len(query)<2:
            return QMessageBox.information(
                self,"Worldwide location lookup",
                "Type at least 2 characters to search worldwide.")
        self.home_station.blockSignals(True)
        self.home_station.setCurrentIndex(self.home_station.findData("online"))
        self.home_station.blockSignals(False)
        self.home_country.setCurrentIndex(self.home_country.findData("all"))
        self.home_auto_online.setChecked(True)
        self._home_request_online(query)

    def _render_home_passes(self,*_):
        if not hasattr(self,"home_pass_results"):
            return
        old=self.home_pass_results.currentItem()
        selected=old.data(0,Qt.UserRole) if old else None
        all_rows=list(self.passes.values())
        rows=sort_filter_passes(
            all_rows,search=self.home_pass_search.text(),
            family=self.home_pass_family.currentData() or "all",
            medium=self.home_pass_media.currentData() or "All",
            order=self.home_pass_sort.currentData() or "soonest")
        self.home_pass_results.blockSignals(True)
        self.home_pass_results.clear()
        selected_item=None
        for row in rows[:150]:
            kinds=kinds_for_pass(row)
            item=QTreeWidgetItem([
                str(row.get("name","?"))+" · "+str(row.get("norad","?")),
                local_time(row["aos"]),
                str(row.get("max_elevation_deg","?"))+"°",
                " / ".join(kinds) if kinds else "RF unknown"
            ])
            item.setData(0,Qt.UserRole,row["id"])
            item.setToolTip(0,
                "TLE-derived orbital prediction only. No signal or media received.")
            self.home_pass_results.addTopLevelItem(item)
            if row["id"]==selected:selected_item=item
        self.home_pass_results.blockSignals(False)
        if selected_item is not None:
            self.home_pass_results.setCurrentItem(selected_item)
        elif rows:
            self.home_pass_results.setCurrentItem(self.home_pass_results.topLevelItem(0))
        else:
            self._home_pass_selected()
        if all_rows:
            self.home_pass_summary.setText(
                f"{len(rows)} match(es) / {len(all_rows)} predicted pass(es)"
                +(" · first 150 shown" if len(rows)>150 else "")+
                " · TLE geometry only, no RF verified.")

    def _home_pass_selected(self):
        item=self.home_pass_results.currentItem()
        row=self.passes.get(item.data(0,Qt.UserRole)) if item else None
        self.home_plan_button.setEnabled(bool(row))
        if not row:
            self.home_pass_detail.setText(
                "No pass selected. Calculate passes or clear the filters.")
            return
        self.home_pass_detail.setText(
            str(row["name"])+" · NORAD "+str(row.get("norad","?"))+
            " · "+local_time(row["aos"])+" → "+local_time(row["los"])+
            " · "+str(row.get("max_elevation_deg","?"))+"° peak · "+
            " / ".join(kinds_for_pass(row))+
            " (candidate formats, not received files)")

    def _home_open_selected_pass(self):
        item=self.home_pass_results.currentItem()
        if item is None:return
        pass_id=item.data(0,Qt.UserRole)
        # The same data underlies both views. Clear hidden detailed filters
        # so a home-selected satellite cannot disappear when navigating.
        self.pass_search.clear()
        self.pass_family_filter.setCurrentIndex(0)
        self.pass_media_filter.setCurrentIndex(0)
        self.pass_sort.setCurrentIndex(
            max(0,self.pass_sort.findData(self.home_pass_sort.currentData())))
        self._render_pass_results()
        target=None
        for i in range(self.pass_list.topLevelItemCount()):
            candidate=self.pass_list.topLevelItem(i)
            if candidate.data(0,Qt.UserRole)==pass_id:
                target=candidate
                break
        if target is None:
            return QMessageBox.warning(
                self,"Satellite pass","The selected pass is no longer available.")
        self.pass_list.setCurrentItem(target)
        self.pass_list.scrollToItem(target)
        self._open_native_tab("Passes & Data")
        self._reveal_pass_schedule()


    def _home_auto(self):
        if self._open_native_tab("Auto reception"):
            self.statusBar().showMessage(
                "Select published satellite formats, set full-pass duration, "
                "then explicitly arm native captures.",12000)

    def _home_analyze(self):
        if self._open_native_tab("Recordings & results"):
            self.result_steps.setCurrentIndex(0)
            self.files.setFocus()
            self.statusBar().showMessage(
                "Select an actual CU8, then analyze the complete file or "
                "detect relative RF peaks. No recording is fabricated.",12000)

    def _home_extract(self):
        if self._open_native_tab("Recordings & results"):
            self.result_steps.setCurrentIndex(2)
            self.output_files.setFocus()
            self.statusBar().showMessage(
                "Use real FM WAV, Robot36, SatDump, spectrum and result ZIP tools. "
                "PNG is only available after a real decoder succeeds.",14000)

    def _station_controls(self,parent):
        group=QGroupBox("Ground station · offline Germany / Türkiye")
        controls=QFormLayout(group)
        self.city=QComboBox()
        self.city.addItems(list(LOCATIONS)+["Custom coordinates"])
        self.city.currentTextChanged.connect(self._preset_location)
        self.lat=QDoubleSpinBox();self.lat.setRange(-90,90);self.lat.setDecimals(5)
        self.lon=QDoubleSpinBox();self.lon.setRange(-180,180);self.lon.setDecimals(5)
        self.hours=QSpinBox();self.hours.setRange(1,72);self.hours.setValue(24)
        self.elev=QDoubleSpinBox();self.elev.setRange(5,75);self.elev.setValue(15)

        self._offline_cities=load_locations()
        self._current_city_suggestions={}
        self.city_country=QComboBox()
        for text,country in [("Germany + Türkiye","all"),("Germany","DE"),("Türkiye","TR")]:
            self.city_country.addItem(text,country)
        self.city_country.currentIndexChanged.connect(self._refresh_city_regions)
        self.city_region=QComboBox()
        self.city_region.addItem("All states / provinces",None)
        self.city_region.currentIndexChanged.connect(self._refresh_city_search)
        self.city_region.currentIndexChanged.connect(self._sync_detail_region_to_home)
        self.city_search=QLineEdit()
        self.city_search.setPlaceholderText(
            "Search 8,084 cities · Hürth, Aachen, İzmir, Karaburun…")
        self.city_search.setClearButtonEnabled(True)
        self.city_search.textEdited.connect(self._search_offline_city)
        self.city_search.returnPressed.connect(self._apply_exact_city)
        self.city_model=QStringListModel([],self.city_search)
        self.city_completer=QCompleter(self.city_model,self.city_search)
        self.city_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.city_completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.city_completer.activated[str].connect(self._choose_offline_city)
        self.city_search.setCompleter(self.city_completer)
        self.city_info=QLabel("8,084 offline cities: Germany 7,104 · Türkiye 980. No network request.")
        self.city_info.setObjectName("dataHint")
        self.city_info.setWordWrap(True)

        controls.addRow("Quick preset",self.city)
        controls.addRow("Country",self.city_country)
        controls.addRow("State / province",self.city_region)
        controls.addRow("Offline city / town search",self.city_search)
        lookup=QHBoxLayout()
        lookup.addWidget(self._button("Worldwide online lookup (opt-in)",
                                      self._search_online_city))
        lookup.addWidget(self._button("Ask OS for GPS location",
                                      self._request_system_location))
        controls.addRow(lookup)
        controls.addRow("",self.city_info)
        controls.addRow("Latitude",self.lat)
        controls.addRow("Longitude",self.lon)
        controls.addRow("Look ahead · hours",self.hours)
        controls.addRow("Minimum elevation · degrees",self.elev)
        self._preset_location()
        self.lat.valueChanged.connect(self._sync_home_from_planner)
        self.lon.valueChanged.connect(self._sync_home_from_planner)
        self.hours.valueChanged.connect(self._sync_home_from_planner)
        self.elev.valueChanged.connect(self._sync_home_from_planner)
        self._sync_home_from_planner()
        self._home_update_regions()
        self._refresh_city_regions()
        parent.addWidget(group)


    def _search_online_city(self, query=None):
        # Detailed planner routes to the SAME inline results as Home.
        # A Qt clicked(bool) signal is not a literal search string.
        typed=query if isinstance(query,str) else self.city_search.text().strip()
        if len(typed)<2:
            return QMessageBox.information(
                self,"Worldwide city search","Enter a city name first.")
        self.home_city_search.setText(typed)
        self._open_native_tab("Overview")
        self._home_worldwide_lookup()

    def _request_system_location(self):
        if QMessageBox.question(
            self,"System location consent",
            "Ask the operating system for a one-time approximate device position? "
            "This may prompt for OS location-service permission. "
            "No location will be sent to online city search. Continue?",
            QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:
            return
        try:
            from PyQt5.QtPositioning import QGeoPositionInfoSource
        except ImportError:
            return QMessageBox.information(
                self,"Optional Qt Positioning support",
                "QtPositioning is not installed. Optionally install "
                "python3-pyqt5.qtpositioning and enable your OS location service, "
                "or choose a city/manual latitude and longitude.")
        source=QGeoPositionInfoSource.createDefaultSource(self)
        if source is None:
            return QMessageBox.information(
                self,"No system location provider",
                "No OS-approved GPS / Wi-Fi positioning provider is available. "
                "Use offline city search or manual coordinates.")
        self._position_source=source
        source.positionUpdated.connect(self._system_position_received)
        source.requestUpdate(12000)
        self.city_info.setText("Waiting for the OS-approved one-time location request…")

    def _system_position_received(self,info):
        if not info.isValid():return
        coordinate=info.coordinate()
        lat,lon=coordinate.latitude(),coordinate.longitude()
        if not -90<=lat<=90 or not -180<=lon<=180:return
        self.home_station.blockSignals(True)
        self.home_station.setCurrentIndex(self.home_station.findData("custom"))
        self.home_station.blockSignals(False)
        self.city.setCurrentText("Custom coordinates")
        self.lat.setValue(lat);self.lon.setValue(lon)
        self.city_info.setText(
            f"One-time OS device position applied: {lat:.5f}°, {lon:.5f}°. "
            "No RF/GPS acquisition was inferred from satellite tracking. "
            "Recalculate passes.")
        self.home_city_info.setText(
            "OS location applied to shared station (user authorized). "
            "Recalculate passes.")

    def _preset_location(self, *_):
        place=LOCATIONS.get(self.city.currentText())
        if place:
            self.lat.setValue(place[0]);self.lon.setValue(place[1])
            if hasattr(self,"city_info"):
                self.city_info.setText(
                    "Preset station: "+self.city.currentText()+
                    " · coordinates editable. Recalculate passes after changing station.")

    def _refresh_city_regions(self,*_):
        if not hasattr(self,"city_region"):return
        country=self.city_country.currentData() or "all"
        self.city_region.blockSignals(True)
        self.city_region.clear()
        self.city_region.addItem("All states / provinces",None)
        for region in regions_for(self._offline_cities,country):
            self.city_region.addItem(region,region)
        self.city_region.blockSignals(False)
        self._refresh_city_search()
        self._sync_detail_region_to_home()

    def _refresh_city_search(self, *_):
        if hasattr(self,"city_search"):
            self._search_offline_city(self.city_search.text())

    def _search_offline_city(self, value):
        country=self.city_country.currentData() or "all"
        region=self.city_region.currentData()
        rows=search_locations(self._offline_cities,value,country,limit=12,region=region)
        self._current_city_suggestions={city_label(row):row for row in rows}
        self.city_model.setStringList(list(self._current_city_suggestions))
        if rows and self.city_search.hasFocus():
            self.city_completer.complete()
            self.city_info.setText(
                str(len(rows))+" matching offline places. Select one to set coordinates.")
        elif len(value.strip())<2:
            self.city_info.setText("Type at least two letters. City search is entirely offline.")
        else:
            self.city_info.setText("No local city match. Use manual latitude/longitude.")

    def _choose_offline_city(self, label):
        row=self._current_city_suggestions.get(label)
        if row is None:return
        self.city.setCurrentText("Custom coordinates")
        self.lat.setValue(row[3]);self.lon.setValue(row[4])
        self.city_search.setText(label)
        self.city_info.setText(
            "Station set: "+label+" · "+f"{row[3]:.5f}°, {row[4]:.5f}°."+
            " Recalculate satellite passes for this ground station.")

    def _apply_exact_city(self):
        label=self.city_search.text()
        if label in self._current_city_suggestions:
            self._choose_offline_city(label)
        elif len(self._current_city_suggestions)==1:
            self._choose_offline_city(next(iter(self._current_city_suggestions)))
        else:
            self.city_info.setText(
                "Select a city from the matching choices, or enter coordinates manually.")

    def _media_badges(self, kinds, *, compact=False):
        """Real Qt QLabel chips: never HTML/WebView or browser content."""
        widget=QWidget()
        layout=QHBoxLayout(widget)
        layout.setContentsMargins(3,1,3,1)
        layout.setSpacing(5)
        for kind in kinds:
            badge=QLabel((MEDIA_SYMBOLS.get(kind,"")+" "+("RF" if kind=="RF data" else kind.upper())).strip())
            color=MEDIA_COLORS[kind]
            badge.setStyleSheet(
                "QLabel { background:#233f5a; border:1px solid "+color+
                "; color:"+color+"; border-radius:7px; padding:3px 8px;"
                " font-size:"+("10" if compact else "11")+"px; font-weight:650; }")
            badge.setToolTip(kind+" candidate / capability; satellite transmission not verified")
            layout.addWidget(badge)
        layout.addStretch(1)
        widget.setStyleSheet("background:transparent;")
        return widget

    def _passes_tab(self):
        host=self._new_tab("Passes & Data")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page=QWidget()
        body=QVBoxLayout(page)
        body.setContentsMargins(8,8,8,8)
        body.setSpacing(10)
        scroll.setWidget(page)
        host.addWidget(scroll)
        self.pass_scroll=scroll
        top=QHBoxLayout();body.addLayout(top)
        self._station_controls(top)
        group=QGroupBox("Satellite reception planner")
        actions=QVBoxLayout(group)
        actions.addWidget(self._button("↻  Update public orbital TLEs",self.refresh_tles))
        actions.addWidget(self._button("◉  Calculate satellite passes",self.calculate_passes))
        self.tle_source=QComboBox()
        for label,code in (
            ("Amateur / CubeSats","amateur"),("ISS","iss"),
            ("Meteor M2-3","meteor3"),("Meteor M2-4","meteor4"),
            ("Iridium orbital elements","iridium")):
            self.tle_source.addItem(label,code)
        actions.addWidget(self.tle_source)
        actions.addWidget(self._button("Import local TLE file…",self.import_tle))
        self.tle_import_feedback=self._hint(
            "You may import orbital elements offline. Recalculate passes afterward.")
        actions.addWidget(self.tle_import_feedback)
        actions.addWidget(self._hint("Geometry from local TLEs is not evidence of RF. "
                                    "Media tags describe supported *candidate formats*, "
                                    "not files already available onboard or received."))
        actions.addStretch(1);top.addWidget(group)
        top.setStretch(0,1);top.setStretch(1,1)

        searchRow=QHBoxLayout()
        self.pass_search=QLineEdit()
        self.pass_search.setPlaceholderText("Search satellite, NORAD ID, family or receiver profile…")
        self.pass_search.setClearButtonEnabled(True)
        self.pass_search.textChanged.connect(self._render_pass_results)
        self.pass_media_filter=QComboBox()
        for title,key in [
            ("All media types","All"),("▧  Image candidates","Image"),
            ("♫  Audio candidates","Audio"),("≡  Text / packets","Text"),
            ("◈  RF data","RF data"),("RF-only satellites","RF only")]:
            self.pass_media_filter.addItem(title,key)
        self.pass_media_filter.currentIndexChanged.connect(self._render_pass_results)
        self.pass_family_filter=QComboBox()
        for label,key in (
            ("All satellite families","all"),("ISS","iss"),
            ("Meteor-M","meteor"),("CubeSats","cubesat"),
            ("Iridium","iridium")):
            self.pass_family_filter.addItem(label,key)
        self.pass_family_filter.currentIndexChanged.connect(self._render_pass_results)
        self.pass_sort=QComboBox()
        for label,key in (
            ("Soonest passes","soonest"),("Latest passes","latest"),
            ("Highest elevation","high"),("Lowest elevation","low"),
            ("Longest pass","duration-long"),("Shortest pass","duration-short"),
            ("Satellite name A–Z","name")):
            self.pass_sort.addItem(label,key)
        self.pass_sort.currentIndexChanged.connect(self._render_pass_results)
        searchRow.addWidget(self.pass_search,3)
        searchRow.addWidget(self.pass_media_filter,1)
        searchRow.addWidget(self.pass_family_filter,1)
        body.addLayout(searchRow)
        sorter=QHBoxLayout()
        sorter.addWidget(QLabel("Sort passes"))
        sorter.addWidget(self.pass_sort)
        sorter.addStretch(1)
        body.addLayout(sorter)

        self.pass_overview=QLabel("Calculate passes to discover candidate image, audio, text and RF profiles.")
        self.pass_overview.setObjectName("passSubtitle")
        self.pass_overview.setWordWrap(True)
        body.addWidget(self.pass_overview)
        self.pass_list=QTreeWidget()
        self.pass_list.setHeaderLabels([
            "Satellite · NORAD","Potential data formats","AOS · local",
            "LOS · local","Peak","Family"])
        self.pass_list.setUniformRowHeights(False)
        self.pass_list.setRootIsDecorated(False)
        self.pass_list.setMinimumHeight(155)
        self.pass_list.setMaximumHeight(290)
        self.pass_list.setAlternatingRowColors(False)
        self.pass_list.setSelectionMode(QTreeWidget.SingleSelection)
        self.pass_list.setSortingEnabled(False) # AOS order is preserved
        self.pass_list.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.pass_list.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        for col in (2,3,4,5):
            self.pass_list.header().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        self.pass_list.itemSelectionChanged.connect(self.pass_selected)
        body.addWidget(self.pass_list)

        self.pass_detail=QFrame()
        self.pass_detail.setObjectName("passDetail")
        detail=QVBoxLayout(self.pass_detail)
        detail.setContentsMargins(16,12,16,12)
        detail.setSpacing(6)
        self.pass_title=QLabel("Choose a satellite pass")
        self.pass_title.setObjectName("passTitle")
        self.pass_subtitle=QLabel("No received satellite data yet. Select a candidate pass to see protocols.")
        self.pass_subtitle.setObjectName("passSubtitle")
        self.pass_subtitle.setWordWrap(True)
        self.pass_media_bar=QWidget()
        self.pass_media_bar.setLayout(QHBoxLayout())
        self.pass_media_bar.layout().setContentsMargins(0,1,0,1)
        self.pass_media_bar.layout().setSpacing(7)
        self.pass_requirements=QLabel("Image, audio, text and raw RF capability will appear here.")
        self.pass_requirements.setWordWrap(True)
        self.pass_requirements.setTextFormat(Qt.PlainText)
        self.pass_requirements.setObjectName("dataHint")
        detail.addWidget(self.pass_title)
        detail.addWidget(self.pass_subtitle)
        detail.addWidget(self.pass_media_bar)
        detail.addWidget(self.pass_requirements)
        self.pass_schedule_button=self._button(
            "Plan recording for this pass  →",self._reveal_pass_schedule)
        self.pass_schedule_button.setEnabled(False)
        self.pass_map_button=self._button(
            "Show selected satellite on map",self._pass_to_map)
        self.pass_map_button.setEnabled(False)
        actions=QHBoxLayout()
        actions.addWidget(self.pass_schedule_button)
        actions.addWidget(self.pass_map_button)
        detail.addLayout(actions)
        body.addWidget(self.pass_detail,1)

        settings=QGroupBox("Recording details · selected pass")
        self.pass_settings=settings
        form=QFormLayout(settings)
        self.pass_profile=QComboBox()
        self.pass_profile.currentIndexChanged.connect(self._pass_modes)
        self.pass_mode=QComboBox()
        self.pass_sample_rate=QComboBox()
        self.pass_sample_rate.addItem("1.024 MS/s",1024000)
        self.pass_sample_rate.addItem("2.048 MS/s",2048000)
        self.pass_sample_rate.currentIndexChanged.connect(self._pass_budget)
        self.pass_time=QDateTimeEdit(QDateTime.currentDateTime())
        self.pass_time.setCalendarPopup(True)
        self.pass_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.pass_seconds=QSpinBox();self.pass_seconds.setRange(8,7200);self.pass_seconds.setValue(60)
        self.pass_length_unit=QComboBox()
        self.pass_length_unit.addItem("Seconds","seconds")
        self.pass_length_unit.addItem("Minutes","minutes")
        self.pass_length_unit.currentIndexChanged.connect(self._pass_unit_changed)
        self.pass_seconds.valueChanged.connect(self._pass_budget)
        self.pass_mode.currentIndexChanged.connect(self._pass_budget)
        self.pass_cost=self._hint("Choose a predicted pass")
        form.addRow("Receiver profile",self.pass_profile)
        form.addRow("RF output mode",self.pass_mode)
        form.addRow("IQ sampling rate",self.pass_sample_rate)
        form.addRow("Local start time",self.pass_time)
        form.addRow("Total recording length",self.pass_seconds)
        form.addRow("Length unit",self.pass_length_unit)
        form.addRow(self._hint("Over 180 seconds, this creates <=180 s native calendar files with 21 s reserved gaps. RF is NOT continuous."))
        form.addRow("Estimated disk space",self.pass_cost)
        self.arm_pass=self._button("Arm selected RF capture",self.schedule_selected_pass)
        form.addRow(self.arm_pass)
        self.pass_feedback=self._hint("Not scheduled yet.")
        form.addRow(self.pass_feedback)
        body.addWidget(settings)
        settings.setVisible(False)
        self._render_pass_results()

    def _pass_to_map(self):
        item=self.pass_list.currentItem()
        row=self.passes.get(item.data(0,Qt.UserRole)) if item else None
        if not row:return
        norad=int(row["norad"])
        self._open_native_tab("Maps & Live")
        self.map_search.setText(str(norad))
        self._map_choose_satellite(norad)
        self.statusBar().showMessage(
            "Showing predicted orbit for NORAD "+str(norad)+
            " · this does not start a radio receiver.",10000)

    def _reveal_pass_schedule(self):
        if not self.pass_list.currentItem():
            return QMessageBox.information(self,"Plan recording",
                                           "Select a satellite pass first.")
        self.pass_settings.setVisible(True)
        self.pass_scroll.ensureWidgetVisible(self.pass_settings)
        self.pass_profile.setFocus()

    def _set_pass_media_bar(self, kinds):
        layout=self.pass_media_bar.layout()
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        if kinds:
            chip_row=self._media_badges(kinds)
            layout.addWidget(chip_row)
        else:
            empty=QLabel("No catalogued media formats for this selected pass")
            empty.setObjectName("passSubtitle")
            layout.addWidget(empty)

    def _render_pass_results(self, *_):
        """Only user search/filter or new predictions rebuild the native table.

        Unlike old browser UI, periodic status updates never close a dropdown
        or replace a focused Qt combo box.
        """
        previous=self.pass_list.currentItem()
        selected=previous.data(0,Qt.UserRole) if previous is not None else None
        all_rows=list(self.passes.values())
        rows=sort_filter_passes(
            all_rows,search=self.pass_search.text(),
            family=self.pass_family_filter.currentData() or "all",
            medium=self.pass_media_filter.currentData() or "All",
            order=self.pass_sort.currentData() or "soonest")
        self.pass_list.blockSignals(True)
        self.pass_list.clear()
        selected_item=None
        for row in rows:
            kinds=kinds_for_pass(row)
            norad=row.get("norad","?")
            item=QTreeWidgetItem([
                row["name"]+"  ·  "+str(norad),"",
                local_time(row["aos"]),local_time(row["los"]),
                str(row["max_elevation_deg"])+"°",row.get("family","unknown").upper()
            ])
            item.setData(0,Qt.UserRole,row["id"])
            item.setToolTip(0,"Predicted orbital pass only; data transmission is unverified")
            item.setToolTip(1,"Possible from known receiver protocols, not received files")
            item.setSizeHint(1,QSize(360,45))
            if "Image" in kinds:
                item.setForeground(0,QColor("#F3D3A4"))
            self.pass_list.addTopLevelItem(item)
            self.pass_list.setItemWidget(item,1,self._media_badges(kinds,compact=True))
            if row["id"]==selected:selected_item=item
        self.pass_list.blockSignals(False)
        counts={kind:sum(kind in kinds_for_pass(row) for row in rows)
                for kind in ("Image","Audio","Text")}
        self.pass_overview.setText(
            f"{len(rows)} shown / {len(all_rows)} predicted · "
            f"▧ {counts['Image']} image candidate(s) · "
            f"♫ {counts['Audio']} audio · ≡ {counts['Text']} text · "
            "No transmission or complete image guaranteed")
        if selected_item is not None:
            self.pass_list.setCurrentItem(selected_item)
        elif rows:
            self.pass_list.setCurrentItem(self.pass_list.topLevelItem(0))
        else:
            self.pass_selected()


    def _maps_tab(self):
        body=self._new_tab("Maps & Live")
        self.map_index=self.tabs.count()-1
        body.addWidget(self._hint(
            "Live TLE-derived orbital positions, NOT live RF detections. "
            "Native sky/earth maps; offline Natural Earth by default. "
            "OpenStreetMap downloads only tiles visibly requested after you enable them."))
        line=QHBoxLayout()
        self.map_family=QComboBox()
        for name,value in (("All satellite families","all"),("ISS","iss"),
                           ("Meteor","meteor"),("CubeSat","cubesat"),
                           ("Iridium","iridium")):
            self.map_family.addItem(name,value)
        self.map_family.currentIndexChanged.connect(self._map_options_changed)
        self.map_media=QComboBox()
        for label,kind in (
            ("All media","All"),("▧ Image candidates","Image"),
            ("♫ Audio candidates","Audio"),("≡ Text/AX.25","Text"),
            ("◈ RF data","RF data"),("RF-only / unknown","RF only")):
            self.map_media.addItem(label,kind)
        self.map_media.currentIndexChanged.connect(self._map_options_changed)
        self.map_above=QCheckBox("Above local horizon only")
        self.map_above.toggled.connect(self._map_options_changed)
        self.map_follow=QCheckBox("Follow selected satellite")
        self.map_follow.toggled.connect(self._map_options_changed)
        self.map_live_button=QPushButton("● LIVE · 1 s")
        self.map_live_button.setCheckable(True)
        self.map_live_button.setChecked(True)
        self.map_live_button.clicked.connect(self._toggle_map_live)
        for widget in (self.map_family,self.map_media,self.map_live_button):
            line.addWidget(widget)
        body.addLayout(line)
        self.map_search=QLineEdit()
        self.map_search.setPlaceholderText("Find satellite by name or NORAD · local TLE search")
        self.map_search.setClearButtonEnabled(True)
        self.map_search.textChanged.connect(self._map_options_changed)
        body.addWidget(self.map_search)
        timebar=QHBoxLayout()
        timebar.addWidget(QLabel("Orbit time"))
        self.map_offset=QSlider(Qt.Horizontal)
        self.map_offset.setRange(-45,90)
        self.map_offset.setSingleStep(5)
        self.map_offset.setPageStep(5)
        self.map_offset.setTickInterval(15)
        self.map_offset.setValue(0)
        self.map_offset.valueChanged.connect(self._map_time_changed)
        self.map_clock=QLabel("Now · live TLE prediction")
        timebar.addWidget(self.map_offset,2)
        timebar.addWidget(self.map_clock,1)
        body.addLayout(timebar)
        self.map_extra_button=QPushButton("Advanced map overlays  ▸")
        self.map_extra_button.setCheckable(True)
        self.map_extra=QWidget()
        opts=QHBoxLayout(self.map_extra)
        opts.setContentsMargins(0,0,0,0)
        self.map_coverage=QComboBox()
        for name,value in (("Coverage · selected","selected"),
                           ("Coverage · all visible","all"),
                           ("Coverage · off","none")):
            self.map_coverage.addItem(name,value)
        self.map_coverage.currentIndexChanged.connect(self._map_options_changed)
        self.map_track_scope=QComboBox()
        for title,mode in (
            ("Orbit path · selected","selected"),
            ("Orbit paths · visible (max 12)","all"),
            ("Orbit paths · off","none")):
            self.map_track_scope.addItem(title,mode)
        self.map_track_scope.currentIndexChanged.connect(self._map_track_scope_changed)
        self.map_osm=QCheckBox("OpenStreetMap streets · online")
        self.map_osm.setToolTip("User-triggered visible viewport tiles only; no offline bulk download.")
        self.map_osm.toggled.connect(self._map_osm_toggled)
        quick=QHBoxLayout()
        quick.addWidget(self.map_osm)
        quick.addWidget(self._button("Center ground station",self._map_center_station))
        quick.addWidget(self._button("Fit visible satellites",self._map_fit_tracked))
        quick.addWidget(self.map_extra_button)
        body.addLayout(quick)
        opts.addWidget(self.map_coverage)
        opts.addWidget(self.map_track_scope)
        opts.addWidget(self.map_above)
        opts.addWidget(self.map_follow)
        self.map_extra.setVisible(False)
        self.map_extra_button.toggled.connect(self.map_extra.setVisible)
        self.map_extra_button.toggled.connect(
            lambda visible:self.map_extra_button.setText(
                "Advanced map overlays  ▾" if visible else "Advanced map overlays  ▸"))
        body.addWidget(self.map_extra)

        split=QSplitter(Qt.Horizontal)
        self.map_views=QTabWidget()
        self.map_sky=OrbitCanvas("sky")
        self.map_earth=OrbitCanvas("earth")
        self.map_views.addTab(self.map_sky,"Sky · Azimuth/Elevation")
        self.map_views.addTab(self.map_earth,"Earth · OSM/Offline")
        self.map_views.setCurrentIndex(1)
        self.map_views.currentChanged.connect(self._map_view_switched)
        self.map_sky.selected.connect(self._map_choose_satellite)
        self.map_earth.selected.connect(self._map_choose_satellite)
        split.addWidget(self.map_views)

        panel=QWidget()
        side=QVBoxLayout(panel)
        side.setContentsMargins(8,2,4,2)
        side.addWidget(QLabel("Predicted satellites · click map pin or list row"))
        self.map_satellites=QTreeWidget()
        self.map_satellites.setHeaderLabels(
            ["TLE satellite","Elevation","Possible formats"])
        self.map_satellites.setRootIsDecorated(False)
        self.map_satellites.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.map_satellites.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.map_satellites.header().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.map_satellites.itemSelectionChanged.connect(self._map_list_selected)
        side.addWidget(self.map_satellites,3)
        self.map_details=QPlainTextEdit()
        self.map_details.setReadOnly(True)
        self.map_details.setPlainText(
            "Import/refresh public orbit data in Passes & Data. "
            "An orbital pin never proves a transmitter.")
        side.addWidget(self.map_details,2)
        side.addWidget(self._button("Use selected family receiver preset",
                                  self._map_tune_receiver))
        side.addWidget(self._button("Find next predicted pass for selected satellite",
                                  self._map_find_next_pass))
        split.addWidget(panel)
        split.setStretchFactor(0,4)
        split.setStretchFactor(1,2)
        body.addWidget(split,1)
        export_row=QHBoxLayout()
        export_row.addWidget(self._button("Save visible map PNG…",self._map_export_png))
        export_row.addWidget(self._button("Export orbit pins/tracks GeoJSON…",
                                           self._map_export_geojson))
        export_row.addStretch(1)
        body.addLayout(export_row)
        self.map_status=QLabel(
            "No TLE trajectory loaded. Earth map opens offline without network.")
        self.map_status.setWordWrap(True)
        body.addWidget(self.map_status)

    def _on_tab_change(self,index):
        if index==self.map_index and self.active:
            self.refresh_orbit_map()

    def _map_osm_toggled(self,enabled):
        self.map_earth.set_street(enabled)
        self.map_status.setText(
            "OSM street tiles enabled only for visible viewport · © OpenStreetMap contributors"
            if enabled else "Offline Natural Earth map · no street-tile downloads.")
    def _map_view_switched(self,index):
        if index==1 and self.map_osm.isChecked():
            self.map_earth._sync_tiles()
        if self.active:self.refresh_orbit_map()
    def _map_center_station(self):
        self.map_earth.center_station()
    def _map_fit_tracked(self):
        if not self.map_earth.fit_satellites():
            self.statusBar().showMessage(
                "No TLE subpoints match the current map filter.",8000)
    def _map_track_scope_changed(self,*_):
        # Invalidate previously sampled selected/all orbit paths immediately.
        self.map_track_segments=[]
        self.map_last_track_at=0
        self._map_options_changed()
    def _map_options_changed(self,*_):
        self.map_sky.above_only=self.map_above.isChecked()
        self.map_earth.above_only=self.map_above.isChecked()
        self.map_earth.coverage_scope=self.map_coverage.currentData()
        self.map_earth.tracks_visible=self.map_track_scope.currentData()!="none"
        self.map_sky.update();self.map_earth.update()
        if self.active and self.tabs.currentIndex()==self.map_index:
            self.refresh_orbit_map()
    def _toggle_map_live(self):
        self.map_live=self.map_live_button.isChecked()
        if self.map_live:
            self.map_paused_at=None
            self.map_offset.blockSignals(True)
            self.map_offset.setValue(0)
            self.map_offset.blockSignals(False)
        else:
            self.map_paused_at=datetime.now(timezone.utc)
        self.map_live_button.setText(
            "● LIVE · 1 s" if self.map_live else "Ⅱ PAUSED · simulated")
        self.refresh_orbit_map()
    def _map_time_changed(self,minutes):
        if minutes!=0 and self.map_live:
            self.map_live=False
            self.map_live_button.blockSignals(True)
            self.map_live_button.setChecked(False)
            self.map_live_button.blockSignals(False)
            self.map_live_button.setText("Ⅱ PAUSED · simulated")
            self.map_paused_at=datetime.now(timezone.utc)
        if self.active:self.refresh_orbit_map()
    def _map_when(self):
        origin=(datetime.now(timezone.utc) if self.map_live else
                self.map_paused_at or datetime.now(timezone.utc))
        return origin+timedelta(minutes=self.map_offset.value())
    def refresh_orbit_map(self):
        if not self.active or self.tabs.currentIndex()!=self.map_index:return
        if not self.isVisible() and self.map_live:return
        if not self.map_live and self.map_last_snapshot is not None:
            # User options can still request a new synthetic-time snapshot.
            pass
        latitude=self.lat.value();longitude=self.lon.value()
        fam=self.map_family.currentData()
        at=self._map_when()
        self.map_clock.setText(
            ("LIVE · " if self.map_live else "SIMULATED · ")+
            at.astimezone().strftime("%H:%M:%S · %d %b %Y"))
        selected=self.map_selected_norad
        track_scope=self.map_track_scope.currentData()
        want_track=(track_scope!="none" and
                    (track_scope=="all" or selected is not None) and
                    (not self.map_track_segments or not self.map_live or
                     (time.monotonic()-self.map_last_track_at)>15))
        options={"family_filter":fam,"minimum_el":-90,
                 "selected_norad":selected,"with_track":want_track,
                 "track_scope":track_scope if track_scope!="none" else "selected"}
        def calculate():
            return self.orbit_engine.snapshot(latitude,longitude,at,**options)
        self._task("map-orbit",calculate,
                   lambda value:self._apply_map_snapshot(value,want_track),silent=True)
    def _apply_map_snapshot(self,view,track_refreshed):
        if self.map_track_scope.currentData()=="none":
            self.map_track_segments=[]
            view["track_segments"]=[]
        elif track_refreshed:
            self.map_track_segments=view.get("track_segments",[])
            self.map_last_track_at=time.monotonic()
        elif self.map_track_segments:
            view["track_segments"]=self.map_track_segments
        view=filter_orbit_snapshot(
            view,self.map_media.currentData() or "All",
            self.map_above.isChecked(),self.map_search.text())
        self.map_last_snapshot=view
        self.map_sky.set_snapshot(view);self.map_earth.set_snapshot(view)
        self.map_sky.set_selected(self.map_selected_norad)
        self.map_earth.set_selected(self.map_selected_norad)
        focused=self.map_satellites.currentItem()
        before=focused.data(0,Qt.UserRole) if focused else self.map_selected_norad
        self.map_satellites.blockSignals(True)
        self.map_satellites.clear()
        active=None
        for sat in view["satellites"]:
            if self.map_above.isChecked() and sat["el"]<0:continue
            kinds=map_satellite_capabilities(sat)
            formats="  ".join(
                "▧ IMG" if k=="Image" else "♫ WAV" if k=="Audio" else
                "≡ TEXT" if k=="Text" else "◈ RF" for k in kinds)
            item=QTreeWidgetItem([sat["name"],f'{sat["el"]:+.1f}°',formats])
            item.setToolTip(2,"Published receiver candidates, not verified RF/media")
            item.setData(0,Qt.UserRole,sat["norad"])
            self.map_satellites.addTopLevelItem(item)
            if sat["norad"]==before:active=item
        if active:self.map_satellites.setCurrentItem(active)
        self.map_satellites.blockSignals(False)
        self._update_map_details()
        self.map_status.setText(
            f'{len(view["satellites"])} shown / {view.get("unfiltered_orbital_candidates",0)} '
            f'orbital candidates · {view["total_loaded"]} local TLE objects · '+
            (view["warnings"][0] if view["warnings"] else "Current cached orbital data")+
            " · Map pins are not RF detections")
        if self.map_follow.isChecked() and view.get("selected"):
            sat=view["selected"]
            self.map_earth.center_lat=sat["lat"]
            self.map_earth.center_lon=sat["lon"]
            self.map_earth.update()
            # Never fetch extra OSM tiles automatically as satellite moves.
    def _map_choose_satellite(self,norad):
        self.map_selected_norad=int(norad)
        self.map_track_segments=[]
        if self.map_last_snapshot:self._apply_map_snapshot(self.map_last_snapshot,False)
        self.refresh_orbit_map()
    def _map_list_selected(self):
        item=self.map_satellites.currentItem()
        if item is not None:self._map_choose_satellite(item.data(0,Qt.UserRole))
    def _update_map_details(self):
        sat=next((s for s in (self.map_last_snapshot or {}).get("satellites",[])
                  if s["norad"]==self.map_selected_norad),None)
        if not sat:
            self.map_details.setPlainText(
                "Choose an orbital candidate. No RF, audio, image or packet is verified.")
            return
        self.map_details.setPlainText(
            f'{sat["name"]} · NORAD {sat["norad"]}\n'
            f'{sat["family"].upper()} · Az {sat["az"]}° · El {sat["el"]}°\n'
            f'Latitude {sat["lat"]}° · Longitude {sat["lon"]}°\n'
            f'Altitude {sat["alt_km"]} km · Range {sat["range_km"]} km\n'
            f'TLE age {sat["tle_age_days"]} d · status ORBITAL_POSITION_ONLY\n'
            "Potential formats: "+", ".join(map_satellite_capabilities(sat))+"\n"+
            "\n".join(map_satellite_protocols(sat))+"\n"
            "Orbital geometry only: no actual RF reception or decoded imagery.")
    def _map_tune_receiver(self):
        sat=next((s for s in (self.map_last_snapshot or {}).get("satellites",[])
                  if s["norad"]==self.map_selected_norad),None)
        if sat is None:return
        priorities={"iss":["iss_voice","iss_sstv","iss_aprs_uhf"],
                    "meteor":["meteor","meteor_backup"],
                    "iridium":["iridium_rf_iq","iridium"]}
        key=next((x for x in priorities.get(sat["family"],[]) if x in PROFILES),None)
        if key is None:
            QMessageBox.information(self,"Receiver","No verified published receiver profile for this satellite family.")
            return
        idx=self.capture_profile.findData(key)
        if idx>=0:
            self.capture_profile.setCurrentIndex(idx)
            self.tabs.setCurrentIndex(5)
            self.statusBar().showMessage("Receiver preset selected. No USB scan started.",9000)

    def _map_find_next_pass(self):
        norad=self.map_selected_norad
        if norad is None:
            return QMessageBox.information(
                self,"Select satellite","Choose an orbital pin/list row first.")
        self.map_pending_pass_norad=norad
        self.tabs.setCurrentIndex(1)
        self.calculate_passes()
        self.statusBar().showMessage(
            "Searching predicted passes for NORAD "+str(norad)+
            " · no receiver was activated.",10000)

    def _map_export_png(self):
        canvas=self.map_sky if self.map_views.currentIndex()==0 else self.map_earth
        target,_=QFileDialog.getSaveFileName(
            self,"Save current orbital map (not satellite imagery)",
            str(Path.home()/"TIHULU_predicted_orbit_map.png"),"PNG image (*.png)")
        if not target:return
        path=Path(target).expanduser()
        if path.suffix.lower()!=".png":
            return QMessageBox.warning(self,"Map export","Use .png for this export.")
        if path.exists() or path.is_symlink():
            return QMessageBox.warning(self,"Map export","Existing file: no overwrite.")
        if not canvas.grab().save(str(path),"PNG"):
            return QMessageBox.warning(self,"Map export","Qt could not save the displayed map.")
        self.statusBar().showMessage(
            "Predicted orbit map saved (not a received satellite photo): "+str(path),14000)

    def _map_export_geojson(self):
        if not self.map_last_snapshot:
            return QMessageBox.information(
                self,"Map export","Calculate orbital positions before export.")
        target,_=QFileDialog.getSaveFileName(
            self,"Save actual computed orbit pins and selected track",
            str(Path.home()/"TIHULU_orbit_prediction.geojson"),
            "GeoJSON (*.geojson)")
        if not target:return
        try:file=export_orbit_geojson(self.map_last_snapshot,target)
        except (OSError,ValueError) as error:
            return QMessageBox.warning(self,"Map export",str(error))
        self.statusBar().showMessage(
            "Saved TLE-based GeoJSON with explicit no-RF provenance: "+str(file),14000)


    def _auto_tab(self):
        host=self._new_tab("Auto reception")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host.addWidget(scroll)
        panel=QWidget()
        body=QVBoxLayout(panel)
        body.setSpacing(12)
        scroll.setWidget(panel)
        title=QLabel("Automatically capture selected satellite passes")
        title.setObjectName("passTitle")
        body.addWidget(title)
        body.addWidget(self._hint(
            "Select only what you want to receive. The app estimates suitable passes and "
            "writes real data locally if an RTL-SDR is available. No capture starts just by opening this page."))

        mission_panel=QGroupBox("1 · Choose the data to receive")
        missions=QVBoxLayout(mission_panel)
        self.mission_boxes={}
        for mid, (norad, profile, mode) in AUTO_DOWNLINK_PROFILES.items():
            label={
                "iss-sstv":"IMAGE · ISS SSTV · event only · WAV",
                "iss-aprs":"TEXT · ISS public APRS packets",
                "iss-voice":"AUDIO · ISS voice FM · WAV",
                "meteor-m2-3":"IMAGE · Meteor-M2-3 weather · raw CU8",
                "meteor-m2-4":"IMAGE · Meteor-M2-4 weather · raw CU8",
            }.get(mid,mid)
            item=QCheckBox(label)
            if mid.startswith("meteor"):item.setChecked(True)
            self.mission_boxes[mid]=item
            missions.addWidget(item)
        body.addWidget(mission_panel)

        basic=QGroupBox("2 · Plan the reception")
        form=QFormLayout(basic)
        self.coverage=QComboBox()
        self.coverage.addItem("Prefer full visible pass","full")
        self.coverage.addItem("Quick RF sample","sample")
        form.addRow("Recording goal",self.coverage)
        self.auto_iss_format=QComboBox()
        self.auto_iss_format.addItem("WAV · FM audio only", "wav")
        self.auto_iss_format.addItem("CU8 · full IQ data only", "cu8")
        self.auto_iss_format.addItem("CU8 + WAV · from same physical capture", "both")
        self.auto_iss_format.setToolTip(
            "Native CU8 + WAV records actual IQ first, then derives 32-kHz "
            "FM audio from that same IQ. It does not use WebUSB.")
        form.addRow("ISS SSTV recording files",self.auto_iss_format)
        self.auto_schedule_button=self._button(
            "Calculate passes & schedule recordings",self.auto_schedule)
        form.addRow(self.auto_schedule_button)
        body.addWidget(basic)

        self.auto_expand=QPushButton("Advanced recording settings  ▸")
        self.auto_expand.setCheckable(True)
        self.auto_expand.setAccessibleName("Show advanced reception parameters")
        body.addWidget(self.auto_expand)
        self.auto_settings=QGroupBox("Advanced · capture and processing")
        advanced=QFormLayout(self.auto_settings)
        self.auto_seconds=QSpinBox()
        self.auto_seconds.setRange(0,900)
        self.auto_length_unit=QComboBox()
        self.auto_length_unit.addItem("Seconds","seconds")
        self.auto_length_unit.addItem("Minutes","minutes")
        self.auto_length_unit.currentIndexChanged.connect(self._auto_unit_changed)
        self.auto_seconds.setSpecialValueText("Auto · fit pass")
        self.auto_seconds.setValue(0)
        self.auto_jobs=QSpinBox()
        self.auto_jobs.setRange(1,12)
        self.auto_jobs.setValue(6)
        self.auto_elev=QDoubleSpinBox()
        self.auto_elev.setRange(5,75)
        self.auto_elev.setValue(20)
        self.auto_compute=QComboBox()
        for title,mode,targets in (
            ("Auto · detect available backend","auto",[]),
            ("CPU only","custom",["cpu"]),
            ("CPU + GPU (if supported)","custom",["cpu","gpu"]),
            ("CPU + NPU (if supported)","custom",["cpu","npu"]),
            ("CPU + GPU + NPU (if supported)","custom",["cpu","gpu","npu"]),
        ):
            self.auto_compute.addItem(title,(mode,targets))
        self.auto_compute.setToolTip(
            "Selecting GPU/NPU is a request, not evidence of real accelerator use.")
        advanced.addRow("Duration · 0 = fit pass",self.auto_seconds)
        advanced.addRow("Length unit",self.auto_length_unit)
        advanced.addRow("Maximum jobs",self.auto_jobs)
        advanced.addRow("Minimum elevation (°)",self.auto_elev)
        advanced.addRow("Analysis hardware",self.auto_compute)
        self.auto_settings.setVisible(False)
        self.auto_expand.toggled.connect(self.auto_settings.setVisible)
        self.auto_expand.toggled.connect(
            lambda visible:self.auto_expand.setText(
                "Advanced recording settings  ▾" if visible else "Advanced recording settings  ▸"))
        body.addWidget(self.auto_settings)
        self.auto_feedback=self._hint("Nothing scheduled yet. Select data above and press Calculate & schedule.")
        body.addWidget(self.auto_feedback)
        body.addWidget(self._hint(
            "Scheduling needs valid TLEs, free disk space and one free SDR. "
            "IMAGE labels are protocol candidates; an image appears only if decoding succeeds."))
        actions=QHBoxLayout()
        actions.addWidget(self._button("View reception calendar",
                                     lambda:self._open_native_tab("Reception calendar")))
        actions.addWidget(self._button("Cancel pending AUTO jobs",self.cancel_automatic))
        actions.addStretch(1)
        body.addLayout(actions)
        body.addStretch(1)

    def _calendar_tab(self):
        body=self._new_tab("Reception calendar")
        controls=QHBoxLayout()
        self.cal_day=QDateEdit(QDate.currentDate());self.cal_day.setCalendarPopup(True)
        self.cal_day.dateChanged.connect(self._render_calendar)
        controls.addWidget(self._button("Previous day",lambda:self.cal_day.setDate(self.cal_day.date().addDays(-1))))
        controls.addWidget(self.cal_day)
        controls.addWidget(self._button("Next day",lambda:self.cal_day.setDate(self.cal_day.date().addDays(1))))
        controls.addWidget(self._button("Refresh",self.refresh_status))
        body.addLayout(controls)
        self.timeline=QTableWidget(24,2)
        self.timeline.setHorizontalHeaderLabels(["Local time","Scheduled RF captures"])
        self.timeline.horizontalHeader().setStretchLastSection(True)
        self.timeline.verticalHeader().hide()
        self.timeline.setEditTriggers(QTableWidget.NoEditTriggers)
        for hour in range(24):
            self.timeline.setItem(hour,0,QTableWidgetItem(f"{hour:02d}:00–{(hour+1)%24:02d}:00"))
            self.timeline.setRowHeight(hour,40)
        body.addWidget(self.timeline,2)
        self.job_list=QTreeWidget()
        self.job_list.setHeaderLabels(["Satellite","Local start","Local end","Duration","State","Protocol"])
        self.job_list.itemSelectionChanged.connect(self._job_selected)
        body.addWidget(self.job_list,1)
        self.job_note=self._hint("Cancelled jobs are hidden from the calendar; "
                                 "audit history is preserved on local disk.")
        body.addWidget(self.job_note)
        self._row(body,
                  self._button("Cancel selected pending job",self.cancel_job),
                  self._button("Edit selected automatic job",self.edit_auto_job))
        self._calendar_jobs=[]
        self.calendar_countdown=self._hint("Next scheduled RF job: none")
        body.addWidget(self.calendar_countdown)
        self.calendar_clock=QTimer(self)
        self.calendar_clock.timeout.connect(self._update_calendar_countdown)
        self.calendar_clock.start(1000)

    def _update_calendar_countdown(self):
        if not hasattr(self,"calendar_countdown"):return
        current=datetime.now(timezone.utc)
        pending=[]
        for j in self._calendar_jobs:
            if j.get("state") not in ("pending","armed"):continue
            try:
                start=datetime.fromisoformat(j.get("run_at") or j["aos"]).astimezone(timezone.utc)
            except (TypeError,ValueError,KeyError):continue
            if start>=current:pending.append((start,j))
        if not pending:
            self.calendar_countdown.setText("Next scheduled RF job: none")
            return
        start,j=min(pending,key=lambda item:item[0])
        seconds=max(0,int((start-current).total_seconds()))
        days,seconds=divmod(seconds,86400)
        hours,seconds=divmod(seconds,3600)
        minutes,seconds=divmod(seconds,60)
        part=(f" · part {j['chain_index']}/{j['chain_total']}"
              if j.get("chain_index") else "")
        self.calendar_countdown.setText(
            f"Next RF: {j.get('satellite','Satellite')}{part} · "
            f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s remaining")

    def _capture_tab(self):
        body=self._new_tab("Manual RF capture")
        form=QFormLayout()
        self.capture_profile=QComboBox()
        for key,value in PROFILES.items():
            self.capture_profile.addItem(value["label"],key)
        self.capture_profile.currentIndexChanged.connect(self._capture_modes)
        self.capture_mode=QComboBox()
        self.capture_sample_rate=QComboBox()
        self.capture_sample_rate.addItem("1.024 MS/s",1024000)
        self.capture_sample_rate.addItem("2.048 MS/s",2048000)
        self.capture_sample_rate.currentIndexChanged.connect(self._capture_budget)
        self.capture_seconds=QSpinBox();self.capture_seconds.setRange(8,900)
        self.capture_seconds.setValue(60)
        self.capture_length_unit=QComboBox()
        self.capture_length_unit.addItem("Seconds","seconds")
        self.capture_length_unit.addItem("Minutes","minutes")
        self.capture_length_unit.currentIndexChanged.connect(self._capture_unit_changed)
        self.capture_budget=self._hint("Long captures write real CU8 directly to disk.")
        self.capture_mode.currentIndexChanged.connect(self._capture_budget)
        self.capture_seconds.valueChanged.connect(self._capture_budget)
        form.addRow("Receiver frequency / band",self.capture_profile)
        form.addRow("Hardware mode",self.capture_mode)
        form.addRow("IQ sample rate",self.capture_sample_rate)
        form.addRow("Actual sample length",self.capture_seconds)
        form.addRow("Length unit",self.capture_length_unit)
        form.addRow("Estimated disk budget",self.capture_budget)
        body.addLayout(form)
        self._row(body,
                  self._button("Start physical RF capture",self.start_capture),
                  self._button("Stop my current capture",self.stop_capture))
        self.capture_live_state=self._hint(
            "Relative real CU8 power chart appears during a physical recording.")
        body.addWidget(self.capture_live_state)
        self.capture_level_chart=NativeIqLevelView()
        body.addWidget(self.capture_level_chart)
        body.addWidget(self._hint("Only the actual attached RTL2832U SDR is used. "
            "A busy readsb/Gqrx device is not stolen or forcibly terminated. "
            "Long recordings are written locally without browser memory caps."))
        body.addStretch(1)
        self._capture_modes()

    def _results_tab(self):
        outer=self._new_tab("Recordings & results")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        panel=QWidget()
        body=QVBoxLayout(panel)
        body.setSpacing(8)
        scroll.setWidget(panel)
        outer.addWidget(scroll)
        intro=self._hint(
            "Open a recording → Analyze its contents → Inspect and export genuine outputs. "
            "Raw RF is not automatically an image or speech.")
        body.addWidget(intro)
        self.results_file_banner=QLabel("No recording selected. Start with Step 1.")
        self.results_file_banner.setObjectName("fileBanner")
        self.results_file_banner.setWordWrap(True)
        body.addWidget(self.results_file_banner)
        self.result_steps=QTabWidget()
        self.result_steps.setObjectName("resultSteps")
        for title in (
            "1 · Choose recording",
            "2 · Analyze RF",
            "3 · Decode & save",
        ):
            step=QWidget()
            inner=QVBoxLayout(step)
            inner.setSpacing(10)
            self.result_steps.addTab(step,title.replace("&","&&"))
        browse=self.result_steps.widget(0).layout()
        analyze=self.result_steps.widget(1).layout()
        extract=self.result_steps.widget(2).layout()
        body.addWidget(self.result_steps)
        self._row(browse,
                  self._button("Refresh local recordings",self.refresh_status),
                  self._button("Open existing file…",self.import_file),
                  self._button("Reveal recordings folder",self.open_archive_folder))
        self.files=QTreeWidget()
        self.files.setMinimumHeight(125)
        self.files.setMaximumHeight(260)
        self.files.setHeaderLabels(["Actual local file","Data type · format","Size","Modified · local"])
        self.files.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.files.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.files.header().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.files.header().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        self.files.itemSelectionChanged.connect(self._file_selected)
        browse.addWidget(self.files)
        self.browse_file_info=self._hint(
            "Pick an actual local file. Its data format will be displayed; "
            "a file name or format header cannot authenticate a satellite.")
        browse.addWidget(self.browse_file_info)
        self.continue_analysis=self._button(
            "Continue to analysis  →",lambda:self.result_steps.setCurrentIndex(1))
        self.continue_analysis.setEnabled(False)
        self._row(browse,self.continue_analysis,
                  self._button("See generated results  →",
                               lambda:self.result_steps.setCurrentIndex(2)))
        # Keep next-step actions immediately below the archive list instead
        # of distributing empty vertical space through the entire tab.
        browse.addStretch(1)
        analyze_controls=QHBoxLayout()
        self.rate=QComboBox()
        self.rate.addItem("1.024 MS/s",1024000)
        self.rate.addItem("2.048 MS/s",2048000)
        self.center=QDoubleSpinBox()
        self.center.setRange(0,2000);self.center.setDecimals(4)
        self.center.setSuffix(" MHz");self.center.setValue(137.9)
        self.analysis_mode=QComboBox()
        self.analysis_mode.addItem("Fast time-spread overview","overview")
        self.analysis_mode.addItem("Whole-file streaming FFT","full")
        for widget in [QLabel("Rate"),self.rate,QLabel("Center"),self.center,
                       QLabel("Analysis"),self.analysis_mode]:
            analyze_controls.addWidget(widget)
        analyze.addWidget(self._hint(
            "For raw CU8, enter the original sample rate and center frequency. "
            "Spectrum peaks are uncalibrated RF evidence, not a verified transmitter."))
        analyze.addLayout(analyze_controls)
        self._row(analyze,
                  self._button("Analyze real CU8",self.analyze_file),
                  self._button("Auto-discover RF candidates",self.discover_signals))
        extract.addWidget(self._hint(
            "Decoder results appear only from actual saved data. "
            "Meteor requires a compatible external SatDump installation."))
        self._row(extract,
                  self._button("Decode Meteor 72k",lambda:self.decode_meteor("72k")),
                  self._button("Decode Meteor 80k",lambda:self.decode_meteor("80k")))
        analog=QHBoxLayout()
        analog.addWidget(QLabel("FM channel offset"))
        self.audio_offset=QDoubleSpinBox()
        self.audio_offset.setRange(-900,900)
        self.audio_offset.setDecimals(2)
        self.audio_offset.setSuffix(" kHz")
        self.audio_offset.setValue(0)
        analog.addWidget(self.audio_offset)
        analog.addWidget(self._button("CU8 → genuine FM WAV",self.demodulate_fm))
        analog.addWidget(self._button("Play selected / extracted WAV",self.play_audio))
        analog.addWidget(self._button("Stop audio",self.stop_audio))
        analyze.addLayout(analog)
        robot=QHBoxLayout()
        self.sstv_compute=QComboBox()
        for label,mode,targets in (
            ("SSTV compute · Auto","auto",[]),
            ("CPU","custom",["cpu"]),
            ("CPU + GPU","custom",["cpu","gpu"]),
            ("CPU + NPU","custom",["cpu","npu"]),
            ("CPU + GPU + NPU","custom",["cpu","gpu","npu"])):
            self.sstv_compute.addItem(label,(mode,targets))
        robot.addWidget(self.sstv_compute)
        robot.addWidget(self._button("Decode WAV → Robot36 PNG",self.decode_robot36_native))
        robot.addWidget(self._button("Save decoded PNG / WAV…",self.save_selected_output))
        extract.addLayout(robot)
        self._row(extract,
                  self._button("Export spectrum/waterfall PNG",self.export_spectrum_png),
                  self._button("Export spectrum CSV",self.export_spectrum_csv),
                  self._button("Save real results ZIP",self.save_results_zip))
        self.output_files=QTreeWidget()
        self.output_files.setHeaderLabels(["Generated file","Data type · format","Saved directory"])
        self.output_files.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.output_files.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.output_files.setMaximumHeight(130)
        self.output_files.itemSelectionChanged.connect(self._output_file_selected)
        extract.addWidget(self.output_files)
        self.candidate_label=self._hint("RF discovery is based on energy above a local noise estimate. A peak alone is not a decoded packet or picture.")
        analyze.addWidget(self.candidate_label)
        self.spectrum=SpectrumView()
        self.spectrum.setMinimumHeight(260)
        analyze.addWidget(self.spectrum,2)
        self.image=QLabel()
        self.image.setMinimumHeight(90)
        self.image.setAlignment(Qt.AlignCenter)
        extract.addWidget(self.image,1)
        self.file_details=QPlainTextEdit()
        self.file_details.setReadOnly(True)
        self.file_details.setMaximumHeight(125)
        analyze.addWidget(self.file_details,1)
        self.file_details.setPlainText("Select a real recording or import a local .cu8, WAV, PNG or text file.")
        self._row(analyze,
                  self._button("←  Choose another file",
                               lambda:self.result_steps.setCurrentIndex(0)),
                  self._button("View decoded outputs  →",
                               lambda:self.result_steps.setCurrentIndex(2)))
        self._row(extract,
                  self._button("←  Back to signal analysis",
                               lambda:self.result_steps.setCurrentIndex(1)),
                  self._button("Choose another file",
                               lambda:self.result_steps.setCurrentIndex(0)))

    def _images_tab(self):
        """Native equivalent of Satellite Images & Data, never a WebView."""
        host=self._new_tab("Satellite Images & Data")
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host.addWidget(scroll)
        page=QWidget()
        body=QVBoxLayout(page)
        body.setSpacing(12)
        scroll.setWidget(page)
        heading=QLabel("Satellite Images & Data")
        heading.setObjectName("passTitle")
        body.addWidget(heading)
        body.addWidget(self._hint(
            "Decode only genuinely recorded SSTV / Meteor data, browse your local files, "
            "or request official NASA photographs separately. "
            "An online NASA image is NEVER a picture received by your RTL-SDR."))

        receiver=QGroupBox("1 · Real RF imagery · ISS SSTV / Meteor LRPT")
        controls=QVBoxLayout(receiver)
        controls.addWidget(self._hint(
            "ISS Robot36 needs an actually recorded WAV; Meteor LRPT needs raw CU8 "
            "and the installed SatDump decoder. No invented PNG is created."))
        actions=QHBoxLayout()
        actions.addWidget(self._button("Select ISS SSTV receiver",self._image_tune_iss))
        actions.addWidget(self._button("Open recorded WAV / CU8",self._image_import))
        controls.addLayout(actions)
        decoders=QHBoxLayout()
        decoders.addWidget(self._button("Decode WAV → Robot36 PNG",self._image_decode_sstv))
        decoders.addWidget(self._button("Meteor 72k",lambda:self.decode_meteor("72k")))
        decoders.addWidget(self._button("Meteor 80k",lambda:self.decode_meteor("80k")))
        controls.addLayout(decoders)
        controls.addWidget(self._button("Inspect decoded result files / ZIP",
                                        self._home_extract))
        body.addWidget(receiver)

        local=QGroupBox("2 · Recorded files · PNG, WAV, CU8, text and JSON")
        local_layout=QVBoxLayout(local)
        local_buttons=QHBoxLayout()
        local_buttons.addWidget(self._button("Refresh saved files",self.refresh_status))
        local_buttons.addWidget(self._button("Open any local file",self._image_import))
        local_buttons.addWidget(self._button("Play selected audio/video",self._play_local_media))
        local_buttons.addWidget(self._button("Open recordings folder",self.open_archive_folder))
        local_layout.addLayout(local_buttons)
        self.native_image_files=QTreeWidget()
        self.native_image_files.setHeaderLabels(
            ["Saved file","Data type / format","Bytes"])
        self.native_image_files.setMaximumHeight(185)
        self.native_image_files.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.native_image_files.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.native_image_files.itemSelectionChanged.connect(self._image_local_selected)
        local_layout.addWidget(self.native_image_files)
        self.native_local_preview=QLabel(
            "Choose a real local image/WAV/text file to inspect it. "
            "Only actual PNG/JPEG images are drawn here.")
        self.native_local_preview.setWordWrap(True)
        self.native_local_preview.setAlignment(Qt.AlignCenter)
        self.native_local_preview.setMinimumHeight(85)
        local_layout.addWidget(self.native_local_preview)
        self.native_selected_media=None
        self.native_local_status=self._hint(
            "No file chosen. Source identity cannot be inferred from filename alone.")
        local_layout.addWidget(self.native_local_status)
        body.addWidget(local)

        nasa=QGroupBox("3 · Online NASA Earth imagery · NOT received by SDR")
        online=QVBoxLayout(nasa)
        nasa_toolbar=QHBoxLayout()
        self.online_provider=QComboBox()
        self.online_provider.addItem("NASA DSCOVR EPIC · whole Earth","epic")
        self.online_provider.addItem("NASA ISS Earth photo archive","iss")
        nasa_toolbar.addWidget(self.online_provider)
        nasa_toolbar.addWidget(self._button("Fetch official image catalog",
                                            self._image_fetch_catalog))
        online.addLayout(nasa_toolbar)
        self.online_image_status=self._hint(
            "Online imagery is optional, fetched only on click over HTTPS. "
            "No RF recording, WebUSB or embedded browser required.")
        online.addWidget(self.online_image_status)
        self.online_image_files=QTreeWidget()
        self.online_image_files.setHeaderLabels(["NASA image","UTC / archive time","Source"])
        self.online_image_files.setMaximumHeight(180)
        self.online_image_files.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.online_image_files.itemSelectionChanged.connect(self._image_online_selected)
        online.addWidget(self.online_image_files)
        self.online_image_preview=QLabel(
            "Select an official NASA item and click Preview to download it.")
        self.online_image_preview.setWordWrap(True)
        self.online_image_preview.setMinimumHeight(130)
        self.online_image_preview.setAlignment(Qt.AlignCenter)
        online.addWidget(self.online_image_preview)
        self.online_records=[]
        self.online_selected=None
        self.online_image_bytes=None
        self.online_image_format=None
        downloads=QHBoxLayout()
        downloads.addWidget(self._button("Preview selected NASA image",
                                         self._image_preview_online))
        downloads.addWidget(self._button("Save NASA image with source label",
                                         self._image_save_online))
        online.addLayout(downloads)
        body.addWidget(nasa)
        body.addWidget(self._button(
            "Explore satellite signal / user-saved protocol profiles",
            lambda:self._open_native_tab("Saved protocols")))
        body.addStretch(1)

    def _image_tune_iss(self):
        key="iss_sstv"
        self.home_capture_profile.setCurrentIndex(
            self.home_capture_profile.findData(key))
        self.capture_profile.setCurrentIndex(self.capture_profile.findData(key))
        self._open_native_tab("Overview")
        self.statusBar().showMessage(
            "ISS SSTV candidate 437.550 MHz selected for native RF acquisition. "
            "Check current ARISS event before recording.",12000)

    def _image_import(self):
        path,_=QFileDialog.getOpenFileName(
            self,"Open actual local RF / image / audio / text",
            str(self.station.archive),
            "Supported files (*.cu8 *.wav *.mp3 *.ogg *.flac *.mp4 *.m4v *.mov *.webm *.png *.jpg *.jpeg *.gif *.webp *.txt *.json *.csv);;All files (*)")
        if not path:return
        self._choose_path(path)
        self.native_selected_media=Path(path)
        self._image_show_local(Path(path))

    def _image_decode_sstv(self):
        self._open_native_tab("Recordings & results")
        self.result_steps.setCurrentIndex(2)
        self.decode_robot36_native()

    def _image_local_selected(self):
        item=self.native_image_files.currentItem()
        if item is None:return
        path=Path(str(item.data(0,Qt.UserRole)))
        self.native_selected_media=path
        self._image_show_local(path)

    def _image_show_local(self,path):
        if not path.is_file():
            self.native_local_status.setText("File removed or unavailable: "+str(path))
            return
        label,why=describe_local_file(path)
        self.native_local_status.setText(
            str(path)+"  ·  "+label+"  ·  "+why)
        self.native_local_preview.clear()
        if path.suffix.lower() in (".png",".jpg",".jpeg") and path.stat().st_size<20_000_000:
            pixmap=QPixmap(str(path))
            if not pixmap.isNull():
                self.native_local_preview.setPixmap(
                    pixmap.scaled(700,255,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                return
        self.native_local_preview.setText(
            path.name+"  ·  "+label+"\nUse Signal analysis for CU8 FFT, "
            "the Play audio/video button for supported local media, "
            "or real decoder tools for RF files.")

    def _play_local_media(self):
        """Native QtMedia playback only; never an embedded browser or URL."""
        source=self.native_selected_media
        if source is None or not source.is_file():
            return QMessageBox.information(
                self,"Play local media","Choose or import an actual audio/video file first.")
        suffix=source.suffix.lower()
        audio={".wav",".mp3",".ogg",".flac"}
        video={".mp4",".m4v",".mov",".webm"}
        if suffix not in audio|video:
            return QMessageBox.information(
                self,"Play local media","This source is not a supported audio/video file.")
        from .native_data_labels import describe_local_file
        label,_=describe_local_file(source)
        if label.startswith(("INVALID?","UNREADABLE")):
            return QMessageBox.warning(self,"Local media","File signature could not be verified.")
        try:
            from PyQt5.QtMultimedia import QMediaPlayer,QMediaContent
        except ImportError:
            return QMessageBox.information(
                self,"Optional native Qt Multimedia",
                "Install python3-pyqt5.qtmultimedia for local audio/video playback. "
                "No WebUSB/HTML is needed.")
        if suffix in audio:
            self.preview_wav=str(source) if suffix==".wav" else self.preview_wav
            if self.media_player is None:self.media_player=QMediaPlayer(self)
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(str(source))))
            self.media_player.play()
            self.native_local_status.setText(
                "Playing actual local audio via native Qt backend: "+source.name+
                ". Codec support depends on the OS. No satellite identity proved.")
            return
        try:
            from PyQt5.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            return QMessageBox.information(
                self,"Optional native video backend",
                "Install python3-pyqt5.qtmultimedia and Qt video backend to preview local video.")
        dialog=QDialog(self)
        dialog.setWindowTitle("Native local video · "+source.name)
        dialog.resize(840,570)
        layout=QVBoxLayout(dialog)
        labelWidget=QLabel(
            "Actual LOCAL video file · "+source.name+
            " · This is not evidence of a satellite downlink")
        labelWidget.setWordWrap(True)
        layout.addWidget(labelWidget)
        screen=QVideoWidget(dialog)
        layout.addWidget(screen,1)
        player=QMediaPlayer(dialog)
        player.setVideoOutput(screen)
        player.setMedia(QMediaContent(QUrl.fromLocalFile(str(source))))
        row=QHBoxLayout()
        row.addWidget(self._button("Play",player.play))
        row.addWidget(self._button("Pause",player.pause))
        row.addWidget(self._button("Stop",player.stop))
        row.addWidget(self._button("Close",dialog.accept))
        layout.addLayout(row)
        player.play()
        try:dialog.exec_()
        finally:player.stop()

    def _update_native_image_files(self,archive):
        selected=(self.native_image_files.currentItem().data(0,Qt.UserRole)
                  if self.native_image_files.currentItem() is not None else None)
        self.native_image_files.blockSignals(True)
        self.native_image_files.clear()
        for item in archive:
            name=item.get("file","")
            path=self.station.archive/name
            if not path.is_file():continue
            label,_=describe_local_file(path)
            row=QTreeWidgetItem([name,label,str(item.get("bytes",0))])
            row.setData(0,Qt.UserRole,str(path))
            self.native_image_files.addTopLevelItem(row)
            if str(path)==selected:
                self.native_image_files.setCurrentItem(row)
        self.native_image_files.blockSignals(False)

    def _image_fetch_catalog(self):
        provider=self.online_provider.currentData()
        self.online_image_status.setText("Requesting official NASA catalog over HTTPS…")
        self._task("NASA image catalog",
                   lambda:list_official_images(provider),
                   self._image_catalog_done)

    def _image_catalog_done(self,rows):
        self.online_records=rows
        self.online_image_bytes=None
        self.online_selected=None
        self.online_image_preview.clear()
        self.online_image_files.clear()
        for index,record in enumerate(rows):
            item=QTreeWidgetItem([
                str(record.get("caption","NASA image"))[:105],
                str(record.get("time","unknown")),
                str(record.get("provider","NASA"))])
            item.setData(0,Qt.UserRole,index)
            self.online_image_files.addTopLevelItem(item)
        self.online_image_status.setText(
            f"{len(rows)} official NASA archive item(s), NONE received over RF. "
            "Select one to preview.")

    def _image_online_selected(self):
        item=self.online_image_files.currentItem()
        if item is None:return
        index=item.data(0,Qt.UserRole)
        if not isinstance(index,int) or not 0<=index<len(self.online_records):return
        self.online_selected=self.online_records[index]
        self.online_image_bytes=None
        self.online_image_preview.setText(
            str(self.online_selected["caption"])+"\n"+
            str(self.online_selected["time"])+"\nSource: "+
            str(self.online_selected["provider"])+" (ONLINE ONLY, not RF)")

    def _image_preview_online(self):
        if self.online_selected is None:
            return QMessageBox.information(self,"NASA preview",
                "Choose an official NASA image from the list first.")
        item=dict(self.online_selected)
        self.online_image_status.setText("Downloading selected NASA image preview…")
        self._task("NASA image preview",lambda:fetch_official_image(item),
                   lambda data:self._image_preview_done(item,data))

    def _image_preview_done(self,item,data):
        if self.online_selected is None or item.get("url")!=self.online_selected.get("url"):
            return
        pixmap=QPixmap()
        if not pixmap.loadFromData(data):
            self.online_image_status.setText("NASA image is not readable by local Qt.")
            return
        self.online_image_bytes=data
        self.online_image_format=".png" if data.startswith(b"\x89PNG") else ".jpg"
        self.online_image_preview.setPixmap(pixmap.scaled(
            760,330,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.online_image_status.setText(
            f"Official online NASA image downloaded ({len(data)} bytes); "
            "not an RF reception, ISS downlink or local SDR acquisition.")

    def _image_save_online(self):
        if self.online_image_bytes is None or self.online_selected is None:
            return QMessageBox.information(self,"Save NASA image",
                "First select and preview a real official NASA image.")
        import re as _re
        basename=_re.sub(r"[^A-Za-z0-9_-]","_",
                         str(self.online_selected.get("id") or "nasa_earth"))[:50]
        filename="NASA_ONLINE_"+basename+(self.online_image_format or ".jpg")
        path,_=QFileDialog.getSaveFileName(
            self,"Save official online NASA photo (NOT RF)",
            str(Path.home()/filename),
            "Images (*.jpg *.png)")
        if not path:return
        target=Path(path).expanduser()
        if target.exists():
            return QMessageBox.warning(self,"Save NASA image",
                                       "Destination already exists; not overwriting.")
        # Keep original verified format and provenance in sidecar metadata.
        if target.suffix.lower() != self.online_image_format:
            return QMessageBox.warning(self,"Save NASA image",
                                       "Keep original NASA PNG/JPEG file extension.")
        manifest=target.with_suffix(target.suffix+".source.json")
        if manifest.exists():
            return QMessageBox.warning(self,"Save NASA image",
                                       "Provenance metadata already exists; choose another name.")
        try:
            with target.open("xb") as stream:
                stream.write(self.online_image_bytes)
            manifest.write_text(json.dumps({
                **self.online_selected,"source_medium":"ONLINE_HTTPS_NOT_RF",
                "saved_at":datetime.now(timezone.utc).isoformat()
            },indent=2),encoding="utf-8")
        except OSError as error:
            return QMessageBox.warning(self,"Save NASA image",str(error))
        self.online_image_status.setText(
            "Saved NASA ONLINE image and provenance JSON to "+str(target))

    def _protocols_tab(self):
        """Manual public downlink catalog, independent of receiver allowlist."""
        body=self._new_tab("Saved protocols")
        body.addWidget(self._hint(
            "Same JSON schema as the web Satellite Center. Up to 32 manual "
            "NORAD/frequency/image/audio/text/video references, saved privately on disk. "
            "These are user-supplied hypotheses, not verified transmitters, "
            "working decoders or automatic RF jobs."))
        self.protocol_list=QTreeWidget()
        self.protocol_list.setHeaderLabels(
            ["NORAD","Possible media","Frequency","Protocol label","Reference HTTPS"])
        self.protocol_list.setRootIsDecorated(False)
        self.protocol_list.header().setSectionResizeMode(3,QHeaderView.Stretch)
        self.protocol_list.itemSelectionChanged.connect(self._protocol_selected)
        body.addWidget(self.protocol_list,1)
        self.protocol_details=self._hint(
            "Add your own radio profile or import browser-exported JSON. "
            "No RF acquisition happens.")
        body.addWidget(self.protocol_details)
        first=QHBoxLayout()
        first.addWidget(self._button("Add user protocol…",lambda:self._edit_protocol(None)))
        first.addWidget(self._button("Edit selected…",self._protocol_edit_selected))
        first.addWidget(self._button("Remove selected…",self._protocol_remove_selected))
        body.addLayout(first)
        second=QHBoxLayout()
        second.addWidget(self._button("Import browser protocol JSON…",self._protocol_import))
        second.addWidget(self._button("Export portable protocol JSON…",self._protocol_export))
        second.addWidget(self._button("Use center frequency in CU8 analyzer",
                                      self._protocol_to_analyzer))
        body.addLayout(second)
        self._protocol_refresh()

    def _protocol_refresh(self):
        try:rows=load_profiles(self.station.directory)
        except (OSError,ValueError,TypeError,json.JSONDecodeError) as error:
            self.protocol_details.setText(
                "Cannot read saved protocol catalog safely: "+str(error))
            return
        self.protocol_list.clear()
        for profile in rows:
            item=QTreeWidgetItem([
                str(profile["norad"]),profile["kind"].upper(),
                f'{profile["frequencyHz"]/1e6:.6f} MHz',
                profile["protocol"],profile["source"]])
            item.setData(0,Qt.UserRole,profile)
            item.setToolTip(0,"User-supplied and unverified NORAD/protocol data")
            self.protocol_list.addTopLevelItem(item)
        self.protocol_details.setText(
            f'{len(rows)} custom references saved locally · no decoder or '
            'unattended scan enabled by these references')

    def _protocol_selected(self):
        item=self.protocol_list.currentItem()
        if item:
            profile=item.data(0,Qt.UserRole)
            self.protocol_details.setText(
                f'USER-SUPPLIED / NOT VERIFIED · NORAD {profile["norad"]} · '+
                profile["protocol"]+" · "+profile["kind"].upper()+
                " · never auto-tunes a receiver or starts an unknown decoder.")

    def _protocol_edit_selected(self):
        item=self.protocol_list.currentItem()
        if item:self._edit_protocol(item.data(0,Qt.UserRole))
        else:QMessageBox.information(self,"Protocol catalog","Select a saved protocol first.")

    def _edit_protocol(self,current):
        dialog=QDialog(self)
        dialog.setWindowTitle("Receive-only user protocol · UNVERIFIED")
        form=QFormLayout(dialog)
        norad=QSpinBox();norad.setRange(1000,9999999)
        norad.setValue(int(current["norad"]) if current else 59051)
        freq=QDoubleSpinBox();freq.setDecimals(6)
        freq.setRange(24,1750);freq.setSingleStep(0.0125)
        freq.setSuffix(" MHz")
        freq.setValue(current["frequencyHz"]/1e6 if current else 137.9)
        kind=QComboBox()
        for name in ("image","audio","text","video"):
            kind.addItem(name.upper(),name)
        if current:kind.setCurrentIndex(kind.findData(current["kind"]))
        protocol=QLineEdit(current["protocol"] if current else "")
        protocol.setMaxLength(64)
        protocol.setPlaceholderText("e.g. LRPT / AFSK / SSTV · your published reference")
        source=QLineEdit(current["source"] if current else "https://db.satnogs.org/")
        source.setMaxLength(300)
        form.addRow("NORAD number",norad)
        form.addRow("Receive-only RF frequency",freq)
        form.addRow("Potential output",kind)
        form.addRow("Protocol name",protocol)
        form.addRow("HTTPS source reference",source)
        form.addRow(self._hint("Only a user-provided reference is saved. "
                              "No radio, satellite or decoder is activated."))
        controls=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        form.addRow(controls)
        if dialog.exec_()!=QDialog.Accepted:return
        try:
            row=parse_user_protocol({
                "norad":norad.value(),
                "frequencyHz":round(freq.value()*1e6),
                "kind":kind.currentData(),
                "protocol":protocol.text(),"source":source.text()})
            existing=load_profiles(self.station.directory)
            existing=[p for p in existing if p["id"] not in (
                row["id"],current["id"] if current else row["id"])]
            save_profiles(self.station.directory,existing+[row])
            self._protocol_refresh()
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,"Cannot save protocol",str(error))

    def _protocol_remove_selected(self):
        item=self.protocol_list.currentItem()
        if not item:return
        profile=item.data(0,Qt.UserRole)
        if QMessageBox.question(
                self,"Remove local protocol",
                "Archive of RF data will NOT be modified. Remove this "
                "user-supplied reference?",
                QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        try:
            save_profiles(self.station.directory,[
                p for p in load_profiles(self.station.directory)
                if p["id"]!=profile["id"]])
            self._protocol_refresh()
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,"Protocol deletion",str(error))

    def _protocol_import(self):
        path,_=QFileDialog.getOpenFileName(
            self,"Import user-supplied Satellite Center web profiles",
            str(Path.home()),"Protocol JSON (*.json)")
        if not path:return
        try:
            import_profiles(self.station.directory,path)
            self._protocol_refresh()
        except (OSError,ValueError,json.JSONDecodeError) as error:
            QMessageBox.warning(self,"Protocol import rejected",str(error))

    def _protocol_export(self):
        path,_=QFileDialog.getSaveFileName(
            self,"Export portable user protocol JSON",
            str(Path.home()/"TIHULU_satellite_user_profiles.json"),
            "Protocol JSON (*.json)")
        if not path:return
        try:
            export_profiles(self.station.directory,path)
            self.statusBar().showMessage(
                "User reference JSON saved · no RF recordings exported",11000)
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,"Protocol export",str(error))

    def _protocol_to_analyzer(self):
        item=self.protocol_list.currentItem()
        if not item:return
        profile=item.data(0,Qt.UserRole)
        self.center.setValue(profile["frequencyHz"]/1e6)
        if self._open_native_tab("Recordings & results"):
            self.result_steps.setCurrentIndex(1)
            self.statusBar().showMessage(
                "Analysis center frequency from UNVERIFIED user reference: "+
                f'{profile["frequencyHz"]/1e6:.6f} MHz. '+
                "Select actual CU8 with correct acquisition metadata.",13000)

    def _task(self, key, function, completed=None, silent=False):
        if not self.active or key in self.tasks:
            return
        worker=BackgroundTask(function)
        self.tasks[key]=worker
        def on_result(value):
            if self.active:
                if completed:completed(value)
                if not silent:self.statusBar().showMessage(key+" completed",8000)
        def on_error(message):
            if self.active:
                self.statusBar().showMessage(key+": "+message,15000)
                if key=="Auto mission planning":
                    self.auto_feedback.setText("Could not schedule: "+message)
                elif key=="Arm scheduled RF":
                    self.pass_feedback.setText("Recording not scheduled: "+message)
                elif key=="Local TLE import":
                    self.tle_import_feedback.setText("TLE import failed: "+message)
                elif key=="Worldwide geocoding":
                    self.city_info.setText("Online city lookup failed: "+message)
                    self.home_city_info.setText(
                        "Worldwide lookup failed: "+message+
                        " · Offline search and custom coordinates still work.")
                elif key=="Predict satellite passes":
                    self.home_pass_summary.setText(
                        "Unable to calculate orbital passes: "+message+
                        " · Confirm Skyfield/TLE data, refresh orbit files, "
                        "or import a local TLE.")
                elif key=="Public TLE refresh":
                    self.home_pass_summary.setText(
                        "Orbit refresh failed: "+message+
                        " · Use cached files or import a local TLE.")
                elif key in ("Connect SDR","Disconnect SDR","USB diagnostic","Real RF sample test"):
                    self.hardware_feedback.setText(key+" failed: "+message)
                    self.refresh_status()
                if key.startswith("NASA "):
                    self.online_image_status.setText(key+" failed: "+message)
                if not silent:
                    QMessageBox.warning(self,"Satellite Center",message)
        def on_finished():
            self.tasks.pop(key,None)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.pool.start(worker)

    def _refresh_live_iq_level(self):
        """Read only a bounded tail of Station's actual on-disk IQ stream.

        No extra USB consumer is opened. Does not run a radio test on its own.
        """
        with self.station.lock:
            session=dict(self.station.session)
        if not session.get("active") or session.get("mode")!="iq":
            return
        rawname=session.get("path")
        if not isinstance(rawname,str) or not rawname.endswith(".cu8"):
            return
        source=self.station.archive/rawname
        try:
            size=source.stat().st_size
            if size<8192:return
            with source.open("rb") as stream:
                stream.seek(max(0,size-65536))
                data=stream.read(65536)
        except OSError:
            return
        sample=data[::32]
        if len(sample)<128:return
        rms=math.sqrt(sum((v-127.5)**2 for v in sample)/len(sample))
        if rms<=0:return
        dbfs=20*math.log10(rms/127.5)
        self.home_level_chart.push(dbfs)
        self.capture_level_chart.push(dbfs)
        description=f"ACTUAL CU8 RF samples · {dbfs:.1f} relative dBFS · {size} bytes saved"
        self.home_sample_state.setText(description)
        self.capture_live_state.setText(description)

    def refresh_status(self):
        self._task("status",self.station.status,self._apply_status,silent=True)

    def _apply_status(self,state):
        session=state.get("session",{})
        hardware=state.get("hardware") or {}
        enabled=hardware.get("receiver_enabled",True)
        released=hardware.get("app_released",False)
        present=state.get("tuner_present")
        self.top_status.setText(
            "RF DISABLED · receiver released" if not enabled and released else
            "RF DISABLED · release pending" if not enabled else
            "RTL-SDR: recording" if session.get("active") else
            "RTL-SDR: detected · idle" if present else "RTL-SDR: not detected")
        usb_count=hardware.get("usb_rtl_count")
        devices=hardware.get("usb_devices") or []
        self.hardware_presence.setText(
            ("RTL-SDR USB detected · "+str(usb_count)+" device(s)" if usb_count else
             "RTL-SDR not seen in USB inventory" if usb_count==0 else
             "USB enumeration unavailable on this platform"))
        last_test=hardware.get("last_usb_test") or {}
        last_sample=hardware.get("last_real_sample") or {}
        self.hardware_access.setText(
            "Connect verified: USB OPEN + real IQ, test released · "+
            str(last_test.get("verified_at","unknown")) if last_test else
            "Real IQ test passed · "+str(last_sample.get("sample_bytes",0))+
            " bytes at "+str(last_sample.get("verified_at","unknown"))+
            " (does NOT enable scheduled RF)" if last_sample else
            "No real IQ verified yet · use Connect or Test real RF")
        self.hardware_mode.setText(
            "RF acquisition: ENABLED for explicit captures and pending jobs" if enabled
            else "RF acquisition: DISABLED · survives restart; no new scheduled capture")
        self.hardware_lease.setText(
            "Application SDR handle: RELEASED · no owned process or receiver lock" if released
            else "Application SDR handle: IN USE / STARTING / RELEASING · see status")
        busy=state.get("busy") or []
        self.hardware_busy.setText(
            "Active SDR-related processes (may be ours or other apps): "+
            ", ".join(str(e.get("process","?"))+" (PID "+str(e.get("pid","?"))+")"
                      for e in busy[:6]) if busy else
            "No known competing SDR process detected (passive scan)")
        self.hardware_schedules.setText(
            str(hardware.get("pending_schedules",0))+
            (" pending RF job(s) · PAUSED while disabled" if not enabled
             else " pending RF job(s) · may run when scheduled"))
        inv_key=json.dumps(devices,sort_keys=True)
        if inv_key!=self.hardware_inventory_key:
            self.hardware_inventory_key=inv_key
            self.hardware_devices.clear()
            for device in devices:
                kind=("RTL-SDR · raw IQ capable"
                      if device.get("receiver_type")=="rtl_sdr" else
                      "DVB television · not RTL-SDR")
                item=QTreeWidgetItem([
                    str(device.get("name") or "USB receiver"),
                    kind,
                    str(device.get("vendor_id","?"))+":"+
                    str(device.get("product_id","?")),
                    str(device.get("sysfs_device","?"))])
                self.hardware_devices.addTopLevelItem(item)
            if not devices:
                self.hardware_devices.addTopLevelItem(QTreeWidgetItem(
                    ["No supported USB SDR/TV hardware detected","—","—","—"]))
        self.hardware_connect_button.setEnabled(
            not session.get("active") and not hardware.get("opening",False))
        self.hardware_test_button.setEnabled(
            not session.get("active") and not hardware.get("opening",False))
        self.hardware_sample_button.setEnabled(
            not session.get("active") and not hardware.get("opening",False))
        self.device_label.setText("Receiver: "+(
            "RTL2832U USB detected (passive)" if state.get("tuner_present") else
            "No RTL2832U detected passively. Verify device/udev and rtl_test."))
        self.session_label.setText("Last session: "+session.get("state","idle")+
                                   " · "+session.get("message","no reception attempted"))
        self.cache_label.setText("TLE cache: "+ " · ".join(
            key+(": "+str(val.get("age_hours"))+"h" if val.get("present") else ": not downloaded")
            for key,val in state.get("orbit_cache",{}).items()))
        self.disk_label.setText("Recordings: "+str(len(state.get("archive",[])))+
                                " actual local files · "+str(self.station.archive))
        self.home_jobs_status.setText(
            str(hardware.get("pending_schedules",0))+" scheduled future RF capture(s). "+
            ("RF DISABLED · pending jobs paused." if not enabled
             else "Native receiver jobs run only while this Qt program remains open."))
        self.home_usb_state.setText(
            "RF DISABLED · lease released" if not enabled and released else
            "RF DISABLED · release incomplete" if not enabled else
            "USB IQ VERIFIED · idle ready" if hardware.get("last_usb_test") else
            "Real IQ sample TEST passed; Connect to arm future recordings" if hardware.get("last_real_sample") else
            "USB not yet verified by real IQ capture; open Hardware / USB.")
        self._calendar_jobs=state.get("jobs",[])
        jobs_key=json.dumps([(j.get("id"),j.get("state"),j.get("run_at"),j.get("result"),
                              j.get("capture_seconds"),j.get("mission_id"))
                             for j in self._calendar_jobs],sort_keys=True,default=str)
        if jobs_key!=self.last_jobs_key:
            self.last_jobs_key=jobs_key
            self._render_job_list()
            self._render_calendar()
        archive_key=json.dumps(state.get("archive",[]),sort_keys=True)
        if archive_key!=self.last_archive_key:
            self.last_archive_key=archive_key
            self._render_files(state.get("archive",[]))
            self._update_native_image_files(state.get("archive",[]))

    def usb_test(self):
        self.hardware_feedback.setText("Testing physical USB access without enabling capture…")
        def completed(report):
            message=json.dumps(report,indent=2,default=str)
            self.hardware_log.setPlainText(message)
            self.hardware_feedback.setText(
                "USB successfully opened and released for test. "
                "No RF was captured, and RF enable state was not changed.")
            self.refresh_status()
        self._task("USB diagnostic",self.station.usb_test,completed)

    def refresh_tles(self):
        self.home_pass_summary.setText(
            "Refreshing public orbital TLEs over HTTPS (explicit request)…")
        def finished(result):
            self.file_details.setPlainText(json.dumps(result,indent=2))
            successes=sum(bool(v.get("cached")) for v in result.values())
            errors=[name+": "+str(v.get("error")) for name,v in result.items()
                    if v.get("error")]
            if successes:
                self.home_pass_summary.setText(
                    str(successes)+" orbit catalog source(s) refreshed. Calculating passes…")
                self.calculate_passes()
            else:
                self.home_pass_summary.setText(
                    "TLE refresh failed · "+("; ".join(errors[:2]) or "unknown error")+
                    " · Import a local TLE file from Full pass planner.")
            self.refresh_status()
        self._task("Public TLE refresh",self.station.refresh,finished)

    def _station_kwargs(self):
        return {"lat":self.lat.value(),"lon":self.lon.value(),
                "hours":self.hours.value(),"elevation":self.elev.value()}

    def import_tle(self):
        source=self.tle_source.currentData()
        path,_=QFileDialog.getOpenFileName(
            self,"Import locally saved orbital TLE elements",
            str(Path.home()),"TLE orbit text (*.tle *.txt);;All files (*)")
        if not path:return
        self.tle_import_feedback.setText("Validating locally saved orbital elements…")
        def finished(report):
            self.tle_import_feedback.setText(
                "Imported "+str(report["tle_count"])+" validated TLE pair(s) for "+
                source+". Click Calculate satellite passes.")
            self.refresh_status()
        self._task("Local TLE import",
                   lambda:self.station.import_tle(path,source),finished)

    def calculate_passes(self):
        if "Predict satellite passes" in self.tasks:
            return
        # Snapshot the same coordinates and lookahead used by BOTH Qt views.
        parameters=self._station_kwargs()
        self.home_pass_summary.setText(
            f"Calculating real TLE predictions for {parameters['lat']:.5f}°, "
            f"{parameters['lon']:.5f}° · {parameters['hours']} h… "
            "Missing/expired orbit files will be refreshed on demand.")
        self._task("Predict satellite passes",
                   lambda:self.station.plan_passes(**parameters),
                   self._apply_passes)

    def _apply_passes(self,data):
        rows=data.get("predictions",[])
        self.passes={r["id"]:r for r in rows}
        self._render_pass_results()
        self._render_home_passes()
        if not rows:
            warnings=data.get("warnings") or []
            refresh=data.get("automatic_tle_refresh") or {}
            errors=[str(name)+": "+str(entry["error"]) for name,entry in
                    refresh.items() if entry.get("error")]
            self.home_pass_summary.setText(
                "0 predicted passes. "+
                (" · ".join((warnings+errors)[:3]) if warnings or errors else
                 "Try a longer lookahead, lower min elevation or refresh TLE data.")+
                " · Local .tle import available in Full pass planner.")
        self.home_city_info.setText(
            "Ground station for results: "+
            f"{data.get('observer',{}).get('lat',self.lat.value()):.5f}°, "+
            f"{data.get('observer',{}).get('lon',self.lon.value()):.5f}° · "
            "orbital geometry, not RF detections.")
        target=getattr(self,"map_pending_pass_norad",None)
        if target is not None:
            self.map_pending_pass_norad=None
            for i in range(self.pass_list.topLevelItemCount()):
                item=self.pass_list.topLevelItem(i)
                row=self.passes.get(item.data(0,Qt.UserRole))
                if row and int(row.get("norad",-1))==int(target):
                    self.pass_list.setCurrentItem(item)
                    self.pass_list.scrollToItem(item)
                    break
        warning=" · ".join(data.get("warnings",[])[:2])
        self.statusBar().showMessage(
            str(len(rows))+" orbital passes (not RF detections)"+
            (" · "+warning if warning else ""),15000)

    def pass_selected(self):
        item=self.pass_list.currentItem()
        row=self.passes.get(item.data(0,Qt.UserRole)) if item else None
        self.pass_profile.blockSignals(True)
        self.pass_profile.clear()
        self.arm_pass.setEnabled(bool(row))
        self.pass_schedule_button.setEnabled(bool(row))
        self.pass_map_button.setEnabled(bool(row))
        if row:
            kinds=kinds_for_pass(row)
            self.pass_title.setText(row["name"]+"  ·  NORAD "+str(row.get("norad","?")))
            self.pass_subtitle.setText(
                local_time(row["aos"])+"  →  "+local_time(row["los"])+
                "   |   "+str(row.get("max_elevation_deg","?"))+"° peak   |   "
                +str(row.get("family","unknown")).upper())
            self._set_pass_media_bar(kinds)
            self.pass_requirements.setText("\n".join("• "+s for s in media_summary(
                row,check_decoders=False)))
            for key in row.get("profiles",[]):
                if key in PROFILES:self.pass_profile.addItem(PROFILES[key]["label"],key)
            self.pass_time.setDateTime(native_datetime(row["aos"]))
            remaining=(datetime.fromisoformat(row["los"])-
                       datetime.fromisoformat(row["aos"])).total_seconds()
            self.pass_seconds.setValue(max(8,min(900,int(remaining)-25)))
        else:
            self.pass_title.setText("No pass selected")
            self.pass_subtitle.setText("Choose a candidate from the list or clear your filters.")
            self._set_pass_media_bar([])
            self.pass_requirements.setText(
                "Image = known potential decoder protocol; RF data = raw samples only. "
                "No transmission or decoded files are confirmed by orbital predictions.")
        self.pass_profile.blockSignals(False)
        self._pass_modes()

    def _pass_modes(self):
        key=self.pass_profile.currentData()
        current=self.pass_mode.currentData()
        self.pass_mode.blockSignals(True)
        self.pass_mode.clear()
        mode_labels={
            "iq":"Raw IQ · CU8 disk (8–900 s)",
            "iq_and_fm_wav":"CU8 + derived FM WAV · same capture",
            "survey":"RF spectrum survey (8–180 s)",
            "sstv_audio":"SSTV FM audio · WAV (event-only)",
            "fm_audio":"Voice / FM audio · WAV",
            "aprs":"AX.25 APRS text · real decoder required"}
        for mode in ("iq","iq_and_fm_wav","sstv_audio","fm_audio","aprs","survey"):
            if key and allowed_mode(key,mode):
                self.pass_mode.addItem(mode_labels[mode],mode)
        index=self.pass_mode.findData(current)
        if index>=0:self.pass_mode.setCurrentIndex(index)
        self.pass_mode.blockSignals(False)
        self._pass_budget()

    def _pass_unit_changed(self):
        minute=self.pass_length_unit.currentData()=="minutes"
        current=self.pass_seconds.value()
        self.pass_seconds.blockSignals(True)
        self.pass_seconds.setRange(1,120) if minute else self.pass_seconds.setRange(8,7200)
        self.pass_seconds.setValue(max(1,(current+59)//60) if minute else max(8,current*60))
        self.pass_seconds.blockSignals(False)
        self._pass_budget()

    def _pass_budget(self):
        mode=self.pass_mode.currentData()
        rate=int(self.pass_sample_rate.currentData() or 1024000)
        self.pass_sample_rate.setEnabled(mode in ("iq","iq_and_fm_wav"))
        seconds=self.pass_seconds.value()*(60 if self.pass_length_unit.currentData()=="minutes" else 1)
        parts=max(1,(seconds+179)//180)
        gaps=max(0,parts-1)*21
        if mode=="iq_and_fm_wav":
            estimate=seconds*(2*rate/1e6+.064)
            label="CU8 + actual FM WAV, same RF; both unverified"
        elif mode=="iq":
            estimate=seconds*2*rate/1e6
            label="raw CU8 on disk"
        elif mode in ("sstv_audio","fm_audio"):
            estimate=seconds*.096
            label="real FM WAV audio"
        else:
            estimate=0
            label="approved local spectrum / packet receiver"
        self.pass_cost.setText(
            f"~{estimate:.1f} MB · {parts} separate RF file(s) · "
            f"{seconds+gaps} s total elapsed ({gaps} s reserved gaps). "
            "No lossless continuity; receiver must be free and visible pass must fit.")

    def schedule_selected_pass(self):
        item=self.pass_list.currentItem()
        if not item:return QMessageBox.information(self,"Schedule","Choose a predicted pass first.")
        key=item.data(0,Qt.UserRole)
        profile=self.pass_profile.currentData()
        mode=self.pass_mode.currentData()
        seconds=self.pass_seconds.value()*(60 if self.pass_length_unit.currentData()=="minutes" else 1)
        sample_rate=int(self.pass_sample_rate.currentData() or 1024000)
        start=datetime.fromtimestamp(self.pass_time.dateTime().toSecsSinceEpoch(),timezone.utc).isoformat()
        def completed(job):
            n=job.get("scheduled_count",1)
            text=(str(n)+" native capture file(s) scheduled · "+str(seconds)+" s RF. "+
                  (str(job.get("total_gap_seconds",0))+" s reserved gaps. " if n>1 else "")+
                  "The native Qt app must remain running.")
            self.pass_feedback.setText(text)
            self.statusBar().showMessage(text,12000)
            self.refresh_status()
        self._task("Arm scheduled RF",
                   lambda:self.station.schedule_chain(key,profile,mode,start,seconds,
                       sample_rate=sample_rate) if seconds>180 else
                   self.station.schedule(key,profile,mode,start,seconds,
                       sample_rate=sample_rate),completed)

    def _auto_unit_changed(self):
        minute=self.auto_length_unit.currentData()=="minutes"
        current=self.auto_seconds.value()
        self.auto_seconds.blockSignals(True)
        self.auto_seconds.setRange(0,15 if minute else 900)
        self.auto_seconds.setValue((current+59)//60 if minute else current*60)
        self.auto_seconds.blockSignals(False)

    def auto_schedule(self):
        missions=[mid for mid,box in self.mission_boxes.items() if box.isChecked()]
        if not missions:return QMessageBox.information(self,"Auto reception","Select at least one satellite mode.")
        seconds=self.auto_seconds.value()*(60 if self.auto_length_unit.currentData()=="minutes" else 1) or None
        coverage=self.coverage.currentData()
        compute_mode,compute_targets=self.auto_compute.currentData()
        params={"lat":self.lat.value(),"lon":self.lon.value(),"hours":self.hours.value(),
                "elevation":self.auto_elev.value(),"max_jobs":self.auto_jobs.value(),
                "coverage_goal":coverage,"duration_seconds":seconds,
                "compute_mode":compute_mode,"compute_targets":compute_targets,
                "iss_record_format":self.auto_iss_format.currentData()}
        self.auto_feedback.setText("Calculating local satellite passes and checking receiver feasibility…")
        self._task("Auto mission planning",lambda:self.station.auto_schedule(missions,**params),
                   self._auto_schedule_finished)

    def _auto_schedule_finished(self,result):
        count=int(result.get("scheduled_count",0))
        skipped=result.get("skipped") or []
        disabled=result.get("disabled_targets") or []
        text=f"{count} real RF capture job(s) scheduled locally."
        if skipped:text+=" "+str(len(skipped))+" candidate(s) skipped; "+str(skipped[0])
        if disabled:text+=" Some selected decoders are unavailable: "+", ".join(map(str,disabled))
        if not count:text="No feasible capture job scheduled. "+(" ".join(map(str,skipped[:2])) or "Check TLEs, elevation and receiver tools.")
        self.auto_feedback.setText(text)
        if hasattr(self,"home_auto_status"):
            self.home_auto_status.setText(text)
        self.refresh_status()
        self.statusBar().showMessage(text[:220],14000)

    def cancel_automatic(self):
        self._task("Cancel auto jobs",self.station.cancel_auto_missions,
                   lambda result:self.refresh_status())

    def _render_job_list(self):
        selected=self.job_list.currentItem()
        old=selected.data(0,Qt.UserRole) if selected else None
        self.job_list.clear()
        for job in self._calendar_jobs:
            if job.get("state")=="cancelled":continue
            start=job.get("run_at") or job.get("aos")
            secs=int(job.get("capture_seconds") or 0)
            end=job.get("los")
            if start and secs:
                end=datetime.fromtimestamp(datetime.fromisoformat(start).timestamp()+secs,
                                           timezone.utc).isoformat()
            item=QTreeWidgetItem([job.get("satellite","Unknown"),local_time(start),
                local_time(end),str(secs)+" s",job.get("state",""),
                job.get("mission_id") or job.get("profile","")])
            item.setData(0,Qt.UserRole,job["id"])
            self.job_list.addTopLevelItem(item)
            if job["id"]==old:self.job_list.setCurrentItem(item)

    def _render_calendar(self):
        if not hasattr(self,"timeline"):return
        day=self.cal_day.date().toString("yyyy-MM-dd")
        hours=[[] for _ in range(24)]
        for job in self._calendar_jobs:
            if job.get("state")=="cancelled":continue
            timestamp=job.get("run_at") or job.get("aos")
            try:
                start=datetime.fromisoformat(timestamp).astimezone()
                secs=int(job.get("capture_seconds") or 0)
            except (TypeError,ValueError):
                continue
            for hour in range(24):
                slot=datetime.fromisoformat(day+f"T{hour:02d}:00:00").astimezone()
                finish=slot.replace(hour=(hour+1)%24) if hour<23 else slot.replace(
                    hour=0)+timedelta(days=1)
                end=start+timedelta(seconds=secs)
                if start<finish and end>slot:
                    hours[hour].append(start.strftime("%H:%M")+"–"+end.strftime("%H:%M")+
                     " · "+job.get("satellite","Unknown")+" · "+job.get("state",""))
        for hour,entries in enumerate(hours):
            current=self.timeline.item(hour,1)
            text="\n".join(entries) if entries else "—"
            if current is None or current.text()!=text:
                self.timeline.setItem(hour,1,QTableWidgetItem(text))
            self.timeline.setRowHeight(hour,max(36,26*len(entries)))
        self.job_note.setText("Local device timeline · "+day+
            " · "+str(sum(bool(e) for e in hours))+" occupied hour(s). Cancelled jobs hidden.")

    def _job_selected(self):
        item=self.job_list.currentItem()
        if item:
            self.job_note.setText("Selected task: "+str(item.data(0,Qt.UserRole))+
             " · Only tasks created by this app can be stopped.")

    def cancel_job(self):
        item=self.job_list.currentItem()
        if not item:return
        job_id=item.data(0,Qt.UserRole)
        self._task("Cancel scheduled pass",lambda:self.station.cancel(job_id),
                   lambda result:self.refresh_status())

    def edit_auto_job(self):
        item=self.job_list.currentItem()
        if not item:return
        job=next((j for j in self._calendar_jobs if j["id"]==item.data(0,Qt.UserRole)),None)
        if not job or not job.get("mission_id") or job.get("state")!="pending":
            return QMessageBox.information(self,"Edit job",
                 "Select a pending automatic mission. Manual passes can be cancelled and rearmed.")
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox
        dialog=QDialog(self);dialog.setWindowTitle("Edit native automatic reception")
        form=QFormLayout(dialog)
        clock=QDateTimeEdit(native_datetime(job["run_at"]))
        clock.setCalendarPopup(True);clock.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        dur=QSpinBox();dur.setRange(0,900);dur.setSpecialValueText("Auto (fit pass)")
        dur.setValue(int(job.get("requested_seconds") or 0))
        options=QComboBox()
        norad=str(job.get("pass_id","")).split(":")[0]
        for mid,(num,_,_) in AUTO_DOWNLINK_PROFILES.items():
            if str(num)==norad:options.addItem(mid,mid)
        index=options.findData(job["mission_id"])
        if index>=0:options.setCurrentIndex(index)
        form.addRow("Start time · local",clock);form.addRow("Duration",dur)
        form.addRow("Published RF protocol",options)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_()!=QDialog.Accepted:return
        start=datetime.fromtimestamp(clock.dateTime().toSecsSinceEpoch(),timezone.utc).isoformat()
        self._task("Edit automatic pass",lambda:self.station.edit_auto_schedule(
            job["id"],start,options.currentData(),dur.value() or None),
            lambda result:self.refresh_status())

    def _capture_modes(self):
        key=self.capture_profile.currentData()
        self.capture_mode.blockSignals(True)
        self.capture_mode.clear()
        for mode in ("iq","iq_and_fm_wav","survey","aprs","sstv_audio","fm_audio"):
            if key and allowed_mode(key,mode):
                self.capture_mode.addItem({"iq":"Save raw CU8 IQ",
                     "iq_and_fm_wav":"Save both CU8 + derived FM WAV",
                     "survey":"RF spectrum survey",
                     "aprs":"AX.25 APRS (if actual data)","sstv_audio":"SSTV audio WAV",
                     "fm_audio":"FM voice WAV"}[mode],mode)
        self.capture_mode.blockSignals(False)
        self._capture_budget()

    def _capture_unit_changed(self):
        minute=self.capture_length_unit.currentData()=="minutes"
        current=self.capture_seconds.value()
        self.capture_seconds.blockSignals(True)
        limit=180 if self.capture_mode.currentData()=="survey" else 900
        rate=int(self.capture_sample_rate.currentData() or 1024000)
        if self.capture_mode.currentData() in ("iq","iq_and_fm_wav"):
            limit=min(900,MAX_IQ_BYTES//(2*rate+(64000 if self.capture_mode.currentData()=="iq_and_fm_wav" else 0)))
        self.capture_seconds.setRange(1,(limit+59)//60) if minute else self.capture_seconds.setRange(8,limit)
        self.capture_seconds.setValue((current+59)//60 if minute else current*60)
        self.capture_seconds.blockSignals(False)
        self._capture_budget()

    def _capture_budget(self):
        mode=self.capture_mode.currentData()
        rate=int(self.capture_sample_rate.currentData() or 1024000)
        is_iq=mode in ("iq","iq_and_fm_wav")
        maximum=(min(900,MAX_IQ_BYTES//(2*rate+(64000 if mode=="iq_and_fm_wav" else 0)))
                 if is_iq else 180 if mode=="survey" else 900)
        minute=self.capture_length_unit.currentData()=="minutes"
        max_display=(maximum+59)//60 if minute else maximum
        if self.capture_seconds.maximum()!=max_display:
            self.capture_seconds.setMaximum(max(1,max_display))
        self.capture_sample_rate.setEnabled(is_iq)
        secs=self.capture_seconds.value()*(60 if minute else 1)
        self.capture_budget.setText(
            f"~{secs*2*rate/1e6:.1f} MB raw CU8 · maximum {maximum}s at {rate/1e6:.3f} MS/s"
            if mode=="iq" else
            f"~{secs*(2*rate/1e6+.064):.1f} MB CU8 + FM WAV from same IQ recording"
            if mode=="iq_and_fm_wav" else
            "Native rtl_power surveys limited to 180 s per manual file; schedule a chain for longer."
            if mode=="survey" else
            "Native receiver saves actual packet/audio output. Long scheduled runs split into files.")

    def start_capture(self):
        key=self.capture_profile.currentData()
        mode=self.capture_mode.currentData()
        secs=self.capture_seconds.value()*(60 if self.capture_length_unit.currentData()=="minutes" else 1)
        rate=int(self.capture_sample_rate.currentData() or 1024000)
        if not key or not mode:return
        if QMessageBox.question(self,"Receive-only capture",
                 f"Acquire the real RTL-SDR for {secs} seconds at {PROFILES[key]['label']}?\n"
                 "This does NOT prove a satellite is transmitting.",
                 QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        self._task("Physical SDR capture",lambda:self.station.capture(
            key,mode,secs,sample_rate=rate),self._manual_capture_completed)

    def _manual_capture_completed(self,result):
        self.file_details.setPlainText(json.dumps(result,indent=2,default=str))
        if result.get("wav"):
            self.preview_wav=str(self.station.archive/result["wav"])
            self._register_output_files([self.station.archive/result["wav"]])
        if result.get("wav_error"):
            self.statusBar().showMessage(
                "Raw CU8 saved, but WAV conversion failed: "+result["wav_error"],14000)
        self.refresh_status()

    def stop_capture(self):
        self._task("Stop owned receiver",self.station.request_stop,
                   lambda result:self.refresh_status())

    def _render_files(self,archives):
        old=self.selected_path
        self.files.clear()
        for record in archives:
            path=self.station.archive/record["file"]
            label, explanation = describe_local_file(path)
            item=QTreeWidgetItem([record["file"],label,small_bytes(record["bytes"]),
                                  local_time(record["modified"])])
            item.setData(0,Qt.UserRole,str(path))
            item.setToolTip(0, "Actual local file; transmitter/source not authenticated")
            item.setToolTip(1, explanation)
            self.files.addTopLevelItem(item)
            if str(path)==old:self.files.setCurrentItem(item)

    def _file_selected(self):
        item=self.files.currentItem()
        if not item:return
        self._choose_path(item.data(0,Qt.UserRole))

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Open actual recording / decoded output",str(Path.home()),
           "Satellite results (*.cu8 *.wav *.png *.jpg *.txt *.json);;All files (*)")
        if path:self.imported_path=path;self._choose_path(path)

    def _choose_path(self,path):
        if path!=self.selected_path:
            self.last_analysis=None
            self.last_report_path=None
            self.decoded_paths=[]
            self.spectrum.set_report(None)
        self.selected_path=path
        p=Path(path)
        self.results_file_banner.setText(
            "Selected file: "+p.name+"  ·  Not independently attributed to a satellite")
        if not p.is_file():
            self.continue_analysis.setEnabled(False)
            self.file_details.setPlainText("File no longer exists")
            return
        media_label, media_explanation = describe_local_file(p)
        self.continue_analysis.setEnabled(True)
        self.results_file_banner.setText(
            "Selected: "+p.name+"  ·  "+media_label)
        self.browse_file_info.setText(media_explanation)
        self.file_details.setPlainText(
            str(p)+"\n"+small_bytes(p.stat().st_size)+
            "\nData type: "+media_label+"\n"+media_explanation+
            "\nSource identity unverified. No data automatically uploaded.")
        suffix=p.suffix.lower()
        self.image.clear()
        if suffix in (".png",".jpg",".jpeg") and p.stat().st_size<=15_000_000:
            pix=QPixmap(str(p))
            if not pix.isNull():
                self.image.setPixmap(pix.scaled(720,250,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        elif suffix in (".txt",".json") and p.stat().st_size <= 1048576:
            self.file_details.setPlainText(p.read_text(encoding="utf-8",errors="replace")[:12000])
        elif suffix==".wav":
            try:
                with wave.open(str(p),"rb") as w:
                    self.file_details.appendPlainText(
                        f"\nActual WAV: {w.getnchannels()} channel(s), {w.getframerate()} Hz, "
                        f"{w.getnframes()/w.getframerate():.2f} seconds")
            except (wave.Error,OSError):pass
        elif suffix==".cu8":
            marker=re.search(r"_(\d{7,11})Hz",p.name)
            if marker:self.center.setValue(int(marker.group(1))/1e6)
            rate_match=re.search(r"_(1024000|2048000)SPS",p.name)
            if rate_match:
                index=self.rate.findData(int(rate_match.group(1)))
                if index>=0:self.rate.setCurrentIndex(index)
            self.file_details.appendPlainText("\nRaw unsigned interleaved IQ; select sample rate, "
               "then Fast overview or Whole-file streaming FFT. Peak ≠ validated spacecraft.")

    def analyze_file(self):
        if not self.selected_path:
            return QMessageBox.information(self,"Analyze","Select or import an actual CU8 recording.")
        source=self.selected_path
        rate=self.rate.currentData()
        hz=int(self.center.value()*1e6)
        mode=self.analysis_mode.currentData()
        def work():
            report=analyze_cu8(source,rate,hz,mode=mode)
            path=save_spectrum_report(source,report,self.station.archive)
            return report,path
        def done(value):
            report,path=value
            self.last_analysis=report;self.last_report_path=path
            self._register_output_files([path])
            self.spectrum.set_report(report)
            summary={k:v for k,v in report.items() if k not in
                     ("frequencies_hz","relative_spectrum_db","waterfall_db")}
            self.file_details.setPlainText(json.dumps(summary,indent=2))
            self.refresh_status()
        self._task("Real CU8 "+mode+" FFT",work,done)

    def discover_signals(self):
        if not self.selected_path or Path(self.selected_path).suffix.lower()!=".cu8":
            return QMessageBox.information(self,"Signal discovery",
                "Select an actual .cu8 recording first. The native app does not fabricate RF.")
        source=self.selected_path
        rate=self.rate.currentData();hz=int(self.center.value()*1e6)
        prior=self.last_analysis
        def analyze():
            if prior and prior.get("source")==str(source):
                report=prior
            else:
                report=analyze_cu8(source,rate,hz,mode="overview")
            result=discover_channels(report)
            match_user_hints(result,load_profiles(self.station.directory))
            outfile=self.station.archive/(Path(source).stem[:85]+"_candidates.json")
            outfile.write_text(json.dumps(result,indent=2),encoding="utf-8")
            return report,result,outfile
        def completed(value):
            report,result,filepath=value
            self.last_analysis=report
            self.last_candidate_report=filepath
            self._register_output_files([filepath])
            self.spectrum.set_report(report)
            self.candidate_label.setText(
                str(len(result["candidates"]))+
                " statistically elevated channel candidate(s) · identity unverified")
            self.file_details.setPlainText(json.dumps(result,indent=2))
            self.refresh_status()
        self._task("Native RF candidate discovery",analyze,completed)

    def demodulate_fm(self):
        if not self.selected_path or Path(self.selected_path).suffix.lower()!=".cu8":
            return QMessageBox.information(self,"FM audio","Select a real CU8 recording first.")
        source=self.selected_path;rate=self.rate.currentData()
        center=int(self.center.value()*1e6)
        offset=self.audio_offset.value()*1000
        def completed(report):
            self.preview_wav=report["output_wav"]
            self.candidate_label.setText(
                "Real 32 kHz PCM WAV saved; FM audio content is UNVERIFIED.")
            self.file_details.setPlainText(json.dumps(report,indent=2))
            self._register_output_files([report["output_wav"],
                Path(report["output_wav"]).with_suffix(".json")])
            self.refresh_status()
        self._task("Extract real FM audio",lambda:fm_to_wav(
            source,self.station.archive,rate,center,offset),completed)

    def play_audio(self):
        candidate=(self.selected_path if self.selected_path and
                   Path(self.selected_path).suffix.lower()==".wav"
                   else self.preview_wav)
        if not candidate or not Path(candidate).is_file():
            return QMessageBox.information(self,"Audio","Select a real WAV or demodulate CU8 first.")
        try:
            from PyQt5.QtMultimedia import QMediaPlayer,QMediaContent
        except ImportError:
            return QMessageBox.information(self,"Native audio backend",
                "Install python3-pyqt5.qtmultimedia for in-app WAV playback.")
        if self.media_player is None:self.media_player=QMediaPlayer(self)
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(str(candidate))))
        self.media_player.play()
        self.statusBar().showMessage("Playing actual local WAV · "+Path(candidate).name,8000)

    def stop_audio(self):
        if self.media_player is not None:self.media_player.stop()

    def decode_meteor(self,variant):
        if not self.selected_path:
            return QMessageBox.information(
                self,"Meteor decoding","Choose a real CU8 recording first.")
        name=Path(self.selected_path).name
        def done(result):
            self.decoded_paths=[self.station.archive/p for p in result.get("images",[])]
            self.file_details.setPlainText(json.dumps(result,indent=2))
            if self.decoded_paths:
                image=QPixmap(str(self.decoded_paths[0]))
                if not image.isNull():
                    self.image.setPixmap(image.scaled(720,250,Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation))
            self.refresh_status()
        self._task("SatDump Meteor "+variant,
                   lambda:self.station.decode_meteor(name,variant),done)


    def _register_output_files(self,paths):
        """List only genuine saved outputs without changing current recording."""
        for raw in paths:
            path=Path(raw)
            if not path.is_file():continue
            if not any(self.output_files.topLevelItem(i).data(0,Qt.UserRole)==str(path)
                       for i in range(self.output_files.topLevelItemCount())):
                label, explanation = describe_local_file(path)
                item=QTreeWidgetItem([path.name,label,str(path.parent)])
                item.setData(0,Qt.UserRole,str(path))
                item.setToolTip(1,explanation)
                self.output_files.addTopLevelItem(item)

    def _output_file_selected(self):
        item=self.output_files.currentItem()
        if item is None:return
        path=Path(item.data(0,Qt.UserRole))
        if not path.is_file():return
        if path.suffix.lower() in (".png",".jpg",".jpeg") and path.stat().st_size<20_000_000:
            pix=QPixmap(str(path))
            if not pix.isNull():
                self.image.setPixmap(pix.scaled(
                    720,250,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        elif path.suffix.lower() in (".txt",".json",".csv") and path.stat().st_size<1_000_000:
            self.file_details.setPlainText(
                path.read_text(encoding="utf-8",errors="replace")[:12000])
        elif path.suffix.lower()==".wav":
            self.file_details.setPlainText("Actual WAV saved: "+str(path))
        # Never call _choose_path, which resets analysis/export state.

    def decode_robot36_native(self):
        """Decode an actual local PCM WAV: a PNG is emitted only after real sync."""
        source=(self.selected_path if self.selected_path and
                Path(self.selected_path).suffix.lower()==".wav" else self.preview_wav)
        if not source or not Path(source).is_file():
            return QMessageBox.information(
                self,"Robot36 SSTV","Choose a recorded WAV, or demodulate a CU8 into WAV first.")
        mode,targets=self.sstv_compute.currentData()
        def completed(report):
            self.robot36_source_wav=Path(source)
            self.decoded_paths.extend(
                self.station.archive/item["file"]
                for item in report.get("images",[])
                if (self.station.archive/item["file"]).is_file())
            # Persist processing metadata even on no-sync. Never fake an image.
            safe_stem=re.sub(r"[^A-Za-z0-9_-]+","_",Path(source).stem)[:80]
            dest=self.station.archive/(safe_stem+"_robot36_report.json")
            dest.write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
            self.robot36_report=dest
            self._register_output_files(
                [source,dest]+[self.station.archive/item["file"]
                               for item in report.get("images",[])])
            if report.get("images"):
                actual=self.station.archive/report["images"][0]["file"]
                pixmap=QPixmap(str(actual))
                if not pixmap.isNull():
                    self.image.setPixmap(pixmap.scaled(
                        720,250,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                self.candidate_label.setText(
                    "Real Robot36 sync candidate decoded · PNG saved next to source WAV. "
                    "ISS origin is not verified. Use Save decoded PNG / WAV or ZIP.")
            else:
                self.candidate_label.setText(
                    "No valid Robot36 line synchronization: no PNG was produced. "
                    "Source WAV remains available to save.")
            self.file_details.setPlainText(json.dumps(report,indent=2,default=str))
            self.refresh_status()
        self._task("Actual Robot36 WAV decoder",
                   lambda:extract_robot36_wav(
                       source,compute_mode=mode,compute_targets=targets,
                       output_dir=self.station.archive),completed)

    def export_spectrum_png(self):
        """Save a rendering of the actually analyzed RF spectrum, never an ISS image."""
        if self.last_analysis is None:
            return QMessageBox.information(
                self,"Export","Analyze a real CU8 recording first.")
        suffix=uuid.uuid4().hex[:8]
        dest=self.station.archive/("actual_rf_spectrum_"+suffix+".png")
        if not self.spectrum.grab().save(str(dest),"PNG"):
            return QMessageBox.warning(self,"Export","Unable to save measured RF plot.")
        self.extra_visual_outputs.append(dest)
        self._register_output_files([dest])
        self.statusBar().showMessage(
            "Saved uncalibrated RF spectrum (not satellite image): "+str(dest),10000)

    def export_spectrum_csv(self):
        """Export literal frequency/relative dB pairs from the actual RF analyzer."""
        report=self.last_analysis
        if report is None:
            return QMessageBox.information(
                self,"Export","Analyze a real CU8 recording first.")
        frequencies=report.get("frequencies_hz",[])
        power=report.get("relative_spectrum_db",[])
        if not frequencies or len(frequencies)!=len(power):
            return QMessageBox.warning(self,"Export","RF spectrum contains no valid bin data.")
        dest=self.station.archive/("actual_rf_spectrum_"+uuid.uuid4().hex[:8]+".csv")
        with dest.open("x",newline="",encoding="utf-8") as f:
            writer=csv.writer(f)
            writer.writerow(["frequency_hz","relative_spectrum_db_uncalibrated"])
            writer.writerows(zip(frequencies,power))
        self.extra_visual_outputs.append(dest)
        self._register_output_files([dest])
        self.statusBar().showMessage("Saved real relative RF data as CSV: "+str(dest),10000)

    def save_selected_output(self):
        """Native Save As for an actual decoded PNG, WAV, report or imported result."""
        paths=[p for p in reversed(self.decoded_paths) if p.is_file()]
        if self.robot36_source_wav and self.robot36_source_wav.is_file():
            paths.append(self.robot36_source_wav)
        if self.preview_wav and Path(self.preview_wav).is_file():
            paths.append(Path(self.preview_wav))
        if self.robot36_report and self.robot36_report.is_file():
            paths.append(self.robot36_report)
        paths += [p for p in self.extra_visual_outputs if p.is_file()]
        if self.selected_path and Path(self.selected_path).is_file() and (
                Path(self.selected_path).suffix.lower() in (".png",".jpg",".jpeg",".wav",".txt",".json")):
            paths.append(Path(self.selected_path))
        if not paths:
            return QMessageBox.information(
                self,"Save result","No real decoded image, WAV or result file exists.")
        from PyQt5.QtWidgets import QInputDialog
        labels=[p.name+" — "+str(p.parent) for p in paths]
        label,ok=QInputDialog.getItem(self,"Select actual result to save",
                                      "Generated / imported file",labels,0,False)
        if not ok:return
        source=paths[labels.index(label)]
        dest,_=QFileDialog.getSaveFileName(
            self,"Save actual "+source.suffix.upper().lstrip(".")+" output",
            str(Path.home()/source.name),
            "Same file type (*"+source.suffix+")")
        if not dest:return
        target=Path(dest).expanduser()
        if target.suffix.lower()!=source.suffix.lower():
            return QMessageBox.warning(
                self,"Save result","Keep the original result format "+source.suffix+".")
        if target.resolve()==source.resolve():
            self.statusBar().showMessage("Original result is already saved: "+str(source),10000)
            return
        if target.exists():
            return QMessageBox.warning(
                self,"Save result","Destination already exists; refusing to overwrite.")
        self._task("Save decoded output",
                   lambda:shutil.copy2(source,target),
                   lambda path:self.statusBar().showMessage(
                       "Actual result copied to "+str(path),12000))

    def save_results_zip(self):
        sources=[]
        if self.last_report_path and self.last_report_path.is_file():sources.append(self.last_report_path)
        if self.last_candidate_report and self.last_candidate_report.is_file():
            sources.append(self.last_candidate_report)
        if self.preview_wav and Path(self.preview_wav).is_file():
            sources.append(Path(self.preview_wav))
        sources += [p for p in self.decoded_paths if p.is_file()]
        if self.robot36_report and self.robot36_report.is_file():
            sources.append(self.robot36_report)
        sources += [p for p in self.extra_visual_outputs if p.is_file()]
        if self.robot36_source_wav and self.robot36_source_wav.is_file():
            sources.append(self.robot36_source_wav)
        if self.selected_path and Path(self.selected_path).suffix.lower() in (
            ".png",".jpg",".jpeg",".wav",".txt",".json"):
            sources.append(Path(self.selected_path))
        if not sources:
            return QMessageBox.information(self,"Save ZIP",
                "Analyze a real CU8 file or select a decoded PNG/WAV/text output first. "
                "Raw .cu8 is intentionally stored separately.")
        dest,_=QFileDialog.getSaveFileName(self,"Save actual decoded evidence ZIP",
                   str(Path.home()/"TIHULU_satellite_results.zip"),"ZIP archive (*.zip)")
        if not dest:return
        self._task("Package real results",lambda:export_results_zip(
            sources,dest,source=self.selected_path),
            lambda path:self.statusBar().showMessage("ZIP saved locally: "+str(path),15000))

    def open_archive_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.station.archive)))

    def closeEvent(self,event):
        if self.station.session.get("active") or any(
            j.get("state")=="pending" for j in self._calendar_jobs):
            reply=QMessageBox.question(self,"Exit native receiver",
                "Closing Satellite Center stops only its owned RF capture and scheduler. "
                "Pending jobs remain on disk but will not run until the app opens again. Quit?",
                QMessageBox.Yes|QMessageBox.No)
            if reply!=QMessageBox.Yes:
                event.ignore();return
        self.active=False
        self.timer.stop()
        self.map_timer.stop()
        self.level_timer.stop()
        self.stop_audio()
        self.station.close()
        event.accept()


def main(argv=None):
    args=list(argv) if argv is not None else sys.argv[1:]
    smoke="--smoke" in args
    if smoke:args.remove("--smoke")
    app=QApplication([sys.argv[0]]+args)
    app.setApplicationName("TIHULU Satellite Center")
    app.setOrganizationName("TIHULU")
    app.setWindowIcon(QIcon(str(Path(__file__).parent/"assets"/"tihulu-satellite.png")))
    if hasattr(app,"setDesktopFileName"):
        app.setDesktopFileName("tihulu-satellite-center")
    if smoke:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix="tihulu-native-smoke-") as td:
            station=Station(Path(td))
            window=SatelliteWindow(station,auto_poll=False)
            assert window.tabs.count()==10, "Native pages not built"
            assert window.tabs.tabBar().isHidden(), "Expose guided primary navigation"
            assert len(window.nav_buttons)==6
            assert "Hardware" in window.nav_buttons
            assert window._open_native_tab("Hardware")
            assert window.tabs.tabText(window.tabs.currentIndex())=="Hardware"
            assert window.hardware_connect_button.text()=="Connect && enable RF"
            assert len(window.home_level_chart.levels)==0
            assert len(window.capture_level_chart.levels)==0
            assert window.hardware_disconnect_button.text()=="Stop && disconnect RF"
            window._open_native_tab("Overview")
            assert window.nav_buttons["Overview"].isChecked()
            assert window.result_steps.count()==3
            assert window.result_steps.tabText(0).startswith("1 ")
            assert window.result_steps.tabText(2).startswith("3 ")
            window._home_analyze()
            assert window.tabs.tabText(window.tabs.currentIndex())=="Recordings & results"
            assert window.result_steps.currentIndex()==0
            window._home_extract()
            assert window.result_steps.currentIndex()==2
            window._open_native_tab("Overview")
            assert window.protocol_list.topLevelItemCount()==0
            assert window.tabs.tabText(9)=="Saved protocols"
            assert window._open_native_tab("Satellite Images & Data")
            assert window.online_provider.count()==2
            assert window.native_image_files.topLevelItemCount()==0
            window._open_native_tab("Overview")
            assert window.map_sky.mode=="sky"
            assert window.map_earth.mode=="earth"
            assert window.map_views.currentIndex()==1, "Default map should be Earth"
            assert window.map_extra.isHidden(), "Beginner map overlays must be collapsed"
            assert not window.map_osm.isChecked()
            assert window.map_earth._land, "Offline Natural Earth is required"
            assert window.map_media.findData("Image")>=0
            assert window.map_media.findData("Text")>=0
            assert window.map_track_scope.findData("all")>=0
            assert window.map_track_scope.findData("none")>=0
            assert callable(window.map_earth.fit_satellites)
            assert callable(window._map_export_geojson)
            assert window.home_auto.text().startswith("2 ")
            assert window.home_analyze.text().startswith("3 ")
            assert window.home_extract.text()=="View decoded results"
            assert window.files.headerItem().text(1)=="Data type · format"
            assert window.output_files.headerItem().text(1)=="Data type · format"
            assert not window.auto_settings.isVisible()
            assert not window.pass_settings.isVisible()
            assert window.auto_compute.count()==5
            assert window.auto_compute.currentData()[0]=="auto"
            # The pass planner allows 1–7200 s via native chained captures.
            # The individual IQ disk file still has its own 2 GB bound.
            assert window.pass_seconds.maximum()==7200
            assert window.pass_sample_rate.count()==2
            assert window.capture_sample_rate.count()==2
            assert window.home_capture_rate.count()==2
            assert window.home_iss_format.count()==3
            window.capture_profile.setCurrentIndex(
                window.capture_profile.findData("meteor"))
            window.capture_mode.setCurrentIndex(window.capture_mode.findData("iq"))
            window.capture_sample_rate.setCurrentIndex(
                window.capture_sample_rate.findData(2048000))
            assert window.capture_seconds.maximum()==488
            window.capture_sample_rate.setCurrentIndex(0)
            assert window.capture_seconds.maximum()==900
            assert len(window._offline_cities)==8084
            # Same station state in Home and full planner: offline DE/TR
            # country > real region > local city, then manual coordinates.
            assert window.home_country.count()==3
            assert window.home_station.findData("custom")>=0
            assert window.home_station.findData("online")>=0
            assert window.home_pass_sort.count()==7
            assert window.home_pass_family.findData("meteor")>=0
            assert window.home_pass_media.findData("Image")>=0
            window.home_country.setCurrentIndex(window.home_country.findData("DE"))
            region_index=window.home_region.findData("North Rhine-Westphalia")
            assert region_index>=0, "Offline German Bundesland missing"
            window.home_region.setCurrentIndex(region_index)
            assert window.city_country.currentData()=="DE"
            assert window.city_region.currentData()=="North Rhine-Westphalia"
            window.home_city_search.setText("huerth")
            assert window.home_city_results.count()>0, "Home offline place search failed"
            assert "Hürth" in window.home_city_results.item(0).text()
            window._home_apply_city_item(window.home_city_results.item(0))
            assert abs(window.lat.value()-50.87079)<0.0001
            assert abs(window.home_lat.value()-window.lat.value())<0.00001
            window.home_lon.setValue(7.12345)
            assert abs(window.lon.value()-7.12345)<0.00001
            window.lat.setValue(49.12345)
            assert abs(window.home_lat.value()-49.12345)<0.00001
            window.home_hours.setValue(48)
            window.home_elev.setValue(25)
            assert window._station_kwargs()["hours"]==48
            assert window._station_kwargs()["elevation"]==25
            assert window.city_region.findData("North Rhine-Westphalia")>=0
            # Native city search and station selection without geocoding.
            window.city_search.setText("huerth")
            window._search_offline_city("huerth")
            matches=list(window._current_city_suggestions)
            assert any("Hürth" in label for label in matches)
            window._choose_offline_city(next(label for label in matches if "Hürth" in label))
            assert abs(window.lat.value()-50.87079)<0.0001
            # Render a clearly synthetic orbital pass in real Qt widgets.
            aos=datetime.now(timezone.utc)+timedelta(minutes=15)
            window._apply_passes({"predictions":[{
                "id":"59051:synthetic","norad":59051,"name":"METEOR test only",
                "family":"meteor","aos":aos.isoformat(),
                "los":(aos+timedelta(minutes=9)).isoformat(),
                "max_elevation_deg":44.0,"profiles":["meteor"]}]})
            assert window.pass_list.topLevelItemCount()==1
            assert window.home_pass_results.topLevelItemCount()==1
            assert "METEOR" in window.home_pass_results.topLevelItem(0).text(0).upper()
            window.home_pass_sort.setCurrentIndex(window.home_pass_sort.findData("high"))
            assert window.home_pass_results.topLevelItemCount()==1
            window.home_pass_media.setCurrentIndex(window.home_pass_media.findData("Text"))
            assert window.home_pass_results.topLevelItemCount()==0
            window.home_pass_media.setCurrentIndex(window.home_pass_media.findData("Image"))
            assert window.home_pass_results.topLevelItemCount()==1
            window._home_open_selected_pass()
            assert window.tabs.tabText(window.tabs.currentIndex())=="Passes & Data"
            assert window.pass_list.currentItem().data(0,Qt.UserRole)=="59051:synthetic"
            assert not window.pass_settings.isHidden(), "Home pass must open editable schedule"
            window._open_native_tab("Overview")
            assert window.pass_sort.count()==7
            assert window.pass_family_filter.findData("meteor")>=0
            assert window.tle_source.findData("amateur")>=0
            assert window.pass_map_button.isEnabled()
            assert "image" in window.pass_overview.text().lower()
            assert "LRPT" in window.pass_requirements.text()
            window.pass_media_filter.setCurrentIndex(
                window.pass_media_filter.findData("Text"))
            assert window.pass_list.topLevelItemCount()==0
            window.pass_media_filter.setCurrentIndex(
                window.pass_media_filter.findData("Image"))
            assert window.pass_list.topLevelItemCount()==1
            # Draw both maps with synthetic orbital points, no USB/network.
            map_test={"observer":{"lat":50.87079,"lon":6.86761},
              "satellites":[{
                "name":"SYNTHETIC MAP TEST","norad":59051,"family":"meteor",
                "lat":40.2,"lon":13.1,"alt_km":810.,"az":102.,
                "el":36.,"range_km":1320.,"tle_age_days":0.,
                "status":"ORBITAL_POSITION_ONLY"}],
              "track_segments":[[
                {"lat":39.,"lon":12.},{"lat":40.2,"lon":13.1},
                {"lat":41.,"lon":14.}]],
              "total_loaded":1,"warnings":[]}
            window.map_sky.set_snapshot(map_test)
            window.map_earth.set_snapshot(map_test)
            window.map_sky.set_selected(59051)
            window.map_earth.set_selected(59051)
            # Real native map controls: search, media, zoom fit and exports.
            window.map_search.setText("SYNTHETIC")
            window._apply_map_snapshot(map_test,True)
            assert window.map_satellites.topLevelItemCount()==1
            window.map_media.setCurrentIndex(window.map_media.findData("Text"))
            window._apply_map_snapshot(map_test,False)
            assert window.map_satellites.topLevelItemCount()==0
            window.map_media.setCurrentIndex(window.map_media.findData("Image"))
            window._apply_map_snapshot(map_test,True)
            assert window.map_satellites.topLevelItemCount()==1
            assert window.map_earth.fit_satellites()
            assert 2<=window.map_earth.zoom<=5, "Satellite fit must remain a readable regional view"
            export_test=Path(td)/"orbit-test.geojson"
            export_orbit_geojson(window.map_last_snapshot,export_test)
            content=json.loads(export_test.read_text(encoding="utf-8"))
            assert content["type"]=="FeatureCollection"
            assert content["properties"]["has_rf_evidence"] is False
            assert any(f["properties"].get("status")=="ORBITAL_POSITION_ONLY"
                       for f in content["features"])
            window.show()
            app.processEvents()
            window._open_native_tab("Overview")
            app.processEvents()
            assert window.home_scroll.horizontalScrollBar().maximum()==0, (
                "Home must fit inside 1320 px without global horizontal scrolling")
            # Optional CI screenshots use synthetic orbital positions, never RF
            # or a fabricated received picture. They are visual QA artifacts.
            snapshot_dir=os.environ.get("TIHULU_UI_SNAPSHOT_DIR")
            if snapshot_dir:
                root=Path(snapshot_dir)
                root.mkdir(parents=True,exist_ok=True)
                for name,filename in (
                    ("Overview","01-home.png"),
                    ("Hardware","06-hardware.png"),
                    ("Satellite Images & Data","07-satellite-images.png"),
                    ("Passes & Data","02-find-satellites.png"),
                    ("Maps & Live","03-earth-map.png"),
                    ("Auto reception","04-auto-receive.png"),
                    ("Recordings & results","05-recordings.png"),
                ):
                    assert window._open_native_tab(name)
                    if name=="Recordings & results":
                        window.result_steps.setCurrentIndex(0)
                    window.statusBar().showMessage(
                        "UI PREVIEW ONLY · synthetic orbital example; NO physical RF acquisition")
                    app.processEvents()
                    assert window.grab().save(str(root/filename),"PNG"),filename
                window._open_native_tab("Overview")
                app.processEvents()
            assert not window.map_sky.grab().isNull()
            assert not window.map_earth.grab().isNull()
            QTimer.singleShot(100,app.quit)
            result=app.exec_()
            window.active=False
            station.close()
            return result
    window=SatelliteWindow()
    window.show()
    return app.exec_()


if __name__=="__main__":
    raise SystemExit(main())
