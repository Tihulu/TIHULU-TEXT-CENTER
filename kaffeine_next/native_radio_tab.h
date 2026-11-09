/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Embedded TIHULU Radio (DAB+) tab for pinned KDE Kaffeine v2.0.19.
 * Uses native Kaffeine/libVLC for station playback; welle-cli owns DAB
 * demodulation in its own optional, LOOPBACK-ONLY local subprocess.
 * No WebUSB, no cloud SDR service, no receiver use until explicit Start.
 */
#ifndef TIHULU_NATIVE_RADIO_TAB_H
#define TIHULU_NATIVE_RADIO_TAB_H

#include "tabbase.h"
#include "mediawidget.h"

#include <QCheckBox>
#include <QComboBox>
#include <QCompleter>
#include <QDateTime>
#include <QDial>
#include <QDoubleSpinBox>
#include <QDialog>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QNetworkRequest>
#include <QVector>
#include <QFile>
#include <QFileDialog>
#include <QFormLayout>
#include <QGridLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHostAddress>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLocale>
#include <QLineEdit>
#include <QListWidget>
#include <QSet>
#include <QHash>
#include <QSignalBlocker>
#include <QHeaderView>
#include <QMap>
#include <QMessageBox>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QPainter>
#include <QPen>
#include <QPixmap>
#include <QProgressBar>
#include <QPointer>
#include <QSizePolicy>
#include <QTcpSocket>
#include <QLinearGradient>
#include <QPlainTextEdit>
#include <QProcess>
#include <QPushButton>
#include <QRegularExpression>
#include <QSettings>
#include <QSaveFile>
#include <QScrollArea>
#include <QUrlQuery>
#include <QSlider>
#include <QSpinBox>
#include <QSplitter>
#include <QTabWidget>
#include <QTabBar>
#include <QResizeEvent>
#include <QStandardPaths>
#include <QTcpServer>
#include <QTimer>
#include <QTreeWidget>
#include <QUrl>
#include <QVBoxLayout>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <functional>
#include <memory>
#include <limits>

// Retuned analog radio: functional wheel/mouse QDial with a retro brass face.
class TihuluBrassDial final : public QDial {
public:
    explicit TihuluBrassDial(QWidget *parent=nullptr):QDial(parent) {
        setMinimumSize(88,88);
        setMaximumSize(100,100);
        setNotchesVisible(false);
        setFocusPolicy(Qt::StrongFocus);
    }
protected:
    void paintEvent(QPaintEvent *) override {
        QPainter painter(this);
        painter.setRenderHint(QPainter::Antialiasing);
        const QRectF bounds=QRectF(rect()).adjusted(5,5,-5,-5);
        const QPointF center=bounds.center();
        const double radius=qMin(bounds.width(),bounds.height())/2;
        QLinearGradient gold(bounds.topLeft(),bounds.bottomRight());
        gold.setColorAt(0,QColor("#f8db94"));
        gold.setColorAt(.45,QColor("#b48c44"));
        gold.setColorAt(1,QColor("#5e461f"));
        painter.setPen(QPen(QColor("#6d502b"),3));
        painter.setBrush(gold);
        painter.drawEllipse(bounds);
        painter.setPen(QPen(QColor("#fff2b9"),1));
        painter.drawEllipse(bounds.adjusted(8,8,-8,-8));
        const double turn=(maximum()>minimum())
          ?double(value()-minimum())/(maximum()-minimum()):0;
        const double angle=(225.-270.*turn)*3.141592653589793/180.;
        painter.setPen(QPen(QColor("#542d10"),4,Qt::SolidLine,Qt::RoundCap));
        painter.drawLine(center,QPointF(center.x()+radius*.68*std::cos(angle),
                                      center.y()-radius*.68*std::sin(angle)));
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor("#34291d"));
        painter.drawEllipse(center,4,4);
    }
};

class TihuluAnalogScale final : public QWidget {
public:
    explicit TihuluAnalogScale(QWidget *parent=nullptr):QWidget(parent) {
        setMinimumHeight(95);
        setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Fixed);
    }
    void updateFrequency(double minValue,double maxValue,double current,
                         const QString &units) {
        minimum_=minValue;maximum_=maxValue;value_=current;units_=units;update();
    }
protected:
    void paintEvent(QPaintEvent *) override {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const QRectF frame=QRectF(rect()).adjusted(2,2,-2,-2);
        p.setPen(QPen(QColor("#a97a36"),2));
        p.setBrush(QColor("#171814"));
        p.drawRoundedRect(frame,9,9);
        const double left=20,right=qMax(25,width()-21);
        p.setPen(QColor("#ebcf94"));
        for(int i=0;i<=20;++i) {
            const double x=left+(right-left)*i/20.;
            const int yEnd=(i%5==0?52:45);
            p.drawLine(QPointF(x,32),QPointF(x,yEnd));
            if(i%5==0)
                p.drawText(QRectF(x-33,54,66,20),Qt::AlignCenter,
                           QString::number(minimum_+(maximum_-minimum_)*i/20.,'f',
                                           maximum_>200?0:1));
        }
        p.setPen(QColor("#f6dca9"));
        p.drawText(QRectF(left,8,right-left,22),Qt::AlignCenter,units_);
        const double f=qBound(0.,(value_-minimum_)/qMax(1e-6,maximum_-minimum_),1.);
        const double marker=left+(right-left)*f;
        p.setPen(QPen(QColor("#ff674c"),3));
        p.drawLine(QPointF(marker,22),QPointF(marker,77));
    }
private:
    double minimum_=87.5,maximum_=108.,value_=99.2;
    QString units_=QStringLiteral("FM · MHz");
};

class TihuluRadioTab final : public TabBase
{
public:
	explicit TihuluRadioTab(MediaWidget *player, QWidget *parent = nullptr)
		: TabBase(), player_(player), backend_(this), captionProcess_(this),
		  recorder_(this), lyricsProcess_(this), network_(this), tick_(this)
	{
		setParent(parent);
		// Keep every radio control reachable on laptop-sized windows.
		auto *outer = new QVBoxLayout(this);
		outer->setContentsMargins(0, 0, 0, 0);
		auto *scroll = new QScrollArea(this);
		scroll->setWidgetResizable(true);
		scroll->setFrameShape(QFrame::NoFrame);
		outer->addWidget(scroll);
		auto *page = new QWidget(scroll);
		auto *root = new QVBoxLayout(page);
		root->setContentsMargins(9, 9, 9, 9);
		root->setSpacing(8);
		scroll->setWidget(page);
        // Single compact dashboard: independent radio modes no longer
        // stack all advanced settings under one enormous scrolling page.
        auto *selected = new QLabel(tr("Selected source: none · choose DAB+, Internet or FM/MW/LW"),page);
        selected->setWordWrap(true);
        selected->setStyleSheet(QLatin1String(
            "background:#142e3b;color:#c0edf6;border:1px solid #385a67;"
            "border-radius:6px;padding:7px;font-weight:600;"));
        selectedSource_=selected;
        root->addWidget(selectedSource_);
        radioCaptionBanner_=new QLabel(tr("Live radio subtitles OFF · DLS is not speech"),page);
        radioCaptionBanner_->setTextFormat(Qt::PlainText);
        radioCaptionBanner_->setWordWrap(true);
        radioCaptionBanner_->setMaximumHeight(120);
        radioCaptionBanner_->setStyleSheet(QLatin1String(
            "background:#14242e;color:#f5e6bb;border:1px solid #405365;"
            "border-radius:6px;padding:7px;"));
        root->addWidget(radioCaptionBanner_);
        // Translation diagnostics are never represented as spoken lyrics.
        // This slim status line remains visible even when AI settings
        // are collapsed and the radio station art occupies most of the tab.
        radioTranslationBanner_=new QLabel(page);
        radioTranslationBanner_->setWordWrap(true);
        radioTranslationBanner_->setTextFormat(Qt::PlainText);
        radioTranslationBanner_->setStyleSheet(QLatin1String(
            "QLabel{color:#adcbe0;background:transparent;font-size:12px;"
            "padding:4px 8px;}"));
        radioTranslationBanner_->setVisible(false);
        root->addWidget(radioTranslationBanner_);
        modes_=new QTabWidget(page);
        modes_->setDocumentMode(true);
        modes_->setUsesScrollButtons(true);
        modes_->tabBar()->setExpanding(false);
        modes_->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Preferred);
        root->addWidget(modes_,1);
        auto *dabPage=new QWidget(modes_);
        auto *dabLayout=new QVBoxLayout(dabPage);
        dabLayout->setContentsMargins(8,8,8,8);
        dabLayout->setSpacing(7);
        modes_->addTab(dabPage,tr("DAB+ · stations"));
        auto *header = new QHBoxLayout();
		auto *name = new QLabel(tr("Radio · DAB+ (powered by welle.io)"), this);
		name->setStyleSheet(QLatin1String("font-weight:700;font-size:16px"));
		header->addWidget(name, 1);
		channel_ = new QComboBox(this);
		const QStringList blocks = {
			"5A","5B","5C","5D","6A","6B","6C","6D",
			"7A","7B","7C","7D","8A","8B","8C","8D",
			"9A","9B","9C","9D","10A","10B","10C","10D",
			"11A","11B","11C","11D","12A","12B","12C","12D",
			"13A","13B","13C","13D","13E","13F"};
		channel_->addItems(blocks);
		channel_->setCurrentText(QLatin1String("11D"));
		channel_->setToolTip(tr("European Band III blocks. No tuning until Start."));
		header->addWidget(channel_);
		driver_ = new QComboBox(this);
		driver_->addItem(tr("Auto SDR"), QLatin1String("auto"));
		driver_->addItem(tr("RTL-SDR"), QLatin1String("rtl_sdr"));
		driver_->addItem(tr("SoapySDR"), QLatin1String("soapysdr"));
		driver_->addItem(tr("Airspy"), QLatin1String("airspy"));
		driver_->setToolTip(tr("Choose the DAB-capable receiver driver. "
			"An ordinary DVB-T2 frontend alone cannot be assumed to work."));
		header->addWidget(driver_);
		start_ = new QPushButton(tr("Start receiver"), this);
		start_->setToolTip(tr("Open an actual DAB-capable RTL-SDR/Soapy device on demand."));
		stop_ = new QPushButton(tr("Stop radio"), this);
        stop_->setToolTip(tr("Stop DAB audio, AI captions and recordings. "
            "By default also terminate welle-cli and release the RTL-SDR. "
            "Use the option below to keep the receiver ready."));
		record_ = new QPushButton(tr("Record station"), this);
		record_->setToolTip(tr("Save selected radio service to a local MP3; "
			"stop recording to release the file."));
		scan_ = new QPushButton(tr("Scan all blocks"), this);
		scan_->setToolTip(tr("Retunes across Band III blocks; can take minutes."));
		dabLayout->addLayout(header);
		// Two-row responsive operation grid; large monitors no longer stretch
		// every action across 400 px, and laptop windows do not clip controls.
		auto *receiverActions=new QGridLayout();
		receiverActions->setHorizontalSpacing(9);
		for(QPushButton *button:{start_,scan_,record_,stop_})
			button->setMaximumWidth(200);
		receiverActions->addWidget(start_,0,0);
		receiverActions->addWidget(scan_,0,1);
		receiverActions->addWidget(stop_,0,2);
        releaseOnStop_=new QCheckBox(
            tr("Release SDR when radio stops (default)"),page);
        QSettings radioResourceSettings(QLatin1String("TIHULU"),
                                        QLatin1String("KaffeineRadio"));
        releaseOnStop_->setChecked(radioResourceSettings.value(
            QLatin1String("releaseSdrOnStop"),true).toBool());
        releaseOnStop_->setToolTip(tr("ON (recommended): stopping radio, "
            "including the main Kaffeine Stop button, ends TIHULU's "
            "welle-cli receiver and releases the RTL-SDR to other apps. "
            "OFF keeps this application's DAB receiver occupying the SDR "
            "after playback stops; full application exit still releases."));
        receiverActions->addWidget(releaseOnStop_,1,2);
        forceRelease_=new QPushButton(tr("Release SDR now"),page);
        forceRelease_->setToolTip(tr("Always stop this app-owned radio receiver "
            "and release the RTL-SDR, regardless of the keep-ready preference. "
            "Does not stop other applications' SDR processes."));
        receiverActions->addWidget(forceRelease_,2,2);
        subtitledRecord_=new QCheckBox(tr("Make subtitled recording"),this);
		subtitledRecord_->setToolTip(tr("On Stop, create offline time-coded SRT from the "
			"saved audio and mux a selectable-subtitle MKV. Never fake live synchronization."));
		receiverActions->addWidget(record_,1,0);
		receiverActions->addWidget(subtitledRecord_,1,1);
		receiverActions->setColumnStretch(2,1);
		dabLayout->addLayout(receiverActions);
		// Keep actual scan progress + SNR in view even when the RF graph and
		// AI settings are far down the scroll area.
		auto *scanReadouts=new QHBoxLayout();
		scanProgress_=new QProgressBar(page);
		scanProgress_->setRange(0,channel_->count());
		scanProgress_->setValue(0);
		scanProgress_->setFormat(tr("DAB scan · not started"));
		scanProgress_->setMinimumWidth(160);
		scanSNR_=new QProgressBar(page);
		scanSNR_->setRange(0,100);
		scanSNR_->setValue(0);
		scanSNR_->setFormat(tr("RF SNR: no live measurement"));
		scanSNR_->setToolTip(tr("Actual reported DAB signal-to-noise ratio converted "
			"to a relative progress indicator, NOT a measured RF power level."));
		scanReadouts->addWidget(scanProgress_,1);
		scanReadouts->addWidget(scanSNR_,1);
		dabLayout->addLayout(scanReadouts);

		state_ = new QLabel(tr("Receiver disconnected. A separate DAB-capable SDR is required; "
			"the DVB-T2 television adapter is not automatically a DAB receiver."), this);
		state_->setWordWrap(true);
		state_->setTextFormat(Qt::PlainText);
		dabLayout->addWidget(state_);
        receiverOwnership_=new QLabel(tr(
            "SDR: RELEASED by TIHULU · select a DAB station or Start "
            "receiver to acquire it"),page);
        receiverOwnership_->setWordWrap(true);
        dabLayout->addWidget(receiverOwnership_);
		playStatus_=new QLabel(tr("Station: no live stream verified"),page);
		playStatus_->setWordWrap(true);
		dabLayout->addWidget(playStatus_);
		stationOpenProgress_=new QProgressBar(page);
		stationOpenProgress_->setRange(0,4);
		stationOpenProgress_->setValue(0);
		stationOpenProgress_->setFormat(tr("Stream status · choose a station"));
		dabLayout->addWidget(stationOpenProgress_);
        radioAudioHealth_=new QLabel(tr(
            "Audio health · awaiting real RF error-counter deltas; "
            "libVLC output clock not measured"),page);
        radioAudioHealth_->setWordWrap(true);
        dabLayout->addWidget(radioAudioHealth_);
        // DAB playback is RF/audio first. Heavy AI and EXTRA network cache
        // are opt-in; they must never be required just to tune or scan.
        radioQuickRow_=new QHBoxLayout();
        quickAi_=new QCheckBox(tr("AI captions · OFF"),page);
        quickAi_->setChecked(false);
        quickAi_->setToolTip(tr("Whisper and translation are OFF at startup. "
            "When enabled, captions follow station changes; scanning disables them."));
        quickBuffer_=new QCheckBox(tr("Extra buffer · OFF"),page);
        quickBuffer_->setChecked(false);
        quickBuffer_->setToolTip(tr("Enable a user-selected libVLC network cache. "
            "OFF means no EXTRA cache request; demodulator and device "
            "latency cannot be disabled. Changing this while playing "
            "reopens the audio stream once."));
        radioQuickRow_->addWidget(quickAi_);
        quickLanguageButton_=new QPushButton(
            tr("IN: AUTO · OUT: EN, DE, TR · Edit"),page);
        quickLanguageButton_->setToolTip(tr(
            "Choose original speech and translation languages; "
            "updates reach the current radio ASR worker live."));
        radioQuickRow_->addWidget(quickLanguageButton_);
        radioQuickRow_->addStretch(1);
        dabLayout->addLayout(radioQuickRow_);
        radioPlaybackRow_=new QHBoxLayout();
        radioPlaybackRow_->addWidget(quickBuffer_);
        radioPlaybackRow_->addStretch(1);
        dabLayout->addLayout(radioPlaybackRow_);
        // Common controls must be reachable while listening, without
        // opening the advanced Whisper/AI menu. Radio has no video lips:
        // this is audio-to-subtitle timing, not a measured DAC clock.
        auto *captionComfortRow=new QHBoxLayout();
        captionComfortRow->addWidget(new QLabel(tr(
            "Audio ↔ captions (estimated):"),page));
        captionEarlier_=new QPushButton(tr("−250 ms"),page);
        captionLater_=new QPushButton(tr("+250 ms"),page);
        captionEarlier_->setToolTip(tr(
            "Text appears 250 ms earlier. Does not retune radio audio."));
        captionLater_->setToolTip(tr(
            "Text appears 250 ms later. Does not retune radio audio."));
        captionOffsetReadout_=new QLabel(tr("Offset +0 ms"),page);
        captionOffsetReadout_->setToolTip(tr(
            "Your manual subtitle offset (negative = earlier). "
            "Actual libVLC/ALSA audio presentation time is unmeasured."));
        captionComfortRow->addWidget(captionEarlier_);
        captionComfortRow->addWidget(captionLater_);
        captionComfortRow->addWidget(captionOffsetReadout_);
        captionComfortRow->addSpacing(12);
        captionComfortRow->addWidget(new QLabel(tr("Reading:"),page));
        radioReadingPreset_=new QComboBox(page);
        radioReadingPreset_->addItem(tr("Live · fast"),0);
        radioReadingPreset_->addItem(tr("Comfort · recommended"),1);
        radioReadingPreset_->addItem(tr("Relaxed · longer hold"),2);
        radioReadingPreset_->setToolTip(tr(
            "Avoid rapidly flashing phrases. Comfort pauses between new "
            "captions so they remain readable; extra languages may lag "
            "behind live speech. Does not change radio audio."));
        QSettings captionPreferences(QLatin1String("TIHULU"),
                                     QLatin1String("KaffeineRadio"));
        const int readingPreference=qBound(0,captionPreferences.value(
            QLatin1String("radioReadingPreset"),1).toInt(),2);
        radioReadingPreset_->setCurrentIndex(readingPreference);
        captionComfortRow->addWidget(radioReadingPreset_);
        captionComfortRow->addWidget(new QLabel(tr("Text:"),page));
        radioCaptionFontSize_=new QSpinBox(page);
        radioCaptionFontSize_->setRange(14,28);
        radioCaptionFontSize_->setSuffix(tr(" pt"));
        radioCaptionFontSize_->setValue(qBound(14,captionPreferences.value(
            QLatin1String("radioCaptionFontPt"),18).toInt(),28));
        captionComfortRow->addWidget(radioCaptionFontSize_);
        captionComfortRow->addStretch(1);
        dabLayout->addLayout(captionComfortRow);
        connect(radioReadingPreset_,QOverload<int>::of(
            &QComboBox::currentIndexChanged),this,[this](int){
            QSettings prefs(QLatin1String("TIHULU"),
                            QLatin1String("KaffeineRadio"));
            prefs.setValue(QLatin1String("radioReadingPreset"),
                           radioReadingPreset_->currentData().toInt());
        });
        connect(radioCaptionFontSize_,QOverload<int>::of(
            &QSpinBox::valueChanged),this,[this](int size){
            QSettings prefs(QLatin1String("TIHULU"),
                            QLatin1String("KaffeineRadio"));
            prefs.setValue(QLatin1String("radioCaptionFontPt"),size);
            updateRadioCaptionTypography();
        });
        quickBufferProgress_=new QProgressBar(page);
        quickBufferProgress_->setRange(0,100);
        quickBufferProgress_->setValue(0);
        quickBufferProgress_->setFormat(tr(
            "Extra buffer OFF · enable it to view startup progress"));
        quickBufferProgress_->setToolTip(tr(
            "Progress shows estimated startup time against the requested "
            "extra libVLC cache, NOT measured buffer occupancy, audio "
            "latency or physical speaker output."));
        quickBufferProgress_->setVisible(false);
        dabLayout->addWidget(quickBufferProgress_);

		// Public internet radio requires no SDR, welle-cli or DVB frontend.
		// Search happens only when clicked, and uses HTTPS Radio Browser API.
		auto *webGroup = new QGroupBox(tr("Internet radio · independent of tuner"), page);
		auto *webLayout = new QVBoxLayout(webGroup);
		auto *webSearchRow = new QGridLayout();
		webSearch_ = new QLineEdit(webGroup);
		webSearch_->setPlaceholderText(tr("Search station name · e.g. WDR, BBC, TRT"));
		webCountry_ = new QComboBox(webGroup);
		webCountry_->setMinimumWidth(175);
		webCountry_->setMaximumWidth(300);
		webCountry_->setSizePolicy(QSizePolicy::Preferred,QSizePolicy::Fixed);
		webCountry_->addItem(tr("All countries · worldwide"),QString());
		QMap<QString,QString> world;
		const auto locales=QLocale::matchingLocales(
			QLocale::AnyLanguage,QLocale::AnyScript,QLocale::AnyCountry);
		for(const QLocale &loc:locales) {
			const QString code=loc.name().section(QLatin1Char('_'),1).toUpper();
			if(!QRegularExpression(QLatin1String("^[A-Z]{2}$")).match(code).hasMatch())
				continue;
			QString countryName=QLocale::countryToString(loc.country());
			if(countryName.isEmpty()) continue;
			world.insert(countryName+QLatin1String(" (")+code+QLatin1Char(')'),code);
		}
		// Debian's ISO-3166 source supplements locales with territories
		// for which Qt does not ship a user-interface locale.
		QFile countries(QLatin1String("/usr/share/iso-codes/json/iso_3166-1.json"));
		if(countries.open(QIODevice::ReadOnly) && countries.size()<512*1024) {
			const QJsonDocument catalog=QJsonDocument::fromJson(countries.readAll());
			const QJsonArray entries=catalog.object().value(
				QLatin1String("3166-1")).toArray();
			for(const QJsonValue &v:entries) {
				const QJsonObject e=v.toObject();
				const QString code=e.value(QLatin1String("alpha_2")).toString();
				const QString title=e.value(QLatin1String("name")).toString();
				if(QRegularExpression(QLatin1String("^[A-Z]{2}$"))
				   .match(code).hasMatch() && !title.isEmpty())
					world.insert(title+QLatin1String(" (")+code+QLatin1Char(')'),code);
			}
		}
		for(auto it=world.constBegin();it!=world.constEnd();++it)
			webCountry_->addItem(it.key(),it.value());
		webCountry_->setEditable(true);
		webCountry_->setInsertPolicy(QComboBox::NoInsert);
		webCountry_->setMaxVisibleItems(20);
		webCountry_->setToolTip(tr("Choose a country or type its name/ISO code; "
			"the online directory is searched after selecting a country."));
		webCountry_->completer()->setFilterMode(Qt::MatchContains);
		webCountry_->completer()->setCaseSensitivity(Qt::CaseInsensitive);
		webCountry_->setCurrentIndex(0);
		webSearchButton_ = new QPushButton(tr("Find stations online"), webGroup);
		webSearchRow->addWidget(webSearch_,0,0,1,2);
        webSearchRow->addWidget(webCountry_,1,0);
        webSearchRow->addWidget(webSearchButton_,1,1);
        webSearchRow->setColumnStretch(0,1);
		webLayout->addLayout(webSearchRow);
		webStations_ = new QTreeWidget(webGroup);
		webStations_->setHeaderLabels({tr("★"),tr("Station"),tr("Country"),tr("Codec")});
		webStations_->setRootIsDecorated(false);
		webStations_->setAlternatingRowColors(true);
		webStations_->setMinimumHeight(105);
		webStations_->setMaximumHeight(170);
		webStations_->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
		webStations_->header()->setSectionResizeMode(1, QHeaderView::Stretch);
		webLayout->addWidget(webStations_);
		auto *webPlayRow = new QGridLayout();
		webSource_ = new QLineEdit(webGroup);
		webSource_->setPlaceholderText(tr("Or paste an HTTP(S) radio stream URL"));
		webPlay_ = new QPushButton(tr("Play stream"), webGroup);
		webAlternate_=new QPushButton(tr("Try alternate station URL"),webGroup);
		webAlternate_->setToolTip(tr("If the resolved stream is broken, explicitly try the "
			"station's original Radio Browser URL, when it differs."));
		webProbeButton_=new QPushButton(tr("Test stream / codec"),webGroup);
		webProbeButton_->setToolTip(tr("Ask local FFprobe to inspect the station URL "
			"without opening DVB or claiming that audio is audible."));
		webStop_ = new QPushButton(tr("Stop stream"), webGroup);
		webFavoritesOnly_ = new QCheckBox(tr("★ Favorites"),webGroup);
		webPlayRow->addWidget(webSource_,0,0,1,3);
        webPlayRow->addWidget(webPlay_,1,0);
        webPlayRow->addWidget(webProbeButton_,1,1);
        webPlayRow->addWidget(webAlternate_,1,2);
        webPlayRow->addWidget(webStop_,2,0);
        webPlayRow->addWidget(webFavoritesOnly_,2,1,1,2);
        webPlayRow->setColumnStretch(0,1);
		webLayout->addLayout(webPlayRow);
		webStatus_ = new QLabel(tr("Internet radio is ready. No tuner connection required."),webGroup);
		webStatus_->setWordWrap(true);
		webLayout->addWidget(webStatus_);
		modes_->addTab(webGroup,tr("Internet radio"));

		// The analog radio is optional hardware; keep a bounded, collapsible
		// retro cabinet so the DAB channel table stays visible.
		auto *analogGroup=new QGroupBox(tr("Vintage analogue tuner · enable FM / MW / LW"),page);
		analogGroup->setCheckable(true);
		analogGroup->setChecked(false);
		analogGroup->setStyleSheet(QLatin1String(
			"QGroupBox{background:#30251b;color:#f1d6a1;border:2px solid #8d6634;"
			"border-radius:11px;margin-top:16px;padding-top:8px;font-weight:600;}"
			"QGroupBox::title{subcontrol-origin:margin;left:15px;padding:2px 8px;}"
			"QLabel{color:#f2d4a0;}"
			"QComboBox,QDoubleSpinBox{background:#171b1b;color:#efc783;"
			"border:1px solid #ac8042;border-radius:5px;padding:5px;}"
			"QPushButton{background:#6a4928;color:#fff0ce;border:1px solid #b69358;"
			"border-radius:6px;padding:6px 11px;min-height:30px;}"));
		auto *analogLayout=new QVBoxLayout(analogGroup);
		analogLayout->setSpacing(9);
		analogLayout->setContentsMargins(14,22,14,10);
		auto *analogCabinet=new QWidget(analogGroup);
		auto *cabinetLayout=new QVBoxLayout(analogCabinet);
		cabinetLayout->setContentsMargins(2,2,2,2);
        selectedStationVintage_=new QLabel(
            tr("Selected station: none · analogue dial controls FM/MW/LW only"),
            analogCabinet);
        selectedStationVintage_->setWordWrap(true);
        selectedStationVintage_->setTextFormat(Qt::PlainText);
        selectedStationVintage_->setStyleSheet(QLatin1String(
            "background:#141c1a;color:#eaca90;border:1px solid #96704a;"
            "border-radius:5px;padding:5px;font-weight:600;"));
        cabinetLayout->addWidget(selectedStationVintage_);
        vintageDabReadout_=new QLabel(analogCabinet);
        vintageDabReadout_->setWordWrap(true);
        vintageDabReadout_->setTextFormat(Qt::PlainText);
        vintageDabReadout_->setStyleSheet(QLatin1String(
            "background:#102b32;color:#c5f0fa;border:1px solid #47717d;"
            "border-radius:5px;padding:7px;font-weight:600;"));
        vintageDabReadout_->setVisible(false);
        vintageDabReadout_->setToolTip(tr(
            "Current/selected DAB+ Band III ensemble centre frequency. "
            "The brass analogue FM/MW/LW dial below remains independent."));
        cabinetLayout->addWidget(vintageDabReadout_);
		auto *analogHead=new QGridLayout();
		analogBand_=new QComboBox(analogCabinet);
		analogBand_->addItem(tr("FM · 87.5–108 MHz"),QLatin1String("fm"));
		analogBand_->addItem(tr("AM / MW · 531–1602 kHz"),QLatin1String("mw"));
		analogBand_->addItem(tr("LW · 150–280 kHz"),QLatin1String("lw"));
		analogBand_->setMinimumWidth(115);
        analogBand_->setMaximumWidth(260);
		analogFrequency_=new QDoubleSpinBox(analogCabinet);
		analogFrequency_->setDecimals(2);
		analogFrequency_->setRange(87.5,108.0);
		analogFrequency_->setValue(99.2);
		analogFrequency_->setSuffix(tr(" MHz"));
		analogFrequency_->setMinimumWidth(100);
        analogFrequency_->setMaximumWidth(160);
		analogDigital_=new QLabel(tr("99.20 MHz"),analogCabinet);
		analogDigital_->setStyleSheet(QLatin1String(
			"font: bold 20px monospace;color:#ffe1a1;background:#131916;"
			"border:1px solid #ac8042;border-radius:6px;padding:7px;"));
		analogHead->addWidget(analogBand_,0,0);
        analogHead->addWidget(analogFrequency_,0,1);
        analogHead->addWidget(analogDigital_,1,0,1,2);
        analogHead->setColumnStretch(1,1);
		cabinetLayout->addLayout(analogHead);
		auto *analogFace=new QHBoxLayout();
		analogScale_=new TihuluAnalogScale(analogCabinet);
		analogDial_=new TihuluBrassDial(analogCabinet);
		analogDial_->setRange(8750,10800);
		analogDial_->setValue(9920);
		analogDial_->setToolTip(tr("Turn with mouse wheel/drag; live retune after "
			"brief 450ms pause. RF hardware must reopen and may briefly go silent."));
		analogFace->addWidget(analogScale_,1);
		analogFace->addWidget(analogDial_);
		cabinetLayout->addLayout(analogFace);
		analogAudioVu_=new QProgressBar(analogCabinet);
		analogAudioVu_->setRange(0,100);
		analogAudioVu_->setValue(0);
		analogAudioVu_->setFormat(tr("Audio VU: no input (not an RF strength reading)"));
		analogAudioVu_->setToolTip(tr("Actual signed-PCM audio RMS level from rtl_fm. "
			"It does not measure SDR RSSI, DAB lock, or antenna RF power."));
		cabinetLayout->addWidget(analogAudioVu_);
		auto *buttons=new QGridLayout();
		analogStart_=new QPushButton(tr("Tune / play"),analogCabinet);
		analogStop_=new QPushButton(tr("Stop / release"),analogCabinet);
		analogStart_->setMaximumWidth(155);
		analogStop_->setMaximumWidth(155);
		buttons->addWidget(analogStart_,0,0);
        buttons->addWidget(analogStop_,0,1);
        buttons->addWidget(new QLabel(tr("Volume"),analogCabinet),1,0);
		analogVolume_=new QSlider(Qt::Horizontal,analogCabinet);
		analogVolume_->setRange(0,100);
		analogVolume_->setValue(player_->getVolume());
		analogVolume_->setMaximumWidth(170);
		analogVolume_->setToolTip(tr("Real libVLC player volume; controls the "
			"same stream as the main TIHULU media transport."));
		analogMute_=new QPushButton(tr("Toggle mute"),analogCabinet);
		analogMute_->setMaximumWidth(125);
		buttons->addWidget(analogVolume_,1,1);
        buttons->addWidget(analogMute_,1,2);
        buttons->setColumnStretch(1,1);
		buttons->setColumnStretch(3,1);
		connect(analogVolume_,&QSlider::valueChanged,player_,&MediaWidget::setVolume);
		connect(analogMute_,&QPushButton::clicked,player_,&MediaWidget::toggleMuted);
		cabinetLayout->addLayout(buttons);
		directSampling_=new QCheckBox(
			tr("Use hardware-specific direct sampling for MW/LW (opt-in)"),analogCabinet);
		directSampling_->setToolTip(tr("For compatible HF RTL-SDR hardware only."));
		cabinetLayout->addWidget(directSampling_);
		analogStatus_=new QLabel(tr("Optional RTL-SDR required. Built-in Kaffeine volume/"
			"mute controls the local analog stream; DVB-T2 Si2168 does not tune FM."),analogCabinet);
		analogStatus_->setWordWrap(true);
		cabinetLayout->addWidget(analogStatus_);
		analogLayout->addWidget(analogCabinet);
		modes_->addTab(analogGroup,tr("Vintage FM / AM / LW"));
		analogRetune_.setSingleShot(true);
		analogRetune_.setInterval(450);
		connect(&analogRetune_,&QTimer::timeout,this,[this](){
			if(analogServer_.isListening()) retuneAnalogDemod();
		});
		connect(analogBand_,QOverload<int>::of(&QComboBox::currentIndexChanged),
			this,[this](){configureAnalogBand();});
		connect(analogDial_,&QDial::valueChanged,this,[this](int v){
			analogFrequency_->setValue(v/100.);
		});
		connect(analogFrequency_,QOverload<double>::of(&QDoubleSpinBox::valueChanged),
			this,[this](double v){
			analogDial_->setValue(qRound(v*100.));
			analogDigital_->setText(QString::number(v,'f',
				analogBand_->currentData().toString()==QLatin1String("fm")?2:0)+
				analogFrequency_->suffix());
			analogScale_->updateFrequency(
				analogFrequency_->minimum(),analogFrequency_->maximum(),v,
				analogBand_->currentText());
			if(analogServer_.isListening()) analogRetune_.start();
		});
		connect(analogStart_,&QPushButton::clicked,this,[this](){
            startAnalog();
            if(analogServer_.isListening()) showSelectedSource(
                tr("Live analogue SDR"),analogBand_->currentText(),
                QString::number(analogFrequency_->value(),'f',2)+
                    analogFrequency_->suffix());
        });
		connect(analogStop_,&QPushButton::clicked,this,[this](){stopAnalog();});
		connect(&analogDemod_,&QProcess::readyReadStandardError,this,[this](){
			const QString msg=QString::fromLocal8Bit(analogDemod_.readAllStandardError());
            if(!msg.trimmed().isEmpty()) lastAnalogError_=msg.trimmed().right(600);
			if(msg.contains(QLatin1String("Failed"),Qt::CaseInsensitive) ||
			   msg.contains(QLatin1String("error"),Qt::CaseInsensitive))
				analogStatus_->setText(msg.right(320));
		});
		connect(&analogDemod_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int code,QProcess::ExitStatus){
				if(!analogStopping_) {
                    lastAnalogError_=tr("rtl_fm exited (%1). %2")
                        .arg(code).arg(lastAnalogError_).right(600);
                    analogStatus_->setText(tr("Analog SDR exited (%1). "
                        "Open Hardware tab for USB presence and owner scan.").arg(code));
                }
			});
		configureAnalogBand();

		auto *split = new QSplitter(Qt::Horizontal, page);
		auto *library = new QWidget(split);
		auto *libraryLayout = new QVBoxLayout(library);
		libraryLayout->setContentsMargins(1,1,1,1);
		libraryLayout->setSpacing(5);
		auto *libraryHeader = new QLabel(tr("All scanned DAB stations"),library);
		libraryHeader->setStyleSheet(QLatin1String("font-weight:600;font-size:15px"));
		libraryLayout->addWidget(libraryHeader);
		stationSearch_ = new QLineEdit(library);
		stationSearch_->setPlaceholderText(tr("Search every saved DAB ensemble…"));
		stationSearch_->setClearButtonEnabled(true);
		libraryLayout->addWidget(stationSearch_);
		auto *libraryFilters = new QHBoxLayout();
		libraryBlock_ = new QComboBox(library);
		libraryBlock_->addItem(tr("All DAB blocks"),QString());
		for (const QString &block : blocks)
			libraryBlock_->addItem(block,block);
		favoritesOnly_ = new QCheckBox(tr("★ Favorites only"),library);
		libraryFilters->addWidget(libraryBlock_,1);
		libraryFilters->addWidget(favoritesOnly_);
		libraryLayout->addLayout(libraryFilters);
		stations_ = new QTreeWidget(library);
		stations_->setHeaderLabels({tr("★"),tr("Station"),tr("DAB block"),tr("Service ID")});
		stations_->setRootIsDecorated(false);
		stations_->setAlternatingRowColors(true);
		stations_->setSortingEnabled(true);
		stations_->setMinimumWidth(200);
        stations_->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Expanding);
		stations_->header()->setSectionResizeMode(0,QHeaderView::Fixed);
		stations_->header()->resizeSection(0,29);
		stations_->header()->setSectionResizeMode(1,QHeaderView::Stretch);
		stations_->header()->setSectionResizeMode(2,QHeaderView::ResizeToContents);
		stations_->header()->setSectionResizeMode(3,QHeaderView::ResizeToContents);
		stations_->setSortingEnabled(true);
		libraryLayout->addWidget(stations_,1);
		libraryStatus_ = new QLabel(tr("Scan every Band III block or open a saved station"),library);
		libraryLayout->addWidget(libraryStatus_);
		split->addWidget(library);

		auto *right = new QWidget(split);
		auto *rightLayout = new QVBoxLayout(right);
		rightLayout->setContentsMargins(5, 4, 5, 4);
		rightLayout->setSpacing(6);
		playerHost_ = new QWidget(right);
		playerHostLayout_ = new QVBoxLayout(playerHost_);
		playerHostLayout_->setContentsMargins(0, 0, 0, 0);
		rightLayout->addWidget(playerHost_, 3);
		// The radio is audio-only. Keep Kaffeine's global libVLC MediaWidget
		// owned by Playback/Playlist/Television. Reparenting it into Radio
		// broke file playback and left a duplicate transport bar in the
		// video canvas. This is a radio visualization and caption surface.
		radioCanvas_ = new QLabel(tr("Radio · choose a station to listen"), playerHost_);
		radioCanvas_->setAlignment(Qt::AlignCenter);
		radioCanvas_->setWordWrap(true);
		radioCanvas_->setMinimumHeight(135);
		radioCanvas_->setStyleSheet(QLatin1String(
			"QLabel{background:#122637;color:#eef9fc;font-size:19px;"
			"border:1px solid #2b566b;border-radius:8px;padding:12px;}"));
		playerHostLayout_->addWidget(radioCanvas_);
        // Radio subtitles belong INSIDE the large station surface, not
        // in the settings-only panel. Preserve radioCanvas_'s station art/
        // receiver text; a separate bottom child overlays real cues.
        auto *captionSurface=new QVBoxLayout(radioCanvas_);
        captionSurface->setContentsMargins(12,12,12,12);
        captionSurface->addStretch(1);
        radioCanvasCaption_=new QLabel(radioCanvas_);
        radioCanvasCaption_->setTextFormat(Qt::PlainText);
        radioCanvasCaption_->setWordWrap(true);
        radioCanvasCaption_->setAlignment(Qt::AlignHCenter | Qt::AlignVCenter);
        radioCanvasCaption_->setStyleSheet(QLatin1String(
            "QLabel{background:rgba(0,0,0,205);color:white;"
            "border-radius:5px;padding:8px;font-size:16px;}"));
        radioCanvasCaption_->setVisible(false);
        radioCanvasCaption_->setMaximumHeight(210);
        radioCanvasCaption_->setToolTip(tr(
            "Original heard audio + selected translation outputs. "
            "Captions are aligned to captured PCM timestamps, not "
            "measured libVLC audio presentation timestamps."));
        radioLyricMatchStatus_=new QLabel(radioCanvas_);
        radioLyricMatchStatus_->setTextFormat(Qt::PlainText);
        radioLyricMatchStatus_->setWordWrap(true);
        radioLyricMatchStatus_->setAlignment(Qt::AlignCenter);
        radioLyricMatchStatus_->setStyleSheet(QLatin1String(
            "QLabel{background:rgba(0,0,0,205);color:#cdebf5;"
            "border-radius:5px;padding:4px;font-size:13px;}"));
        radioLyricMatchStatus_->setVisible(false);
        radioLyricMatchStatus_->setToolTip(tr(
            "Lyrics FOUND means matching song metadata. Audio MATCHED "
            "requires a real Whisper lyric line match; when no match "
            "exists, actual speech stays visible as a transcription."));
        captionSurface->addWidget(radioLyricMatchStatus_);
        captionSurface->addWidget(radioCanvasCaption_);
        updateRadioCaptionTypography();

		auto *meta = new QHBoxLayout();
		slide_ = new QLabel(tr("No DAB slideshow"), right);
		slide_->setAlignment(Qt::AlignCenter);
		slide_->setFixedSize(185, 112);
		slide_->setStyleSheet(QLatin1String("border:1px solid #466;"));
		auto *slides = new QVBoxLayout();
		slides->addWidget(slide_);
		auto *slideControls=new QHBoxLayout();
		slidePrev_=new QPushButton(tr("◀"),right);
		slideNext_=new QPushButton(tr("▶"),right);
		slideControls->addWidget(slidePrev_);
		slideControls->addWidget(slideNext_);
		slides->addLayout(slideControls);
		meta->addLayout(slides);
		auto *textBlock = new QVBoxLayout();
		dls_ = new QLabel(tr("DLS radio text will appear here."), right);
		dls_->setTextFormat(Qt::PlainText);
		dls_->setWordWrap(true);
		signal_ = new QLabel(tr("SNR / FIC / ensemble diagnostics: no RF readings."), right);
		signal_->setTextFormat(Qt::PlainText);
		signal_->setWordWrap(true);
		rfQuality_=new QProgressBar(right);
		rfQuality_->setRange(0,100);
		rfQuality_->setValue(0);
		rfQuality_->setFormat(tr("DAB signal: unmeasured"));
		rfQuality_->setToolTip(tr("Relative indication derived from receiver-reported "
			"SNR, not calibrated RF power or signal strength."));
		textBlock->addWidget(dls_);
		textBlock->addWidget(signal_);
		textBlock->addWidget(rfQuality_);
		meta->addLayout(textBlock, 1);
		rightLayout->addLayout(meta);
		split->addWidget(right);
		split->setStretchFactor(0,1);
		split->setStretchFactor(1,2);
		stationSplit_=split;
        dabLayout->addWidget(split, 4);

		auto *lab = new QGroupBox(tr("Captions · input language / output translations / lyrics"), this);
		auto *v = new QVBoxLayout(lab);
		auto *row = new QGridLayout();
        row->setHorizontalSpacing(7);
        row->setVerticalSpacing(5);
        v->addWidget(new QLabel(
            tr("<b>1 · Heard audio (IN)</b> · Auto detect or choose English, German, etc."),lab));
		speechLanguage_ = new QComboBox(lab);
		speechLanguage_->addItem(tr("Auto detect · Whisper (selected local model)"),"auto");
        // The complete supported Whisper input set is filled from the
        // shared catalog. Keep a usable offline fallback until it arrives.
        for(const QString &code:QStringList{"de","en","tr","fr","es","pl","ar","ja"})
            speechLanguage_->addItem(code.toUpper(),code);
        speechLanguage_->setEditable(false);
        speechLanguage_->setToolTip(tr(
            "Auto detect uses the selected Whisper model. Every other IN "
            "language is supported by a multilingual speech model, NOT a "
            "separately installed translation package. Actual source "
            "detection confidence depends on engine and the audio."));
        spokenModelStatus_=new QLabel(tr(
            "Checking locally installed Whisper model…"),lab);
        spokenModelStatus_->setWordWrap(true);
        QSettings initialRadioLanguages(QLatin1String("TIHULU"),
                                       QLatin1String("KaffeineRadio"));
        const int savedSpeechIndex=speechLanguage_->findData(
            initialRadioLanguages.value(
                QLatin1String("radioSpeechLanguage"),"auto").toString());
        speechLanguage_->setCurrentIndex(savedSpeechIndex>=0?savedSpeechIndex:0);
		captionSource_=new QComboBox(lab);
		captionSource_->addItem(tr("Whisper ASR · recognized live audio"),
			QLatin1String("asr"));
		captionSource_->addItem(tr("Broadcaster DLS · metadata only, NOT subtitles"),
			QLatin1String("dls"));
		captionSource_->setToolTip(tr("DAB DLS is program/song metadata, not a "
			"guaranteed subtitle channel. Whisper generates spoken-word subtitles "
			"from actual audio; timed lyrics are separate."));
		german_ = new QCheckBox(tr("German"), lab); german_->setChecked(true);
		english_ = new QCheckBox(tr("English"), lab); english_->setChecked(true);
		turkish_ = new QCheckBox(tr("Turkish"), lab); turkish_->setChecked(true);
		music_ = new QCheckBox(tr("Transcribe singing / music vocals"), lab);
        music_->setToolTip(tr("Show original sung words and selected translations "
            "when Whisper confirms song language. If matched lyrics exist, "
            "prefer their text; uncertain language is NEVER guessed. "
            "Choose a specific language for immediate lyric translation."));
		speakerLabels_=new QCheckBox(tr("Label different speakers · offline"),lab);
		speakerLabels_->setToolTip(tr("Optional installed voice-clustering model. "
			"Outputs Speaker 1/2, NOT inferred woman/man/child labels. "
			"Disable when music is playing."));
		connect(music_,&QCheckBox::toggled,speakerLabels_,[this](bool enabled){
			speakerLabels_->setEnabled(!enabled);
			if(enabled) speakerLabels_->setChecked(false);
		});
		caption_ = new QPushButton(tr("Start offline live captions"), lab);
        applyCaptions_=new QPushButton(tr("Apply caption settings"),lab);
        applyCaptions_->setToolTip(tr("Restart only local Whisper/translation "
            "with the current speech language, music, source and targets. "
            "Keeps receiver tuning, radio playback and requested cache untouched."));
		stopCaption_ = new QPushButton(tr("Stop AI captions"), lab);
		row->addWidget(new QLabel(tr("Caption source:"),lab),0,0);
        row->addWidget(captionSource_,0,1,1,2);
        row->addWidget(new QLabel(tr("Speech language:"),lab),1,0);
        row->addWidget(speechLanguage_,1,1,1,2);
        row->addWidget(spokenModelStatus_,2,0,1,3);
        // Legacy quick checkboxes are retained as disabled compatibility
        // objects only. ONE checkable multi-output list below owns targets.
        english_->hide(); german_->hide(); turkish_->hide();
        row->addWidget(music_,3,0,1,2);
        row->addWidget(speakerLabels_,3,2);
        row->setColumnStretch(1,1);
		v->addLayout(row);
        v->addWidget(new QLabel(tr(
            "<b>2 · Subtitle languages (OUT)</b> · check multiple languages. "
            "The original is always shown; missing translations are reported."),lab));
        translationStatus_=new QLabel(tr(
            "Translations: show original audio first. Select output languages; "
            "automatic source translation waits for reliable Whisper detection."),lab);
        translationStatus_->setWordWrap(true);
        translationStatus_->setTextFormat(Qt::PlainText);
        v->addWidget(translationStatus_);
		extraTargets_=new QLineEdit(lab);
		extraTargets_->setPlaceholderText(
			tr("Advanced · additional ISO targets not listed (comma-separated)"));
        extraTargets_->setToolTip(tr(
            "Advanced override for NLLB/MADLAD-supported ISO codes. "
            "A model weight file is not proof of real translation ability."));
        extraTargets_->setVisible(false);
        advancedLanguages_=new QCheckBox(tr("Advanced · enter other output language codes"),lab);
        connect(advancedLanguages_,&QCheckBox::toggled,extraTargets_,
                &QWidget::setVisible);
        v->addWidget(advancedLanguages_);
		v->addWidget(extraTargets_);
		auto *targetRow=new QHBoxLayout();
		installedTargets_=new QListWidget(lab);
		installedTargets_->setMinimumHeight(110);
        installedTargets_->setMaximumHeight(180);
		installedTargets_->setToolTip(tr("Shared TV/Radio Model Market catalog: "
            "Argos pairs, NLLB/MADLAD installed weights and explicitly configured "
            "online DeepL. Check up to six outputs. Listed does not guarantee "
            "the selected source-to-target translation will succeed."));
		refreshTargets_=new QPushButton(tr("Refresh installed models / languages"),lab);
		refreshTargets_->setToolTip(tr("Read-only local model catalog; never downloads models."));
		targetRow->addWidget(installedTargets_,1);
        auto *modelButtons=new QVBoxLayout();
        modelButtons->addWidget(refreshTargets_);
        auto *openModelMarket=new QPushButton(tr("Open AI Model Market"),lab);
        openModelMarket->setToolTip(tr(
            "Open the same Whisper / translator manager used by TV. "
            "Refresh this radio catalog after applying another model."));
        connect(openModelMarket,&QPushButton::clicked,this,[this](){
            if(!QProcess::startDetached(QLatin1String("tihulu-tv-center"),
                {QLatin1String("ai-market")}))
                translationStatus_->setText(tr(
                    "Could not open Model Market; use the TIHULU AI menu."));
        });
        modelButtons->addWidget(openModelMarket);
		targetRow->addLayout(modelButtons);
		v->addLayout(targetRow);
		connect(refreshTargets_,&QPushButton::clicked,this,[this](){refreshLanguagePacks();});
        connect(&languagePackWorker_,
            QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),this,
            [this](int status,QProcess::ExitStatus exitStatus){
                refreshTargets_->setEnabled(true);
                if(status!=0 || exitStatus!=QProcess::NormalExit){
                    translationStatus_->setText(tr(
                        "Language catalog unavailable. Refresh to retry; "
                        "current checked outputs are preserved."));
                    return;
                }
                const QJsonDocument doc=QJsonDocument::fromJson(
                    languagePackWorker_.readAllStandardOutput());
                const QJsonObject info=doc.object();
                const QJsonArray catalog=info.value(
                    QLatin1String("languages")).toArray();
                if(catalog.isEmpty() && !info.contains(
                    QLatin1String("speech_languages"))) {
                    translationStatus_->setText(tr(
                        "No model catalog returned; previous language choices kept."));
                    return;
                }
                QSet<QString> selected;
                if(installedTargets_->count()>0) {
                    for(int i=0;i<installedTargets_->count();++i) {
                        const QListWidgetItem *item=installedTargets_->item(i);
                        if(item->checkState()==Qt::Checked)
                            selected.insert(item->data(Qt::UserRole).toString());
                    }
                } else {
                    QSettings preferences(QLatin1String("TIHULU"),
                                         QLatin1String("KaffeineRadio"));
                    const QStringList saved=preferences.value(
                        QLatin1String("radioOutputs"),
                        QStringList{QLatin1String("en"),QLatin1String("de"),
                                    QLatin1String("tr")}).toStringList();
                    for(const QString &code:saved) selected.insert(code);
                }
                {
                    const QSignalBlocker block(installedTargets_);
                    installedTargets_->clear();
                    QSet<QString> available;
                    for(const QJsonValue &value:catalog) {
                        const QJsonObject model=value.toObject();
                        const QString code=model.value(
                            QLatin1String("code")).toString();
                        if(!QRegularExpression(QLatin1String("^[a-z]{2,3}$"))
                           .match(code).hasMatch()) continue;
                        available.insert(code);
                        QStringList engines;
                        for(const QJsonValue &engine:model.value(
                            QLatin1String("engines")).toArray())
                            engines<<engine.toString();
                        auto *item=new QListWidgetItem(
                            code.toUpper()+QLatin1String(" · ")+
                            model.value(QLatin1String("label")).toString()+
                            QLatin1String(" · ")+engines.join(QLatin1String(" / ")),
                            installedTargets_);
                        item->setData(Qt::UserRole,code);
                        item->setFlags(item->flags()|Qt::ItemIsUserCheckable);
                        item->setCheckState(selected.contains(code)?
                            Qt::Checked:Qt::Unchecked);
                        item->setToolTip(tr(
                            "Installed/local model metadata, NOT verified "
                            "source-to-target inference. Online DeepL sends "
                            "text only with existing consent and API key."));
                    }
                    // Keep saved languages visible even if the translator
                    // catalog cannot find any compatible installed model.
                    for(const QString &code:selected) {
                        if(available.contains(code) || !QRegularExpression(
                            QLatin1String("^[a-z]{2,3}$"))
                            .match(code).hasMatch()) continue;
                        auto *item=new QListWidgetItem(
                            code.toUpper()+tr(" · selected · model not found"),
                            installedTargets_);
                        item->setData(Qt::UserRole,code);
                        item->setFlags(item->flags()|Qt::ItemIsUserCheckable);
                        item->setCheckState(Qt::Checked);
                        item->setToolTip(tr(
                            "You requested this output language, but no "
                            "installed translation model candidate was found. "
                            "Install a compatible model and refresh. "
                            "Unavailable text will never be invented."));
                    }
                }
                const QString previous=speechLanguage_->currentData().isValid()?
                    speechLanguage_->currentData().toString():
                    speechLanguage_->currentText().trimmed().toLower();
                const QJsonArray inputLanguages=info.value(
                    QLatin1String("speech_languages")).toArray();
                if(!inputLanguages.isEmpty()){
                    const QSignalBlocker block(speechLanguage_);
                    speechLanguage_->clear();
                    speechLanguage_->addItem(tr("Auto detect · Whisper (selected local model)"),"auto");
                    for(const QJsonValue &value:inputLanguages){
                        const QJsonObject entry=value.toObject();
                        const QString code=entry.value(
                            QLatin1String("code")).toString();
                        if(code.isEmpty()) continue;
                        speechLanguage_->addItem(
                            entry.value(QLatin1String("label")).toString()+
                            QLatin1String(" (")+code.toUpper()+QLatin1Char(')'),
                            code);
                    }
                    const int index=speechLanguage_->findData(previous);
                    speechLanguage_->setCurrentIndex(index>=0?index:0);
                }
                spokenModelStatus_->setText(info.value(
                    QLatin1String("speech_model_present")).toBool()?
                    tr("IN · Whisper model files found: %1. Listed spoken "
                       "languages use the selected multilingual model "
                       "(not installed one by one). Auto detect remains available.")
                        .arg(info.value(QLatin1String("speech_models_installed"))
                            .toArray().size()):
                    tr("IN · No local Whisper model found. Choose or install "
                       "one in Model Market. Auto detect is listed but "
                       "cannot run until a speech model is available."));
                translationStatus_->setText(tr(
                    "Selected TV/Radio translator: %1 · speech backend: %2. "
                    "%3 candidate outputs from installed model metadata. "
                    "Check up to six; inference is verified only during playback.")
                    .arg(info.value(QLatin1String("selected_translator"))
                            .toString(QLatin1String("unknown")),
                         info.value(QLatin1String("selected_speech_backend"))
                            .toString(QLatin1String("auto")))
                    .arg(installedTargets_->count()));
            });
        // Keep output selections stable across AI tab and station changes.
        connect(installedTargets_,&QListWidget::itemChanged,this,
            [this](QListWidgetItem *changed){
                if(!changed || changed->data(Qt::UserRole).toString().isEmpty())
                    return;
                QStringList selected;
                for(int i=0;i<installedTargets_->count();++i) {
                    QListWidgetItem *item=installedTargets_->item(i);
                    if(item->checkState()==Qt::Checked)
                        selected<<item->data(Qt::UserRole).toString();
                }
                if(selected.size()>6) {
                    const QSignalBlocker block(installedTargets_);
                    changed->setCheckState(Qt::Unchecked);
                    translationStatus_->setText(tr(
                        "Select at most six output languages."));
                    return;
                }
                QSettings preferences(QLatin1String("TIHULU"),
                                     QLatin1String("KaffeineRadio"));
                preferences.setValue(QLatin1String("radioOutputs"),selected);
                refreshRadioLanguageSummary();
                if(writeRadioLanguageControls() &&
                   captionProcess_.state()!=QProcess::NotRunning)
                    translationStatus_->setText(tr(
                        "Output languages updated LIVE. New selections "
                        "apply on the next decoded 5 s audio hop; no "
                        "Whisper or radio restart."));
            });
        connect(speechLanguage_,QOverload<int>::of(&QComboBox::currentIndexChanged),
            this,[this](int){
                QSettings settings(QLatin1String("TIHULU"),
                                   QLatin1String("KaffeineRadio"));
                settings.setValue(QLatin1String("radioSpeechLanguage"),
                    speechLanguage_->currentData().toString());
                refreshRadioLanguageSummary();
                writeRadioLanguageControls();
            });
        connect(extraTargets_,&QLineEdit::editingFinished,this,[this](){
            refreshRadioLanguageSummary();
            writeRadioLanguageControls();
        });
        connect(advancedLanguages_,&QCheckBox::toggled,this,[this](bool){
            refreshRadioLanguageSummary();
            writeRadioLanguageControls();
        });
		auto *syncControls=new QGridLayout();
		bufferMs_=new QSpinBox(lab);
		bufferMs_->setRange(0,60000);
		bufferMs_->setSingleStep(500);
		bufferMs_->setSuffix(tr(" ms"));
		QSettings radioSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		bufferMs_->setValue(qBound(0,
            radioSettings.value(QLatin1String("radioBufferDesiredMs"),
                radioSettings.value(QLatin1String("playbackBufferMs"),12000)).toInt(),
            60000));
        quickBuffer_->setChecked(
            radioSettings.value(QLatin1String("radioBufferEnabled"),false).toBool());
        quickBuffer_->setText(quickBuffer_->isChecked()?
            tr("Extra buffer · ON"):tr("Extra buffer · OFF"));
        // Legacy 12s network cache is intentionally NOT reenabled just
        // because an earlier installation had saved it. Preserve its
        // numeric preference for the next explicit user enable.
        activePlaybackCacheMs_=quickBuffer_->isChecked()?bufferMs_->value():0;
        radioSettings.setValue(QLatin1String("playbackBufferMs"),activePlaybackCacheMs_);
		bufferMs_->setToolTip(tr("Radio libVLC network cache requested at stream OPEN. "
            "Range 0–60000 ms (safety limit, 60 s). If changed during playback "
            "it remains PENDING until Apply or the next station; not verified "
            "physical DAC/ALSA delay."));
        autoSync_=new QCheckBox(tr("Auto size · ASR + safety"),page);
        autoSync_->setChecked(quickBuffer_->isChecked() &&
            radioSettings.value(QLatin1String("radioAutoBufferEnabled"),false).toBool());
        autoSync_->setToolTip(tr("Optional. Estimate extra playback cache from "
            "five-second speech capture, observed ASR/translation workload "
            "and a three-second margin. NOT a measured DAC clock or RF "
            "dropout detector. Does NOT restart live audio by default."));
        radioPlaybackRow_->insertWidget(1,autoSync_);
		radioOffsetMs_=new QSpinBox(lab);
		radioOffsetMs_->setRange(-12000,12000);
		radioOffsetMs_->setSingleStep(250);
		radioOffsetMs_->setSuffix(tr(" ms"));
		radioOffsetMs_->setValue(qBound(-12000,
			radioSettings.value(QLatin1String("captionOffsetMs"),0).toInt(),12000));
		radioOffsetMs_->setToolTip(tr("Positive: subtitles later; negative: earlier. "
			"Changes also shift pending cues without re-running Whisper."));
		autoRestartAudio_=new QCheckBox(tr("Allow automatic radio audio restart"),lab);
		autoRestartAudio_->setChecked(false);
		autoRestartAudio_->setToolTip(tr("OFF (recommended) never disrupts ongoing audio. "
            "When ON, a large compute-driven increase can reopen the stream "
            "at most once per 3 minutes. Restarting can still cause dropouts."));
		auto *applyBuffer=new QPushButton(tr("Apply radio buffer"),lab);
		syncControls->addWidget(new QLabel(tr("Audio buffer:"),lab),0,0);
		syncControls->addWidget(bufferMs_,0,1);
        bufferUnit_=new QComboBox(lab);
        bufferUnit_->addItem(tr("Milliseconds"),1);
        bufferUnit_->addItem(tr("Seconds"),1000);
        bufferUnit_->setToolTip(tr("Display and enter extra buffer in ms or s; "
            "saved setting remains milliseconds."));
        syncControls->addWidget(bufferUnit_,0,2);
		syncControls->addWidget(applyBuffer,0,3);
		syncControls->addWidget(new QLabel(tr("Caption offset:"),lab),1,0);
		syncControls->addWidget(radioOffsetMs_,1,1);
        syncControls->addWidget(new QLabel(tr(
            "Timing is estimated; no sound-card sample clock"),lab),1,2,1,2);
		syncControls->setColumnStretch(2,1);
        // Keep latency diagnostics available without turning the normal
        // caption/lyrics workflow into a wall of timing controls.
        auto *advancedSyncToggle=new QCheckBox(
            tr("Advanced · audio cache, timing & diagnostics"),lab);
        advancedSyncToggle->setChecked(false);
        auto *advancedSyncPanel=new QWidget(lab);
        auto *advancedSyncLayout=new QVBoxLayout(advancedSyncPanel);
        advancedSyncLayout->setContentsMargins(0,2,0,2);
        advancedSyncLayout->addLayout(syncControls);
        advancedSyncLayout->addWidget(autoRestartAudio_);
        connect(bufferUnit_,QOverload<int>::of(&QComboBox::currentIndexChanged),
            this,[this](int){
                const int previousMs=bufferMs_->value()*
                    (bufferUnitsSeconds_?1000:1);
                bufferUnitsSeconds_=(bufferUnit_->currentData().toInt()==1000);
                const QSignalBlocker block(bufferMs_);
                bufferMs_->setRange(0,bufferUnitsSeconds_?60:60000);
                bufferMs_->setSingleStep(bufferUnitsSeconds_?1:500);
                bufferMs_->setSuffix(bufferUnitsSeconds_?tr(" s"):tr(" ms"));
                bufferMs_->setValue(bufferUnitsSeconds_?
                    qBound(0,(previousMs+500)/1000,60):
                    qBound(0,previousMs,60000));
            });
        advancedSyncPanel->setVisible(false);
        connect(advancedSyncToggle,&QCheckBox::toggled,
                advancedSyncPanel,&QWidget::setVisible);
        v->addWidget(advancedSyncToggle);
        v->addWidget(advancedSyncPanel);
        lastCaptionOffsetMs_=radioOffsetMs_->value();
        const auto updateOffsetReadout=[this](){
            if(captionOffsetReadout_) captionOffsetReadout_->setText(
                tr("Offset %1%2 ms")
                .arg(radioOffsetMs_->value()>=0?QLatin1String("+"):QString())
                .arg(radioOffsetMs_->value()));
        };
        updateOffsetReadout();
        connect(captionEarlier_,&QPushButton::clicked,this,[this](){
            radioOffsetMs_->setValue(qMax(-12000,radioOffsetMs_->value()-250));
        });
        connect(captionLater_,&QPushButton::clicked,this,[this](){
            radioOffsetMs_->setValue(qMin(12000,radioOffsetMs_->value()+250));
        });
        connect(radioOffsetMs_,QOverload<int>::of(&QSpinBox::valueChanged),
            this,[updateOffsetReadout](int){ updateOffsetReadout(); });
		connect(radioOffsetMs_,QOverload<int>::of(&QSpinBox::valueChanged),
			this,[this](int newOffset){
				QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
				saved.setValue(QLatin1String("captionOffsetMs"),newOffset);
				const int adjustment=newOffset-lastCaptionOffsetMs_;
				lastCaptionOffsetMs_=newOffset;
				for(auto &cue:cueQueue_) cue.dueMs+=adjustment;
			});
		syncStatus_=new QLabel(tr("Sync: requested playback cache %1 ms, "
            "unverified physical audio clock. No automatic audio restarts.")
            .arg(activePlaybackCacheMs_),lab);
		syncStatus_->setWordWrap(true);
        advancedSyncLayout->addWidget(syncStatus_);
		audioCacheProgress_=new QProgressBar(lab);
		audioCacheProgress_->setRange(0,100);
		audioCacheProgress_->setValue(0);
		audioCacheProgress_->setFormat(tr("Requested audio cache · not started"));
		audioCacheProgress_->setToolTip(tr("Estimated time since opening a stream, NOT "
			"verified buffer fill, actual DAC output clock or lip sync."));
        advancedSyncLayout->addWidget(audioCacheProgress_);
		bufferRecommendation_=new QLabel(tr("Buffer recommendation: awaiting real ASR timing"),lab);
		bufferRecommendation_->setWordWrap(true);
        advancedSyncLayout->addWidget(bufferRecommendation_);
		captionProgress_=new QProgressBar(lab);
		captionProgress_->setRange(0,100);
		captionProgress_->setValue(0);
		captionProgress_->setFormat(tr("Caption timeline · waiting for decoded audio"));
		captionProgress_->setToolTip(tr("Estimated time to hear the decoded phrase. "
			"Audio cache is requested, not independently measured at the sound card."));
        captionProgress_->setVisible(false);
        // Progress belongs next to the actual radio subtitle overlay,
        // not underneath all Model Market / language settings. Hide it
        // completely while ASR is off.
        rightLayout->addWidget(captionProgress_);
        connect(applyBuffer,&QPushButton::clicked,this,[this](){ applyRadioBuffer(); });
        connect(quickBuffer_,&QCheckBox::toggled,this,[this](bool enabled){
            quickBuffer_->setText(enabled?
                tr("Extra audio buffer · ON"):tr("Extra audio buffer · OFF"));
            if(!enabled && autoSync_->isChecked()) {
                const QSignalBlocker block(autoSync_);
                autoSync_->setChecked(false);
            }
            QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
            saved.setValue(QLatin1String("radioBufferEnabled"),enabled);
            saved.setValue(QLatin1String("radioAutoBufferEnabled"),autoSync_->isChecked());
            if(active() && !playingKey_.isEmpty()) applyRadioBuffer();
            else {
                activePlaybackCacheMs_=0;
                saved.setValue(QLatin1String("playbackBufferMs"),0);
            }
            refreshRadioBufferProgress();
        });
        connect(autoSync_,&QCheckBox::toggled,this,[this](bool enabled){
            QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
            if(enabled && !quickBuffer_->isChecked()) {
                // Never reopen with a legacy 12s setting just for Auto.
                // Start from zero EXTRA delay and measure real ASR first.
                // Save recommendation for next tune or explicit Apply.
                const QSignalBlocker block(quickBuffer_);
                quickBuffer_->setChecked(true);
                quickBuffer_->setText(tr("Extra audio buffer · ON"));
                setBufferDisplayMs(0);
                saved.setValue(QLatin1String("radioBufferEnabled"),true);
                saved.setValue(QLatin1String("radioBufferDesiredMs"),0);
            }
            saved.setValue(QLatin1String("radioAutoBufferEnabled"),enabled);
            bufferRecommendation_->setText(enabled?
                tr("Auto estimate enabled · measuring Whisper latency. "
                   "No forced radio restart; next tune uses the estimate "
                   "or choose Apply buffer now."):
                tr("Auto estimate OFF · buffer controlled manually."));
            refreshRadioBufferProgress();
        });
		auto *captionActions=new QHBoxLayout();
		captionActions->addStretch(1);
		captionActions->addWidget(caption_);
        captionActions->addWidget(applyCaptions_);
		captionActions->addWidget(stopCaption_);
		v->addLayout(captionActions);
		radioCaption_ = new QLabel(tr("Radio AI is OFF; it never starts without your request."), lab);
		radioCaption_->setTextFormat(Qt::PlainText);
		radioCaption_->setWordWrap(true);
		v->addWidget(radioCaption_);
		auto *lyricsRow = new QGridLayout();
		lyrics_ = new QPushButton(tr("Find lyrics (timed OR plain, optional online)"), lab);
		lyricsImport_=new QPushButton(tr("Import local TXT / LRC"),lab);
		lyricsImport_->setToolTip(tr("Use your own legally obtained lyric file. "
			"Plain TXT lines can be matched to audible Whisper speech; "
			"timed LRC can be rechecked against actual vocals."));
		lyricsArtist_=new QLineEdit(lab);
		lyricsArtist_->setPlaceholderText(tr("Artist correction (optional)"));
		lyricsTitle_=new QLineEdit(lab);
		lyricsTitle_->setPlaceholderText(tr("Song title correction (optional)"));
		lyricsArtist_->setMaximumWidth(240);
		lyricsTitle_->setMaximumWidth(320);
		stopLyrics_=new QPushButton(tr("Stop lyrics / listening"),lab);
		stopLyrics_->setEnabled(false);
        listenLyrics_=new QPushButton(tr("Listen & transcribe vocals offline"),lab);
        listenLyrics_->setToolTip(tr("Use the playing DAB audio with Whisper "
            "singing mode, without online metadata. Heard words are "
            "approximate, not synchronized reference lyrics."));
        listenFallbackOnMiss_=new QCheckBox(tr("On miss: listen offline"),lab);
        listenFallbackOnMiss_->setChecked(true);
        listenFallbackOnMiss_->setToolTip(tr("After an authorized lyrics search "
            "returns no matching text, fall back to local audio transcription. "
            "No radio audio is sent to online lyrics services."));
		lyricsOffset_ = new QSlider(Qt::Horizontal, lab);
		lyricsOffset_->setRange(-90000, 90000);
		lyricsOffset_->setValue(0);
		lyricsOffset_->setToolTip(tr("Manual lyric sync offset, milliseconds (-90s to +90s)."));
		autoLyrics_=new QCheckBox(tr("Auto search lyrics on new DLS song"),lab);
		autoLyrics_->setChecked(false);
		autoLyrics_->setToolTip(tr("OFF by default. When enabled, the current radio DLS "
			"artist/title is sent to LRCLIB on each new song. No audio or private RF data are uploaded."));
		connect(autoLyrics_,&QCheckBox::toggled,this,[this](bool enabled){
			if(enabled && active() && !playingKey_.isEmpty() &&
			   !lyricsEnabled_ && lastDls_.contains(QLatin1String(" - ")))
				QTimer::singleShot(100,this,[this](){fetchLyrics(true);});
		});
		autoLyricSync_=new QCheckBox(tr("Auto lyric timing (DLS estimate)"),lab);
		autoLyricSync_->setChecked(true);
		autoLyricSync_->setToolTip(tr("Use song metadata change and requested audio "
			"buffer as an estimated timeline, not a verified sound-card timebase."));
		preferLyrics_=new QCheckBox(tr("Prefer matched lyrics / hide uncertain sung words"),lab);
		preferLyrics_->setChecked(true);
        preferLyrics_->setToolTip(tr(
            "Prefer actual retrieved and audio-matched lyric lines. "
            "Unverified sung words are not invented or shown as [music] "
            "in the on-screen radio caption. Presenter speech is unaffected."));
        lyricsSourceLanguage_=new QComboBox(lab);
        lyricsSourceLanguage_->addItem(
            tr("Auto · wait for confirmed sung audio language"),QLatin1String("auto"));
        const QStringList lyricSources={"de","en","tr","fr","es","it","pl","ar","ja","pt"};
        for(const QString &lang:lyricSources)
            lyricsSourceLanguage_->addItem(lang.toUpper(),lang);
        lyricsSourceLanguage_->setToolTip(tr(
            "Independent song lyric language. Explicitly choose it for immediate "
            "translation of retrieved lyrics; Auto never reuses an unverified "
            "presenter's language for the singer."));
		lyricsOffsetValue_=new QLabel(tr("Offset: +0.00 s"),lab);
		lyricsOffsetValue_->setMinimumWidth(120);
		lyricsOffsetValue_->setToolTip(tr("Signed manual correction in seconds "
			"(+ delays lyrics; - displays earlier)."));
		lyricsSyncState_=new QLabel(tr("Audio lyric sync: no verified vocal match"),lab);
		lyricsSyncState_->setWordWrap(true);
		connect(lyricsOffset_,&QSlider::valueChanged,this,[this](int value){
			lyricsOffsetValue_->setText(
				tr("Offset: %1%2 s").arg(value>=0?QLatin1String("+"):QString())
				.arg(QString::number(value/1000.,'f',2)));
			const int delta=value-lastLyricOffsetMs_;
			lastLyricOffsetMs_=value;
			for(auto &cue:plainLyricQueue_) cue.dueMs+=delta;
		});
		lyricsRow->addWidget(lyrics_,0,0);
		lyricsRow->addWidget(stopLyrics_,0,1);
		radioPlaybackRow_->insertWidget(2,autoLyrics_);
        autoLyrics_->setText(tr("Auto lyrics · online opt-in"));
        lyricsRow->addWidget(listenLyrics_,5,0,1,2);
        lyricsRow->addWidget(listenFallbackOnMiss_,5,2);
		lyricsRow->addWidget(autoLyricSync_,1,0,1,2);
		lyricsRow->addWidget(new QLabel(tr("Lyric timing:"), lab),1,2);
		lyricsRow->addWidget(lyricsOffset_,2,0,1,2);
		lyricsRow->addWidget(lyricsOffsetValue_,2,2);
		lyricsRow->addWidget(lyricsImport_,3,0);
		lyricsRow->addWidget(lyricsArtist_,3,1);
		lyricsRow->addWidget(lyricsTitle_,3,2);
        lyricsRow->addWidget(new QLabel(tr("Song lyric language:"),lab),4,0);
        lyricsRow->addWidget(lyricsSourceLanguage_,4,1,1,2);
		lyricsRow->setColumnStretch(1,1);
        v->addWidget(new QLabel(tr(
            "<b>3 · Lyrics</b> · optional; no search until you choose Find lyrics"),lab));
        auto *quickLyrics=new QPushButton(tr("Find lyrics for current song"),lab);
        v->addWidget(quickLyrics);
        auto *showLyricsOptions=new QCheckBox(
            tr("Advanced · lyrics source, timing, import and auto search"),lab);
        showLyricsOptions->setChecked(false);
        // A quick lookup must expose Stop lyrics while it is active.
        connect(quickLyrics,&QPushButton::clicked,this,[this,showLyricsOptions](){
            showLyricsOptions->setChecked(true);
            fetchLyrics();
        });
        v->addWidget(showLyricsOptions);
        auto *lyricsPanel=new QWidget(lab);
        auto *lyricsLayout=new QVBoxLayout(lyricsPanel);
        lyricsLayout->setContentsMargins(0,2,0,2);
        lyricsLayout->addLayout(lyricsRow);
        lyricsLayout->addWidget(lyricsSyncState_);
        lyricsLayout->addWidget(preferLyrics_);
        lyricsPanel->setVisible(false);
        connect(showLyricsOptions,&QCheckBox::toggled,
                lyricsPanel,&QWidget::setVisible);
        v->addWidget(lyricsPanel);
        lyricProvider_=new QLabel(tr("Sources: LRCLIB; lyrics.ovh; optional "
            "licensed Musixmatch API. Plain text must match heard audio."),lab);
        lyricProvider_->setWordWrap(true);
        lyricProvider_->setTextFormat(Qt::PlainText);
        v->addWidget(lyricProvider_);
		lyricText_ = new QLabel(tr("No synchronized lyrics loaded."), lab);
		lyricText_->setTextFormat(Qt::PlainText);
		lyricText_->setWordWrap(true);
		v->addWidget(lyricText_);
		modes_->addTab(lab,tr("AI subtitles / lyrics"));
        connect(quickLanguageButton_,&QPushButton::clicked,this,[this,lab](){
            modes_->setCurrentWidget(lab);
            installedTargets_->setFocus();
        });
        refreshRadioLanguageSummary();

		auto *diagnosticCard = new QGroupBox(tr("DAB receiver diagnostics / welle.io"),this);
		auto *diagnosticLayout=new QVBoxLayout(diagnosticCard);
		auto *diagnostics = new QGridLayout();
		plotKind_ = new QComboBox(this);
		plotKind_->addItem(tr("Spectrum"), "spectrum");
		plotKind_->addItem(tr("Waterfall"), "waterfall");
		plotKind_->addItem(tr("Null spectrum"), "nullspectrum");
		plotKind_->addItem(tr("CIR / impulse response"), "impulseresponse");
		plotKind_->addItem(tr("Constellation phase"), "constellation");
		fftPlacement_ = new QComboBox(this);
		fftPlacement_->addItem(tr("FFT earliest"),QLatin1String("EarliestPeakWithBinning"));
		fftPlacement_->addItem(tr("FFT strongest"),QLatin1String("StrongestPeak"));
		fftPlacement_->addItem(tr("FFT threshold"),QLatin1String("ThresholdBeforePeak"));
		fftPlacement_->setToolTip(tr("Original welle.io FFT synchronization placement; "
			"changes are applied only on explicit click."));
		coarseCorrector_ = new QCheckBox(tr("Coarse correction"),this);
		coarseCorrector_->setChecked(true);
		coarseCorrector_->setToolTip(tr("Toggle welle.io coarse frequency corrector "
			"using the local receiver only."));
		plot_ = new QLabel(tr("On-demand RF plots"), this);
		plot_->setMinimumSize(200,110);
        plot_->setMaximumHeight(110);
        plot_->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Fixed);
		plot_->setAlignment(Qt::AlignCenter);
		plot_->setStyleSheet(QLatin1String("border:1px solid #456;"));
		auto *plotButton = new QPushButton(tr("Capture RF plot"), this);
		livePlot_=new QCheckBox(tr("Live RF"),this);
		livePlot_->setToolTip(tr("Update spectrum/waterfall every 1.6 seconds while enabled"));
		showWidgets_=new QCheckBox(tr("Show welle.io RF widgets"),this);
		showWidgets_->setChecked(false);
		multiRf_=new QCheckBox(tr("Multi-widget live RF dashboard"),this);
		multiRf_->setChecked(false);
		multiRf_->setToolTip(tr("Rotate real welle.io receiver samples across spectrum, "
			"waterfall and constellation without blocking the GUI. "
			"Requires DAB SDR; does not show invented values."));
		auto *detailsButton = new QPushButton(tr("Receiver / TII details"),this);
		auto *applyRf = new QPushButton(tr("Apply RF options"),this);
		diagnostics->addWidget(plotKind_,0,0);
        diagnostics->addWidget(plotButton,0,1);
        diagnostics->addWidget(livePlot_,0,2);
        diagnostics->addWidget(plot_,1,0,1,3);
        diagnostics->setColumnStretch(0,1);
		diagnosticLayout->addLayout(diagnostics);
		diagnosticLayout->addWidget(multiRf_);
		multiPanel_=new QWidget(diagnosticCard);
		auto *multiGrid=new QGridLayout(multiPanel_);
		const QStringList kinds={tr("Live spectrum"),tr("Live waterfall"),
			tr("Live constellation")};
		for(int i=0;i<3;++i) {
			auto *frame=new QWidget(multiPanel_);
			auto *column=new QVBoxLayout(frame);
			column->setContentsMargins(2,2,2,2);
			column->addWidget(new QLabel(kinds[i],frame));
			auto *image=new QLabel(tr("Waiting for real RF samples"),frame);
			image->setMinimumSize(180,110);
            image->setMaximumHeight(110);
            image->setSizePolicy(QSizePolicy::Expanding,QSizePolicy::Fixed);
			image->setAlignment(Qt::AlignCenter);
			image->setStyleSheet(QLatin1String("border:1px solid #456;"));
			column->addWidget(image);
			multiPlots_.append(image);
			multiGrid->addWidget(frame,i/2,i%2);
		}
		multiPanel_->setVisible(false);
		diagnosticLayout->addWidget(multiPanel_);
		auto *rfOptions=new QGridLayout();
		rfOptions->addWidget(fftPlacement_,0,0);
        rfOptions->addWidget(coarseCorrector_,0,1);
        rfOptions->addWidget(applyRf,1,0);
        rfOptions->addWidget(detailsButton,1,1);
        rfOptions->setColumnStretch(0,1);
		diagnosticLayout->addLayout(rfOptions);
        auto *rfPage=new QWidget(modes_);
        auto *rfLayout=new QVBoxLayout(rfPage);
        rfLayout->setContentsMargins(5,5,5,5);
        rfLayout->addWidget(showWidgets_);
        rfLayout->addWidget(diagnosticCard);
        modes_->addTab(rfPage,tr("RF Lab · advanced"));
		diagnosticCard->setVisible(false);
		connect(showWidgets_,&QCheckBox::toggled,diagnosticCard,&QWidget::setVisible);
		connect(multiRf_,&QCheckBox::toggled,this,[this](bool enabled){
			multiPanel_->setVisible(enabled);
			if(enabled) {
				showWidgets_->setChecked(true);
				livePlot_->setChecked(true);
			}
			if(enabled) rfTick_.start();
			else rfTick_.stop();
		});

		connect(start_, &QPushButton::clicked, this, [this](){ startReceiver(); });
        connect(stop_, &QPushButton::clicked, this, [this](){ stopRadioListening(); });
        connect(forceRelease_,&QPushButton::clicked,this,[this](){
            stopReceiver();
            state_->setText(active()?
                tr("Radio Stop requested, but welle-cli has not exited; "
                   "the SDR may still be in use. Check the receiver PID."):
                tr("Radio stopped · TIHULU released its DAB receiver. "
                   "Other applications may now claim the device."));
            updateReceiverOwnership();
        });
        connect(releaseOnStop_,&QCheckBox::toggled,this,[this](bool enabled){
            QSettings settings(QLatin1String("TIHULU"),
                               QLatin1String("KaffeineRadio"));
            settings.setValue(QLatin1String("releaseSdrOnStop"),enabled);
            updateReceiverOwnership();
        });
		connect(record_, &QPushButton::clicked, this, [this](){ toggleRecording(); });
		connect(&recordAi_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int result,QProcess::ExitStatus status){
				const QString srt=QFileInfo(recordedPath_).absolutePath()+QLatin1Char('/')+
					QFileInfo(recordedPath_).completeBaseName()+QLatin1String(".srt");
				if(result!=0 || status!=QProcess::NormalExit || !QFileInfo(srt).isFile()){
					state_->setText(tr("Recording preserved, offline SRT failed: %1")
						.arg(QString::fromUtf8(recordAi_.readAllStandardError()).right(180)));
					return;
				}
				const QString output=QFileInfo(recordedPath_).absolutePath()+QLatin1Char('/')+
					QFileInfo(recordedPath_).completeBaseName()+QLatin1String("-subtitled.mkv");
				if(QFileInfo(output).exists()) {
					state_->setText(tr("SRT saved; subtitled MKV destination already exists. "
						"Existing files will not be overwritten."));
					return;
				}
				recordMux_.start(QLatin1String("ffmpeg"),
					{QLatin1String("-nostdin"),QLatin1String("-hide_banner"),
					 QLatin1String("-loglevel"),QLatin1String("error"),
					 QLatin1String("-n"),QLatin1String("-i"),recordedPath_,
					 QLatin1String("-i"),srt,
					 QLatin1String("-map"),QLatin1String("0:a:0"),
					 QLatin1String("-map"),QLatin1String("1:0"),
					 QLatin1String("-c:a"),QLatin1String("copy"),
					 QLatin1String("-c:s"),QLatin1String("srt"),output});
				state_->setText(tr("Offline SRT generated; creating MKV with subtitle track…"));
			});
		connect(&recordMux_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int result,QProcess::ExitStatus status){
				state_->setText(result==0 && status==QProcess::NormalExit?
					tr("Subtitled recording complete. Audio, SRT and MKV saved.") :
					tr("Recorded audio and SRT saved; MKV mux failed (check FFmpeg)."));
			});
		connect(scan_, &QPushButton::clicked, this, [this](){ beginScan(); });
		connect(webSearchButton_, &QPushButton::clicked, this, [this](){ searchInternetRadio(); });
		connect(webCountry_,QOverload<int>::of(&QComboBox::activated),
			this,[this](int){
				QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
				saved.setValue(QLatin1String("webCountry"),webCountry_->currentData());
				searchInternetRadio();
			});
		connect(webSearch_, &QLineEdit::returnPressed, this, [this](){ searchInternetRadio(); });
		connect(webPlay_, &QPushButton::clicked, this, [this](){ playInternetRadio(webSource_->text()); });
		connect(webProbeButton_, &QPushButton::clicked, this,[this](){probeInternetRadio();});
		connect(webAlternate_,&QPushButton::clicked,this,[this](){
			QTreeWidgetItem *current=webStations_->currentItem();
			if(!current) { webStatus_->setText(tr("Choose a directory station first."));return; }
			const QString fallback=current->data(1,Qt::UserRole+1).toString();
			const QUrl url(fallback);
			if(!url.isValid() || url.host().isEmpty() ||
			   (url.scheme()!=QLatin1String("http") &&
			    url.scheme()!=QLatin1String("https")) ||
			   fallback==current->data(1,Qt::UserRole).toString()) {
				webStatus_->setText(tr("No different valid alternate station URL."));
				return;
			}
			webSource_->setText(fallback);
			playInternetRadio(fallback);
			webStatus_->setText(tr("Trying original directory URL. "
				"Use Test stream to inspect its decoder/audio availability."));
		});
		connect(&internetProbe_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int code,QProcess::ExitStatus status){
				webProbeButton_->setEnabled(true);
				if(webSource_->text().trimmed()!=testedWebUrl_) return;
				const QByteArray bytes=internetProbe_.readAllStandardOutput();
				const QJsonDocument doc=QJsonDocument::fromJson(bytes);
				QStringList audioCodecs;
				for(const auto &entry:doc.object().value(QLatin1String("streams")).toArray()){
					const auto stream=entry.toObject();
					if(stream.value(QLatin1String("codec_type")).toString()!=QLatin1String("audio")) continue;
					const QString codec=stream.value(QLatin1String("codec_name")).toString();
					if(!codec.isEmpty()) audioCodecs<<codec;
				}
				if(code==0 && status==QProcess::NormalExit && !audioCodecs.isEmpty()) {
					webStatus_->setText(tr("URL provides audio codecs: %1. "
						"FFprobe succeeded, but live VLC playback still depends on station availability.")
						.arg(audioCodecs.join(QLatin1String(", "))));
				} else {
					const QString problem=QString::fromLocal8Bit(
						internetProbe_.readAllStandardError()).right(260);
					webStatus_->setText(tr("Station stream could not be decoded: %1")
						.arg(problem.isEmpty()?tr("timeout / no audio stream"):problem));
				}
			});
		connect(webSource_, &QLineEdit::returnPressed, this, [this](){ playInternetRadio(webSource_->text()); });
		connect(webStop_, &QPushButton::clicked, this, [this](){ stopInternetRadio(); });
		connect(webStations_, &QTreeWidget::itemDoubleClicked, this,
			[this](QTreeWidgetItem *item, int column) {
				if (column != 0 && item)
					playInternetRadio(item->data(1,Qt::UserRole).toString());
			});
		connect(webStations_, &QTreeWidget::itemClicked, this,
			[this](QTreeWidgetItem *item, int column) {
				if (column == 0 && item) toggleInternetFavorite(item);
				else if (item) {
                    webSource_->setText(item->data(1,Qt::UserRole).toString());
                    showSelectedSource(item->text(1),tr("Internet radio · selected"),
                        tr("Internet stream · no FM frequency"));
                }
			});
		connect(webFavoritesOnly_, &QCheckBox::toggled, this,
			[this](){ filterInternetStations(); });
		QSettings webSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		for (const QString &url : webSettings.value(QLatin1String("internetFavorites")).toStringList())
			internetFavorites_.insert(url);
		connect(stations_, &QTreeWidget::itemDoubleClicked, this,
			[this](QTreeWidgetItem *item, int column){
				if (column!=0) selectStation(item);
			});
		connect(stations_, &QTreeWidget::itemClicked, this,
			[this](QTreeWidgetItem *item, int column){
				if(!item)return;
                if(column==0)toggleFavorite(item);
                else showSelectedSource(item->text(1),tr("DAB+ · selected"),
                    tr("Block %1 · %2 · SID %3 · double-click to tune")
                        .arg(item->text(2),dabCenterFrequencyMHz(item->text(2)),
                             item->text(3)));
			});
		connect(stationSearch_, &QLineEdit::textChanged,this,
			[this](){ filterStations(); });
		connect(libraryBlock_,QOverload<int>::of(&QComboBox::currentIndexChanged),
			this,[this](){ filterStations(); });
		connect(favoritesOnly_,&QCheckBox::toggled,this,
			[this](){ filterStations(); });
		connect(quickAi_,&QCheckBox::toggled,this,[this](bool enabled){
            quickAi_->setText(enabled?tr("AI captions · ON"):tr("AI captions · OFF"));
            if(enabled) {
                if(active() && !playingKey_.isEmpty()) startCaptioning();
                else radioCaptionBanner_->setText(tr(
                    "AI armed for the next station. No speech processing "
                    "until a DAB station is playing."));
            } else {
                stopCaptioning();
                if(captionProgress_) captionProgress_->setVisible(false);
                radioCaptionBanner_->setText(tr("Live radio AI OFF · audio only"));
            }
        });
        connect(caption_, &QPushButton::clicked, this, [this](){
            if(!quickAi_->isChecked()) quickAi_->setChecked(true);
            else startCaptioning();
        });
        connect(applyCaptions_,&QPushButton::clicked,this,[this](){
            if(!quickAi_->isChecked()) {
                radioCaption_->setText(tr("AI is OFF. Choose Start captions "
                    "or enable the AI switch first."));
                return;
            }
            if(captionProcess_.state()!=QProcess::NotRunning) stopCaptioning();
            cueQueue_.clear();
            lastRadioChunk_=-1; lastRadioRevision_=-1;
            displayedRadioChunk_=-1;
            startCaptioning();
            radioCaptionBanner_->setText(tr("Applying local caption options; "
                "waiting for a new real audio segment…"));
        });
		connect(stopCaption_, &QPushButton::clicked, this, [this](){
            const QSignalBlocker block(quickAi_);
            quickAi_->setChecked(false);
            quickAi_->setText(tr("AI captions · OFF"));
            const bool lyricOnly=lyricsAudioFallbackActive_;
            if(lyricOnly) {
                lyricsAudioFallbackActive_=false;
                lyricsFallbackStartedAi_=false;
                lyricText_->setText(tr("Offline lyric listening stopped."));
            }
            stopCaptioning();
            radioCaptionBanner_->setText(tr("Live radio captions stopped."));
            lastCaptionVisibleMs_=0;
        });
        connect(&captionProcess_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
            this,[this](int code,QProcess::ExitStatus exitState){
                if(captionsStopping_) return;
                if(code==0 && exitState==QProcess::NormalExit) {
                    // An EOF from the AI-only welle HTTP client is not the
                    // same as verified silence or a healthy ASR session.
                    if(active() && !playingKey_.isEmpty()) {
                        const QString note=tr(
                            "Radio AI audio stream ended. Check welle HTTP "
                            "and ffmpeg; station playback has a separate "
                            "libVLC path and may still be running.");
                        radioCaption_->setText(note);
                        radioTranslationBanner_->setText(note);
                        radioTranslationBanner_->setVisible(true);
                    }
                    return;
                }
                const QString error=QString::fromLocal8Bit(
                    captionProcess_.readAllStandardError()).right(200);
                const QString message=tr("Live radio Whisper stopped unexpectedly. "
                    "Check the installed AI model, DAB stream and ffmpeg. %1")
                    .arg(error.isEmpty()?tr("No decoder details"):error);
                radioCaption_->setText(message);
                radioCaptionBanner_->setText(message);
                if(lyricsAudioFallbackActive_) lyricText_->setText(message);
            });
		connect(lyrics_, &QPushButton::clicked, this, [this](){ fetchLyrics(); });
		connect(lyricsImport_,&QPushButton::clicked,this,[this](){
			const QString path=QFileDialog::getOpenFileName(
				this,tr("Import your plain text or timed song lyrics"),QString(),
				tr("Lyric files (*.txt *.lrc)"));
			if(path.isEmpty()) return;
			stopLyrics();
			const QString runtime=QStandardPaths::writableLocation(
				QStandardPaths::RuntimeLocation);
			if(runtime.isEmpty()) {
				lyricText_->setText(tr("Cannot import: private runtime directory missing."));
				return;
			}
			lyricPath_=runtime+QLatin1String("/tihulu-radio-lyrics-")+
				QString::number(QCoreApplication::applicationPid())+QLatin1String(".json");
			QFile::remove(lyricPath_);
			lyricsEnabled_=true;
			lyricLoaded_=false;
			lyricsProcess_.start(QLatin1String("tihulu-tv-center"),{
				QLatin1String("lyrics-import"),QLatin1String("--file"),path,
				QLatin1String("--output"),lyricPath_});
			if(!lyricsProcess_.waitForStarted(900)) {
				lyricsEnabled_=false;
				lyricText_->setText(tr("Local lyrics companion failed to start."));
				return;
			}
			lyrics_->setEnabled(false);
			stopLyrics_->setEnabled(true);
			lyricText_->setText(tr("Importing plain TXT / timed LRC; no network lookup."));
		});
		connect(stopLyrics_, &QPushButton::clicked, this, [this](){ stopLyrics(); });
        connect(listenLyrics_,&QPushButton::clicked,this,[this](){
            beginLyricListening();
        });
		connect(slidePrev_,&QPushButton::clicked,this,[this](){slideMove(-1);});
		connect(slideNext_,&QPushButton::clicked,this,[this](){slideMove(1);});
		connect(plotButton, &QPushButton::clicked, this, [this](){ fetchPlot(); });
		connect(applyRf, &QPushButton::clicked, this, [this](){ applyRfOptions(); });
		connect(detailsButton, &QPushButton::clicked, this, [this](){ showReceiverDetails(); });
		connect(&backend_, &QProcess::readyReadStandardError, this, [this]() {
            const QString tail=QString::fromUtf8(backend_.readAllStandardError());
            if(!tail.trimmed().isEmpty()) lastWelleError_=tail.trimmed().right(600);
            const bool busy=tail.contains(QLatin1String("busy"),Qt::CaseInsensitive) ||
                tail.contains(QLatin1String("No device"),Qt::CaseInsensitive) ||
                tail.contains(QLatin1String("usb_claim"),Qt::CaseInsensitive) ||
                tail.contains(QLatin1String("Failed to open"),Qt::CaseInsensitive);
            if(busy) state_->setText(tr("DAB RTL-SDR not accessible · %1")
                .arg(apiFailureDetails()));
            else if(tail.contains(QLatin1String("Cannot")) ||
                    tail.contains(QLatin1String("Failed")))
                state_->setText(tail.right(250));
        });
        connect(&backend_,&QProcess::errorOccurred,this,[this](QProcess::ProcessError){
            lastWelleError_=backend_.errorString().right(600);
            if(!shuttingDown_) state_->setText(
                tr("welle-cli process failure: %1 · no RF measurement")
                .arg(lastWelleError_));
        });
		connect(&backend_, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
			this, [this](int exitCode, QProcess::ExitStatus){
                if(!shuttingDown_)
                    lastWelleError_=tr("welle-cli exited (%1) · %2")
                        .arg(exitCode).arg(lastWelleError_).right(600);
				stopCaptioning();
				tick_.stop();
                apiReady_=false;
                scanning_=false;
                scan_->setEnabled(true);
                scanProgress_->setValue(0);
                scanProgress_->setFormat(tr("Scan stopped: receiver exited"));
                scanSNR_->setValue(0);
                scanSNR_->setFormat(tr("DAB SNR NOT MEASURED · welle-cli exited"));
                rfQuality_->setValue(0);
                rfQuality_->setFormat(tr("DAB RF unmeasured · receiver exited"));
                lastMux_=QJsonObject();
                dabPlaybackObserved_=false;
                dabIdleSinceMs_=0;
                updateReceiverOwnership();
				if (!shuttingDown_) state_->setText(tr("welle-cli stopped (%1): %2")
                    .arg(exitCode).arg(lastWelleError_));
			});
		tick_.setInterval(1400);
		// Audio captions no longer wait for the expensive 1600-ms RF poll.
		captionTick_.setInterval(300);
		connect(&captionTick_,&QTimer::timeout,this,[this](){
            monitorRadioPlaybackStop();
			pollCaption();updateLyrics();
            refreshRadioBufferProgress();
		});
		captionTick_.start();
		rfTick_.setInterval(300);
		connect(&rfTick_,&QTimer::timeout,this,[this](){
			if(!active() || plotPending_) return;
			if(multiRf_->isChecked() && multiPlots_.size()==3) {
				const QStringList kinds={
					QLatin1String("spectrum"),QLatin1String("waterfall"),
					QLatin1String("constellation")};
				const int index=(multiRfIndex_++)%3;
				fetchPlot(kinds[index],multiPlots_.at(index));
			} else if(livePlot_->isChecked()) {
				fetchPlot();
			}
		});
		connect(livePlot_,&QCheckBox::toggled,this,[this](bool enabled){
			if(enabled || multiRf_->isChecked()) rfTick_.start();
			else rfTick_.stop();
		});
		connect(&tick_, &QTimer::timeout, this, [this](){pollMux();});
        QSettings uiSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
        modes_->setCurrentIndex(qBound(0,uiSettings.value(
            QLatin1String("radioModeTab"),0).toInt(),modes_->count()-1));
        connect(modes_,&QTabWidget::currentChanged,this,[](int tab){
            QSettings config(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
            config.setValue(QLatin1String("radioModeTab"),tab);
        });
		loadStations();
		stations_->sortItems(1,Qt::AscendingOrder);
		filterStations();
	}

	~TihuluRadioTab() override { stopReceiver(); }

	void activate() override {
		// Never move the shared video MediaWidget into this radio panel.
		radioCanvas_->setFocus();
		if(!languagePacksLoaded_) {
			languagePacksLoaded_=true;
			QTimer::singleShot(0,this,[this](){refreshLanguagePacks();});
		}
		if(!webCatalogRequested_) {
			webCatalogRequested_=true;
			QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
			const QString preference=saved.value(QLatin1String("webCountry")).toString();
			const int index=webCountry_->findData(preference);
			webCountry_->setCurrentIndex(index>=0?index:0);
			QTimer::singleShot(100,this,[this](){searchInternetRadio();});
		}
	}

protected:
    void resizeEvent(QResizeEvent *event) override {
        TabBase::resizeEvent(event);
        if(stationSplit_)
            stationSplit_->setOrientation(width()<930?Qt::Vertical:Qt::Horizontal);
    }
public:
    // Native hardware operations stop only processes owned by this tab.
    // Never unbind USB drivers or terminate unrelated SDR applications.
    bool hardwareDabOwned() const {
        return backend_.state()!=QProcess::NotRunning;
    }
    bool hardwareAnalogOwned() const {
        return analogServer_.isListening() ||
               analogDemod_.state()!=QProcess::NotRunning;
    }
    QString hardwareDabStatus() const {
        const QString error=lastWelleError_.isEmpty()?
            tr("No receiver error captured"):lastWelleError_.right(230);
        if(backend_.state()==QProcess::NotRunning)
            return tr("RELEASED · welle-cli stopped. Last diagnostic: %1").arg(error);
        if(!apiReady_)
            return tr("STARTING / DEGRADED · welle-cli PID %1; loopback API not ready. %2")
                .arg(backend_.processId()).arg(error);
        return tr("ACTIVE · welle-cli PID %1, DAB %2, localhost API port %3%4")
            .arg(backend_.processId()).arg(activeChannel_).arg(port_)
            .arg(scanning_?tr(" · scanning"):QString());
    }
    QString hardwareAnalogStatus() const {
        const QString error=lastAnalogError_.isEmpty()?
            tr("No rtl_fm error captured"):lastAnalogError_.right(230);
        if(analogDemod_.state()==QProcess::NotRunning)
            return tr("RELEASED / FAILED · rtl_fm not running. %1").arg(error);
        return tr("ACTIVE · rtl_fm PID %1 · %2 Hz · local audio endpoint %3")
            .arg(analogDemod_.processId())
            .arg(qRound64(analogFrequency_->value()*
                 (analogBand_->currentData().toString()==QLatin1String("fm")?1000000.:1000.)))
            .arg(analogServer_.isListening()?tr("ready"):tr("not listening"));
    }
    void hardwareStartDab() { startReceiver(); }
    void hardwareStopDab() { stopReceiver(); }
    void hardwareStartAnalog() { startAnalog(); }
    void hardwareStopAnalog() { stopAnalog(); }

private:
	struct TimedRadioCue { int chunkIndex; qint64 dueMs; qint64 queuedMs; QString text; };
	struct TimedPlainLyric { qint64 dueMs; QString text; double confidence; };
	static QString label(const QJsonValue &value) {
		if (value.isString()) return value.toString();
		if (value.isObject()) return value.toObject().value(QLatin1String("label")).toString();
		return QString();
	}
	QString base() const {
		return QLatin1String("http://127.0.0.1:") + QString::number(port_);
	}
	QString binaryPath() const {
		return QDir::homePath() + QLatin1String("/.local/opt/tihulu-welle/bin/welle-cli");
	}
	bool prepared() const {
		return QFile::exists(binaryPath()) &&
			QFile::exists(QDir::homePath() +
			  QLatin1String("/.local/opt/tihulu-welle/.tihulu-loopback-welle-revision"));
	}
	bool active() const { return backend_.state() == QProcess::Running; }

	void filterInternetStations() {
		if (!webStations_) return;
		for (int i=0;i<webStations_->topLevelItemCount();++i) {
			auto *item=webStations_->topLevelItem(i);
			const QString url=item->data(1,Qt::UserRole).toString();
			item->setHidden(webFavoritesOnly_->isChecked() &&
				!internetFavorites_.contains(url));
		}
	}
	void toggleInternetFavorite(QTreeWidgetItem *item) {
		const QString url=item->data(1,Qt::UserRole).toString();
		if (url.isEmpty()) return;
		if (internetFavorites_.contains(url)) internetFavorites_.remove(url);
		else internetFavorites_.insert(url);
		item->setText(0,internetFavorites_.contains(url)?QStringLiteral("★"):QStringLiteral("☆"));
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		settings.setValue(QLatin1String("internetFavorites"),QStringList(internetFavorites_.values()));
		filterInternetStations();
	}
	void searchInternetRadio() {
		const QString name=webSearch_->text().trimmed();
		QString country=webCountry_->currentData().toString();
		const QString typed=webCountry_->currentText().trimmed();
		const QString selected=webCountry_->itemText(webCountry_->currentIndex());
		if(typed!=selected) {
			if(QRegularExpression(QLatin1String("^[a-zA-Z]{2}$")).match(typed).hasMatch())
				country=typed.toUpper();
			else {
				const int selectedIndex=webCountry_->findText(typed,Qt::MatchExactly);
				if(selectedIndex>=0) country=webCountry_->itemData(selectedIndex).toString();
				else {
					webStatus_->setText(tr("Choose a country from the list, "
						"or type its two-letter ISO code."));
					return;
				}
			}
		}
		QUrl url(QLatin1String("https://de1.api.radio-browser.info/json/stations/search"));
		QUrlQuery query;
		if (!name.isEmpty()) query.addQueryItem(QLatin1String("name"),name.left(90));
		if (!country.isEmpty()) query.addQueryItem(QLatin1String("countrycode"),country);
		query.addQueryItem(QLatin1String("hidebroken"),QLatin1String("true"));
		query.addQueryItem(QLatin1String("order"),QLatin1String("votes"));
		query.addQueryItem(QLatin1String("reverse"),QLatin1String("true"));
		query.addQueryItem(QLatin1String("limit"),QLatin1String("120"));
		url.setQuery(query);
		QNetworkRequest request(url);
		request.setRawHeader("User-Agent","TIHULU-Media-Center/0.2 (desktop; station discovery)");
		request.setTransferTimeout(15000);
		webSearchButton_->setEnabled(false);
		webStatus_->setText(tr("Searching the online station directory…"));
		QNetworkReply *reply=network_.get(request);
		connect(reply,&QNetworkReply::finished,this,[this,reply]() {
			webSearchButton_->setEnabled(true);
			const QByteArray data=reply->readAll();
			const bool ok=reply->error()==QNetworkReply::NoError && data.size()<2*1024*1024;
			const QString error=reply->errorString();
			reply->deleteLater();
			if (!ok) { webStatus_->setText(tr("Online search failed: %1").arg(error)); return; }
			QJsonParseError parsed;
			const QJsonDocument doc=QJsonDocument::fromJson(data,&parsed);
			if (parsed.error!=QJsonParseError::NoError || !doc.isArray()) {
				webStatus_->setText(tr("Invalid station directory response.")); return;
			}
			webStations_->clear();
			for(const QJsonValue &value:doc.array()) {
				const QJsonObject station=value.toObject();
				const QString link=station.value(QLatin1String("url_resolved")).toString();
				const QUrl stream(link);
				if (!stream.isValid() || !stream.host().size() ||
				    (stream.scheme()!=QLatin1String("http") && stream.scheme()!=QLatin1String("https")))
					continue;
				const QString name=station.value(QLatin1String("name")).toString().trimmed();
				if (name.isEmpty()) continue;
				const QString country=station.value(QLatin1String("countrycode")).toString();
				const QString codec=station.value(QLatin1String("codec")).toString();
				auto *item=new QTreeWidgetItem(webStations_);
				item->setText(0,internetFavorites_.contains(link)?QStringLiteral("★"):QStringLiteral("☆"));
				item->setText(1,name.left(120));
				item->setText(2,country);
				item->setText(3,codec);
				item->setData(1,Qt::UserRole,link);
				const QUrl originalUrl(station.value(QLatin1String("url")).toString());
				if(originalUrl.isValid() && !originalUrl.host().isEmpty() &&
				  (originalUrl.scheme()==QLatin1String("http") ||
				   originalUrl.scheme()==QLatin1String("https")))
					item->setData(1,Qt::UserRole+1,originalUrl.toString());
			}
			filterInternetStations();
			webStatus_->setText(tr("%1 real stations discovered. Double-click to play; click ★ to save.")
				.arg(webStations_->topLevelItemCount()));
		});
	}
    void refreshRadioLanguageSummary() {
        if(!quickLanguageButton_ || !speechLanguage_) return;
        const QStringList langs=selectedRadioTargets();
        const QString source=speechLanguage_->currentData().toString();
        quickLanguageButton_->setText(tr("IN: %1 · OUT: %2 · Edit")
            .arg(source.isEmpty()?tr("AUTO"):source.toUpper(),
                 langs.isEmpty()?tr("none"):langs.join(
                     QLatin1String(", ")).toUpper()));
    }
    bool writeRadioLanguageControls() {
        if(captionControlsPath_.isEmpty() || !speechLanguage_) return false;
        QJsonArray targets;
        for(const QString &code:selectedRadioTargets()) targets.append(code);
        const QString source=speechLanguage_->currentData().isValid()?
            speechLanguage_->currentData().toString():
            speechLanguage_->currentText().trimmed().toLower();
        const QJsonDocument document(QJsonObject{
            {QStringLiteral("source"),source},
            {QStringLiteral("targets"),targets}});
        QSaveFile file(captionControlsPath_);
        if(!file.open(QIODevice::WriteOnly)) {
            if(translationStatus_) translationStatus_->setText(tr(
                "Live radio language preferences could not be written. "
                "Check your private runtime directory."));
            return false;
        }
        if(file.write(document.toJson(QJsonDocument::Compact))<0 ||
           !file.commit()) {
            if(translationStatus_) translationStatus_->setText(tr(
                "Language changes were NOT applied; keep previous worker settings."));
            return false;
        }
        return true;
    }
    QStringList selectedRadioTargets() const {
        // One output selection for live ASR, recorded SRT and lyric lookup.
        // No hidden legacy checkboxes or duplicated language paths.
        QStringList codes;
        if(installedTargets_->count()==0) {
            QSettings preferences(QLatin1String("TIHULU"),
                                 QLatin1String("KaffeineRadio"));
            codes=preferences.value(QLatin1String("radioOutputs"),
                QStringList{QLatin1String("en"),QLatin1String("de"),
                            QLatin1String("tr")}).toStringList();
        } else {
            for(int i=0;i<installedTargets_->count();++i) {
                const QListWidgetItem *item=installedTargets_->item(i);
                if(item->checkState()==Qt::Checked)
                    codes<<item->data(Qt::UserRole).toString();
            }
        }
        if(advancedLanguages_->isChecked()) {
            for(const QString &part:extraTargets_->text().split(
                QLatin1Char(','),Qt::SkipEmptyParts))
                codes<<part.trimmed().toLower();
        }
        QStringList unique;
        const QRegularExpression code(QLatin1String("^[a-z]{2,3}$"));
        for(const QString &candidate:codes)
            if(code.match(candidate).hasMatch() && !unique.contains(candidate)
                    && unique.size()<6)
                unique<<candidate;
        return unique;
    }
	void refreshLanguagePacks() {
		if(languagePackWorker_.state()!=QProcess::NotRunning) return;
		refreshTargets_->setEnabled(false);
		languagePackWorker_.start(QLatin1String("tihulu-tv-center"),
			{QLatin1String("ai-radio-languages")});
		if(!languagePackWorker_.waitForStarted(1000)) {
			refreshTargets_->setEnabled(true);
			translationStatus_->setText(tr(
                "AI companion not installed; radio language catalog unavailable."));
		}
	}
	void configureAnalogBand() {
		const QString band=analogBand_->currentData().toString();
		const bool fm=band==QLatin1String("fm");
		const bool mw=band==QLatin1String("mw");
		const QSignalBlocker blockFreq(analogFrequency_);
		const QSignalBlocker blockDial(analogDial_);
		analogFrequency_->setDecimals(fm?2:0);
		analogFrequency_->setRange(fm?87.5:(mw?531:150),fm?108:(mw?1602:280));
		analogFrequency_->setSuffix(fm?tr(" MHz"):tr(" kHz"));
		analogFrequency_->setSingleStep(fm?0.1:(mw?9:1));
		analogDial_->setRange(fm?8750:(mw?53100:15000),
			fm?10800:(mw?160200:28000));
		analogFrequency_->setValue(fm?99.2:(mw?999:198));
		analogDial_->setValue(qRound(analogFrequency_->value()*100));
		analogDigital_->setText(QString::number(analogFrequency_->value(),'f',fm?2:0)+
			analogFrequency_->suffix());
		analogScale_->updateFrequency(analogFrequency_->minimum(),
			analogFrequency_->maximum(),analogFrequency_->value(),
			analogBand_->currentText());
		directSampling_->setEnabled(!fm);
		if(analogServer_.isListening()) analogRetune_.start();
	}
	static QByteArray analogWavHeader() {
		QByteArray wav(44,'\0');
		auto put16=[&wav](int i,quint16 value){
			wav[i]=char(value&255);wav[i+1]=char((value>>8)&255);
		};
		auto put32=[&wav](int i,quint32 value){
			for(int p=0;p<4;++p) wav[i+p]=char((value>>(8*p))&255);
		};
		memcpy(wav.data(),"RIFF",4);put32(4,0x7fffffffu);
		memcpy(wav.data()+8,"WAVEfmt ",8);put32(16,16);
		put16(20,1); // PCM, mono 48 kHz signed 16-bit
		put16(22,1);put32(24,48000);put32(28,96000);
		put16(32,2);put16(34,16);
		memcpy(wav.data()+36,"data",4);put32(40,0x7fffffffu-36);
		return wav;
	}
	void prepareAnalogLocalStream() {
		if(analogSocketsWired_) return;
		analogSocketsWired_=true;
		connect(&analogServer_,&QTcpServer::newConnection,this,[this](){
			while(analogServer_.hasPendingConnections()) {
				QTcpSocket *socket=analogServer_.nextPendingConnection();
				// One browser/player + one recorder. The bounded third slot
				// supports a graceful reconnect without evicting playback.
				if(analogSockets_.size()>=3) {
					socket->disconnectFromHost();
					socket->deleteLater();
					continue;
				}
				analogSockets_.insert(socket);
				analogRequests_.insert(socket,QByteArray());
				connect(socket,&QTcpSocket::readyRead,this,[this,socket](){
					const QByteArray request=socket->readAll();
					if(!analogSockets_.contains(socket) || analogStreaming_.contains(socket))
						return;
					QByteArray &pending=analogRequests_[socket];
					pending+=request;
					if(pending.size()>4096) {
						socket->disconnectFromHost();return;
					}
					if(!pending.contains("\r\n\r\n"))return;
					if(!pending.startsWith("GET /analog.wav ")) {
						socket->disconnectFromHost();return;
					}
					QByteArray response("HTTP/1.1 200 OK\r\n"
						"Content-Type: audio/wav\r\n"
						"Cache-Control: no-store\r\n"
						"Connection: keep-alive\r\n\r\n");
					response+=analogWavHeader();
					socket->write(response);
					analogRequests_.remove(socket);
					analogStreaming_.insert(socket);
				});
				connect(socket,&QTcpSocket::disconnected,this,[this,socket](){
					analogSockets_.remove(socket);
					analogStreaming_.remove(socket);
					analogRequests_.remove(socket);
					socket->deleteLater();
				});
			}
		});
		connect(&analogDemod_,&QProcess::readyReadStandardOutput,this,[this](){
			const QByteArray pcm=analogDemod_.readAllStandardOutput();
			const qint64 now=QDateTime::currentMSecsSinceEpoch();
			if(analogAudioVu_ && now-lastAnalogVuUpdateMs_>=170 && pcm.size()>200) {
				lastAnalogVuUpdateMs_=now;
				double squared=0.;
				int sampled=0;
				for(int i=0;i+1<pcm.size();i+=32) {
					const quint16 raw=quint16(quint8(pcm.at(i))) |
						(quint16(quint8(pcm.at(i+1)))<<8);
					const double level=double(qint16(raw))/32768.;
					squared+=level*level;
					++sampled;
				}
				if(sampled>0) {
					const double db=20*std::log10(qMax(1e-6,std::sqrt(squared/sampled)));
					analogAudioVu_->setValue(qBound(0,qRound((db+60.)*100./60.),100));
					analogAudioVu_->setFormat(tr("Audio VU %1 dBFS · audio, NOT RF strength")
						.arg(db,0,'f',1));
				}
			}
			// Share exactly the same PCM samples with VLC and FFmpeg;
			// recording must never steal or restart the analog receiver.
			for(QTcpSocket *socket : analogStreaming_) {
				if(socket && socket->state()==QAbstractSocket::ConnectedState) {
					if(socket->bytesToWrite()<262144) socket->write(pcm);
					else socket->disconnectFromHost(); // bounded backpressure
				}
			}
		});
	}
	void retuneAnalogDemod() {
		if(!analogServer_.isListening()) return;
		analogRetune_.stop();
		const QString band=analogBand_->currentData().toString();
		const bool fm=band==QLatin1String("fm");
		if(!fm && !directSampling_->isChecked()) {
			analogStatus_->setText(tr("MW/LW require compatible direct-sampling hardware "
				"or an external upconverter."));
			return;
		}
		analogStopping_=true;
		if(analogDemod_.state()!=QProcess::NotRunning) {
			analogDemod_.terminate();
			if(!analogDemod_.waitForFinished(500)) analogDemod_.kill();
		}
		analogDemod_.readAllStandardOutput();
		analogStopping_=false;
		const quint64 hz=qRound64(analogFrequency_->value()*(fm?1000000.:1000.));
		QStringList args{QLatin1String("-M"),fm?QLatin1String("wbfm"):
			QLatin1String("am"),QLatin1String("-f"),QString::number(hz),
			QLatin1String("-s"),fm?QLatin1String("170000"):QLatin1String("48000"),
			QLatin1String("-r"),QLatin1String("48000")};
		if(!fm && directSampling_->isChecked())
			args<<QLatin1String("-D")<<QLatin1String("2");
		analogDemod_.start(QLatin1String("rtl_fm"),args);
		if(!analogDemod_.waitForStarted(1000)) {
			analogStatus_->setText(tr("RTL-SDR retune failed; device disconnected or busy."));
			return;
		}
		analogStatus_->setText(tr("Live analog frequency %1 Hz · volume/mute through "
			"TIHULU player · RF retune briefly interrupts decoding.").arg(hz));
        analogPlaybackObserved_=false;
        analogIdleSinceMs_=0;
        updateReceiverOwnership();
	}
	void stopAnalog() {
		analogRetune_.stop();
		const bool wasPlaying=analogServer_.isListening();
		analogStopping_=true;
		if(analogDemod_.state()!=QProcess::NotRunning) {
			analogDemod_.terminate();
			if(!analogDemod_.waitForFinished(850)) analogDemod_.kill();
		}
		for(QTcpSocket *client : analogSockets_) {
			if(client)client->disconnectFromHost();
		}
		analogSockets_.clear();
		analogStreaming_.clear();
		analogRequests_.clear();
		analogServer_.close();
		if(analogAudioVu_) {
			analogAudioVu_->setValue(0);
			analogAudioVu_->setFormat(tr("Audio VU: stopped (not RF strength)"));
		}
		if(wasPlaying) { player_->stop(); audioStartedMs_=0; }
        analogPlaybackObserved_=false;
        analogIdleSinceMs_=0;
		if(analogStatus_) analogStatus_->setText(tr("Analogue SDR released."));
        updateReceiverOwnership();
	}
	void startAnalog() {
		if(QStandardPaths::findExecutable(QLatin1String("rtl_fm")).isEmpty()) {
			analogStatus_->setText(tr("Optional rtl-sdr package missing. Install it to tune."));
			return;
		}
		if(analogBand_->currentData().toString()!=QLatin1String("fm") &&
		   !directSampling_->isChecked()) {
			analogStatus_->setText(tr("MW/LW need compatible direct sampling or upconverter."));
			return;
		}
		if(analogServer_.isListening()) {
			retuneAnalogDemod();
			return;
		}
		stopReceiver();
		stopAnalog();
		prepareAnalogLocalStream();
		if(!analogServer_.listen(QHostAddress::LocalHost,0)) {
			analogStatus_->setText(tr("Could not bind private local analog stream server."));
			return;
		}
		// Reuse Kaffeine/libVLC's own audio sink so the main player volume,
		// mute and audio-device selection work, unlike the former aplay fork.
		retuneAnalogDemod();
		audioStartedMs_=QDateTime::currentMSecsSinceEpoch();
		player_->play(QUrl(QLatin1String("http://127.0.0.1:")+
			QString::number(analogServer_.serverPort())+QLatin1String("/analog.wav")));
	}
	void probeInternetRadio() {
		if(internetProbe_.state()!=QProcess::NotRunning) return;
		const QUrl url=QUrl::fromUserInput(webSource_->text().trimmed());
		if(!url.isValid() || url.host().isEmpty() ||
			(url.scheme()!=QLatin1String("http") && url.scheme()!=QLatin1String("https"))) {
			webStatus_->setText(tr("Select an HTTP(S) station before testing."));return;
		}
		testedWebUrl_=webSource_->text().trimmed();
		webProbeButton_->setEnabled(false);
		webStatus_->setText(tr("Testing stream via FFprobe (timeout 8 seconds)…"));
		internetProbe_.start(QLatin1String("ffprobe"),{
			QLatin1String("-v"),QLatin1String("error"),
			QLatin1String("-rw_timeout"),QLatin1String("6000000"),
			QLatin1String("-analyzeduration"),QLatin1String("1500000"),
			QLatin1String("-probesize"),QLatin1String("262144"),
			QLatin1String("-show_entries"),QLatin1String("stream=codec_type,codec_name"),
			QLatin1String("-of"),QLatin1String("json"),
			QLatin1String("-i"),url.toString()});
		if(!internetProbe_.waitForStarted(700)) {
			webProbeButton_->setEnabled(true);
			webStatus_->setText(tr("FFprobe executable unavailable; install ffmpeg."));
			return;
		}
		QTimer::singleShot(8500,this,[this](){
			if(internetProbe_.state()!=QProcess::NotRunning) internetProbe_.kill();
		});
	}
	void playInternetRadio(const QString &address) {
		stopAnalog();
		const QUrl url=QUrl::fromUserInput(address.trimmed());
		if (!url.isValid() || url.host().isEmpty() ||
		    (url.scheme()!=QLatin1String("http") && url.scheme()!=QLatin1String("https"))) {
			webStatus_->setText(tr("Enter a valid HTTP or HTTPS stream URL.")); return;
		}
		// Internet playback has no reason to lock a TV/DAB tuner.
		if (active()) stopReceiver();
		else if (webPlaying_) player_->stop();
		playingKey_.clear();
		webPlaying_=true;
		webSource_->setText(url.toString());
        const QTreeWidgetItem *entry=webStations_->currentItem();
        const QString knownName=(entry &&
            entry->data(1,Qt::UserRole).toString()==url.toString())?
            entry->text(1):url.host();
        showSelectedSource(knownName,tr("Internet radio · opening"),
            tr("Online stream · not an FM/MW/LW frequency"));
		player_->play(url);
		audioStartedMs_=QDateTime::currentMSecsSinceEpoch();
		radioCanvas_->setText(tr("♪ Internet radio\\n%1\\nAudio uses the built-in player.")
			.arg(url.host()));
		webStatus_->setText(tr("Opening internet radio stream · no DVB device required."));
	}
	void stopInternetRadio() {
		if (!webPlaying_) return;
		player_->stop();
		webPlaying_=false;
		audioStartedMs_=0;
		webStatus_->setText(tr("Internet radio stopped."));
	}
	void startReceiver() {
		stopAnalog();
		if (webPlaying_) stopInternetRadio();
		if (active() && apiReady_) {
            state_->setText(tr("DAB+ receiver already running · localhost API ready."));
            return;
        }
        if(active() && !apiReady_) {
            // Only an explicit Start restarts this app's owned backend.
            // Never kill readsb, rtl_tcp, WebUSB or arbitrary USB users.
            stopReceiver();
            state_->setText(tr("Restarting this app-owned DAB backend…"));
        }
		if (!prepared()) {
			QMessageBox::information(this,tr("Optional local DAB+ receiver"),
				tr("Install the pinned loopback-only welle-cli backend first:\n"
				   "bash ~/.local/share/tihulu-kaffeine/install_welle.sh\n"
				   "Or run the documented TIHULU install_welle.sh from the repo.\n\n"
				   "A DAB-capable RTL-SDR/SoapySDR device is required."));
			return;
		}
		// Port discovery is local. The patched receiver itself is *guaranteed*
		// to bind 127.0.0.1, not the unauthenticated INADDR_ANY default.
		QTcpServer temp;
		if (!temp.listen(QHostAddress::LocalHost, 0)) {
			state_->setText(tr("Cannot reserve localhost receiver control port."));
			return;
		}
		port_ = temp.serverPort();
		temp.close();
		const QString current = channel_->currentText();
		if (!QRegularExpression(QLatin1String("^(?:[5-9]|1[0-3])[A-F]$"))
			.match(current).hasMatch()) {
			state_->setText(tr("Invalid DAB frequency block.")); return;
		}
		shuttingDown_ = false;
        lastWelleError_.clear();
        lastMux_=QJsonObject(); // Old mux is NOT new live RF evidence.
        apiReady_=false;apiWaitCount_=0;
        scanSNR_->setValue(0);
        scanSNR_->setFormat(tr("DAB receiver starting · SNR not measured"));
        rfQuality_->setValue(0);
        rfQuality_->setFormat(tr("DAB SNR unmeasured · receiver starting"));
		QStringList receiverArgs{QLatin1String("-c"),current,
			QLatin1String("-w"),QString::number(port_)};
		const QString device=driver_->currentData().toString();
		if (device != QLatin1String("auto"))
			receiverArgs<<QLatin1String("-F")<<device;
		backend_.start(binaryPath(), receiverArgs);
		if (!backend_.waitForStarted(1800)) {
            lastWelleError_=backend_.errorString();
            state_->setText(tr("Cannot start welle-cli: %1. This does NOT measure antenna signal.")
                .arg(lastWelleError_));
            updateReceiverOwnership();
			return;
		}
		activeChannel_ = current;
		// The remote hub can attach to this already running loopback backend
		// without opening USB or stealing the receiver. Runtime file is 0600
		// and scoped to this native application's PID.
		const QString runtimeDir=QStandardPaths::writableLocation(
			QStandardPaths::RuntimeLocation);
		if(!runtimeDir.isEmpty()) {
			wellePortFile_=runtimeDir+QLatin1String("/tihulu-welle-")+
				QString::number(QCoreApplication::applicationPid())+
				QLatin1String(".port");
			QFile file(wellePortFile_);
			if(file.open(QIODevice::WriteOnly|QIODevice::Truncate)) {
				file.setPermissions(QFile::ReadOwner|QFile::WriteOwner);
				file.write(QByteArray::number(port_));
			}
		}
		apiReady_=false;
		apiWaitCount_=0;
        ++receiverGeneration_;
		state_->setText(tr("welle-cli PID %1 · block %2 · API 127.0.0.1:%3; "
            "waiting for SDR and localhost control…")
            .arg(backend_.processId()).arg(current).arg(port_));
        tick_.start();
        updateReceiverOwnership();
		probeReceiverApi();
	}

    void updateReceiverOwnership() {
        if(!receiverOwnership_) return;
        const bool dab=backend_.state()!=QProcess::NotRunning;
        const bool analog=analogDemod_.state()!=QProcess::NotRunning ||
                          analogServer_.isListening();
        if(dab) {
            receiverOwnership_->setText(tr(
                "SDR: IN USE by TIHULU DAB · welle-cli PID %1%2")
                .arg(backend_.processId())
                .arg(releaseOnStop_ && !releaseOnStop_->isChecked()?
                    tr(" · keep receiver ready enabled"):
                    tr(" · releases on radio Stop")));
        } else if(analog) {
            receiverOwnership_->setText(tr(
                "SDR: IN USE by TIHULU analogue · rtl_fm PID %1")
                .arg(analogDemod_.processId()));
        } else {
            receiverOwnership_->setText(tr(
                "SDR: RELEASED by TIHULU · other applications may "
                "claim the device"));
        }
    }
    void stopRadioListening() {
        // Scanning uses the receiver itself and always needs a hard stop.
        if(scanning_ || !releaseOnStop_ || releaseOnStop_->isChecked()) {
            stopReceiver();
            if(state_) state_->setText(active()?
                tr("Radio Stop requested, but the DAB receiver process "
                   "is still active; SDR release not verified."):
                tr("Radio stopped · this application's DAB receiver released."));
            updateReceiverOwnership();
            return;
        }
        // Optional keep-ready: stop all playback/AI/recording resources,
        // leaving only our welle-cli receiver process alive.
        ++stationRequestId_;
        ++scanRequestId_;
        stopCaptioning();
        stopLyrics();
        stopRecording();
        if(!playingKey_.isEmpty()) player_->stop();
        playingKey_.clear();
        audioStartedMs_=0;
        dabPlaybackObserved_=false;
        dabIdleSinceMs_=0;
        {
            const QSignalBlocker block(quickAi_);
            quickAi_->setChecked(false);
            quickAi_->setText(tr("AI captions · OFF"));
        }
        if(stationOpenProgress_) {
            stationOpenProgress_->setValue(0);
            stationOpenProgress_->setFormat(tr(
                "Radio stopped · SDR held (keep-ready selected)"));
        }
        if(playStatus_) playStatus_->setText(tr(
            "Radio playback stopped. TIHULU still owns the SDR "
            "because release-on-stop was unchecked."));
        if(state_) state_->setText(tr(
            "Receiver kept ready by choice. Use Release SDR now "
            "before starting another SDR application."));
        updateReceiverOwnership();
    }
    void monitorRadioPlaybackStop() {
        if(shuttingDown_) return;
        const qint64 now=QDateTime::currentMSecsSinceEpoch();
        const auto playback=player_->getPlaybackStatus();
        if(playback==MediaWidget::Playing) {
            if(active() && !playingKey_.isEmpty())
                dabPlaybackObserved_=true;
            if(analogServer_.isListening())
                analogPlaybackObserved_=true;
            dabIdleSinceMs_=0;
            analogIdleSinceMs_=0;
            return;
        }
        if(playback!=MediaWidget::Idle) {
            // Paused/buffering is not user Stop.
            dabIdleSinceMs_=0;
            analogIdleSinceMs_=0;
            return;
        }
        // Kaffeine main playback Stop can leave welle-cli holding USB.
        // Debounce only when this station was actually Playing before:
        // transient Idle while tuning must not release the receiver.
        if(active() && !playingKey_.isEmpty() && dabPlaybackObserved_
           && !scanning_) {
            if(!dabIdleSinceMs_) dabIdleSinceMs_=now;
            if(now-dabIdleSinceMs_>=2300) {
                stopRadioListening();
                return;
            }
        } else dabIdleSinceMs_=0;
        if(analogServer_.isListening() && analogPlaybackObserved_) {
            if(!analogIdleSinceMs_) analogIdleSinceMs_=now;
            if(now-analogIdleSinceMs_>=2300) {
                analogPlaybackObserved_=false;
                analogIdleSinceMs_=0;
                if(releaseOnStop_ && releaseOnStop_->isChecked())
                    stopAnalog();
                else if(analogStatus_)
                    analogStatus_->setText(tr(
                        "Playback stopped; analogue SDR is still reserved. "
                        "Press Stop / release to free it."));
                updateReceiverOwnership();
            }
        } else analogIdleSinceMs_=0;
    }
	void stopReceiver() {
        dabPlaybackObserved_=false;
        analogPlaybackObserved_=false;
        dabIdleSinceMs_=0;
        analogIdleSinceMs_=0;
        ++receiverGeneration_; // Invalidate delayed replies from old process/port.
		stopAnalog();
		stopInternetRadio();
		shuttingDown_ = true;
		++stationRequestId_;
		scanning_ = false;
        // Stopping radio disarms optional AI, even when the next station
        // is selected later. No hidden background capture survives Stop.
        if(quickAi_) {
            const QSignalBlocker block(quickAi_);
            quickAi_->setChecked(false);
            quickAi_->setText(tr("AI captions · OFF"));
        }
		stopCaptioning();
		stopLyrics();
		stopRecording();
		tick_.stop();
		if (!playingKey_.isEmpty()) player_->stop();
		playingKey_.clear();
		audioStartedMs_=0;
		if (active()) {
			backend_.terminate();
			if (!backend_.waitForFinished(1200)) {
				backend_.kill();
				backend_.waitForFinished(1200);
			}
		}
		port_ = 0;
		if(!wellePortFile_.isEmpty()) QFile::remove(wellePortFile_);
		wellePortFile_.clear();
		apiReady_=false;apiWaitCount_=0;
        scanSNR_->setValue(0);
        scanSNR_->setFormat(tr("DAB SNR unmeasured · receiver stopped"));
        rfQuality_->setValue(0);
        rfQuality_->setFormat(tr("DAB RF unmeasured · receiver stopped"));
        lastMux_=QJsonObject();
        if(stationOpenProgress_) {
            stationOpenProgress_->setValue(0);
            stationOpenProgress_->setFormat(tr(
                "Radio stopped · DAB receiver released"));
        }
        updateReceiverOwnership();
	}


    QString apiFailureDetails() const {
        const QString stderrTail=lastWelleError_.trimmed().right(320);
        const bool busy=stderrTail.contains(QLatin1String("busy"),Qt::CaseInsensitive) ||
            stderrTail.contains(QLatin1String("usb_claim"),Qt::CaseInsensitive) ||
            stderrTail.contains(QLatin1String("no device"),Qt::CaseInsensitive) ||
            stderrTail.contains(QLatin1String("cannot open"),Qt::CaseInsensitive) ||
            stderrTail.contains(QLatin1String("failed to open"),Qt::CaseInsensitive);
        const QString cause=busy?
            tr("SDR may be owned by readsb, rtl_tcp, WebUSB or a kernel DVB driver. "
               "Release only the actual owner deliberately.") :
            tr("Check the pinned welle-cli driver, SDR permissions and startup log.");
        return tr("127.0.0.1:%1 · PID %2 · %3%4")
            .arg(port_).arg(backend_.processId())
            .arg(cause).arg(stderrTail.isEmpty()?QString():
                 tr(" · welle-cli stderr: %1").arg(stderrTail));
    }
    void probeReceiverApi() {
        if(!active() || apiReady_ || port_==0) return;
        const quint64 generation=receiverGeneration_;
        const quint16 targetPort=port_;
        QNetworkRequest request(QUrl(base()+QLatin1String("/channel")));
        request.setTransferTimeout(850);
        QNetworkReply *reply=network_.get(request);
        connect(reply,&QNetworkReply::finished,this,[this,reply,generation,targetPort]() {
            const bool ready=reply->error()==QNetworkReply::NoError;
            const QString networkError=reply->errorString();
            reply->deleteLater();
            // A delayed answer must never activate a new backend/port by mistake.
            if(generation!=receiverGeneration_ || targetPort!=port_ || !active()) return;
            if(ready) {
                apiReady_=true;apiWaitCount_=0;
                state_->setText(tr("DAB API READY · 127.0.0.1:%1 · %2. "
                    "Live station scans are available.").arg(port_).arg(activeChannel_));
            } else if(++apiWaitCount_<18) {
                // welle-cli may be running before USB claim/server startup.
                QTimer::singleShot(450,this,[this,generation](){
                    if(generation==receiverGeneration_) probeReceiverApi();
                });
            } else {
                apiReady_=false;
                scanSNR_->setValue(0);
                scanSNR_->setFormat(tr("DAB SNR NOT MEASURED · API unreachable"));
                rfQuality_->setValue(0);
                rfQuality_->setFormat(tr("DAB RF unmeasured · API unreachable"));
                state_->setText(tr("DAB API unreachable (%1): %2. "
                    "Press Start receiver to retry only this app's backend.")
                    .arg(networkError,apiFailureDetails()));
            }
        });
    }

	void callJson(const QString &endpoint,
	              const std::function<void(const QJsonObject&)> &done) {
        if(!active() || !apiReady_ || !port_) return;
        const quint64 generation=receiverGeneration_;
        const quint16 sourcePort=port_;
		QNetworkRequest request(QUrl(base() + endpoint));
		request.setTransferTimeout(1200);
		QNetworkReply *reply = network_.get(request);
		connect(reply, &QNetworkReply::finished, this, [this,reply,done,generation,sourcePort]() {
			const QByteArray bytes = reply->readAll();
			const bool ok = reply->error()==QNetworkReply::NoError &&
				bytes.size() < 1024 * 1024;
			reply->deleteLater();
            // Never paint stale 0.0 dB/mux data from a stopped or restarted
            // radio. Station cache is separate and remains available offline.
			if (!ok || !active() || !apiReady_ ||
                generation!=receiverGeneration_ || sourcePort!=port_) return;
			QJsonParseError error;
			const QJsonDocument doc = QJsonDocument::fromJson(bytes,&error);
			if (error.error==QJsonParseError::NoError && doc.isObject())
				done(doc.object());
		});
	}
	void pollMux() {
		if (!active() || !apiReady_ || scanning_) return;
		const QString channel = activeChannel_;
		callJson(QLatin1String("/mux.json"), [this,channel](const QJsonObject &object){
			consumeMux(object,channel);
		});
	}
	void consumeMux(const QJsonObject &mux, const QString &ch) {
		lastMux_=mux;
		const auto receiver = mux.value(QLatin1String("receiver")).toObject();
		const auto hardware = receiver.value(QLatin1String("hardware")).toObject();
		const auto demod = mux.value(QLatin1String("demodulator")).toObject();
		const auto fic = demod.value(QLatin1String("fic")).toObject();
		const auto ensemble = mux.value(QLatin1String("ensemble")).toObject();
		const QString stationGroup = label(ensemble.value(QLatin1String("label")));
		const bool snrValid=demod.value(QLatin1String("snr")).isDouble();
		const double snr=demod.value(QLatin1String("snr")).toDouble();
		const QString quality=!snrValid?tr("not measured"):
			(snr>=15?tr("strong"):snr>=8?tr("moderate"):tr("weak / uncertain"));
		if(scanSNR_) {
			scanSNR_->setValue(snrValid?qBound(0,qRound(snr*4),100):0);
			scanSNR_->setFormat(snrValid?
				tr("%1 · actual SNR %2 dB (%3)").arg(ch)
					.arg(snr,0,'f',1).arg(quality):
				tr("%1 · no verified SNR measurement").arg(ch));
		}
		if(scanning_ && snrValid)
			scanSnrByBlock_[ch]=snr;
		rfQuality_->setValue(snrValid?qBound(0,qRound(snr*4),100):0);
		rfQuality_->setFormat(
			snrValid ? tr("DAB SNR: %1 dB · relative %2%").arg(snr,0,'f',1)
				.arg(qBound(0,qRound(snr*4),100)) :
			tr("DAB SNR unavailable · tuner not locked"));
		signal_->setText(tr("DAB+ block %1 · centre %2\n"
                "Ensemble: %3  |  SNR: %4 dB (%5)  |  FIC errors: %6  |  Gain: %7\nSDR: %8")
            .arg(ch,dabCenterFrequencyMHz(ch),
                 stationGroup.isEmpty()?tr("not locked"):stationGroup,
                 snrValid?QString::number(snr,'f',1):tr("unknown"),quality,
                 fic.value(QLatin1String("numcrcerrors")).toVariant().toString(),
                 hardware.value(QLatin1String("gain")).toVariant().toString(),
                 hardware.value(QLatin1String("name")).toString()));
		const auto tii=mux.value(QLatin1String("tii")).toArray();
		if (!tii.isEmpty())
			signal_->setToolTip(tr("welle.io TII transmitters: %1 entries")
				.arg(tii.size()));
		const auto stations = mux.value(QLatin1String("services")).toArray();
		for (const QJsonValue &v : stations) {
			const auto service = v.toObject();
			const QString sid = service.value(QLatin1String("sid")).toString();
			const QString serviceLabel=label(service.value(QLatin1String("label")));
			const QString stream = service.value(QLatin1String("url_mp3")).toString();
			if (serviceLabel.isEmpty() ||
			    !QRegularExpression(QLatin1String("^/mp3/[A-Fa-f0-9x]+$"))
			     .match(stream).hasMatch() || sid.isEmpty()) continue;
			const QString key = ch + QLatin1Char(':') + sid;
			if(scanning_ && !stationGroup.isEmpty() && snrValid)
				scanObserved_.insert(key);
			if (!stationChannels_.contains(key)) {
				auto *item = new QTreeWidgetItem(
					{favorites_.contains(key)?QStringLiteral("★"):QStringLiteral("☆"),
					 serviceLabel, ch, sid});
				item->setData(0,Qt::UserRole,key);
				stations_->addTopLevelItem(item);
				stationData_[key] = service;
				stationChannels_[key] = ch;
				filterStations();
			}
			stationData_[key] = service;
			if (key==playingKey_) {
				const QString dls = label(service.value(QLatin1String("dls"))
				                         .toObject().value(QLatin1String("label")));
				if (!dls.isEmpty() && lastDls_ != dls) {
					lastDls_=dls;
					if(metadataCaptions_) {
						const qint64 received=QDateTime::currentMSecsSinceEpoch();
						cueQueue_.append({++dlsCaptionIndex_,received+
							activePlaybackCacheMs_+radioOffsetMs_->value(),received,
							tr("[DLS broadcaster metadata] %1").arg(dls).left(700)});
						while(cueQueue_.size()>12) cueQueue_.removeFirst();
					}
                    // Many stations rotate DLS song title, announcements
                    // and station slogans while playing the SAME song.
                    // An arbitrary DLS change MUST NOT erase the current
                    // lyric match and start another lookup repeatedly.
                    const QStringList songParts=dls.split(QLatin1String(" - "));
                    const bool songMetadata=songParts.size()>=2 &&
                        !songParts.first().trimmed().isEmpty() &&
                        !songParts.mid(1).join(QLatin1String(" - "))
                            .trimmed().isEmpty();
                    const bool newSongMetadata=songMetadata &&
                        dls!=lastSongDls_;
                    if(newSongMetadata) {
                        lastSongDls_=dls;
					// DLS is live; the audible audio may be delayed by radio caching.
					// This is approximate metadata sync, NOT audio fingerprinting.
					songStartMs_=QDateTime::currentMSecsSinceEpoch()+
						activePlaybackCacheMs_;
					lyricCues_=QJsonArray();
					lastLyricSyncUpdateMs_=0;
                    lastLyricDirection_=0;
                    lyricOffsetConsistency_=0;
                    lastVerifiedLyricMs_=0;
                    lastVerifiedLyricText_.clear();
                    lastVerifiedLyricTranslations_=QJsonObject();
					lyricsSyncState_->setText(tr("New DLS song · awaiting audible lyric verification"));
					plainLyricMode_=false;
					plainLyricQueue_.clear();
                    verifiedLyricQueue_.clear();
                    lastMatchedLyricUntilMs_=0;
                    setRadioLyricMatchStatus(QString());
                    // A DLS metadata change is NOT proof of new audible
                    // song, and must not disable Stop for an offline
                    // listening worker the user explicitly started.
                    const bool listening=lyricsAudioFallbackActive_;
					lyricLoaded_=listening;
					lyricsEnabled_=listening;
					if (lyricsProcess_.state()!=QProcess::NotRunning)
						lyricsProcess_.kill();
					stopLyrics_->setEnabled(listening);
					lyrics_->setEnabled(true);
					if (!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
					lyricPath_.clear();
					lyricText_->setText(listening?
                        tr("DLS metadata updated. Continuing offline vocal "
                           "listening; no proven song boundary.") :
                        tr("New DLS metadata. Automatic lookup requires opt-in; "
                           "timing is only an estimate."));
                    if(autoLyrics_->isChecked())
                        QTimer::singleShot(100,this,[this](){fetchLyrics(true);});
                    } // New song metadata; ordinary rotating DLS does not reset lyrics.
				}
                const QJsonObject errs=service.value(
                    QLatin1String("errorcounters")).toObject();
                const qint64 frames=errs.value(
                    QLatin1String("frameerrors")).toVariant().toLongLong();
                const qint64 rs=errs.value(
                    QLatin1String("rserrors")).toVariant().toLongLong();
                const qint64 aac=errs.value(
                    QLatin1String("aacerrors")).toVariant().toLongLong();
                if(lastErrorStation_==key && lastRfFrameErrors_>=0) {
                    const qint64 frameDelta=frames>=lastRfFrameErrors_?
                        frames-lastRfFrameErrors_:0;
                    const qint64 rsDelta=rs>=lastRfRsErrors_?
                        rs-lastRfRsErrors_:0;
                    const qint64 aacDelta=aac>=lastRfAacErrors_?
                        aac-lastRfAacErrors_:0;
                    if(frameDelta+rsDelta+aacDelta>0)
                        radioAudioHealth_->setText(tr(
                            "DAB decoder error counters increased since "
                            "last live mux: frame +%1 / RS +%2 / AAC +%3. "
                            "Signal/demodulation may be causing audio gaps; "
                            "more VLC buffering cannot repair RF errors.")
                            .arg(frameDelta).arg(rsDelta).arg(aacDelta));
                    else radioAudioHealth_->setText(tr(
                        "DAB error counters stable this sample · "
                        "audible audio/DAC buffer still unmeasured"));
                }
                lastErrorStation_=key;
                lastRfFrameErrors_=frames;
                lastRfRsErrors_=rs;
                lastRfAacErrors_=aac;
				const QString technical=tr("Frame / RS / AAC: %1 / %2 / %3")
					.arg(errs.value(QLatin1String("frameerrors")).toVariant().toString())
					.arg(errs.value(QLatin1String("rserrors")).toVariant().toString())
					.arg(errs.value(QLatin1String("aacerrors")).toVariant().toString());
				dls_->setText(tr("Now playing: %1\n"
                    "DAB+ block %2 · %3 (centre frequency)\nDLS: %4\n%5")
                    .arg(serviceLabel,ch,dabCenterFrequencyMHz(ch),dls,technical));
				requestSlide(sid);
			}
		}
		if (!stations.isEmpty())
			state_->setText(tr("DAB+ %1 · %2 total known stations · local receiver")
				.arg(ch).arg(stations_->topLevelItemCount()));
	}
	void filterStations() {
		const QString query=stationSearch_->text().trimmed();
		const QString block=libraryBlock_->currentData().toString();
		int visible=0, total=stations_->topLevelItemCount();
		for (int i=0;i<total;++i) {
			QTreeWidgetItem *item=stations_->topLevelItem(i);
			const QString key=item->data(0,Qt::UserRole).toString();
			const bool match=(query.isEmpty() ||
				item->text(1).contains(query,Qt::CaseInsensitive) ||
				item->text(2).contains(query,Qt::CaseInsensitive)) &&
				(block.isEmpty() || item->text(2)==block) &&
				(!favoritesOnly_->isChecked() || favorites_.contains(key));
			item->setHidden(!match);
			if (match) ++visible;
		}
		libraryStatus_->setText(tr("%1 visible / %2 saved stations · all DAB blocks")
			.arg(visible).arg(total));
	}
	void toggleFavorite(QTreeWidgetItem *item) {
		if (!item) return;
		const QString key=item->data(0,Qt::UserRole).toString();
		if (key.isEmpty()) return;
		if (favorites_.contains(key)) favorites_.remove(key);
		else favorites_.insert(key);
		item->setText(0,favorites_.contains(key)?
			QStringLiteral("★"):QStringLiteral("☆"));
		saveStations();
		filterStations();
	}
	void loadStations() {
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		favorites_ = QSet<QString>::fromList(
			settings.value(QLatin1String("dabFavorites")).toStringList());
		const QByteArray raw=settings.value(QLatin1String("dabStationCache")).toByteArray();
		if (raw.size() > 150000) return;
		const auto doc=QJsonDocument::fromJson(raw);
		if (!doc.isArray()) return;
		for (const QJsonValue &v : doc.array()) {
			const auto obj=v.toObject();
			const QString ch=obj.value(QLatin1String("channel")).toString();
			const QString sid=obj.value(QLatin1String("sid")).toString();
			const QString name=obj.value(QLatin1String("name")).toString();
			if (ch.size()>3 || sid.size()>16 || name.size()>150 ||
				sid.isEmpty() || ch.isEmpty() || name.isEmpty()) continue;
			const QString key=ch+QLatin1Char(':')+sid;
			if(stationChannels_.contains(key)) continue; // old cache may repeat services
			auto *item = new QTreeWidgetItem(
				{favorites_.contains(key)?QStringLiteral("★"):QStringLiteral("☆"),
				 name,ch,sid});
			item->setData(0,Qt::UserRole,key);
			stations_->addTopLevelItem(item);
			stationChannels_[key]=ch;
		}
	}
	void saveStations() {
		QJsonArray list;
		QSet<QString> written;
		for (int i=0;i<stations_->topLevelItemCount() && i<700;++i) {
			const auto *item=stations_->topLevelItem(i);
			const QString key=item->data(0,Qt::UserRole).toString();
			if(written.contains(key)) continue;
			written.insert(key);
			QJsonObject obj;
			obj[QLatin1String("channel")]=item->text(2);
			obj[QLatin1String("sid")]=item->text(3);
			obj[QLatin1String("name")]=item->text(1);
			list.append(obj);
		}
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		settings.setValue(QLatin1String("dabStationCache"),
			QJsonDocument(list).toJson(QJsonDocument::Compact));
		settings.setValue(QLatin1String("dabFavorites"),
			QStringList(favorites_.values()));
	}
    bool currentTuneRequest(bool scanningRequest,quint64 ticket) const {
        return active() && (scanningRequest?
            (scanning_ && ticket==scanRequestId_):
            (!scanning_ && ticket==stationRequestId_));
    }
    void confirmTunedBlock(const QString &block,
                           const std::function<void()> &ready,
                           bool scanningRequest,quint64 ticket,int retry=0) {
        if(!currentTuneRequest(scanningRequest,ticket)) return;
        QNetworkReply *reply=network_.get(
            QNetworkRequest(QUrl(base()+QLatin1String("/channel"))));
        connect(reply,&QNetworkReply::finished,this,
            [this,reply,block,ready,scanningRequest,ticket,retry](){
                if(!currentTuneRequest(scanningRequest,ticket)) {
                    reply->deleteLater();return;
                }
                const bool matched=reply->error()==QNetworkReply::NoError &&
                    QString::fromUtf8(reply->readAll()).trimmed()==block;
                reply->deleteLater();
                if(matched) {
                    activeChannel_=block;
                    channel_->setCurrentText(block);
                    ready();
                } else if(retry<(scanningRequest?2:5)) {
                    // DAB demodulator can take a little longer to acknowledge
                    // the selected frequency. Poll only this exact request;
                    // stale confirmations must not open a different service.
                    QTimer::singleShot(scanningRequest?700:450,this,
                        [this,block,ready,scanningRequest,ticket,retry](){
                            confirmTunedBlock(block,ready,
                                scanningRequest,ticket,retry+1);
                        });
                } else {
                    state_->setText(tr("DAB %1 retune was not confirmed by "
                        "the live receiver; no cached channel stream opened.")
                        .arg(block));
                    if(scanningRequest)
                        QTimer::singleShot(300,this,[this](){scanStep();});
                }
            });
    }
	void tune(const QString &block, const std::function<void()> &ready) {
        if(!active()) return;
        const bool scanningRequest=scanning_;
        const quint64 ticket=scanningRequest?scanRequestId_:stationRequestId_;
        if(!apiReady_) {
            if(apiWaitCount_>=18) {
                state_->setText(tr("Cannot tune DAB %1: %2. SNR has NOT "
                    "been measured. Press Start receiver to retry.")
                    .arg(block,apiFailureDetails()));
                scanSNR_->setValue(0);
                scanSNR_->setFormat(tr("DAB SNR NOT MEASURED · no API connection"));
                scanning_=false;
                scan_->setEnabled(true);
                return;
            }
            QTimer::singleShot(450,this,
                [this,block,ready,scanningRequest,ticket](){
                    if(currentTuneRequest(scanningRequest,ticket))
                        tune(block,ready);
                });
            return;
        }
        if(!QRegularExpression(QLatin1String("^(?:[5-9]|1[0-3])[A-F]$"))
            .match(block).hasMatch()) return;
        QNetworkRequest request(QUrl(base()+QLatin1String("/channel")));
        request.setHeader(QNetworkRequest::ContentTypeHeader,
                          QLatin1String("text/plain"));
        QNetworkReply *reply=network_.post(request,block.toUtf8());
        connect(reply,&QNetworkReply::finished,this,
            [this,reply,block,ready,scanningRequest,ticket](){
                const bool valid=currentTuneRequest(scanningRequest,ticket);
                const bool ok=reply->error()==QNetworkReply::NoError;
                reply->deleteLater();
                if(!valid) return;
                if(!ok) {
                    state_->setText(tr("DAB retune failed; receiver API error."));
                    if(scanningRequest)
                        QTimer::singleShot(400,this,[this](){scanStep();});
                    return;
                }
                // Only the scan needs a longer FIC discovery/ensemble dwell.
                // A station switch can start verifying the channel quickly;
                // verifyStation separately waits for a real service URL.
                QTimer::singleShot(scanningRequest?3200:650,this,
                    [this,block,ready,scanningRequest,ticket](){
                        confirmTunedBlock(block,ready,scanningRequest,ticket);
                    });
            });
    }
	void beginScan() {
		if (webPlaying_) stopInternetRadio();
		if (!active()) {
			startReceiver();
			if (!active()) return;
		}
        if(scanning_) return;
        if(!playingKey_.isEmpty()) {
			if (QMessageBox::question(this,tr("Full DAB scan"),
				tr("Stop current radio playback, offline captions and "
				"recording while scanning Band III frequencies?"),
				QMessageBox::Yes|QMessageBox::No,QMessageBox::No)!=QMessageBox::Yes)
				return;
            {
                const QSignalBlocker block(quickAi_);
                quickAi_->setChecked(false);
                quickAi_->setText(tr("AI captions · OFF"));
            }
			stopCaptioning();
			stopLyrics();
			stopRecording();
			player_->stop();
			playingKey_.clear();
			lastDetectedLanguage_.clear();
		}
        // Disable AI only AFTER the user accepts the scan interruption;
        // cancelling the scan must preserve the currently running captions.
        {
            const QSignalBlocker block(quickAi_);
            quickAi_->setChecked(false);
            quickAi_->setText(tr("AI captions · OFF"));
        }
        stopCaptioning();
		scanning_=true;
		++stationRequestId_;
		scanRequestId_=0;
		scanIndex_=0;
		scanSnrByBlock_.clear();
		scanObserved_.clear();
		scanProgress_->setRange(0,channel_->count());
		scanProgress_->setValue(0);
		scanProgress_->setFormat(tr("Scanning Band III: %v/%m blocks"));
		scanSNR_->setValue(0);
		scanSNR_->setFormat(tr("Waiting for current DAB block lock…"));
		scan_->setEnabled(false);
		state_->setText(tr("Scanning real DAB Band III frequencies…"));
		// welle-cli first opens the SDR and then starts its HTTP server.
		// Do not send the initial frequency POST before the HTTP port exists.
		QTimer::singleShot(1400,this,[this](){scanStep();});
	}
	void scanStep() {
		if (!scanning_ || !active()) {
			scanning_=false;
			scan_->setEnabled(true);
			saveStations();
			return;
		}
		if (scanIndex_ >= channel_->count()) {
			scanProgress_->setValue(channel_->count());
			scanProgress_->setFormat(tr("DAB scan complete · %v/%m blocks"));
			if(!scanSnrByBlock_.isEmpty()) {
				auto strongest=std::max_element(scanSnrByBlock_.constBegin(),
					scanSnrByBlock_.constEnd(),
					[](double a,double b){return a<b;});
				scanSNR_->setToolTip(tr("Strongest measured block: %1 · %2 dB SNR. "
					"Values are samples obtained during this scan only.")
					.arg(strongest.key()).arg(strongest.value(),0,'f',1));
			}
			scanning_=false;
			scan_->setEnabled(true);
			saveStations();
			state_->setText(tr("DAB scan complete · %1 services seen on measured "
				"RF blocks this scan · %2 total saved from all scans.")
				.arg(scanObserved_.size()).arg(stations_->topLevelItemCount()));
			return;
		}
		const QString block = channel_->itemText(scanIndex_++);
		scanProgress_->setValue(scanIndex_-1);
		scanSNR_->setValue(0);
		scanSNR_->setFormat(tr("%1 · retuning, awaiting new RF measurement").arg(block));
		state_->setText(tr("Scanning DAB %1 (%2/%3)…")
			.arg(block).arg(scanIndex_).arg(channel_->count()));
		const quint64 requestId=++scanRequestId_;
		tune(block,[this,block,requestId]() {
			if(!scanning_ || requestId!=scanRequestId_ || activeChannel_!=block) return;
			auto completed=std::make_shared<bool>(false);
			auto next=[this,requestId,completed](){
				if(*completed) return;
				*completed=true;
				if(scanning_ && requestId==scanRequestId_)
					QTimer::singleShot(120,this,[this,requestId](){
						if(scanning_ && requestId==scanRequestId_) scanStep();
					});
			};
			callJson(QLatin1String("/mux.json"),
				[this,block,requestId,next](const QJsonObject &data){
					// Never attribute a late /mux.json answer to a later block:
					// a scan can otherwise invent duplicate/stale station entries.
					if(scanning_ && requestId==scanRequestId_ && activeChannel_==block) {
						consumeMux(data,block);
						saveStations();
					}
					next();
				});
			// No HTTP callback (error, timeout): continue without inventing SNR.
			QTimer::singleShot(1500,this,next);
		});
	}
	void verifyStation(const QString &key,const QString &name,
	                   const QString &sid,quint64 requestId,int attempt=0) {
		if(requestId!=stationRequestId_ || scanning_ || !active()) return;
		if(attempt>=5) {
			playStatus_->setText(tr("Unavailable now · %1 is only a SAVED station. "
				"The tuner did not report its service on %2. "
				"Rescan this DAB block or check RF SNR/lock.")
				.arg(name,stationChannels_.value(key)));
			stationOpenProgress_->setFormat(tr("OFFLINE / not found · no audio URL opened"));
			stationOpenProgress_->setValue(0);
			return;
		}
		stationOpenProgress_->setValue(qMin(3,attempt+1));
		stationOpenProgress_->setFormat(tr("Checking live DAB service %1 · attempt %2/5")
			.arg(name).arg(attempt+1));
		auto resolved=std::make_shared<bool>(false);
		const QString block=stationChannels_.value(key);
		callJson(QLatin1String("/mux.json"),
			[this,key,name,sid,block,requestId,attempt,resolved](const QJsonObject &mux) {
				if(*resolved || requestId!=stationRequestId_) return;
				*resolved=true;
				if(!active() || activeChannel_!=block) return;
				const QJsonObject demod=mux.value(QLatin1String("demodulator")).toObject();
				const QJsonArray services=mux.value(QLatin1String("services")).toArray();
				QString stream;
				for(const QJsonValue &v:services) {
					const QJsonObject candidate=v.toObject();
					if(candidate.value(QLatin1String("sid")).toString()!=sid) continue;
					const QString candidateStream=candidate.value(
						QLatin1String("url_mp3")).toString();
					if(QRegularExpression(QLatin1String("^/mp3/[A-Fa-f0-9x]+$"))
						.match(candidateStream).hasMatch()) {
						stream=candidateStream;
						break;
					}
				}
				if(stream.isEmpty()) {
					playStatus_->setText(tr("%1 · DAB %2 · service not in LIVE mux "
						"(saved entry may be stale); SNR %3.")
						.arg(name,block).arg(demod.value(QLatin1String("snr"))
						.isDouble()?QString::number(demod.value(QLatin1String("snr"))
						.toDouble(),'f',1):tr("unavailable")));
					QTimer::singleShot(1100,this,[this,key,name,sid,requestId,attempt](){
						verifyStation(key,name,sid,requestId,attempt+1);
					});
					return;
				}
				// URL comes from the verified current welle mux, never fabricated
				// from a possibly months-old cached service ID.
				const bool restartAi=quickAi_->isChecked();
                stopCaptioning();
                stopLyrics();
                stopRecording();
                // Stopping a lyrics-owned worker may clear its AI toggle,
                // but an independently enabled live caption session must
                // survive a station switch until the owner turns it OFF.
                if(restartAi) {
                    const QSignalBlocker block(quickAi_);
                    quickAi_->setChecked(true);
                    quickAi_->setText(tr("AI captions · ON"));
                }
				lastDetectedLanguage_.clear();
				lagSamples_.clear();
				lastRadioChunk_=-1; lastRadioRevision_=-1;
				displayedRadioChunk_=-1;
                lastCaptionVisibleMs_=0;
                lastCanvasLyricMs_=0;
                captionReadingHoldUntilMs_=0;
                if(radioCanvasCaption_) radioCanvasCaption_->setVisible(false);
                radioCaptionBanner_->setText(tr("Opening DAB station · waiting for audio…"));
				pendingRadioCue_.clear();
                playingKey_=key;
                lastErrorStation_.clear();
                lastRfFrameErrors_=-1;
                lastRfRsErrors_=-1;
                lastRfAacErrors_=-1;
                radioAudioHealth_->setText(tr(
                    "New service · collecting real DAB frame/RS/AAC error "
                    "counter samples. Audio output is not measured."));
                showSelectedSource(name,tr("DAB+ · live mux verified"),
                    tr("Block %1 · %2 · service %3 · stream opening")
                        .arg(block,dabCenterFrequencyMHz(block),sid));
				lastDls_.clear();
                lastSongDls_.clear();
				lyricLoaded_=false;
				lyricCues_=QJsonArray();
				slideHistory_.clear();
				lastSlideHash_.clear();
				slideIndex_=0;
				activePlaybackCacheMs_=requestedPlaybackBufferMs();
                QSettings playback(QLatin1String("TIHULU"),
                                   QLatin1String("KaffeineRadio"));
                playback.setValue(QLatin1String("playbackBufferMs"),
                                  activePlaybackCacheMs_);
                playback.setValue(QLatin1String("radioBufferDesiredMs"),
                                  selectedBufferMs());
                player_->play(QUrl(base()+stream));
				audioStartedMs_=QDateTime::currentMSecsSinceEpoch();
				radioCanvas_->setText(tr("♪ %1\nDAB+ %2 · verifying audio playback…")
					.arg(name,block));
				playStatus_->setText(tr("LIVE mux lists %1. Opening audio; "
					"receiver lock does not guarantee decoded sound.").arg(name));
				stationOpenProgress_->setValue(4);
				stationOpenProgress_->setFormat(tr("Live service verified · audio opening"));
				QTimer::singleShot(3500,this,[this,requestId,name](){
					if(requestId!=stationRequestId_) return;
					if(player_->getPlaybackStatus()==MediaWidget::Playing) {
						playStatus_->setText(tr("PLAYER RUNNING · %1 · verify audible "
							"audio and error counters; actual audio output is not metered.")
							.arg(name));
						stationOpenProgress_->setFormat(tr("Player reports PLAYING · %1").arg(name));
                        radioCanvas_->setText(tr(
                            "♪ %1\nDAB+ %2 · player reports Playing\n"
                            "Audible output is not independently measured.")
                            .arg(name,activeChannel_));
					} else {
						playStatus_->setText(tr("NO AUDIO PLAYBACK reported for %1. "
							"Check welle receiver, AAC decoding and stream endpoint.")
							.arg(name));
						stationOpenProgress_->setFormat(tr("Audio failed / stopped"));
                        radioCanvas_->setText(tr(
                            "♪ %1\nDAB+ %2 · decoder/player did not report Playing\n"
                            "Inspect DAB RF errors and local stream.")
                            .arg(name,activeChannel_));
						stationOpenProgress_->setValue(0);
					}
				});
				if(restartAi)
					QTimer::singleShot(900,this,[this,requestId](){
						if(requestId==stationRequestId_) startCaptioning();
					});
			});
		QTimer::singleShot(1700,this,[this,key,name,sid,requestId,attempt,resolved](){
			if(*resolved || requestId!=stationRequestId_) return;
			*resolved=true;
			playStatus_->setText(tr("DAB live mux API timed out; retrying without "
				"opening a nonexistent /mp3 stream."));
			verifyStation(key,name,sid,requestId,attempt+1);
		});
	}
    static QString dabCenterFrequencyMHz(const QString &block) {
        // ETSI DAB Band III nominal ensemble centre frequency in kHz.
        // This is NOT FM station frequency, RSSI or measured SDR offset.
        static const QMap<QString,int> centers = {
            {"5A",174928},{"5B",176640},{"5C",178352},{"5D",180064},
            {"6A",181936},{"6B",183648},{"6C",185360},{"6D",187072},
            {"7A",188928},{"7B",190640},{"7C",192352},{"7D",194064},
            {"8A",195936},{"8B",197648},{"8C",199360},{"8D",201072},
            {"9A",202928},{"9B",204640},{"9C",206352},{"9D",208064},
            {"10A",209936},{"10B",211648},{"10C",213360},{"10D",215072},
            {"11A",216928},{"11B",218640},{"11C",220352},{"11D",222064},
            {"12A",223936},{"12B",225648},{"12C",227360},{"12D",229072},
            {"13A",230784},{"13B",232496},{"13C",234208},{"13D",235776},
            {"13E",237488},{"13F",239200}
        };
        const auto it=centers.constFind(block.toUpper());
        if(it==centers.cend()) return QString();
        return QString::number(it.value()/1000.,'f',3)+
               QStringLiteral(" MHz");
    }
	void showSelectedSource(const QString &name,const QString &mode,
                           const QString &detail) {
        const QString display=tr("%1 · %2 · %3")
            .arg(mode,name.left(120),detail.left(130));
        if(selectedSource_)selectedSource_->setText(display);
        if(selectedStationVintage_)
            selectedStationVintage_->setText(display+tr(
                " · analogue dial remains independent of DAB/Internet"));
        if(vintageDabReadout_) {
            const QRegularExpression blockPattern(
                QLatin1String("\\bBlock\\s+((?:[5-9]|1[0-3])[A-F])\\b"));
            const auto match=blockPattern.match(detail);
            const QString block=match.hasMatch()?match.captured(1):QString();
            const QString mhz=dabCenterFrequencyMHz(block);
            const bool dab=mode.startsWith(QLatin1String("DAB+")) && !mhz.isEmpty();
            vintageDabReadout_->setVisible(dab);
            if(dab) vintageDabReadout_->setText(tr(
                "DAB+ DIGITAL · %1 · Block %2 · %3 (centre frequency)")
                .arg(name,block,mhz));
        }
    }
	void selectStation(QTreeWidgetItem *item) {
		if(!item) return;
        showSelectedSource(item->text(1),tr("DAB+ · tuning"),
            tr("Block %1 · %2 · SID %3")
                .arg(item->text(2),dabCenterFrequencyMHz(item->text(2)),
                     item->text(3)));
		const QString key=item->data(0,Qt::UserRole).toString();
		const QString block=stationChannels_.value(key);
		const QString name=item->text(1),sid=item->text(3);
		if(scanning_) {
			playStatus_->setText(tr("Wait until scan ends before switching station."));
			return;
		}
		if(!QRegularExpression(QLatin1String("^(?:[5-9]|1[0-3])[A-F]$"))
		   .match(block).hasMatch() ||
		   !QRegularExpression(QLatin1String("^(?:0x)?[A-Fa-f0-9]{1,8}$"))
		   .match(sid).hasMatch()) {
			playStatus_->setText(tr("Invalid saved DAB block/service ID; rescan."));
			return;
		}
		if(!active()) {
			startReceiver();
			if(!active()) return;
		}
        // The old station stops temporarily during a new selection.
        // Do not treat this internal retune as a user Stop.
        dabPlaybackObserved_=false;
        dabIdleSinceMs_=0;
		const quint64 requestId=++stationRequestId_;
		player_->stop();
		playingKey_.clear();
		playStatus_->setText(tr("Tuning DAB %1 for %2; checking LIVE service before play.")
			.arg(block,name));
		stationOpenProgress_->setValue(0);
		auto ready=[this,key,name,sid,requestId]() {
			if(requestId==stationRequestId_)
				verifyStation(key,name,sid,requestId);
		};
		if(activeChannel_!=block || !apiReady_) tune(block,ready);
		else ready();
	}

	void toggleRecording() {
		if (recorder_.state()!=QProcess::NotRunning) {
			stopRecording();
			return;
		}
		if (!active() || playingKey_.isEmpty()) {
			state_->setText(tr("Select an actual DAB station before recording."));
			return;
		}
		const QString filename=QFileDialog::getSaveFileName(
			this,tr("Record live DAB station"),QDir::homePath()+QLatin1String("/Radio.mp3"),
			tr("MP3 audio (*.mp3)"));
		if (filename.isEmpty()) return;
		if (QFile::exists(filename)) {
			QMessageBox::information(this,tr("Recording"),
				tr("Recording never overwrites an existing file. Choose another name."));
			return;
		}
		const QString sid=playingKey_.section(QLatin1Char(':'),1);
		if (!QRegularExpression(QLatin1String("^(?:0x)?[A-Fa-f0-9]{1,8}$"))
			.match(sid).hasMatch()) {
			state_->setText(tr("Invalid station ID: recording refused.")); return;
		}
		const QString address=base()+QLatin1String("/mp3/")+sid;
		recorder_.start(QLatin1String("ffmpeg"),
			{QLatin1String("-nostdin"),QLatin1String("-hide_banner"),
			 QLatin1String("-loglevel"),QLatin1String("error"),
			 QLatin1String("-n"),QLatin1String("-i"),address,
			 QLatin1String("-vn"),QLatin1String("-c:a"),QLatin1String("copy"),
			 filename});
		if (recorder_.waitForStarted(1000)) {
			recordedPath_=filename;
			recordWithSubtitles_=subtitledRecord_->isChecked();
			record_->setText(tr("Stop recording"));
			state_->setText(tr("Recording real DAB audio locally to %1").arg(filename));
		} else
			state_->setText(tr("FFmpeg recording could not start."));
	}
	void stopRecording() {
		const bool wasRunning=recorder_.state()!=QProcess::NotRunning;
		if (wasRunning) {
			recorder_.terminate();
			if (!recorder_.waitForFinished(2200))
				recorder_.kill();
		}
		if (record_) record_->setText(tr("Record station"));
		if(!wasRunning || !recordWithSubtitles_ || recordedPath_.isEmpty() ||
		   !QFileInfo(recordedPath_).isFile() || QFileInfo(recordedPath_).size()==0)
			return;
		recordWithSubtitles_=false;
		if(recordAi_.state()!=QProcess::NotRunning) {
			state_->setText(tr("A previous offline recording transcription is still running."));
			return;
		}
        const QStringList targets=selectedRadioTargets();
		QStringList args{QLatin1String("media-captions"),
			QLatin1String("--input"),recordedPath_,
			QLatin1String("--source"),QLatin1String("auto"),
			QLatin1String("--targets"),targets.join(QLatin1Char(','))};
		if(music_->isChecked()) args<<QLatin1String("--music");
		recordAi_.start(QLatin1String("tihulu-tv-center"),args);
		if(!recordAi_.waitForStarted(850))
			state_->setText(tr("Recording saved; could not launch offline caption worker."));
		else state_->setText(tr("Recording saved. Creating accurate offline SRT before MKV mux…"));
	}
	void requestSlide(const QString &sid) {
		if (!active() || sid.isEmpty() || slidePending_) return;
		if (!QRegularExpression(QLatin1String("^[A-Fa-f0-9x]+$"))
			.match(sid).hasMatch()) return;
		slidePending_=true;
		QNetworkReply *reply=network_.get(
			QNetworkRequest(QUrl(base()+QLatin1String("/slide/")+sid)));
		connect(reply,&QNetworkReply::finished,this,[this,reply]() {
			slidePending_=false;
			const QByteArray bytes=reply->readAll();
			const bool ok=reply->error()==QNetworkReply::NoError && bytes.size()<700000;
			reply->deleteLater();
			if (!ok) return;
			QImage image;
			if (image.loadFromData(bytes) && image.width()<2500 && image.height()<2500) {
				const QPixmap candidate=QPixmap::fromImage(image);
				const QByteArray signature=QCryptographicHash::hash(
					bytes,QCryptographicHash::Sha256);
				if (signature!=lastSlideHash_) {
					lastSlideHash_=signature;
					if(slideHistory_.size()>=30) slideHistory_.removeFirst();
					slideHistory_.append(candidate);
					slideIndex_=slideHistory_.size()-1;
				}
				slideMove(0);
			}
		});
	}
	void slideMove(int offset) {
		if (slideHistory_.isEmpty()) return;
		slideIndex_=qBound(0,slideIndex_+offset,slideHistory_.size()-1);
		slide_->setPixmap(slideHistory_.at(slideIndex_).scaled(
			slide_->size(),Qt::KeepAspectRatio,Qt::SmoothTransformation));
		slide_->setToolTip(tr("DAB MOT/SLS slide %1/%2")
			.arg(slideIndex_+1).arg(slideHistory_.size()));
	}
	void fetchPlot(const QString &overrideType=QString(), QLabel *output=nullptr) {
		QLabel *target=output?output:plot_;
		if (!active()) { state_->setText(tr("Start a DAB receiver first.")); return; }
		if(plotPending_) return;
		const QString type=overrideType.isEmpty()?plotKind_->currentData().toString():overrideType;
		if (type!=QLatin1String("spectrum") &&
		    type!=QLatin1String("nullspectrum") &&
		    type!=QLatin1String("impulseresponse") &&
		    type!=QLatin1String("constellation") &&
		    type!=QLatin1String("waterfall")) return;
		plotPending_=true;
		const QString api=type==QLatin1String("waterfall")?
			QLatin1String("spectrum"):type;
		QNetworkReply *reply=network_.get(QNetworkRequest(QUrl(base()+QLatin1Char('/')+api)));
		// Do not leave Live RF permanently locked if the backend stops
		// answering mid-capture.
		QTimer::singleShot(1800,reply,[reply](){
			if(reply->isRunning()) reply->abort();
		});
		connect(reply,&QNetworkReply::finished,this,[this,reply,type,target]() {
			plotPending_=false;
			const QByteArray raw=reply->readAll();
			const bool okay=reply->error()==QNetworkReply::NoError &&
				raw.size()>=32 && raw.size()<=262144 && raw.size()%4==0;
			reply->deleteLater();
			if (!okay) {
				target->setToolTip(tr("No fresh RF data; retaining last valid plot. "
				"Check SDR signal, lock and backend load."));
				return;
			}
			const int count=raw.size()/4;
			const int steps=qMin(count,500);
			QVector<double> points;
			points.reserve(steps);
			for (int i=0;i<steps;++i) {
				const int offset=((qint64)i*count/steps)*4;
				float value=0;
				memcpy(&value,raw.constData()+offset,sizeof(float));
				points.append(std::isfinite(value)?value:0.0);
			}
			if (points.isEmpty()) return;
			const auto mm=std::minmax_element(points.cbegin(),points.cend());
			const double lo=*mm.first,hi=*mm.second;
			if (type==QLatin1String("waterfall")) {
				const QSize size=target->size();
				if(waterfall_.size()!=size) {
					waterfall_=QImage(size,QImage::Format_RGB32);
					waterfall_.fill(QColor("#0e2536"));
				}
				QImage previous=waterfall_.copy();
				QPainter painter(&waterfall_);
				painter.drawImage(QPoint(0,1),previous,
					QRect(0,0,size.width(),size.height()-1));
				for(int x=0;x<size.width();++x) {
					const double level=points[qBound(0,
						int(double(x)*points.size()/qMax(1,size.width())),
						points.size()-1)];
					const double magnitude=qBound(0.,(level-lo)/qMax(.0001,hi-lo),1.);
					const QColor color=QColor::fromHsv(
						qBound(0,230-int(230*magnitude),230),230,
						qBound(25,25+int(230*magnitude),255));
					painter.setPen(color);
					painter.drawPoint(x,0);
				}
				painter.end();
				target->setPixmap(QPixmap::fromImage(waterfall_));
				return;
			}
			QImage picture(target->width(),target->height(),QImage::Format_ARGB32);
			picture.fill(QColor("#101d2a"));
			QPainter p(&picture);
			p.setRenderHint(QPainter::Antialiasing);
			p.setPen(QPen(QColor("#64cfed"),1.5));
			QPolygonF poly;
			for (int i=0;i<points.size();++i) {
				const double x=8+(picture.width()-16.)*i/qMax(1,points.size()-1);
				const double y=picture.height()-9-
					(picture.height()-18.)*(points[i]-lo)/qMax(.0000001,hi-lo);
				poly<<QPointF(x,y);
			}
			p.drawPolyline(poly);
			target->setPixmap(QPixmap::fromImage(picture));
			target->setToolTip(tr("%1 receiver RF samples (native float32; signal dependent)")
				.arg(type));
		});
	}
	void sendRfOption(const QString &endpoint, const QByteArray &body) {
		if (!active()) {
			state_->setText(tr("Start the local DAB receiver first."));
			return;
		}
		QNetworkRequest req(QUrl(base()+endpoint));
		req.setHeader(QNetworkRequest::ContentTypeHeader,QLatin1String("text/plain"));
		QNetworkReply *reply=network_.post(req,body);
		connect(reply,&QNetworkReply::finished,this,[this,reply,endpoint]() {
			const bool okay=reply->error()==QNetworkReply::NoError;
			reply->deleteLater();
			if (!okay)
				state_->setText(tr("Receiver rejected RF option %1").arg(endpoint));
		});
	}
	void applyRfOptions() {
		const QString fft=fftPlacement_->currentData().toString();
		const QStringList allowed={
			"EarliestPeakWithBinning","StrongestPeak","ThresholdBeforePeak"};
		if (!allowed.contains(fft)) return;
		sendRfOption(QLatin1String("/fftwindowplacement"),fft.toUtf8());
		sendRfOption(QLatin1String("/enablecoarsecorrector"),
			coarseCorrector_->isChecked()?"1":"0");
		state_->setText(tr("Requested local welle.io FFT/coarse correction options."));
	}
	void showReceiverDetails() {
		if (lastMux_.isEmpty()) {
			QMessageBox::information(this,tr("Receiver diagnostics"),
                tr("No fresh RF metrics. Native DAB: %1\n"
                   "Binary: %2\nVerified local installation: %3\n"
                   "The antenna alone does not start welle-cli. The SDR must "
                   "be unclaimed and the local API must answer.\n"
                   "Useful checks: lsusb; pgrep -af 'readsb|rtl_tcp|welle-cli'; "
                   "ss -lntp | grep 127.0.0.1")
                   .arg(hardwareDabStatus(),binaryPath(),
                        prepared()?tr("yes"):tr("no")));
			return;
		}
		QDialog dlg(this);
		dlg.setWindowTitle(tr("Native welle.io · receiver / station / TII diagnostics"));
		dlg.resize(850,560);
		auto *layout=new QVBoxLayout(&dlg);
		auto *note=new QLabel(tr("Raw local receiver diagnostics. The FFT, null "
			"spectrum, constellation and CIR graphs are shown in the Radio tab."),&dlg);
		note->setWordWrap(true);
		layout->addWidget(note);
		auto *textView=new QPlainTextEdit(&dlg);
		textView->setReadOnly(true);
		textView->setPlainText(QString::fromUtf8(
			QJsonDocument(lastMux_).toJson(QJsonDocument::Indented)));
		layout->addWidget(textView);
		dlg.exec();
	}
    void refreshRadioBufferProgress() {
        if(!quickBufferProgress_ || !audioCacheProgress_ || !quickBuffer_) return;
        const bool enabled=quickBuffer_->isChecked();
        quickBufferProgress_->setVisible(enabled);
        audioCacheProgress_->setVisible(enabled);
        if(!enabled) return;
        const int requested=activePlaybackCacheMs_;
        const int staged=requestedPlaybackBufferMs();
        const qint64 elapsed=audioStartedMs_>0?
            qMax(qint64(0),QDateTime::currentMSecsSinceEpoch()-audioStartedMs_):0;
        const bool stationOpened=active() && !playingKey_.isEmpty() &&
                                 audioStartedMs_>0;
        const bool playing=stationOpened &&
                           player_->getPlaybackStatus()==MediaWidget::Playing;
        int percent=0;
        QString message;
        if(!stationOpened) {
            message=tr("Extra buffer ON · %1 ms requested for next DAB "
                       "playback; no stream currently opening").arg(staged);
        } else if(playing) {
            percent=100; // The player STARTED, not measured 100% buffer fill.
            message=tr("Player reports PLAYING · %1 ms extra cache requested "
                       "· actual buffer fill unmeasured").arg(requested);
        } else if(requested>0) {
            percent=qMin(95,int(qMin(elapsed,qint64(requested))*95/requested));
            message=tr("Opening DAB audio · estimated startup %1 / %2 ms "
                       "(%3% of requested time; actual fill unmeasured)")
                       .arg(elapsed).arg(requested).arg(percent);
        } else {
            message=tr("Extra buffer enabled, 0 ms requested · %1")
                .arg(autoSync_ && autoSync_->isChecked()?
                    tr("awaiting Whisper latency estimate"):
                    tr("open stream; no extra buffering"));
        }
        if(staged!=requested && stationOpened)
            message+=tr(" · next station: %1 ms").arg(staged);
        for(QProgressBar *bar:{quickBufferProgress_,audioCacheProgress_}) {
            bar->setRange(0,100);
            bar->setValue(percent);
            bar->setFormat(message);
        }
    }
	int selectedBufferMs() const {
        return qBound(0,bufferMs_->value()*(bufferUnitsSeconds_?1000:1),60000);
    }
    int requestedPlaybackBufferMs() const {
        return quickBuffer_->isChecked()?selectedBufferMs():0;
    }
    void setBufferDisplayMs(int milliseconds) {
        const int bounded=qBound(0,milliseconds,60000);
        const QSignalBlocker block(bufferMs_);
        bufferMs_->setValue(bufferUnitsSeconds_?
            qBound(0,(bounded+500)/1000,60):bounded);
    }
    void applyRadioBuffer() {
		QSettings radioSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		const int desired=requestedPlaybackBufferMs();
        radioSettings.setValue(QLatin1String("radioBufferDesiredMs"),selectedBufferMs());
        radioSettings.setValue(QLatin1String("radioBufferEnabled"),
                               quickBuffer_->isChecked());
        radioSettings.setValue(QLatin1String("playbackBufferMs"),desired);
        radioSettings.sync();
        if(desired==activePlaybackCacheMs_) {
            syncStatus_->setText(tr("Radio extra buffer unchanged: %1 ms. "
                "No audio restart.").arg(desired));
            return;
        }
		if (!playingKey_.isEmpty() && active()) {
			const QString sid=playingKey_.section(QLatin1Char(':'),1);
			if (!QRegularExpression(QLatin1String("^(?:0x)?[A-Fa-f0-9]{1,8}$"))
				.match(sid).hasMatch()) return;
			// libVLC network cache applies to media OPEN, not existing
			// stream. Explicitly reopen when the owner chooses a new
			// buffer; this can briefly interrupt sound.
			player_->play(QUrl(base()+QLatin1String("/mp3/")+sid));
            activePlaybackCacheMs_=desired;
            lastAudioRetuneMs_=QDateTime::currentMSecsSinceEpoch();
            audioStartedMs_=lastAudioRetuneMs_;
            const bool wasAiRunning=captionProcess_.state()!=QProcess::NotRunning;
            if(wasAiRunning) stopCaptioning();
			lastRadioChunk_=-1; lastRadioRevision_=-1;
			displayedRadioChunk_=-1;
			cueQueue_.clear();
			plainLyricQueue_.clear();
			pendingRadioCue_.clear();
			lastAdjustmentMs_=QDateTime::currentMSecsSinceEpoch();
            if(wasAiRunning)
                QTimer::singleShot(400,this,[this](){
                    if(active() && !playingKey_.isEmpty())startCaptioning();
                });
			syncStatus_->setText(tr("Requested %1ms cache at media reopen; "
                "captions restarted to discard old audio timeline. DAC delay unverified.")
				.arg(activePlaybackCacheMs_));
		} else {
			syncStatus_->setText(tr("Extra cache %1ms saved for the next station. "
                "No receiver restart.").arg(desired));
		}
	}
	void startCaptioning() {
		if (!active() || playingKey_.isEmpty()) {
			state_->setText(tr("Play a real DAB+ station before starting offline AI.")); return;
		}
		if (captionSource_->currentData().toString()==QLatin1String("dls")) {
			stopCaptioning();
			metadataCaptions_=true;
			lastRadioChunk_=-1; lastRadioRevision_=-1;
			displayedRadioChunk_=-1;
			radioCaption_->setText(tr("Broadcaster DLS selected. "
				"This is NOT a subtitle or spoken transcript; "
				"text is delayed only by the requested buffer and offset."));
			if(!lastDls_.isEmpty())
				cueQueue_.append({++dlsCaptionIndex_,
					QDateTime::currentMSecsSinceEpoch()+activePlaybackCacheMs_+
					radioOffsetMs_->value(),
					QDateTime::currentMSecsSinceEpoch(),
					tr("[DLS broadcaster metadata] %1").arg(lastDls_).left(700)});
			return;
		}
		metadataCaptions_=false;
		if (captionProcess_.state()!=QProcess::NotRunning) return;
		const QString sid=playingKey_.section(QLatin1Char(':'),1);
		const QString sourceCode=speechLanguage_->currentData().isValid()?
			speechLanguage_->currentData().toString():
			speechLanguage_->currentText().trimmed();
		QStringList options{QLatin1String("radio-captions"),
			QLatin1String("--port"),QString::number(port_),
			QLatin1String("--sid"),sid,
			QLatin1String("--source"),sourceCode};
        const QStringList targets=selectedRadioTargets();
		options<<QLatin1String("--targets")<<targets.join(QLatin1Char(','));
		const int sentenceHops=activePlaybackCacheMs_<8000?2:
			activePlaybackCacheMs_<14000?3:activePlaybackCacheMs_<18500?4:5;
		options<<QLatin1String("--sentence-hops")<<QString::number(sentenceHops);
        // Transfer the CURRENT desktop radio timing settings to the
        // separately paired phone. This is a requested native audio cache,
        // not a measured DAC clock. The mobile browser must NOT blindly
        // add this host delay again when decoding its own HLS stream.
        options<<QLatin1String("--host-audio-cache-ms")
               <<QString::number(activePlaybackCacheMs_);
        options<<QLatin1String("--host-caption-offset-ms")
               <<QString::number(radioOffsetMs_->value());
		if (music_->isChecked() || lyricsAudioFallbackActive_)
            options<<QLatin1String("--music");
		if (preferLyrics_->isChecked())
			options<<QLatin1String("--prefer-verified-lyrics");
		if (speakerLabels_->isChecked() && !music_->isChecked() &&
            !lyricsAudioFallbackActive_)
			options<<QLatin1String("--speaker-labels");
		const QString runtime=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
		if (runtime.isEmpty()) return;
		captionPath_=runtime + QLatin1String("/tihulu-radio-captions-")+
			QString::number(QCoreApplication::applicationPid())+QLatin1String(".json");
        captionControlsPath_=runtime+QLatin1String("/tihulu-radio-controls-")+
            QString::number(QCoreApplication::applicationPid())+
            QLatin1String(".json");
        if(!writeRadioLanguageControls()) {
            captionControlsPath_.clear();
            radioCaption_->setText(tr("Cannot save private AI controls; "
                "Whisper was not started."));
            return;
        }
		options<<QLatin1String("--output")<<captionPath_
               <<QLatin1String("--controls")<<captionControlsPath_;
		QFile::remove(captionPath_);
		captionProcess_.start(QLatin1String("tihulu-tv-center"),options);
        if (!captionProcess_.waitForStarted(1200)) {
            radioCaption_->setText(tr("Offline radio AI sidecar could not start."));
            captionProgress_->setVisible(false);
        } else {
            captionProgress_->setVisible(true);
            captionProgress_->setRange(0,0);
            captionProgress_->setFormat(tr(
                "Whisper starting · collecting ~5 s of real DAB audio…"));
            lastCaptionUpdateMs_=QDateTime::currentMSecsSinceEpoch();
            radioCaption_->setText(tr("Offline radio ASR/translation started. "
                "Radio audio plays independently; heavy AI may fall behind."));
        }
	}
    void updateRadioCaptionTypography() {
        if(!radioCanvasCaption_) return;
        const int font=radioCaptionFontSize_?
            radioCaptionFontSize_->value():18;
        radioCanvasCaption_->setStyleSheet(QString::fromLatin1(
            "QLabel{background:rgba(0,0,0,215);color:#ffffff;"
            "border-radius:6px;padding:11px;font-size:%1pt;"
            "font-weight:600;}").arg(font));
    }
    int radioCaptionReadingHoldMs(const QString &text) const {
        const int preset=radioReadingPreset_?
            radioReadingPreset_->currentData().toInt():1;
        if(preset<=0) return 0;
        // Readability budget for all visible source/translation lines.
        // It does NOT delay audio or claim true sample-clock sync.
        const int chars=qMin(1400,text.trimmed().size());
        const int normal=preset==2?
            qBound(5500,chars*65,12000):
            qBound(3300,chars*45,8500);
        // Under load, avoid drifting tens of seconds behind live radio.
        // Backlog contracts the hold to ~2–4s without dropping phrases.
        if(cueQueue_.size()>=4) return qMin(normal,2500);
        if(cueQueue_.size()>=2) return qMin(normal,4000);
        return normal;
    }
    void setRadioLyricMatchStatus(const QString &message) {
        if(!radioLyricMatchStatus_) return;
        const QString label=message.trimmed().left(210);
        if(label!=radioLyricMatchStatus_->text())
            radioLyricMatchStatus_->setText(label);
        radioLyricMatchStatus_->setVisible(!label.isEmpty());
    }
    void showRadioCanvasCaption(const QString &value,bool lyric=false) {
        if(!radioCanvasCaption_) return;
        const QString text=value.trimmed().left(1300);
        if(text.isEmpty() || text==QLatin1String("[music]")) {
            if(!lyric && !lyricsEnabled_) radioCanvasCaption_->setVisible(false);
            return;
        }
        // Actual LRC / audio-matched lyric lines win over uncertain ASR;
        // never replace the radioCanvas_'s station text or slideshow.
        // DLS metadata may still show a song while the announcer talks.
        // Never let estimated timed lyrics erase actual Whisper speech.
        const qint64 currentMs=QDateTime::currentMSecsSinceEpoch();
        if(lyric && lastUnmatchedVoiceUntilMs_>currentMs) return;
        if(!lyric && lyricsEnabled_ && currentMs<lastMatchedLyricUntilMs_ &&
           currentMs>=lastUnmatchedVoiceUntilMs_) return;
        if(radioCanvasCaption_->text()!=text) {
            radioCanvasCaption_->setText(text);
            // Keep full multi-language phrases readable; never change
            // actual libVLC playback or restart the SDR receiver.
            captionReadingHoldUntilMs_=currentMs+
                radioCaptionReadingHoldMs(text);
        }
        radioCanvasCaption_->setVisible(true);
        if(lyric) {
            lastCanvasLyricMs_=currentMs;
            // Keep a verified lyric line readable between 5s ASR hops;
            // a new unmatched presenter/advert immediately cancels this.
            lastMatchedLyricUntilMs_=qMax(lastMatchedLyricUntilMs_,
                                          currentMs+7500);
        }
    }
	void displayDueRadioCues(qint64 now) {
		// Queue rather than overwrite: a new AI chunk must not erase the
		// previous chunk before its estimated playback presentation time.
		if(captionProgress_) {
			if(cueQueue_.isEmpty()) {
                if(captionProcess_.state()!=QProcess::NotRunning) {
                    captionProgress_->setRange(0,0);
                    captionProgress_->setFormat(tr(
                        "Listening / transcribing · awaiting next confirmed phrase"));
                } else {
                    captionProgress_->setRange(0,100);
				    captionProgress_->setValue(0);
				    captionProgress_->setFormat(tr("AI captions are OFF"));
                }
			} else {
                captionProgress_->setRange(0,100);
				const auto &next=cueQueue_.first();
				const qint64 total=qMax(qint64(1),next.dueMs-next.queuedMs);
				captionProgress_->setValue(qBound(0,int((now-next.queuedMs)*100/total),100));
				captionProgress_->setFormat(tr("EST. caption in ~%1 ms · requested cache %2 ms · output unverified")
					.arg(qMax(qint64(0),next.dueMs-now)).arg(activePlaybackCacheMs_));
			}
		}
        while(!cueQueue_.isEmpty() && cueQueue_.first().dueMs<=now) {
            if(captionReadingHoldUntilMs_>now &&
               radioCanvasCaption_ && radioCanvasCaption_->isVisible()) {
                // Keep queued phrases rather than flashing a new one
                // before viewers can read the previous phrase.
                if(captionProgress_) captionProgress_->setFormat(
                    tr("Reading hold %1 ms · %2 phrase(s) queued · "
                       "radio audio uninterrupted")
                    .arg(captionReadingHoldUntilMs_-now)
                    .arg(cueQueue_.size()));
                break;
            }
			const TimedRadioCue cue=cueQueue_.takeFirst();
			if(cue.chunkIndex<=displayedRadioChunk_) continue;
			displayedRadioChunk_=cue.chunkIndex;
            const QString shown=cue.text.trimmed();
            if(shown==QLatin1String("[music]")) {
                radioCaption_->setText(tr("Music detected · waiting for "
                    "verified or audio-matched lyrics; no words invented."));
                radioCaptionBanner_->setText(tr("♪ Music · Find lyrics, "
                    "import LRC or enable vocal transcription."));
            } else {
                radioCaption_->setText(cue.text);
                radioCaptionBanner_->setText(tr(
                    "Live radio subtitles · displayed inside station view"));
                showRadioCanvasCaption(cue.text);
            }
            lastCaptionVisibleMs_=now;
            if(lyricsAudioFallbackActive_) {
                const QString heard=tr("Whisper heard (unverified lyrics) · %1")
                    .arg(cue.text.left(650));
                lyricText_->setText(heard);
            }
            // NEVER replace the main DAB station picture/video panel with
            // a caption string: it destroys its status/artwork and places
            // huge subtitles in the center of an unrelated canvas.
		}
        if(lastCaptionVisibleMs_>0 && now-lastCaptionVisibleMs_>=12000 &&
           cueQueue_.isEmpty() && !metadataCaptions_ &&
           captionProcess_.state()!=QProcess::NotRunning) {
            if(!lyricsEnabled_)
                radioCaptionBanner_->setText(tr(
                    "Listening for radio speech · no confirmed words yet."));
            if(!lyricsEnabled_ && radioCanvasCaption_)
                radioCanvasCaption_->setVisible(false);
            lastCaptionVisibleMs_=0;
        }
	}
	void pollCaption() {
		const qint64 now=QDateTime::currentMSecsSinceEpoch();
		if(captionPath_.isEmpty()) {
			displayDueRadioCues(now);
			return;
		}
		QFile stream(captionPath_);
		if(!stream.open(QIODevice::ReadOnly) || stream.size()>15000) {
			displayDueRadioCues(now);
			return;
		}
		const QJsonObject obj=QJsonDocument::fromJson(stream.readAll()).object();
		const QString detected=obj.value(QLatin1String("source_language")).toString();
		if(detected.size()>=2 && detected.size()<=3 &&
		   detected!=QLatin1String("und"))
			lastDetectedLanguage_=detected;
        const int chunk=obj.value(QLatin1String("chunk_index")).toInt(-1);
        if(chunk<0 && obj.value(QLatin1String("status")).toString()
                ==QLatin1String("waiting_audio")) {
            translationStatus_->setText(tr("AI input: waiting for decoded DAB "
                "audio. Main radio playback is independent."));
        }
        const int revision=obj.value(QLatin1String("caption_revision")).toInt(1);
        const bool newChunk=(chunk!=lastRadioChunk_);
        const bool updatedRevision=(revision>lastRadioRevision_);
		if(chunk>=0 && (newChunk || updatedRevision)) {
            lastCaptionUpdateMs_=now;
            const int lost=obj.value(
                QLatin1String("ai_audio_windows_dropped")).toInt();
            if(lost>0)
                syncStatus_->setText(tr(
                    "AI overload: %1 old audio window(s) dropped to protect "
                    "the live DAB server. Radio audio was NOT retuned. "
                    "Try one output language or a faster Whisper model.")
                    .arg(lost));
            lastRadioChunk_=chunk;
            lastRadioRevision_=revision;
			const double captured=obj.value(QLatin1String("captured_monotonic")).toDouble();
			const double decoded=obj.value(QLatin1String("decoded_monotonic")).toDouble();
			const int inference=(decoded>=captured && decoded-captured<=90.)
				?int((decoded-captured)*1000):0;
			const int carriedChunks=qBound(0,
				obj.value(QLatin1String("sentence_carry_chunks")).toInt(),5);
			const int sentenceHoldMs=qMax(0,carriedChunks-1)*5000;
			if(obj.value(QLatin1String("sentence_pending")).toBool()) {
				syncStatus_->setText(tr("Listening · carrying unfinished sentence "
                    "into next audio segment (up to %1 hops).")
                    .arg(obj.value(QLatin1String("sentence_hops_limit")).toInt(5)));
			}
			if(inference>0) {
				lagSamples_.append(inference);
				while(lagSamples_.size()>8) lagSamples_.removeFirst();
			}
			if(autoSync_->isChecked() && lagSamples_.size()>=4 &&
			   now-lastAdjustmentMs_>30000) {
				QList<int> values=lagSamples_;
				std::sort(values.begin(),values.end());
				const int p80=values[values.size()*4/5];
                // 6s captured PCM + p80 GPU inference + sentence hold,
                // plus a 3s safety margin; all quantities are estimates,
                // not samples of the physical audio output clock.
				const int rawRecommended=
					((6000+p80+sentenceHoldMs+3000+499)/500)*500;
				const int recommended=qBound(0,rawRecommended,60000);
				lastAdjustmentMs_=now;
				bufferRecommendation_->setText(
					tr("Whisper p80 %1 ms · sentence hold %2 ms · estimated "
                    "needed buffer %3 ms (safety ceiling 60000 ms)%4. "
                    "Live output clock NOT verified.")
					.arg(p80).arg(sentenceHoldMs).arg(recommended)
					.arg(rawRecommended>60000?
						tr(" · Above maximum: try fewer target languages or faster model"):
						QString()));
				if(quickBuffer_->isChecked() &&
                   qAbs(recommended-selectedBufferMs())>=1500) {
                    // Hysteresis allows both safer increases AND measured
                    // reductions without oscillating on each five-second hop.
                    // Auto selects a *future* cache request. libVLC cannot
                    // alter the already open media's audio buffering in-place.
                    // Never silently pretend that this changed live lip sync.
                    setBufferDisplayMs(recommended);
                    QSettings radio(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
                    radio.setValue(QLatin1String("radioBufferDesiredMs"),
                                   selectedBufferMs());
                    radio.setValue(QLatin1String("playbackBufferMs"),
                                   activePlaybackCacheMs_);
                    if(autoRestartAudio_->isChecked() &&
                       now-lastAudioRetuneMs_>=180000 &&
                       recommended>=activePlaybackCacheMs_+5000 &&
                       active() && !playingKey_.isEmpty()) {
                        applyRadioBuffer();
                    } else {
                        syncStatus_->setText(tr("Computed buffer %1ms is SAVED "
                            "for next tune; current live audio still requests %2ms. "
                            "No restart; audio uninterrupted.")
                            .arg(recommended).arg(activePlaybackCacheMs_));
                    }
				}
			}
            // Use a real captured PCM phrase-end time rather than
            // anchoring captions to the end of potentially slow multi-
            // language translation. This estimates stream presentation,
            // NOT real libVLC audio/DAC PTS.
            const qint64 wordEpoch=qRound64(obj.value(
                QLatin1String("subtitle_audio_end_epoch_ms")).toDouble(0.));
            const bool hasCaptureTime=wordEpoch>now-120000 &&
                                      wordEpoch<now+20000;
            const int remaining=activePlaybackCacheMs_-6000-inference-
                sentenceHoldMs+550;
            const qint64 requestedDue=hasCaptureTime?
                wordEpoch+activePlaybackCacheMs_+radioOffsetMs_->value():
                now+qMax(0,remaining)+radioOffsetMs_->value();
            const qint64 lateBy=qMax(qint64(0),now-requestedDue);
            const qint64 due=qMax(now,requestedDue);
            if(lateBy>3000)
                syncStatus_->setText(tr(
                    "Radio AI %1 ms behind captured audio; captions are "
                    "late. Reduce output languages or use faster models.")
                    .arg(lateBy));
			QString caption=obj.value(QLatin1String("original")).toString();
			const QJsonArray speakers=obj.value(QLatin1String("speaker_turns")).toArray();
			if(!caption.isEmpty() && !speakers.isEmpty() && !music_->isChecked()) {
				const QString id=speakers.first().toObject().value(QLatin1String("id")).toString();
				if(QRegularExpression(QLatin1String("^SPEAKER_[0-9]{2}$")).match(id).hasMatch())
					caption=QLatin1String("[")+id+QLatin1String("] ")+caption;
			}
            const auto translations=obj.value(
                QLatin1String("translations")).toObject();
            const QString language=detected.isEmpty()||
                detected==QLatin1String("und")?tr("AUTO ?"):detected.toUpper();
            if(!caption.trimmed().isEmpty())
                caption=tr("[ORIGINAL %1] %2").arg(language,caption);
            // Only actual translated strings are shown. Render exactly
            // the checked target languages in user-selected UI order.
            // Missing outputs are displayed as status, not fake subtitles.
            const QStringList selectedOutputs=selectedRadioTargets();
            for(const QString &code:selectedOutputs) {
                const QString translated=translations.value(code).toString().trimmed();
                if(code!=detected && !translated.isEmpty())
                    caption+=QLatin1String("\n[")+code.toUpper()+
                             QLatin1String("] ")+translated;
            }
			if(!caption.isEmpty() &&
               obj.value(QLatin1String("speech_preserved_when_lyrics_unmatched"))
                   .toBool()) {
                lastUnmatchedVoiceUntilMs_=qMax(lastUnmatchedVoiceUntilMs_,
                                                due+7000);
            }
            if(!caption.isEmpty()) {
                if(newChunk) {
                    cueQueue_.append({chunk,due,now,caption.left(1300)});
                    while(cueQueue_.size()>12) cueQueue_.removeFirst();
                } else {
                    // Revision 1 adds translations to the SAME original
                    // caption instead of re-speaking it as another cue.
                    bool queued=false;
                    for(auto &cue:cueQueue_) {
                        if(cue.chunkIndex==chunk) {
                            cue.text=caption.left(1300);
                            queued=true;
                            break;
                        }
                    }
                    if(!queued && displayedRadioChunk_==chunk &&
                       radioCanvasCaption_ &&
                       (!lyricsEnabled_ || lastVerifiedLyricMs_<=0 ||
                        now-lastVerifiedLyricMs_>12000))
                        showRadioCanvasCaption(caption.left(1300));
                }
            }
			const QJsonObject matched=obj.value(QLatin1String("lyric_match")).toObject();
            const QJsonObject lyricTranslations=obj.value(
                QLatin1String("lyric_translations")).toObject();
			if(matched.value(QLatin1String("kind")).toString()==
				QLatin1String("observed_ASR_chunk_match") &&
				matched.value(QLatin1String("confidence")).toDouble()>=0.74) {
				const QString line=matched.value(QLatin1String("text")).toString();
				const double confidence=matched.value(QLatin1String("confidence")).toDouble();
				if(!line.isEmpty() && line.size()<=240) {
                    QString rendered=line;
                    for(auto it=lyricTranslations.begin();it!=lyricTranslations.end();++it)
                        if(it.value().isString() && !it.value().toString().isEmpty())
                            rendered+=QLatin1String("\n[")+it.key().toUpper()+
                                QLatin1String("] ")+it.value().toString();
                    // A genuine audio match is evidence even without a translation.
                    lastVerifiedLyricText_=line;
                    lastVerifiedLyricTranslations_=lyricTranslations;
                    lastVerifiedLyricMs_=now;
                    lastUnmatchedVoiceUntilMs_=qMin(
                        lastUnmatchedVoiceUntilMs_,now);
                    // Found lyrics get to the real radio caption bar at
                    // their audio-derived due time. The plain and timed
                    // forms share the same evidence requirement, but no
                    // unreliable DLS timestamp is used as proof of match.
                    setRadioLyricMatchStatus(tr(
                        "LYRICS MATCHED %1% · real audio · line %2 · queued")
                        .arg(qRound(confidence*100))
                        .arg(matched.value(QLatin1String("index")).toInt()+1));
					if(plainLyricMode_) {
						plainLyricQueue_.append({due+lyricsOffset_->value(),rendered,confidence});
						while(plainLyricQueue_.size()>10) plainLyricQueue_.removeFirst();
						lyricsSyncState_->setText(tr("Verified text match %1% · "
							"audio-derived line ordering, approximate 5s time resolution")
							.arg(qRound(confidence*100)));
                    } else {
                        verifiedLyricQueue_.append({
                            due+lyricsOffset_->value(),rendered,confidence});
                        while(verifiedLyricQueue_.size()>10)
                            verifiedLyricQueue_.removeFirst();
                    }
                    if(!plainLyricMode_ && autoLyricSync_->isChecked() &&
                       confidence>=0.92 && !lyricCues_.isEmpty()) {
						const int idx=matched.value(QLatin1String("index")).toInt(-1);
						if(idx>=0 && idx<lyricCues_.size() && songStartMs_>0) {
							const double lrcSeconds=lyricCues_.at(idx).toObject()
								.value(QLatin1String("start")).toDouble(-1.);
							if(lrcSeconds>=0.) {
								const qint64 inferredStart=due-
									qRound64(lrcSeconds*1000.);
								const qint64 delta=inferredStart-songStartMs_;
								// Require a close observed vocal line, then correct gently.
								// Broad or false ASR lyric matches must not jump by minutes.
								if(qAbs(delta)<=15000) {
                                    if(qAbs(delta)<900) {
                                        lyricOffsetConsistency_=0;
                                    } else {
                                        const int direction=delta>0?1:-1;
                                        lyricOffsetConsistency_=
                                            direction==lastLyricDirection_?
                                            qMin(3,lyricOffsetConsistency_+1):1;
                                        lastLyricDirection_=direction;
                                        // Require two matching vocal lines and a
                                        // 30s cooldown; cap every correction at
                                        // 250 ms to avoid lyric timing oscillation.
                                        if(lyricOffsetConsistency_>=2 &&
                                           now-lastLyricSyncUpdateMs_>=30000) {
                                            const int step=qBound(-250,int(delta/8),250);
                                            songStartMs_+=step;
                                            lastLyricSyncUpdateMs_=now;
                                            lyricOffsetConsistency_=0;
                                            lyricsSyncState_->setText(tr(
                                                "Audio lyric sync %1% · mismatch %2 ms · "
                                                "corrected %3 ms · manual offset %4 ms")
                                                .arg(qRound(confidence*100)).arg(delta).arg(step)
                                                .arg(lyricsOffset_->value()));
                                        }
                                    }
								} else {
									lyricsSyncState_->setText(tr("Lyric match rejected: "
										"observed offset %1 ms outside ±15000 ms guard. "
										"No auto time jump.").arg(delta));
								}
							}
						}
					}
				}
			}
            // A lyrics lookup proves metadata only. If real speech is
            // heard but fails the line matcher, prioritize Whisper and
            // explain the fallback (especially for adverts/presenters).
            if(lyricsEnabled_ && lyricLoaded_ && revision>=1 &&
               !obj.value(QLatin1String("original")).toString().trimmed().isEmpty() &&
               (matched.value(QLatin1String("kind")).toString()!=
                QLatin1String("observed_ASR_chunk_match") ||
                matched.value(QLatin1String("confidence")).toDouble()<0.74)) {
                lastMatchedLyricUntilMs_=0;
                verifiedLyricQueue_.clear();
                plainLyricQueue_.clear();
                lastUnmatchedVoiceUntilMs_=qMax(lastUnmatchedVoiceUntilMs_,
                                                due+5000);
                setRadioLyricMatchStatus(tr(
                    "LYRICS FOUND · NOT MATCHED to this audio · "
                    "Whisper speech/advert fallback"));
            }
            const QJsonObject translationWarnings=obj.value(
                QLatin1String("translation_warnings")).toObject();
            const QJsonObject outputLanguages=obj.value(
                QLatin1String("translations")).toObject();
            const QString translationState=obj.value(
                QLatin1String("translation_state")).toString();
            const QString translationNote=obj.value(
                QLatin1String("translation_note")).toString();
            // This status is on the main Radio page, not hidden inside
            // the AI settings tab. A checked language can be pending,
            // ready, or missing; never report "ready" just because
            // model weights exist on disk.
            QStringList outputStates;
            const QJsonArray requested=obj.value(
                QLatin1String("requested_targets")).toArray();
            for(const QJsonValue &entry:requested) {
                const QString code=entry.toString();
                if(code.isEmpty()) continue;
                if(code==detected)
                    outputStates<<code.toUpper()+tr(" original");
                else if(!outputLanguages.value(code).toString().trimmed().isEmpty())
                    outputStates<<code.toUpper()+tr(" ready");
                else
                    outputStates<<code.toUpper()+tr(" missing/pending");
            }
            const QStringList selected=selectedRadioTargets();
            const QString intended=outputStates.isEmpty()?
                (selected.isEmpty()?tr("none"):selected.join(
                    QLatin1String(", ")).toUpper()):
                outputStates.join(QLatin1String(" · "));
            const QString spoken=detected.isEmpty()||
                detected==QLatin1String("und")?tr("auto detecting"):
                detected.toUpper();
            QString mainNote=tr("Spoken: %1 · output: %2").arg(spoken,intended);
            if(translationState==QLatin1String("language_pending"))
                mainNote+=tr(" · choose spoken language manually to translate sooner");
            else if(translationState==QLatin1String("translator_disabled"))
                mainNote+=tr(" · enable translation in AI Model Market");
            else if(translationState==QLatin1String("failed") ||
                    translationState==QLatin1String("unavailable") ||
                    translationState==QLatin1String("partial"))
                mainNote+=tr(" · inspect AI translations tab for missing model");
            radioTranslationBanner_->setText(mainNote.left(420));
            radioTranslationBanner_->setVisible(true);
            translationStatus_->setText(translationNote.isEmpty()?
                mainNote:translationNote);
			if(obj.value(QLatin1String("language_pending")).toBool())
				syncStatus_->setText(tr("Language change uncertain; translation held "
					"until two reliable detections. Original audio kept."));
			if(obj.contains(QLatin1String("error")))
				state_->setText(tr("Radio ASR: %1")
					.arg(obj.value(QLatin1String("error")).toString().left(170)));
		}
        if(captionProcess_.state()!=QProcess::NotRunning &&
            lastCaptionUpdateMs_>0 && now-lastCaptionUpdateMs_>20000) {
            radioTranslationBanner_->setText(tr(
                "AI has produced no new radio audio window for 20 s. "
                "Check local welle MP3 stream, ffmpeg and Whisper; this "
                "does not establish that the broadcaster is silent."));
            radioTranslationBanner_->setVisible(true);
        }
		displayDueRadioCues(now);
	}
	void stopCaptioning() {
        captionsStopping_=true;
        captionReadingHoldUntilMs_=0;
		cueQueue_.clear();
		metadataCaptions_=false;
		if (captionProcess_.state()!=QProcess::NotRunning) {
			captionProcess_.terminate();
			if (!captionProcess_.waitForFinished(700))
				captionProcess_.kill();
		}
        if(captionProgress_) captionProgress_->setVisible(false);
		if (!captionPath_.isEmpty()) QFile::remove(captionPath_);
		captionPath_.clear();
        if(!captionControlsPath_.isEmpty()) QFile::remove(captionControlsPath_);
        captionControlsPath_.clear();
        if(!lyricsEnabled_ && radioCanvasCaption_)
            radioCanvasCaption_->setVisible(false);
        if(radioTranslationBanner_) radioTranslationBanner_->setVisible(false);
        captionsStopping_=false;
	}
    void beginLyricListening() {
        if (!active() || playingKey_.isEmpty()) {
            lyricText_->setText(tr("Play a DAB station to transcribe vocals."));
            return;
        }
        // DLS cannot masquerade as spoken captions. Reuse the welle.io
        // audio already playing in the receiver, never the metadata text.
        const int asr=captionSource_->findData(QLatin1String("asr"));
        if(asr>=0) captionSource_->setCurrentIndex(asr);
        const bool alreadyRunning=captionProcess_.state()!=QProcess::NotRunning;
        if(!lyricsAudioFallbackActive_)
            lyricsFallbackStartedAi_=(!alreadyRunning || plainLyricsStartedAi_);
        plainLyricsStartedAi_=false;
        lyricsAudioFallbackActive_=true;
        if(!alreadyRunning) {
            // Explicit Listen action opts into ASR, but NEVER interrupt
            // an already-running presenter transcript just to switch
            // music settings. The original speech stream stays continuous.
            {
                const QSignalBlocker block(quickAi_);
                quickAi_->setChecked(true);
                quickAi_->setText(tr("AI captions · ON"));
            }
            startCaptioning();
        }
        if(captionProcess_.state()==QProcess::NotRunning) {
            lyricsAudioFallbackActive_=false;
            lyricText_->setText(tr("Offline music transcription unavailable. "
                "Install/enable Whisper in AI Model Market and play a valid DAB stream."));
            return;
        }
        lyricCues_=QJsonArray();
        plainLyricMode_=false;
        plainLyricQueue_.clear();
        if(!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
        lyricsEnabled_=true;
        lyricLoaded_=true;
        lyrics_->setEnabled(true);
        stopLyrics_->setEnabled(true);
        lyricProvider_->setText(tr("Local Whisper on actual DAB audio; no "
            "lyrics service used. Heard vocal recognition can be wrong."));
        lyricText_->setText(tr("Listening to DAB vocals offline… Approximate "
            "words appear in live captions, NOT verified song lyrics."));
    }
	void stopLyrics() {
        const bool hadListening=lyricsAudioFallbackActive_;
        const bool startedByLyrics=lyricsFallbackStartedAi_;
        lyricsAudioFallbackActive_=false;
        lyricsFallbackStartedAi_=false;
        if(hadListening && startedByLyrics &&
           captionProcess_.state()!=QProcess::NotRunning) {
            stopCaptioning();
            const QSignalBlocker block(quickAi_);
            quickAi_->setChecked(false);
            quickAi_->setText(tr("AI captions · OFF"));
        } else if(plainLyricsStartedAi_ &&
                  captionProcess_.state()!=QProcess::NotRunning) {
            // An ASR worker started ONLY for plain-lyrics matching is
            // owned by lyrics, not by independent live transcription.
            stopCaptioning();
        }
        plainLyricsStartedAi_=false;
		lyricsEnabled_=false;
		lyrics_->setEnabled(true);
		if (lyricsProcess_.state()!=QProcess::NotRunning) {
			lyricsProcess_.terminate();
			if (!lyricsProcess_.waitForFinished(600)) lyricsProcess_.kill();
		}
		if (!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
		lyricPath_.clear();
		lyricCues_=QJsonArray();
		plainLyricMode_=false;
		plainLyricQueue_.clear();
        verifiedLyricQueue_.clear();
        lastMatchedLyricUntilMs_=0;
        setRadioLyricMatchStatus(QString());
        lastVerifiedLyricMs_=0;
        lastVerifiedLyricText_.clear();
        lastVerifiedLyricTranslations_=QJsonObject();
        lyricOffsetConsistency_=0;
		lyricLoaded_=false;
        lastLyricsAutoLookup_=false;
        lastUnmatchedVoiceUntilMs_=0;
		stopLyrics_->setEnabled(false);
        lyricProvider_->setText(tr("Lyrics stopped. Local DAB audio continues."));
		lyricText_->setText(tr("Lyrics / lyric-triggered listening stopped."));
	}
	void fetchLyrics(bool automatic=false) {
		if (!active() || playingKey_.isEmpty()) {
			lyricText_->setText(tr("Play a station first.")); return;
		}
        const QString lyricDls=lastDls_.contains(QLatin1String(" - "))?
            lastDls_:lastSongDls_;
		const QStringList fields=lyricDls.split(QLatin1String(" - "));
		const bool overridden=!automatic && !lyricsArtist_->text().trimmed().isEmpty()
			&& !lyricsTitle_->text().trimmed().isEmpty();
		if(fields.size()<2 && !overridden) {
			lyricText_->setText(tr("No reliable Artist - Title DLS metadata. "
                "You can type artist/title, import LRC, or listen to vocals offline."));
            if(!automatic && listenFallbackOnMiss_->isChecked()) beginLyricListening();
			return;
		}
		const QString artist=overridden?lyricsArtist_->text().trimmed():fields.at(0).trimmed();
		const QString title=overridden?lyricsTitle_->text().trimmed():
            fields.mid(1).join(QLatin1String(" - ")).trimmed();
		if (artist.isEmpty() || title.isEmpty() || artist.size()>130 || title.size()>130)
			return;
		if (automatic && !autoLyrics_->isChecked()) return;
		if(!automatic && QMessageBox::question(this,tr("Optional online lyrics lookup"),
			tr("Search LRCLIB, lyrics.ovh and optional licensed Musixmatch?\nArtist: %1\nTitle: %2\n\n"
			   "Only these metadata are sent; no radio audio is uploaded. "
			   "Start time estimated from DLS, so adjust the timing slider manually.")
			   .arg(artist,title))!=QMessageBox::Yes) return;
		const QString runtime=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
		lyricPath_=runtime+QLatin1String("/tihulu-radio-lyrics-")+
			QString::number(QCoreApplication::applicationPid())+QLatin1String(".json");
		QFile::remove(lyricPath_);
		lyricsEnabled_=true;
        lastLyricsAutoLookup_=automatic;
        lyricLoaded_=false;
        plainLyricMode_=false;
        lyricCues_=QJsonArray();
        plainLyricQueue_.clear();
        verifiedLyricQueue_.clear();
        lastVerifiedLyricMs_=0;
        lastMatchedLyricUntilMs_=0;
        lastVerifiedLyricText_.clear();
        lastVerifiedLyricTranslations_=QJsonObject();
        setRadioLyricMatchStatus(tr(
            "LYRICS SEARCHING · metadata lookup in progress"));
        if(lyricsAudioFallbackActive_) {
            // The current fallback is only for this song's absent lyrics;
            // do not leave a previous track's plain/timed cues visible.
            lyricCues_=QJsonArray();
        }
		lyrics_->setEnabled(false);
        lyricProvider_->setText(tr("Searching LRCLIB, optional licensed "
            "Musixmatch and lyrics.ovh (metadata only)."));
		QString sourceCode=lyricsSourceLanguage_->currentData().toString();
        // Song-specific manual choice never changes automatic spoken ASR.
        // Do not reuse previous spoken presenter language for the NEXT song:
		// an English or Turkish singer may follow a German-language host.
		// Without independently verified song language, keep it auto and
		// suppress ungrounded German/English/Turkish lyric translation.
        const QStringList dests=selectedRadioTargets();
		lyricsProcess_.start(QLatin1String("tihulu-tv-center"),
			{QLatin1String("lyrics-lookup"),QLatin1String("--artist"),artist,
			 QLatin1String("--track"),title,QLatin1String("--output"),lyricPath_,
			 QLatin1String("--source"),sourceCode,
			 QLatin1String("--targets"),dests.join(QLatin1Char(',')),
			 QLatin1String("--online")});
		if (!lyricsProcess_.waitForStarted(900)) {
			lyricsEnabled_=false;
			lyrics_->setEnabled(true);
            stopLyrics_->setEnabled(false);
			lyricText_->setText(tr("Lyrics lookup worker failed to start."));
            setRadioLyricMatchStatus(tr(
                "LYRICS LOOKUP FAILED · Whisper fallback"));
            if(listenFallbackOnMiss_->isChecked()) beginLyricListening();
			return;
		}
		stopLyrics_->setEnabled(true);
		lyricText_->setText(tr("Searching timed OR plain lyrics… Stop available."));
	}
    void updateLyrics() {
        if(!lyricsEnabled_) return;
        const qint64 now=QDateTime::currentMSecsSinceEpoch();
        // Only ASR-confirmed matches enter this extra timed-LRC queue.
        while(!verifiedLyricQueue_.isEmpty() &&
              verifiedLyricQueue_.first().dueMs<=now) {
            const auto cue=verifiedLyricQueue_.takeFirst();
            showRadioCanvasCaption(cue.text,true);
            setRadioLyricMatchStatus(tr(
                "LYRICS MATCHED %1% · showing heard song words")
                .arg(qRound(cue.confidence*100)));
            lyricText_->setText(tr("Audio-matched lyric · %1")
                                .arg(cue.text.left(400)));
        }
		if(plainLyricMode_) {
			while(!plainLyricQueue_.isEmpty() && plainLyricQueue_.first().dueMs<=now) {
				const auto cue=plainLyricQueue_.takeFirst();
				lyricText_->setText(tr("Audio-matched lyric (~%1% confidence) · %2")
					.arg(qRound(cue.confidence*100)).arg(cue.text));
                showRadioCanvasCaption(cue.text,true);
                setRadioLyricMatchStatus(tr(
                    "LYRICS MATCHED %1% · showing heard song words")
                    .arg(qRound(cue.confidence*100)));
            }
            if(lastCanvasLyricMs_>0 && now-lastCanvasLyricMs_>8000 &&
               now>=lastMatchedLyricUntilMs_ && radioCanvasCaption_) {
                radioCanvasCaption_->setVisible(false);
                lastCanvasLyricMs_=0;
            }
			return;
		}
		if (lyricPath_.isEmpty() || lyricLoaded_) {
            const qint64 currentEpoch=QDateTime::currentMSecsSinceEpoch();
            // A DLS song title is metadata, not an exact start time:
            // automatic timed LRC requires real ASR-verified matches
            // (processed above) rather than guessed positions.
            // Manually imported/selected LRC may still estimate timing.
            if(lastLyricsAutoLookup_) return;
            if(now<lastMatchedLyricUntilMs_) return;
            if(lastUnmatchedVoiceUntilMs_>currentEpoch) return;
			if (!lyricCues_.isEmpty() && songStartMs_>0) {
				const qint64 start=autoLyricSync_->isChecked()
					?songStartMs_:manualSongStartMs_;
				const double elapsed=(QDateTime::currentMSecsSinceEpoch()-start+
					lyricsOffset_->value())/1000.;
				QString current;
				for (const QJsonValue &item:lyricCues_) {
					const QJsonObject cue=item.toObject();
					if (cue.value(QLatin1String("start")).toDouble()<=elapsed &&
					    cue.value(QLatin1String("end")).toDouble()>elapsed) {
						current=cue.value(QLatin1String("text")).toString();
						QJsonObject translated=cue.value(
							QLatin1String("translations")).toObject();
                        if(translated.isEmpty() &&
                           lastVerifiedLyricText_==current &&
                           QDateTime::currentMSecsSinceEpoch()-lastVerifiedLyricMs_<12000)
                            translated=lastVerifiedLyricTranslations_;
						for(auto it=translated.begin();it!=translated.end();++it)
							if(it.value().isString() && !it.value().toString().isEmpty())
								current+=QLatin1String("\n[")+it.key().toUpper()+
									QLatin1String("] ")+it.value().toString();
						break;
					}
				}
				if (!current.isEmpty()) {
                    const QString text=tr("Estimated lyric timing · %1").arg(current);
                    if(lyricText_->text()!=text)lyricText_->setText(text);
                    showRadioCanvasCaption(current,true);
                } else if(lastCanvasLyricMs_>0 &&
                    QDateTime::currentMSecsSinceEpoch()-lastCanvasLyricMs_>8000 &&
                    radioCanvasCaption_) {
                    radioCanvasCaption_->setVisible(false);
                    lastCanvasLyricMs_=0;
                }
			}
			return;
		}
		QFile file(lyricPath_);
		if (!file.open(QIODevice::ReadOnly) || file.size()>250000) return;
		const auto value=QJsonDocument::fromJson(file.readAll()).object();
		if (value.value(QLatin1String("status")).toString()==QLatin1String("completed")) {
			lyricLoaded_=true;
            const QString provider=value.value(QLatin1String("provenance"))
                .toObject().value(QLatin1String("provider")).toString();
            lyricProvider_->setText(tr("Lyrics source: %1 · metadata matched, "
                "not yet verified against heard audio.")
                .arg(provider.isEmpty()?tr("user local file"):provider));
			plainLyricMode_=value.value(QLatin1String("alignment_mode")).toString()
				==QLatin1String("asr_lexical");
			lyricCues_=value.value(QLatin1String("cues")).toArray();
            setRadioLyricMatchStatus(tr(
                "LYRICS FOUND · %1 · %2 · matching live audio…")
                .arg(provider.isEmpty()?tr("local file"):provider,
                     plainLyricMode_?tr("plain text"):tr("timed LRC")));
			if(plainLyricMode_) {
				lyricText_->setText(tr("Plain lyrics found. Awaiting REAL Whisper vocal matches; "
					"no fabricated timestamps."));
				lyrics_->setEnabled(true);
				if(captionProcess_.state()==QProcess::NotRunning) {
                    plainLyricsStartedAi_=true;
                    const int asr=captionSource_->findData(QLatin1String("asr"));
                    if(asr>=0) captionSource_->setCurrentIndex(asr);
					startCaptioning();
                }
				return;
			}
			// Manual timing is anchored to the lookup result, not fake audio matching.
			manualSongStartMs_=QDateTime::currentMSecsSinceEpoch();
			lyricText_->setText(tr("%1 synchronized lyric lines · estimated "
				"from DLS time; adjust offset as necessary.")
				.arg(lyricCues_.size()));
		} else if (value.value(QLatin1String("status")).toString()==QLatin1String("error")) {
			lyricLoaded_=true;
            lyricsEnabled_=false;
            lyrics_->setEnabled(true);
            stopLyrics_->setEnabled(false);
            const QString reason=value.value(QLatin1String("reason")).toString().left(190);
			lyricText_->setText(tr("Lyrics unavailable: %1").arg(reason));
            setRadioLyricMatchStatus(tr("LYRICS NOT FOUND · Whisper fallback"));
            lyricProvider_->setText(tr("No trusted online lyrics; no radio audio uploaded."));
            if(listenFallbackOnMiss_->isChecked()) beginLyricListening();
		}
	}
	MediaWidget *player_;
	QLabel *radioCanvas_=nullptr;
	QWidget *playerHost_=nullptr;
	QVBoxLayout *playerHostLayout_=nullptr;
	QTabWidget *modes_=nullptr;
    QSplitter *stationSplit_=nullptr;
    QLabel *selectedSource_=nullptr,*selectedStationVintage_=nullptr,
           *vintageDabReadout_=nullptr;
	QComboBox *lyricsSourceLanguage_=nullptr;
    QLabel *translationStatus_=nullptr,*spokenModelStatus_=nullptr;
    QLabel *radioTranslationBanner_=nullptr;
    QLabel *radioCanvasCaption_=nullptr,*radioLyricMatchStatus_=nullptr;
    QLabel *radioAudioHealth_=nullptr;
    QLabel *receiverOwnership_=nullptr;
    QCheckBox *advancedLanguages_=nullptr;
	QComboBox *channel_=nullptr, *driver_=nullptr, *speechLanguage_=nullptr,
		*captionSource_=nullptr,
		*plotKind_=nullptr, *fftPlacement_=nullptr;
	QPushButton *quickLanguageButton_=nullptr;
    QPushButton *start_=nullptr,*stop_=nullptr,*forceRelease_=nullptr,
        *scan_=nullptr,*record_=nullptr,
		*caption_=nullptr,*applyCaptions_=nullptr,
		*stopCaption_=nullptr,*lyrics_=nullptr,*lyricsImport_=nullptr,*stopLyrics_=nullptr,
        *listenLyrics_=nullptr,
		*slidePrev_=nullptr,*slideNext_=nullptr;
	QTreeWidget *stations_=nullptr;
	QComboBox *libraryBlock_=nullptr;
	QLineEdit *stationSearch_=nullptr;
	QLineEdit *webSearch_=nullptr,*webSource_=nullptr;
	QComboBox *webCountry_=nullptr;
	QPushButton *webSearchButton_=nullptr,*webPlay_=nullptr,*webStop_=nullptr,
		*webProbeButton_=nullptr,*webAlternate_=nullptr;
	QProcess internetProbe_{this};
	QString testedWebUrl_;
	QTreeWidget *webStations_=nullptr;
	QCheckBox *webFavoritesOnly_=nullptr;
	QLabel *webStatus_=nullptr;
	QProgressBar *rfQuality_=nullptr;
	QProgressBar *scanProgress_=nullptr,*scanSNR_=nullptr,
		*stationOpenProgress_=nullptr;
	QMap<QString,double> scanSnrByBlock_;
	QSet<QString> scanObserved_;
	QCheckBox *multiRf_=nullptr;
	QWidget *multiPanel_=nullptr;
	QList<QLabel*> multiPlots_;
	int multiRfIndex_=0;
	QLabel *analogStatus_=nullptr;
	QComboBox *analogBand_=nullptr;
	QDoubleSpinBox *analogFrequency_=nullptr;
	QDial *analogDial_=nullptr;
	QSlider *analogVolume_=nullptr;
	QPushButton *analogMute_=nullptr;
	QLabel *analogDigital_=nullptr;
	QProgressBar *analogAudioVu_=nullptr;
	qint64 lastAnalogVuUpdateMs_=0;
	TihuluAnalogScale *analogScale_=nullptr;
	QTimer analogRetune_{this};
	QTcpServer analogServer_{this};
	QSet<QTcpSocket*> analogSockets_,analogStreaming_;
	QHash<QTcpSocket*,QByteArray> analogRequests_;
	bool analogSocketsWired_=false;
	QPushButton *analogStart_=nullptr,*analogStop_=nullptr;
	QCheckBox *directSampling_=nullptr;
	bool analogStopping_=false;
	QSet<QString> internetFavorites_;
	bool webPlaying_=false,webCatalogRequested_=false,languagePacksLoaded_=false;
	QCheckBox *favoritesOnly_=nullptr;
	QLabel *libraryStatus_=nullptr;
	QSet<QString> favorites_;
	QLabel *state_=nullptr,*playStatus_=nullptr,*dls_=nullptr,*signal_=nullptr,*slide_=nullptr,
		*radioCaption_=nullptr,*radioCaptionBanner_=nullptr,
        *lyricText_=nullptr,*plot_=nullptr;
	QCheckBox *english_=nullptr,*german_=nullptr,*turkish_=nullptr,*music_=nullptr,
		*speakerLabels_=nullptr,
		*livePlot_=nullptr,*showWidgets_=nullptr,
		*coarseCorrector_=nullptr;
	QSlider *lyricsOffset_=nullptr;
	QLabel *lyricsOffsetValue_=nullptr,*lyricsSyncState_=nullptr,
        *lyricProvider_=nullptr;
	QProgressBar *captionProgress_=nullptr,*audioCacheProgress_=nullptr,
                 *quickBufferProgress_=nullptr;
	QLabel *bufferRecommendation_=nullptr;
	qint64 audioStartedMs_=0,lastLyricSyncUpdateMs_=0,
        lastCaptionVisibleMs_=0,lastCanvasLyricMs_=0,lastCaptionUpdateMs_=0,
        lastUnmatchedVoiceUntilMs_=0,lastMatchedLyricUntilMs_=0,
        captionReadingHoldUntilMs_=0;
    bool lastLyricsAutoLookup_=false;
	bool metadataCaptions_=false;
	int dlsCaptionIndex_=0;
	int lastLyricOffsetMs_=0;
	bool plainLyricMode_=false;
	QList<TimedPlainLyric> plainLyricQueue_,verifiedLyricQueue_;
	QCheckBox *autoLyrics_=nullptr,*autoLyricSync_=nullptr,
		*preferLyrics_=nullptr,*listenFallbackOnMiss_=nullptr;
    bool lyricsAudioFallbackActive_=false,lyricsFallbackStartedAi_=false,
        plainLyricsStartedAi_=false,captionsStopping_=false;
	QSpinBox *bufferMs_=nullptr,*radioOffsetMs_=nullptr;
    QComboBox *bufferUnit_=nullptr;
    bool bufferUnitsSeconds_=false;
    QHBoxLayout *radioQuickRow_=nullptr,*radioPlaybackRow_=nullptr;
    QCheckBox *quickAi_=nullptr,*quickBuffer_=nullptr,*releaseOnStop_=nullptr;
    QPushButton *captionEarlier_=nullptr,*captionLater_=nullptr;
    QLabel *captionOffsetReadout_=nullptr;
    QComboBox *radioReadingPreset_=nullptr;
    QSpinBox *radioCaptionFontSize_=nullptr;
	QCheckBox *autoSync_=nullptr,*autoRestartAudio_=nullptr;
	int lastCaptionOffsetMs_=0;
    int activePlaybackCacheMs_=0;
    bool dabPlaybackObserved_=false,analogPlaybackObserved_=false;
    qint64 dabIdleSinceMs_=0,analogIdleSinceMs_=0;
    qint64 lastAudioRetuneMs_=0;
	QList<TimedRadioCue> cueQueue_;
	QLineEdit *extraTargets_=nullptr,*lyricsArtist_=nullptr,*lyricsTitle_=nullptr;
	QLabel *syncStatus_=nullptr;
	QProcess backend_,captionProcess_,recorder_,lyricsProcess_,recordAi_,recordMux_,languagePackWorker_;
	QListWidget *installedTargets_=nullptr;
	QPushButton *refreshTargets_=nullptr;
	QString recordedPath_;
	bool recordWithSubtitles_=false;
	QCheckBox *subtitledRecord_=nullptr;
	QProcess analogDemod_{this};
	QNetworkAccessManager network_;
	QTimer tick_,captionTick_,rfTick_;
	quint16 port_=0;
	bool apiReady_=false;
	int apiWaitCount_=0;
    quint64 receiverGeneration_=0;
	bool scanning_=false,shuttingDown_=false,slidePending_=false,lyricLoaded_=false,
		lyricsEnabled_=false,
		plotPending_=false;
	int scanIndex_=0;
	quint64 scanRequestId_=0,stationRequestId_=0;
	qint64 songStartMs_=0,manualSongStartMs_=0;
	QString lastWelleError_,lastAnalogError_;
    QString lastVerifiedLyricText_;
    QString lastErrorStation_;
    qint64 lastRfFrameErrors_=-1,lastRfRsErrors_=-1,lastRfAacErrors_=-1;
    QJsonObject lastVerifiedLyricTranslations_;
    qint64 lastVerifiedLyricMs_=0;
    int lastLyricDirection_=0,lyricOffsetConsistency_=0;
	QString activeChannel_,playingKey_,lastDls_,lastSongDls_,captionPath_,captionControlsPath_,lyricPath_,
		wellePortFile_,
		lastDetectedLanguage_;
	QMap<QString,QJsonObject> stationData_;
	QMap<QString,QString> stationChannels_;
	QJsonArray lyricCues_;
	QJsonObject lastMux_;
	QList<int> lagSamples_;
	int lastRadioChunk_=-1,displayedRadioChunk_=-1,
        lastRadioRevision_=-1;
	qint64 lastAdjustmentMs_=0,radioCueDueMs_=0;
	QString pendingRadioCue_;
	QList<QPixmap> slideHistory_;
	QByteArray lastSlideHash_;
	QImage waterfall_;
	int slideIndex_=0;
};

#endif // TIHULU_NATIVE_RADIO_TAB_H
