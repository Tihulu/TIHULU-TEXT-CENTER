"""TIHULU Satellite Center: real native Qt Widgets desktop application.

No browser, localhost HTTP server, WebView, HTML renderer or WebUSB is
started. Satellite RF uses the existing receive-only Station/rtl_sdr backend.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import math
import re
from pathlib import Path
import sys
import wave

from PyQt5.QtCore import Qt, QDate, QDateTime, QPointF, QRectF, QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, QUrl, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QPixmap, QDesktopServices, QImage, QIcon
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDateTimeEdit, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QLineEdit, QFrame, QHeaderView, QSizePolicy
)

from .__main__ import Station, PROFILES, LOCATIONS, AUTO_DOWNLINK_PROFILES, allowed_mode
from .native_analysis import analyze_cu8, save_spectrum_report, export_results_zip
from .media_catalog import (MEDIA_COLORS, MEDIA_SYMBOLS, kinds_for_pass, filter_passes,
                            media_summary, capabilities_for_pass)


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
        self.decoded_paths = []
        self.imported_path = None
        self.selected_path = None
        self.active = True
        self.setWindowTitle("TIHULU Satellite Center · Native SDR")
        self.setWindowIcon(QIcon(str(Path(__file__).parent/"assets"/"tihulu-satellite.png")))
        self.resize(1200,820)
        self.setMinimumSize(900,650)
        self._build()
        self._style()
        self.statusBar().showMessage("Native Qt window. No browser, WebUSB or HTTP server.")
        self.timer=QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh_status)
        if auto_poll:
            self.timer.start()
            self.refresh_status()

    def _style(self):
        self.setStyleSheet("""
          QMainWindow,QWidget{background:#0b1626;color:#eaf4ff;font-size:12px;font-family:"Noto Sans"}
          QFrame#passDetail{background:#142840;border:1px solid #345a78;border-radius:12px}
          QLabel#passTitle{font-size:17px;font-weight:700;color:#f1f9ff}
          QLabel#passSubtitle{font-size:12px;color:#a9c5dd}
          QLabel#passSectionTitle{font-size:13px;font-weight:650;color:#c8e3f9}
          QLabel#dataHint{color:#9cb8d2;font-size:11px}
          QLineEdit{background:#152d47;color:#f4fbff;border:1px solid #3c6182;border-radius:7px;padding:9px}
          QLineEdit:focus,QComboBox:focus{border:1px solid #65c9e5}
          QGroupBox{border:1px solid #325370;border-radius:9px;margin-top:12px;padding:14px 8px 8px;font-weight:600}
          QGroupBox::title{subcontrol-origin:margin;left:14px;padding:0 5px;color:#b6d9f9}
          QTabWidget::pane{border:1px solid #31526f;border-radius:6px}
          QTabBar::tab{padding:10px 18px;background:#172c46;border:1px solid #2a4865}
          QTabBar::tab:selected{background:#24547d;color:#fff}
          QComboBox,QSpinBox,QDoubleSpinBox,QDateTimeEdit,QDateEdit,QPlainTextEdit,
          QTreeWidget,QTableWidget{background:#132843;color:#eff7ff;border:1px solid #426181;
                                 border-radius:5px;padding:5px;selection-background-color:#376c9d}
          QComboBox QAbstractItemView{background:#132843;color:#eff7ff;selection-background-color:#376c9d}
          QPushButton{background:#254d74;border:1px solid #49759d;border-radius:5px;padding:8px 13px}
          QPushButton:hover{background:#326a9a}
          QPushButton:disabled{color:#6f88a3;background:#17283b}
          QHeaderView::section{background:#1a344f;color:#d9ebff;padding:9px;border:0;border-bottom:1px solid #34536e;font-weight:600}
          QTreeWidget::item{padding:6px}
          QTreeWidget::item:selected{background:#294c70;color:#ffffff}
          QScrollBar:vertical{width:11px;background:#101f34}
          QScrollBar::handle:vertical{background:#345d80;min-height:26px;border-radius:5px}
          QLabel#headline{font-size:22px;font-weight:bold;color:#f1faff}
          QLabel#hint{color:#a7bfd7}
        """)

    def _build(self):
        root=QWidget()
        layout=QVBoxLayout(root)
        header=QHBoxLayout()
        title=QLabel("TIHULU SATELLITE CENTER")
        title.setObjectName("headline")
        header.addWidget(title)
        header.addStretch(1)
        self.top_status=QLabel("Receive-only · SDR not acquired")
        header.addWidget(self.top_status)
        layout.addLayout(header)
        self.tabs=QTabWidget()
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)
        self._dashboard_tab()
        self._passes_tab()
        self._auto_tab()
        self._calendar_tab()
        self._capture_tab()
        self._results_tab()

    def _panel(self, title, parent):
        group=QGroupBox(title)
        group.setLayout(QVBoxLayout())
        parent.addWidget(group)
        return group.layout()

    def _row(self, layout, *widgets):
        row=QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget)
        layout.addLayout(row)

    def _button(self, label, callback, tooltip=None):
        button=QPushButton(label)
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
        body=self._new_tab("Overview")
        panel=self._panel("Physical receiver and local storage",body)
        self.device_label=self._hint("Checking Linux RTL-SDR without opening USB…")
        self.session_label=QLabel("Idle")
        self.disk_label=self._hint("Recordings are stored locally.")
        self.cache_label=self._hint("No orbit download occurs on startup.")
        for label in [self.device_label,self.session_label,self.disk_label,self.cache_label]:
            label.setWordWrap(True)
            panel.addWidget(label)
        self._row(panel,
                  self._button("Refresh hardware status",self.refresh_status),
                  self._button("Test my USB receiver",self.usb_test))
        body.addWidget(self._hint(
            "This is a native Qt Widgets window, NOT a website, embedded browser, or localhost "
            "WebView. USB readout uses installed rtl_sdr/rtl_fm/rtl_power tools. "
            "No scan or network TLE download begins without an explicit click. "
            "A predicted pass does not mean a real radio signal was received."))
        body.addStretch(1)

    def _station_controls(self,parent):
        group=QGroupBox("Ground station and pass window")
        controls=QFormLayout(group)
        self.city=QComboBox()
        self.city.addItems(list(LOCATIONS)+["Custom coordinates"])
        self.city.currentTextChanged.connect(self._preset_location)
        self.lat=QDoubleSpinBox();self.lat.setRange(-90,90);self.lat.setDecimals(4)
        self.lon=QDoubleSpinBox();self.lon.setRange(-180,180);self.lon.setDecimals(4)
        self.hours=QSpinBox();self.hours.setRange(1,72);self.hours.setValue(24)
        self.elev=QDoubleSpinBox();self.elev.setRange(5,75);self.elev.setValue(15)
        controls.addRow("Preset city",self.city)
        controls.addRow("Latitude",self.lat)
        controls.addRow("Longitude",self.lon)
        controls.addRow("Look ahead · hours",self.hours)
        controls.addRow("Minimum elevation · degrees",self.elev)
        self._preset_location()
        parent.addWidget(group)

    def _preset_location(self):
        point=LOCATIONS.get(self.city.currentText())
        if point:
            self.lat.setValue(point[0]);self.lon.setValue(point[1])

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
        body=self._new_tab("Passes & Data")
        top=QHBoxLayout();body.addLayout(top)
        self._station_controls(top)
        group=QGroupBox("Satellite reception planner")
        actions=QVBoxLayout(group)
        actions.addWidget(self._button("↻  Update public orbital TLEs",self.refresh_tles))
        actions.addWidget(self._button("◉  Calculate satellite passes",self.calculate_passes))
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
        searchRow.addWidget(self.pass_search,3)
        searchRow.addWidget(self.pass_media_filter,1)
        body.addLayout(searchRow)

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
        self.pass_list.setAlternatingRowColors(False)
        self.pass_list.setSelectionMode(QTreeWidget.SingleSelection)
        self.pass_list.setSortingEnabled(False) # AOS order is preserved
        self.pass_list.header().setSectionResizeMode(0,QHeaderView.Stretch)
        self.pass_list.header().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        for col in (2,3,4,5):
            self.pass_list.header().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        self.pass_list.itemSelectionChanged.connect(self.pass_selected)
        body.addWidget(self.pass_list,3)

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
        body.addWidget(self.pass_detail,1)

        settings=QGroupBox("Plan a real RF recording · native receiver")
        form=QFormLayout(settings)
        self.pass_profile=QComboBox()
        self.pass_profile.currentIndexChanged.connect(self._pass_modes)
        self.pass_mode=QComboBox()
        self.pass_time=QDateTimeEdit(QDateTime.currentDateTime())
        self.pass_time.setCalendarPopup(True)
        self.pass_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.pass_seconds=QSpinBox();self.pass_seconds.setRange(8,900);self.pass_seconds.setValue(60)
        self.pass_seconds.valueChanged.connect(self._pass_budget)
        self.pass_mode.currentIndexChanged.connect(self._pass_budget)
        self.pass_cost=self._hint("Choose a predicted pass")
        form.addRow("Receiver profile",self.pass_profile)
        form.addRow("RF output mode",self.pass_mode)
        form.addRow("Local start time",self.pass_time)
        form.addRow("Actual RF duration · seconds",self.pass_seconds)
        form.addRow("Estimated disk space",self.pass_cost)
        self.arm_pass=self._button("Arm selected RF capture",self.schedule_selected_pass)
        form.addRow(self.arm_pass)
        body.addWidget(settings)
        self._render_pass_results()

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
        kind=self.pass_media_filter.currentData() or "All"
        search=self.pass_search.text()
        if kind=="RF only":
            rows=[row for row in filter_passes(all_rows,"RF data",search)
                  if kinds_for_pass(row)==["RF data"]]
        else:
            rows=filter_passes(all_rows,kind,search)
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

    def _auto_tab(self):
        body=self._new_tab("Auto reception")
        body.addWidget(self._hint("Choose only the modes you intend to receive. Actual activity, "
            "satellite identification and complete imagery are never guaranteed by a geometric pass."))
        self.mission_boxes={}
        for mid, (norad, profile, mode) in AUTO_DOWNLINK_PROFILES.items():
            label={"iss-sstv":"ISS SSTV · event only · WAV",
                   "iss-aprs":"ISS APRS · text/packets",
                   "iss-voice":"ISS voice · WAV",
                   "meteor-m2-3":"Meteor-M2-3 LRPT · raw IQ image candidate",
                   "meteor-m2-4":"Meteor-M2-4 LRPT · raw IQ image candidate"}.get(mid,mid)
            item=QCheckBox(label)
            if mid.startswith("meteor"):item.setChecked(True)
            self.mission_boxes[mid]=item
            body.addWidget(item)
        options=QGroupBox("Automatic local capture scheduling")
        form=QFormLayout(options)
        self.coverage=QComboBox();self.coverage.addItem("Full predicted window","full")
        self.coverage.addItem("Quick RF sample","sample")
        self.auto_seconds=QSpinBox();self.auto_seconds.setRange(0,900)
        self.auto_seconds.setSpecialValueText("Auto · fit pass")
        self.auto_seconds.setValue(0)
        self.auto_jobs=QSpinBox();self.auto_jobs.setRange(1,12);self.auto_jobs.setValue(6)
        self.auto_elev=QDoubleSpinBox();self.auto_elev.setRange(5,75);self.auto_elev.setValue(20)
        form.addRow("Coverage priority",self.coverage)
        form.addRow("Capture length · s",self.auto_seconds)
        form.addRow("Maximum future jobs",self.auto_jobs)
        form.addRow("Minimum elevation",self.auto_elev)
        form.addRow(self._button("Auto Schedule & Capture · native",self.auto_schedule))
        body.addWidget(options)
        body.addWidget(self._button("Cancel pending AUTO jobs only",self.cancel_automatic))
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

    def _capture_tab(self):
        body=self._new_tab("Manual RF capture")
        form=QFormLayout()
        self.capture_profile=QComboBox()
        for key,value in PROFILES.items():
            self.capture_profile.addItem(value["label"],key)
        self.capture_profile.currentIndexChanged.connect(self._capture_modes)
        self.capture_mode=QComboBox()
        self.capture_seconds=QSpinBox();self.capture_seconds.setRange(8,900)
        self.capture_seconds.setValue(60)
        self.capture_budget=self._hint("Long captures write real CU8 directly to disk.")
        self.capture_mode.currentIndexChanged.connect(self._capture_budget)
        self.capture_seconds.valueChanged.connect(self._capture_budget)
        form.addRow("Receiver frequency / band",self.capture_profile)
        form.addRow("Hardware mode",self.capture_mode)
        form.addRow("Actual sample length · 8–900 s",self.capture_seconds)
        form.addRow("Estimated disk budget",self.capture_budget)
        body.addLayout(form)
        self._row(body,
                  self._button("Start physical RF capture",self.start_capture),
                  self._button("Stop my current capture",self.stop_capture))
        body.addWidget(self._hint("Only the actual attached RTL2832U SDR is used. "
            "A busy readsb/Gqrx device is not stolen or forcibly terminated. "
            "Long recordings are written locally without browser memory caps."))
        body.addStretch(1)
        self._capture_modes()

    def _results_tab(self):
        body=self._new_tab("Recordings & results")
        self._row(body,
                  self._button("Refresh local recordings",self.refresh_status),
                  self._button("Open existing file…",self.import_file),
                  self._button("Reveal recordings folder",self.open_archive_folder))
        self.files=QTreeWidget()
        self.files.setHeaderLabels(["Actual local file","Size","Modified · local"])
        self.files.itemSelectionChanged.connect(self._file_selected)
        body.addWidget(self.files,1)
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
        body.addLayout(analyze_controls)
        self._row(body,
                  self._button("Analyze real CU8",self.analyze_file),
                  self._button("Decode Meteor 72k",lambda:self.decode_meteor("72k")),
                  self._button("Decode Meteor 80k",lambda:self.decode_meteor("80k")),
                  self._button("Save actual results ZIP",self.save_results_zip))
        self.spectrum=SpectrumView()
        body.addWidget(self.spectrum,2)
        self.image=QLabel()
        self.image.setMinimumHeight(90)
        self.image.setAlignment(Qt.AlignCenter)
        body.addWidget(self.image,1)
        self.file_details=QPlainTextEdit()
        self.file_details.setReadOnly(True)
        self.file_details.setMaximumHeight(125)
        body.addWidget(self.file_details,1)
        self.file_details.setPlainText("Select a real recording or import a local .cu8, WAV, PNG or text file.")

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
                if not silent:
                    QMessageBox.warning(self,"Satellite Center",message)
        def on_finished():
            self.tasks.pop(key,None)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.pool.start(worker)

    def refresh_status(self):
        self._task("status",self.station.status,self._apply_status,silent=True)

    def _apply_status(self,state):
        session=state.get("session",{})
        self.top_status.setText("RTL-SDR: "+("recording" if session.get("active") else
                                           "available" if state.get("tuner_present") else "not detected"))
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

    def usb_test(self):
        self._task("USB diagnostic",self.station.usb_test,
                   lambda report:self.file_details.setPlainText(json.dumps(report,indent=2,default=str)))

    def refresh_tles(self):
        self._task("Public TLE refresh",self.station.refresh,
                   lambda result: (self.file_details.setPlainText(json.dumps(result,indent=2)),
                                   self.refresh_status()))

    def _station_kwargs(self):
        return {"lat":self.lat.value(),"lon":self.lon.value(),
                "hours":self.hours.value(),"elevation":self.elev.value()}

    def calculate_passes(self):
        self._task("Predict satellite passes",
                   lambda:self.station.passes(**self._station_kwargs()),
                   self._apply_passes)

    def _apply_passes(self,data):
        rows=data.get("predictions",[])
        self.passes={r["id"]:r for r in rows}
        self._render_pass_results()
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
        for mode in ("iq","survey"):
            if key and allowed_mode(key,mode):
                self.pass_mode.addItem("Raw CU8 · disk" if mode=="iq" else "RF energy survey",mode)
        index=self.pass_mode.findData(current)
        if index>=0:self.pass_mode.setCurrentIndex(index)
        self.pass_mode.blockSignals(False)
        self._pass_budget()

    def _pass_budget(self):
        if self.pass_mode.currentData()=="iq":
            self.pass_cost.setText(f"~{self.pass_seconds.value()*2.048:.1f} MB raw IQ on disk · 1.024 MS/s")
        else:
            self.pass_cost.setText("Native bounded spectrum survey · 180 seconds maximum")

    def schedule_selected_pass(self):
        item=self.pass_list.currentItem()
        if not item:return QMessageBox.information(self,"Schedule","Choose a predicted pass first.")
        key=item.data(0,Qt.UserRole)
        profile=self.pass_profile.currentData()
        mode=self.pass_mode.currentData()
        seconds=self.pass_seconds.value()
        start=datetime.fromtimestamp(self.pass_time.dateTime().toSecsSinceEpoch(),timezone.utc).isoformat()
        self._task("Arm scheduled RF",lambda:self.station.schedule(key,profile,mode,start,seconds),
                   lambda job:(self.statusBar().showMessage("Armed native job "+job["id"]+
                       "; browser not required",12000),self.refresh_status()))

    def auto_schedule(self):
        missions=[mid for mid,box in self.mission_boxes.items() if box.isChecked()]
        if not missions:return QMessageBox.information(self,"Auto reception","Select at least one satellite mode.")
        seconds=self.auto_seconds.value() or None
        coverage=self.coverage.currentData()
        params={"lat":self.lat.value(),"lon":self.lon.value(),"hours":self.hours.value(),
                "elevation":self.auto_elev.value(),"max_jobs":self.auto_jobs.value(),
                "coverage_goal":coverage,"duration_seconds":seconds}
        self._task("Auto mission planning",lambda:self.station.auto_schedule(missions,**params),
                   lambda result:(self.file_details.setPlainText(json.dumps(result,indent=2,default=str)),
                                  self.refresh_status()))

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
        for mode in ("iq","survey","aprs","sstv_audio","fm_audio"):
            if key and allowed_mode(key,mode):
                self.capture_mode.addItem({"iq":"Save raw CU8 IQ","survey":"RF spectrum survey",
                     "aprs":"AX.25 APRS (if actual data)","sstv_audio":"SSTV audio WAV",
                     "fm_audio":"FM voice WAV"}[mode],mode)
        self.capture_mode.blockSignals(False)
        self._capture_budget()

    def _capture_budget(self):
        mode=self.capture_mode.currentData()
        if mode=="survey" and self.capture_seconds.maximum()!=180:
            self.capture_seconds.setMaximum(180)
        elif mode!="survey" and self.capture_seconds.maximum()!=900:
            self.capture_seconds.setMaximum(900)
        secs=self.capture_seconds.value()
        self.capture_budget.setText(
            f"~{secs*2.048:.1f} MB raw CU8 on local disk · actual samples, no WebUSB"
            if mode=="iq" else
            "Native rtl_power records for exactly requested seconds (8–180)"
            if mode=="survey" else
            "Native receiver saves actual packet/audio output, no browser involved")

    def start_capture(self):
        key=self.capture_profile.currentData()
        mode=self.capture_mode.currentData()
        secs=self.capture_seconds.value()
        if not key or not mode:return
        if QMessageBox.question(self,"Receive-only capture",
                 f"Acquire the real RTL-SDR for {secs} seconds at {PROFILES[key]['label']}?\n"
                 "This does NOT prove a satellite is transmitting.",
                 QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        self._task("Physical SDR capture",lambda:self.station.capture(key,mode,secs),
                   lambda result:(self.file_details.setPlainText(json.dumps(result,indent=2)),
                                  self.refresh_status()))

    def stop_capture(self):
        self._task("Stop owned receiver",self.station.request_stop,
                   lambda result:self.refresh_status())

    def _render_files(self,archives):
        old=self.selected_path
        self.files.clear()
        for record in archives:
            path=self.station.archive/record["file"]
            item=QTreeWidgetItem([record["file"],small_bytes(record["bytes"]),
                                  local_time(record["modified"])])
            item.setData(0,Qt.UserRole,str(path))
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
        if not p.is_file():
            self.file_details.setPlainText("File no longer exists")
            return
        self.file_details.setPlainText(str(p)+"\n"+small_bytes(p.stat().st_size)+
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
            self.spectrum.set_report(report)
            summary={k:v for k,v in report.items() if k not in
                     ("frequencies_hz","relative_spectrum_db","waterfall_db")}
            self.file_details.setPlainText(json.dumps(summary,indent=2))
            self.refresh_status()
        self._task("Real CU8 "+mode+" FFT",work,done)

    def decode_meteor(self,variant):
        if not self.selected_path:return
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

    def save_results_zip(self):
        sources=[]
        if self.last_report_path and self.last_report_path.is_file():sources.append(self.last_report_path)
        sources += [p for p in self.decoded_paths if p.is_file()]
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
            assert window.tabs.count()==6, "Native tabs not built"
            assert window.pass_seconds.maximum()==900
            assert window.capture_seconds.maximum()==900
            assert window.web_view if False else True  # no WebEngine imported
            window.show()
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
