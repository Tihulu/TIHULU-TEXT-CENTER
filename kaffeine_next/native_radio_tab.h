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
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHostAddress>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QSet>
#include <QSignalBlocker>
#include <QHeaderView>
#include <QMap>
#include <QMessageBox>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QPainter>
#include <QPen>
#include <QPixmap>
#include <QPlainTextEdit>
#include <QProcess>
#include <QPushButton>
#include <QRegularExpression>
#include <QSettings>
#include <QScrollArea>
#include <QUrlQuery>
#include <QSlider>
#include <QSpinBox>
#include <QSplitter>
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
#include <limits>

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
		stop_ = new QPushButton(tr("Stop / release SDR"), this);
		record_ = new QPushButton(tr("Record station"), this);
		record_->setToolTip(tr("Save selected radio service to a local MP3; "
			"stop recording to release the file."));
		scan_ = new QPushButton(tr("Scan all blocks"), this);
		scan_->setToolTip(tr("Retunes across Band III blocks; can take minutes."));
		root->addLayout(header);
		// Operational buttons wrap to a second row on narrower displays.
		auto *receiverActions=new QHBoxLayout();
		receiverActions->addWidget(start_);
		receiverActions->addWidget(scan_);
		receiverActions->addWidget(record_);
		receiverActions->addWidget(stop_);
		root->addLayout(receiverActions);

		state_ = new QLabel(tr("Receiver disconnected. A separate DAB-capable SDR is required; "
			"the DVB-T2 television adapter is not automatically a DAB receiver."), this);
		state_->setWordWrap(true);
		state_->setTextFormat(Qt::PlainText);
		root->addWidget(state_);

		// Public internet radio requires no SDR, welle-cli or DVB frontend.
		// Search happens only when clicked, and uses HTTPS Radio Browser API.
		auto *webGroup = new QGroupBox(tr("Internet radio · independent of tuner"), page);
		auto *webLayout = new QVBoxLayout(webGroup);
		auto *webSearchRow = new QHBoxLayout();
		webSearch_ = new QLineEdit(webGroup);
		webSearch_->setPlaceholderText(tr("Search station name · e.g. WDR, BBC, TRT"));
		webCountry_ = new QLineEdit(webGroup);
		webCountry_->setPlaceholderText(tr("Country ISO code (optional: DE, TR...)"));
		webCountry_->setMaximumWidth(230);
		webSearchButton_ = new QPushButton(tr("Find stations online"), webGroup);
		webSearchRow->addWidget(webSearch_, 2);
		webSearchRow->addWidget(webCountry_, 1);
		webSearchRow->addWidget(webSearchButton_);
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
		auto *webPlayRow = new QHBoxLayout();
		webSource_ = new QLineEdit(webGroup);
		webSource_->setPlaceholderText(tr("Or paste an HTTP(S) radio stream URL"));
		webPlay_ = new QPushButton(tr("Play stream"), webGroup);
		webStop_ = new QPushButton(tr("Stop stream"), webGroup);
		webFavoritesOnly_ = new QCheckBox(tr("★ Favorites"),webGroup);
		webPlayRow->addWidget(webSource_, 1);
		webPlayRow->addWidget(webPlay_);
		webPlayRow->addWidget(webStop_);
		webPlayRow->addWidget(webFavoritesOnly_);
		webLayout->addLayout(webPlayRow);
		webStatus_ = new QLabel(tr("Internet radio is ready. No tuner connection required."),webGroup);
		webStatus_->setWordWrap(true);
		webLayout->addWidget(webStatus_);
		root->addWidget(webGroup);

		// Hardware-dependent analogue tuner. Never claim a DVB-T2 frontend
		// can demodulate FM, MW or LW; rtl_fm needs a compatible RTL-SDR.
		auto *analogGroup=new QGroupBox(tr("Analogue tuner · FM / MW-AM / LW"),page);
		auto *analogLayout=new QVBoxLayout(analogGroup);
		auto *analogRow=new QHBoxLayout();
		analogBand_=new QComboBox(analogGroup);
		analogBand_->addItem(tr("FM · 87.5–108 MHz"),QLatin1String("fm"));
		analogBand_->addItem(tr("AM / MW · 531–1602 kHz"),QLatin1String("mw"));
		analogBand_->addItem(tr("LW · 150–280 kHz"),QLatin1String("lw"));
		analogFrequency_=new QDoubleSpinBox(analogGroup);
		analogFrequency_->setDecimals(2);
		analogFrequency_->setRange(87.5,108.0);
		analogFrequency_->setValue(99.2);
		analogFrequency_->setSuffix(tr(" MHz"));
		analogDial_=new QDial(analogGroup);
		analogDial_->setRange(8750,10800);
		analogDial_->setValue(9920);
		analogDial_->setNotchesVisible(true);
		analogDial_->setFixedSize(95,95);
		analogStart_=new QPushButton(tr("Tune frequency"),analogGroup);
		analogStop_=new QPushButton(tr("Release analogue SDR"),analogGroup);
		analogRow->addWidget(analogBand_);
		analogRow->addWidget(analogFrequency_);
		analogRow->addWidget(analogDial_);
		analogRow->addWidget(analogStart_);
		analogRow->addWidget(analogStop_);
		analogLayout->addLayout(analogRow);
		directSampling_=new QCheckBox(
			tr("Hardware-specific direct sampling for MW/LW (explicit opt-in)"),analogGroup);
		directSampling_->setToolTip(tr("Only enable if your RTL-SDR specifically supports direct-sampling below 24 MHz. "
			"Other tuners require a suitable converter or external receiver."));
		analogLayout->addWidget(directSampling_);
		analogStatus_=new QLabel(tr("Frequency tuning requires rtl_fm and a compatible SDR. "
			"Silicon Labs Si2168 alone is not an FM/AM/LW tuner."),analogGroup);
		analogStatus_->setWordWrap(true);
		analogLayout->addWidget(analogStatus_);
		root->addWidget(analogGroup);
		connect(analogBand_,QOverload<int>::of(&QComboBox::currentIndexChanged),
			this,[this](){ configureAnalogBand(); });
		connect(analogDial_,&QDial::valueChanged,this,[this](int value){
			analogFrequency_->setValue(value/100.);
		});
		connect(analogFrequency_,QOverload<double>::of(&QDoubleSpinBox::valueChanged),
			this,[this](double value){
			analogDial_->setValue(qRound(value*100.));
		});
		connect(analogStart_,&QPushButton::clicked,this,[this](){ startAnalog(); });
		connect(analogStop_,&QPushButton::clicked,this,[this](){ stopAnalog(); });
		connect(&analogDemod_,&QProcess::readyReadStandardError,this,[this](){
			const QString msg=QString::fromLocal8Bit(analogDemod_.readAllStandardError());
			if(msg.contains(QLatin1String("Failed"),Qt::CaseInsensitive) ||
			   msg.contains(QLatin1String("error"),Qt::CaseInsensitive))
				analogStatus_->setText(msg.right(320));
		});
		connect(&analogDemod_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int code,QProcess::ExitStatus){
				if(!analogStopping_) analogStatus_->setText(
					tr("Analogue SDR stopped (exit %1); check USB ownership and RF range.").arg(code));
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
		stations_->setMinimumWidth(340);
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
		textBlock->addWidget(dls_);
		textBlock->addWidget(signal_);
		meta->addLayout(textBlock, 1);
		rightLayout->addLayout(meta);
		split->addWidget(right);
		split->setStretchFactor(0,1);
		split->setStretchFactor(1,2);
		root->addWidget(split, 4);

		auto *lab = new QGroupBox(tr("Offline radio AI · Whisper / translation / timed lyrics"), this);
		auto *v = new QVBoxLayout(lab);
		auto *row = new QHBoxLayout();
		speechLanguage_ = new QComboBox(lab);
		speechLanguage_->addItem(tr("Auto detect · GPU Whisper"),"auto");
		speechLanguage_->addItems({"de","en","tr","fr","es","pl","ar","ja"});
		speechLanguage_->setEditable(true);
		speechLanguage_->setCurrentIndex(0);
		german_ = new QCheckBox(tr("German"), lab); german_->setChecked(true);
		english_ = new QCheckBox(tr("English"), lab); english_->setChecked(true);
		turkish_ = new QCheckBox(tr("Turkish"), lab); turkish_->setChecked(true);
		music_ = new QCheckBox(tr("Transcribe singing / music vocals"), lab);
		caption_ = new QPushButton(tr("Start offline live captions"), lab);
		stopCaption_ = new QPushButton(tr("Stop AI captions"), lab);
		row->addWidget(new QLabel(tr("Source:"), lab));
		row->addWidget(speechLanguage_);
		row->addWidget(english_);
		row->addWidget(german_);
		row->addWidget(turkish_);
		row->addWidget(music_);
		v->addLayout(row);
		extraTargets_=new QLineEdit(lab);
		extraTargets_->setPlaceholderText(
			tr("Extra translation targets (optional): fr, es, pl, ar, ja..."));
		v->addWidget(extraTargets_);
		auto *syncControls=new QHBoxLayout();
		bufferMs_=new QSpinBox(lab);
		bufferMs_->setRange(0,20000);
		bufferMs_->setSingleStep(500);
		bufferMs_->setSuffix(tr(" ms"));
		QSettings radioSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		bufferMs_->setValue(qBound(0,
			radioSettings.value(QLatin1String("playbackBufferMs"),12000).toInt(),20000));
		bufferMs_->setToolTip(tr("Radio-only libVLC network cache. Applies on stream reopen; "
			"not a measured DAC/ALSA audio presentation clock."));
		autoSync_=new QCheckBox(tr("Auto synchronize caption timing"),lab);
		autoSync_->setChecked(true);
		autoSync_->setToolTip(tr("Adapt caption timing to measured ASR delay. "
			"Does not reopen audio unless separately enabled."));
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
		autoRestartAudio_->setToolTip(tr("OFF prevents speech gaps during buffer retuning. "
			"Turn on only if occasional brief audio interruption is acceptable."));
		auto *applyBuffer=new QPushButton(tr("Apply radio buffer"),lab);
		syncControls->addWidget(new QLabel(tr("Audio buffer:"),lab));
		syncControls->addWidget(bufferMs_);
		syncControls->addWidget(autoSync_);
		syncControls->addWidget(new QLabel(tr("Caption offset:"),lab));
		syncControls->addWidget(radioOffsetMs_);
		syncControls->addWidget(applyBuffer);
		v->addLayout(syncControls);
		v->addWidget(autoRestartAudio_);
		lastCaptionOffsetMs_=radioOffsetMs_->value();
		connect(radioOffsetMs_,QOverload<int>::of(&QSpinBox::valueChanged),
			this,[this](int newOffset){
				QSettings saved(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
				saved.setValue(QLatin1String("captionOffsetMs"),newOffset);
				const int adjustment=newOffset-lastCaptionOffsetMs_;
				lastCaptionOffsetMs_=newOffset;
				for(auto &cue:cueQueue_) cue.dueMs+=adjustment;
			});
		syncStatus_=new QLabel(tr("Sync: 12s requested radio network cache "
			"· no verified audio output clock · checking every 30s"),lab);
		syncStatus_->setWordWrap(true);
		v->addWidget(syncStatus_);
		connect(applyBuffer,&QPushButton::clicked,this,[this](){ applyRadioBuffer(); });
		auto *captionActions=new QHBoxLayout();
		captionActions->addStretch(1);
		captionActions->addWidget(caption_);
		captionActions->addWidget(stopCaption_);
		v->addLayout(captionActions);
		radioCaption_ = new QLabel(tr("Radio AI is OFF; it never starts without your request."), lab);
		radioCaption_->setTextFormat(Qt::PlainText);
		radioCaption_->setWordWrap(true);
		v->addWidget(radioCaption_);
		auto *lyricsRow = new QHBoxLayout();
		lyrics_ = new QPushButton(tr("Find timed lyrics (optional internet)"), lab);
		stopLyrics_=new QPushButton(tr("Stop lyrics"),lab);
		stopLyrics_->setEnabled(false);
		lyricsOffset_ = new QSlider(Qt::Horizontal, lab);
		lyricsOffset_->setRange(-90000, 90000);
		lyricsOffset_->setValue(0);
		lyricsOffset_->setToolTip(tr("Manual lyric sync offset, milliseconds (-90s to +90s)."));
		lyricsRow->addWidget(lyrics_);
		lyricsRow->addWidget(stopLyrics_);
		lyricsRow->addWidget(new QLabel(tr("Lyric timing:"), lab));
		lyricsRow->addWidget(lyricsOffset_, 1);
		v->addLayout(lyricsRow);
		lyricText_ = new QLabel(tr("No synchronized lyrics loaded."), lab);
		lyricText_->setTextFormat(Qt::PlainText);
		lyricText_->setWordWrap(true);
		v->addWidget(lyricText_);
		root->addWidget(lab);

		auto *diagnosticCard = new QGroupBox(tr("DAB receiver diagnostics / welle.io"),this);
		auto *diagnosticLayout=new QVBoxLayout(diagnosticCard);
		auto *diagnostics = new QHBoxLayout();
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
		plot_->setFixedSize(330, 110);
		plot_->setAlignment(Qt::AlignCenter);
		plot_->setStyleSheet(QLatin1String("border:1px solid #456;"));
		auto *plotButton = new QPushButton(tr("Capture RF plot"), this);
		livePlot_=new QCheckBox(tr("Live RF"),this);
		livePlot_->setToolTip(tr("Update spectrum/waterfall every 1.6 seconds while enabled"));
		showWidgets_=new QCheckBox(tr("Show welle.io RF widgets"),this);
		showWidgets_->setChecked(false);
		auto *detailsButton = new QPushButton(tr("Receiver / TII details"),this);
		auto *applyRf = new QPushButton(tr("Apply RF options"),this);
		diagnostics->addWidget(plotKind_);
		diagnostics->addWidget(plotButton);
		diagnostics->addWidget(livePlot_);
		diagnostics->addWidget(plot_, 1);
		diagnosticLayout->addLayout(diagnostics);
		auto *rfOptions=new QHBoxLayout();
		rfOptions->addWidget(fftPlacement_,1);
		rfOptions->addWidget(coarseCorrector_);
		rfOptions->addWidget(applyRf);
		rfOptions->addWidget(detailsButton);
		diagnosticLayout->addLayout(rfOptions);
		root->addWidget(showWidgets_);
		root->addWidget(diagnosticCard);
		diagnosticCard->setVisible(false);
		connect(showWidgets_,&QCheckBox::toggled,diagnosticCard,&QWidget::setVisible);

		connect(start_, &QPushButton::clicked, this, [this](){ startReceiver(); });
		connect(stop_, &QPushButton::clicked, this, [this](){ stopReceiver(); });
		connect(record_, &QPushButton::clicked, this, [this](){ toggleRecording(); });
		connect(scan_, &QPushButton::clicked, this, [this](){ beginScan(); });
		connect(webSearchButton_, &QPushButton::clicked, this, [this](){ searchInternetRadio(); });
		connect(webSearch_, &QLineEdit::returnPressed, this, [this](){ searchInternetRadio(); });
		connect(webPlay_, &QPushButton::clicked, this, [this](){ playInternetRadio(webSource_->text()); });
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
				else if (item) webSource_->setText(item->data(1,Qt::UserRole).toString());
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
				if (column==0) toggleFavorite(item);
			});
		connect(stationSearch_, &QLineEdit::textChanged,this,
			[this](){ filterStations(); });
		connect(libraryBlock_,QOverload<int>::of(&QComboBox::currentIndexChanged),
			this,[this](){ filterStations(); });
		connect(favoritesOnly_,&QCheckBox::toggled,this,
			[this](){ filterStations(); });
		connect(caption_, &QPushButton::clicked, this, [this](){ startCaptioning(); });
		connect(stopCaption_, &QPushButton::clicked, this, [this](){ stopCaptioning(); });
		connect(lyrics_, &QPushButton::clicked, this, [this](){ fetchLyrics(); });
		connect(stopLyrics_, &QPushButton::clicked, this, [this](){ stopLyrics(); });
		connect(slidePrev_,&QPushButton::clicked,this,[this](){slideMove(-1);});
		connect(slideNext_,&QPushButton::clicked,this,[this](){slideMove(1);});
		connect(plotButton, &QPushButton::clicked, this, [this](){ fetchPlot(); });
		connect(applyRf, &QPushButton::clicked, this, [this](){ applyRfOptions(); });
		connect(detailsButton, &QPushButton::clicked, this, [this](){ showReceiverDetails(); });
		connect(&backend_, &QProcess::readyReadStandardError, this, [this]() {
			const QString tail = QString::fromUtf8(backend_.readAllStandardError());
			if (tail.contains(QLatin1String("Cannot")) ||
			    tail.contains(QLatin1String("No device")) ||
			    tail.contains(QLatin1String("Failed")))
				state_->setText(tail.right(250));
		});
		connect(&backend_, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
			this, [this](int, QProcess::ExitStatus){
				stopCaptioning();
				tick_.stop();
				if (!shuttingDown_) state_->setText(tr("welle-cli stopped; SDR released."));
			});
		tick_.setInterval(1600);
		connect(&tick_, &QTimer::timeout, this, [this](){
			pollMux(); pollCaption(); updateLyrics();
			if(livePlot_->isChecked() && !plotPending_) fetchPlot();
		});
		loadStations();
		stations_->sortItems(1,Qt::AscendingOrder);
		filterStations();
	}

	~TihuluRadioTab() override { stopReceiver(); }

	void activate() override {
		// NEVER move Kaffeine's shared mediaWidget into this radio panel.
		// The normal Playback, Playlist, and Television activate() methods
		// remain sole owners of the video surface. Radio uses libVLC only
		// for audio output, with its own visible AI and station metadata.
		radioCanvas_->setFocus();
	}

private:
	struct TimedRadioCue { int chunkIndex; qint64 dueMs; QString text; };
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
		item->setText(0,internetFavorites_.contains(url)?QLatin1String("★"):QLatin1String("☆"));
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		settings.setValue(QLatin1String("internetFavorites"),QStringList(internetFavorites_.values()));
		filterInternetStations();
	}
	void searchInternetRadio() {
		const QString name=webSearch_->text().trimmed();
		const QString country=webCountry_->text().trimmed().toUpper();
		if (name.isEmpty() && country.isEmpty()) {
			webStatus_->setText(tr("Enter a station name or country code to search."));
			return;
		}
		if (!country.isEmpty() && !QRegularExpression(QLatin1String("^[A-Z]{2}$")).match(country).hasMatch()) {
			webStatus_->setText(tr("Country must be a two-letter ISO code, e.g. DE or TR."));
			return;
		}
		QUrl url(QLatin1String("https://de1.api.radio-browser.info/json/stations/search"));
		QUrlQuery query;
		if (!name.isEmpty()) query.addQueryItem(QLatin1String("name"),name.left(90));
		if (!country.isEmpty()) query.addQueryItem(QLatin1String("countrycode"),country);
		query.addQueryItem(QLatin1String("hidebroken"),QLatin1String("true"));
		query.addQueryItem(QLatin1String("order"),QLatin1String("votes"));
		query.addQueryItem(QLatin1String("reverse"),QLatin1String("true"));
		query.addQueryItem(QLatin1String("limit"),QLatin1String("40"));
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
			const bool ok=reply->error()==QNetworkReply::NoError && data.size()<512*1024;
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
				item->setText(0,internetFavorites_.contains(link)?QLatin1String("★"):QLatin1String("☆"));
				item->setText(1,name.left(120));
				item->setText(2,country);
				item->setText(3,codec);
				item->setData(1,Qt::UserRole,link);
			}
			filterInternetStations();
			webStatus_->setText(tr("%1 real stations discovered. Double-click to play; click ★ to save.")
				.arg(webStations_->topLevelItemCount()));
		});
	}
	void configureAnalogBand() {
		const QString band=analogBand_->currentData().toString();
		const bool fm=band==QLatin1String("fm");
		const bool mw=band==QLatin1String("mw");
		analogFrequency_->setDecimals(fm?2:0);
		analogFrequency_->setRange(fm?87.5:(mw?531:150),fm?108:(mw?1602:280));
		analogFrequency_->setSuffix(fm?tr(" MHz"):tr(" kHz"));
		analogFrequency_->setSingleStep(fm?0.1:(mw?9:1));
		analogDial_->setRange(fm?8750:(mw?53100:15000),fm?10800:(mw?160200:28000));
		analogFrequency_->setValue(fm?99.2:(mw?999:198));
		analogDial_->setValue(qRound(analogFrequency_->value()*100));
		directSampling_->setEnabled(!fm);
	}
	void stopAnalog() {
		analogStopping_=true;
		if(analogDemod_.state()!=QProcess::NotRunning) {
			analogDemod_.terminate();
			if(!analogDemod_.waitForFinished(900)) analogDemod_.kill();
		}
		if(analogAudio_.state()!=QProcess::NotRunning) {
			analogAudio_.terminate();
			if(!analogAudio_.waitForFinished(900)) analogAudio_.kill();
		}
		if(analogStatus_) analogStatus_->setText(tr("Analogue SDR released."));
	}
	void startAnalog() {
		const QString demod=QStandardPaths::findExecutable(QLatin1String("rtl_fm"));
		const QString player=QStandardPaths::findExecutable(QLatin1String("aplay"));
		if(demod.isEmpty() || player.isEmpty()) {
			analogStatus_->setText(tr("Install optional rtl-sdr and alsa-utils tools first. "
				"Neither USB tuner nor AI models are installed automatically."));
			return;
		}
		const QString band=analogBand_->currentData().toString();
		const bool isFm=band==QLatin1String("fm");
		if(!isFm && !directSampling_->isChecked()) {
			analogStatus_->setText(tr("MW/LW need an HF-capable SDR, direct sampling or an upconverter. "
				"Opt into compatible direct sampling only after checking hardware."));
			return;
		}
		stopReceiver(); // Release welle and shared audio before claiming RTL-SDR.
		stopAnalog();
		analogStopping_=false;
		const quint64 hz=qRound64(analogFrequency_->value()*(isFm?1000000.:1000.));
		QStringList args{QLatin1String("-M"),isFm?QLatin1String("wbfm"):QLatin1String("am"),
			QLatin1String("-f"),QString::number(hz),
			QLatin1String("-s"),isFm?QLatin1String("170000"):QLatin1String("48000"),
			QLatin1String("-r"),QLatin1String("48000")};
		if(!isFm && directSampling_->isChecked())
			args<<QLatin1String("-D")<<QLatin1String("2");
		analogDemod_.setStandardOutputProcess(&analogAudio_);
		analogAudio_.start(player,{QLatin1String("-q"),QLatin1String("-t"),
			QLatin1String("raw"),QLatin1String("-f"),QLatin1String("S16_LE"),
			QLatin1String("-r"),QLatin1String("48000"),QLatin1String("-c"),
			QLatin1String("1")});
		if(!analogAudio_.waitForStarted(1200)) {
			analogStatus_->setText(tr("Cannot start ALSA output; check audio device."));return;
		}
		analogDemod_.start(demod,args);
		if(!analogDemod_.waitForStarted(1200)){
			stopAnalog();
			analogStatus_->setText(tr("RTL-SDR backend failed to start; check exclusive device access."));
			return;
		}
		analogStatus_->setText(tr("Tuning %1 Hz via local RTL-SDR. "
			"No fabricated station name or lock confirmation.").arg(hz));
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
		player_->play(url);
		radioCanvas_->setText(tr("♪ Internet radio\\n%1\\nAudio uses the built-in player.")
			.arg(url.host()));
		webStatus_->setText(tr("Opening internet radio stream · no DVB device required."));
	}
	void stopInternetRadio() {
		if (!webPlaying_) return;
		player_->stop();
		webPlaying_=false;
		webStatus_->setText(tr("Internet radio stopped."));
	}
	void startReceiver() {
		stopAnalog();
		if (webPlaying_) stopInternetRadio();
		if (active()) { state_->setText(tr("DAB+ receiver already running.")); return; }
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
		QStringList receiverArgs{QLatin1String("-c"),current,
			QLatin1String("-w"),QString::number(port_)};
		const QString device=driver_->currentData().toString();
		if (device != QLatin1String("auto"))
			receiverArgs<<QLatin1String("-F")<<device;
		backend_.start(binaryPath(), receiverArgs);
		if (!backend_.waitForStarted(1800)) {
			state_->setText(tr("Could not start verified welle-cli receiver."));
			return;
		}
		activeChannel_ = current;
		state_->setText(tr("Initializing local DAB+ receiver on %1…").arg(current));
		tick_.start();
	}

	void stopReceiver() {
		stopAnalog();
		stopInternetRadio();
		shuttingDown_ = true;
		scanning_ = false;
		stopCaptioning();
		stopLyrics();
		stopRecording();
		tick_.stop();
		if (!playingKey_.isEmpty()) player_->stop();
		playingKey_.clear();
		if (active()) {
			backend_.terminate();
			if (!backend_.waitForFinished(1200)) {
				backend_.kill();
				backend_.waitForFinished(1200);
			}
		}
		port_ = 0;
	}

	void callJson(const QString &endpoint,
	              const std::function<void(const QJsonObject&)> &done) {
		if (!active() || !port_) return;
		QNetworkRequest request(QUrl(base() + endpoint));
		QNetworkReply *reply = network_.get(request);
		connect(reply, &QNetworkReply::finished, this, [reply,done]() {
			const QByteArray bytes = reply->readAll();
			const bool ok = reply->error()==QNetworkReply::NoError &&
				bytes.size() < 1024 * 1024;
			reply->deleteLater();
			if (!ok) return;
			QJsonParseError error;
			const QJsonDocument doc = QJsonDocument::fromJson(bytes,&error);
			if (error.error==QJsonParseError::NoError && doc.isObject())
				done(doc.object());
		});
	}
	void pollMux() {
		if (!active() || scanning_) return;
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
		const double snr=demod.value(QLatin1String("snr")).toDouble();
		const QString quality=(snr>=15?tr("strong"):snr>=8?
			tr("moderate"):tr("weak / uncertain"));
		signal_->setText(tr("Ensemble: %1  |  SNR: %2 dB (%3)  |  FIC errors: %4  |  Gain: %5\nSDR: %6")
			.arg(stationGroup.isEmpty()?tr("not locked"):stationGroup)
			.arg(snr,0,'f',1)
			.arg(quality)
			.arg(fic.value(QLatin1String("numcrcerrors")).toVariant().toString())
			.arg(hardware.value(QLatin1String("gain")).toVariant().toString())
			.arg(hardware.value(QLatin1String("name")).toString()));
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
			if (!stationData_.contains(key)) {
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
					// DLS is live; the audible audio may be delayed by radio caching.
					// This is approximate metadata sync, NOT audio fingerprinting.
					songStartMs_=QDateTime::currentMSecsSinceEpoch()+
						bufferMs_->value();
					lyricCues_=QJsonArray();
					lyricLoaded_=false;
					lyricsEnabled_=false;
					if (lyricsProcess_.state()!=QProcess::NotRunning)
						lyricsProcess_.kill();
					stopLyrics_->setEnabled(false);
					lyrics_->setEnabled(true);
					if (!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
					lyricPath_.clear();
					lyricText_->setText(tr("New DLS text. Lyrics need fresh explicit lookup."));
				}
				const QJsonObject errs=service.value(
					QLatin1String("errorcounters")).toObject();
				const QString technical=tr("Frame / RS / AAC: %1 / %2 / %3")
					.arg(errs.value(QLatin1String("frameerrors")).toVariant().toString())
					.arg(errs.value(QLatin1String("rserrors")).toVariant().toString())
					.arg(errs.value(QLatin1String("aacerrors")).toVariant().toString());
				dls_->setText(tr("Now playing: %1\nDLS: %2\n%3")
					.arg(serviceLabel,dls,technical));
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
		for (int i=0;i<stations_->topLevelItemCount() && i<700;++i) {
			const auto *item=stations_->topLevelItem(i);
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
	void tune(const QString &block, const std::function<void()> &ready) {
		if (!active()) return;
		if (!QRegularExpression(QLatin1String("^(?:[5-9]|1[0-3])[A-F]$"))
		        .match(block).hasMatch()) return;
		QNetworkRequest req(QUrl(base()+QLatin1String("/channel")));
		req.setHeader(QNetworkRequest::ContentTypeHeader,
			QLatin1String("text/plain"));
		QNetworkReply *reply=network_.post(req,block.toUtf8());
		connect(reply,&QNetworkReply::finished,this,[this,reply,block,ready]() {
			const bool ok=reply->error()==QNetworkReply::NoError;
			reply->deleteLater();
			if (!ok) {
				state_->setText(tr("DAB retune failed; skipping unavailable block."));
				if (scanning_) QTimer::singleShot(400,this,[this](){scanStep();});
				return;
			}
			QTimer::singleShot(3200,this,[this,block,ready]() {
				// welle-cli replies 200 even to unsupported DAB blocks.
				// Verify its actual tuned /channel before assigning services
				// to this frequency or playing their MP3 path.
				if (!active()) return;
				QNetworkReply *readback=network_.get(
					QNetworkRequest(QUrl(base()+QLatin1String("/channel"))));
				connect(readback,&QNetworkReply::finished,this,
					[this,readback,block,ready]() {
						const bool matched=readback->error()==QNetworkReply::NoError &&
							QString::fromUtf8(readback->readAll()).trimmed()==block;
						readback->deleteLater();
						if (!matched) {
							state_->setText(tr("DAB %1 is unavailable; not attributing "
								"old station metadata to the wrong frequency.").arg(block));
							if (scanning_) QTimer::singleShot(300,this,[this](){scanStep();});
							return;
						}
						activeChannel_=block;
						channel_->setCurrentText(block);
						ready();
					});
			});
		});
	}
	void beginScan() {
		if (webPlaying_) stopInternetRadio();
		if (!active()) {
			startReceiver();
			if (!active()) return;
		}
		if (scanning_) return;
		if (!playingKey_.isEmpty()) {
			if (QMessageBox::question(this,tr("Full DAB scan"),
				tr("Stop current radio playback, offline captions and "
				"recording while scanning Band III frequencies?"),
				QMessageBox::Yes|QMessageBox::No,QMessageBox::No)!=QMessageBox::Yes)
				return;
			stopCaptioning();
			stopLyrics();
			stopRecording();
			player_->stop();
			playingKey_.clear();
			lastDetectedLanguage_.clear();
		}
		scanning_=true;
		scanIndex_=0;
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
			scanning_=false;
			scan_->setEnabled(true);
			saveStations();
			state_->setText(tr("DAB Band III scan completed · %1 discovered stations.")
				.arg(stations_->topLevelItemCount()));
			return;
		}
		const QString block = channel_->itemText(scanIndex_++);
		state_->setText(tr("Scanning DAB %1 (%2/%3)…")
			.arg(block).arg(scanIndex_).arg(channel_->count()));
		tune(block,[this,block]() {
			callJson(QLatin1String("/mux.json"),
				[this,block](const QJsonObject &data){
					consumeMux(data,block);
					saveStations();
				});
			QTimer::singleShot(700,this,[this](){scanStep();});
		});
	}
	void selectStation(QTreeWidgetItem *item) {
		if (!item) return;
		const QString key=item->data(0,Qt::UserRole).toString();
		const QString block=stationChannels_.value(key);
		if (!active()) { startReceiver(); if (!active()) return; }
		if (scanning_) { state_->setText(tr("Stop or finish scanning before playback.")); return; }
		auto play = [this,key,item]() {
			const bool restartAi=captionProcess_.state()!=QProcess::NotRunning;
			stopCaptioning();
			stopLyrics();
			stopRecording();
			lastDetectedLanguage_.clear();
			lagSamples_.clear();
			lastRadioChunk_=-1;
			displayedRadioChunk_=-1;
			pendingRadioCue_.clear();
			const QString sid=item->text(3);
			const QString stream=QLatin1String("/mp3/")+sid;
			if (!QRegularExpression(QLatin1String("^/mp3/[A-Fa-f0-9x]+$"))
				.match(stream).hasMatch()) return;
			playingKey_=key;
			lastDls_.clear();
			lyricLoaded_=false;
			lyricsEnabled_=false;
			if (lyricsProcess_.state()!=QProcess::NotRunning)
				lyricsProcess_.kill();
			stopLyrics_->setEnabled(false);
			lyrics_->setEnabled(true);
			if (!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
			lyricPath_.clear();
			lyricCues_=QJsonArray();
			slideHistory_.clear(); lastSlideHash_.clear(); slideIndex_=0;
			// Kaffeine's native libVLC audio engine, same global playback controls.
			player_->play(QUrl(base()+stream));
			radioCanvas_->setText(tr("♪ %1\nDAB+ %2 · Live radio\n"
				"Offline captions appear here when enabled.")
				.arg(item->text(1),activeChannel_));
			state_->setText(tr("Playing %1 with native TIHULU/libVLC.")
				.arg(item->text(1)));
			if(restartAi)
				QTimer::singleShot(900,this,[this](){startCaptioning();});
		};
		if (activeChannel_!=block) tune(block,play);
		else play();
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
			record_->setText(tr("Stop recording"));
			state_->setText(tr("Recording real DAB audio locally to %1").arg(filename));
		} else
			state_->setText(tr("FFmpeg recording could not start."));
	}
	void stopRecording() {
		if (recorder_.state()!=QProcess::NotRunning) {
			recorder_.terminate();
			if (!recorder_.waitForFinished(1500))
				recorder_.kill();
		}
		if (record_) record_->setText(tr("Record station"));
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
	void fetchPlot() {
		if (!active()) { state_->setText(tr("Start a DAB receiver first.")); return; }
		if(plotPending_) return;
		const QString type=plotKind_->currentData().toString();
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
		QTimer::singleShot(5000,reply,[reply](){
			if(reply->isRunning()) reply->abort();
		});
		connect(reply,&QNetworkReply::finished,this,[this,reply,type]() {
			plotPending_=false;
			const QByteArray raw=reply->readAll();
			const bool okay=reply->error()==QNetworkReply::NoError &&
				raw.size()>=32 && raw.size()<=262144 && raw.size()%4==0;
			reply->deleteLater();
			if (!okay) { plot_->setText(tr("No valid receiver RF sample.")); return; }
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
				const QSize size=plot_->size();
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
				plot_->setPixmap(QPixmap::fromImage(waterfall_));
				return;
			}
			QImage picture(plot_->width(),plot_->height(),QImage::Format_ARGB32);
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
			plot_->setPixmap(QPixmap::fromImage(picture));
			plot_->setToolTip(tr("%1 receiver RF samples (native float32; signal dependent)")
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
				tr("No real welle.io demodulation metrics yet."));
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
	void applyRadioBuffer() {
		QSettings radioSettings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		radioSettings.setValue(QLatin1String("playbackBufferMs"),bufferMs_->value());
		radioSettings.sync();
		if (!playingKey_.isEmpty() && active()) {
			const QString sid=playingKey_.section(QLatin1Char(':'),1);
			if (!QRegularExpression(QLatin1String("^(?:0x)?[A-Fa-f0-9]{1,8}$"))
				.match(sid).hasMatch()) return;
			// libVLC network cache applies to media OPEN, not existing
			// stream. Explicitly reopen when the owner chooses a new
			// buffer; this can briefly interrupt sound.
			player_->play(QUrl(base()+QLatin1String("/mp3/")+sid));
			lastRadioChunk_=-1;
			cueQueue_.clear();
			pendingRadioCue_.clear();
			lastAdjustmentMs_=QDateTime::currentMSecsSinceEpoch();
			syncStatus_->setText(tr("Reopened radio audio with %1ms requested libVLC "
				"cache. Physical sound-card delay not verified.")
				.arg(bufferMs_->value()));
		} else {
			syncStatus_->setText(tr("Saved %1ms; will apply when station starts.")
				.arg(bufferMs_->value()));
		}
	}
	void startCaptioning() {
		if (!active() || playingKey_.isEmpty()) {
			state_->setText(tr("Play a real DAB+ station before starting offline AI.")); return;
		}
		if (captionProcess_.state()!=QProcess::NotRunning) return;
		const QString sid=playingKey_.section(QLatin1Char(':'),1);
		const QString sourceCode=speechLanguage_->currentData().isValid()?
			speechLanguage_->currentData().toString():
			speechLanguage_->currentText().trimmed();
		QStringList options{QLatin1String("radio-captions"),
			QLatin1String("--port"),QString::number(port_),
			QLatin1String("--sid"),sid,
			QLatin1String("--source"),sourceCode};
		QStringList targets;
		if (english_->isChecked()) targets<<QLatin1String("en");
		if (german_->isChecked()) targets<<QLatin1String("de");
		if (turkish_->isChecked()) targets<<QLatin1String("tr");
		for(const QString &extra:extraTargets_->text().split(QLatin1Char(','),Qt::SkipEmptyParts))
			if(!targets.contains(extra.trimmed()) && targets.size()<6)
				targets<<extra.trimmed();
		options<<QLatin1String("--targets")<<targets.join(QLatin1Char(','));
		if (music_->isChecked()) options<<QLatin1String("--music");
		const QString runtime=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
		if (runtime.isEmpty()) return;
		captionPath_=runtime + QLatin1String("/tihulu-radio-captions-")+
			QString::number(QCoreApplication::applicationPid())+QLatin1String(".json");
		options<<QLatin1String("--output")<<captionPath_;
		QFile::remove(captionPath_);
		captionProcess_.start(QLatin1String("tihulu-tv-center"),options);
		if (!captionProcess_.waitForStarted(1200))
			radioCaption_->setText(tr("Offline radio AI sidecar could not start."));
		else radioCaption_->setText(tr("Offline radio ASR/translation started. "
			"Audio stays on this device; latency depends on model."));
	}
	void displayDueRadioCues(qint64 now) {
		// Queue rather than overwrite: a new AI chunk must not erase the
		// previous chunk before its estimated playback presentation time.
		while(!cueQueue_.isEmpty() && cueQueue_.first().dueMs<=now) {
			const TimedRadioCue cue=cueQueue_.takeFirst();
			if(cue.chunkIndex<=displayedRadioChunk_) continue;
			displayedRadioChunk_=cue.chunkIndex;
			radioCaption_->setText(cue.text);
			radioCanvas_->setText(cue.text.left(680));
		}
	}
	void pollCaption() {
		const qint64 now=QDateTime::currentMSecsSinceEpoch();
		if(captionPath_.isEmpty()) return;
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
		if(chunk>=0 && chunk!=lastRadioChunk_) {
			lastRadioChunk_=chunk;
			const double captured=obj.value(QLatin1String("captured_monotonic")).toDouble();
			const double decoded=obj.value(QLatin1String("decoded_monotonic")).toDouble();
			const int inference=(decoded>=captured && decoded-captured<=90.)
				?int((decoded-captured)*1000):0;
			if(inference>0) {
				lagSamples_.append(inference);
				while(lagSamples_.size()>8) lagSamples_.removeFirst();
			}
			if(autoSync_->isChecked() && lagSamples_.size()>=4 &&
			   now-lastAdjustmentMs_>60000) {
				QList<int> values=lagSamples_;
				std::sort(values.begin(),values.end());
				const int p80=values[values.size()*4/5];
				const int recommended=qBound(0,
					((6000+p80+1400+499)/500)*500,20000);
				lastAdjustmentMs_=now;
				if(recommended>bufferMs_->value()+1500) {
					if(autoRestartAudio_->isChecked()) {
						bufferMs_->setValue(recommended);
						applyRadioBuffer();
					} else {
						syncStatus_->setText(tr("ASR lag: %1ms. Suggested radio cache: "
							"%2ms; Apply manually (audio keeps playing).")
							.arg(p80).arg(recommended));
					}
				}
			}
			// The stream cache is only a requested network delay; not a
			// confirmed DAC timestamp. The user's manual offset is ALWAYS
			// applied to the already-generated cue's display time.
			const int remaining=bufferMs_->value()-6000-inference+550;
			QString caption=obj.value(QLatin1String("original")).toString();
			const auto translations=obj.value(QLatin1String("translations")).toObject();
			for(auto it=translations.begin();it!=translations.end();++it)
				if(it.value().isString())
					caption+=QLatin1String("\n[")+it.key().toUpper()+
						QLatin1String("] ")+it.value().toString();
			if(!caption.isEmpty()) {
				const qint64 due=now+qMax(-1500,remaining)+radioOffsetMs_->value();
				cueQueue_.append({chunk,due,caption.left(1300)});
				while(cueQueue_.size()>12) cueQueue_.removeFirst();
			}
			if(obj.contains(QLatin1String("error")))
				state_->setText(tr("Radio ASR: %1")
					.arg(obj.value(QLatin1String("error")).toString().left(170)));
		}
		displayDueRadioCues(now);
	}
	void stopCaptioning() {
		cueQueue_.clear();
		if (captionProcess_.state()!=QProcess::NotRunning) {
			captionProcess_.terminate();
			if (!captionProcess_.waitForFinished(700))
				captionProcess_.kill();
		}
		if (!captionPath_.isEmpty()) QFile::remove(captionPath_);
		captionPath_.clear();
	}
	void stopLyrics() {
		lyricsEnabled_=false;
		lyrics_->setEnabled(true);
		if (lyricsProcess_.state()!=QProcess::NotRunning) {
			lyricsProcess_.terminate();
			if (!lyricsProcess_.waitForFinished(600)) lyricsProcess_.kill();
		}
		if (!lyricPath_.isEmpty()) QFile::remove(lyricPath_);
		lyricPath_.clear();
		lyricCues_=QJsonArray();
		lyricLoaded_=false;
		stopLyrics_->setEnabled(false);
		lyricText_->setText(tr("Timed lyrics stopped (no online lyric polling)."));
	}
	void fetchLyrics() {
		if (!active() || playingKey_.isEmpty()) {
			lyricText_->setText(tr("Play a station first.")); return;
		}
		const QStringList fields=lastDls_.split(QLatin1String(" - "));
		if (fields.size()<2) {
			lyricText_->setText(tr("No reliable Artist - Title DLS metadata. "
				"Open a saved .lrc manually or wait for song metadata."));
			return;
		}
		const QString artist=fields.at(0).trimmed(),title=fields.at(1).trimmed();
		if (artist.isEmpty() || title.isEmpty() || artist.size()>130 || title.size()>130)
			return;
		if (QMessageBox::question(this,tr("Optional online lyrics lookup"),
			tr("Search LRCLIB for synchronized lyrics?\nArtist: %1\nTitle: %2\n\n"
			   "Only these metadata are sent; no radio audio is uploaded. "
			   "Start time estimated from DLS, so adjust the timing slider manually.")
			   .arg(artist,title))!=QMessageBox::Yes) return;
		const QString runtime=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
		lyricPath_=runtime+QLatin1String("/tihulu-radio-lyrics-")+
			QString::number(QCoreApplication::applicationPid())+QLatin1String(".json");
		QFile::remove(lyricPath_);
		lyricsEnabled_=true;
		lyricLoaded_=false;
		lyrics_->setEnabled(false);
		QString sourceCode=speechLanguage_->currentData().isValid()?
			speechLanguage_->currentData().toString():
			speechLanguage_->currentText().trimmed();
		if(sourceCode==QLatin1String("auto") && !lastDetectedLanguage_.isEmpty())
			sourceCode=lastDetectedLanguage_;
		QStringList dests;
		if(english_->isChecked()) dests<<QLatin1String("en");
		if(german_->isChecked()) dests<<QLatin1String("de");
		if(turkish_->isChecked()) dests<<QLatin1String("tr");
		for(const QString &part:extraTargets_->text().split(QLatin1Char(','),Qt::SkipEmptyParts))
			if(dests.size()<6 && !dests.contains(part.trimmed()))
				dests<<part.trimmed();
		lyricsProcess_.start(QLatin1String("tihulu-tv-center"),
			{QLatin1String("lyrics-lookup"),QLatin1String("--artist"),artist,
			 QLatin1String("--track"),title,QLatin1String("--output"),lyricPath_,
			 QLatin1String("--source"),sourceCode,
			 QLatin1String("--targets"),dests.join(QLatin1Char(',')),
			 QLatin1String("--online")});
		if (!lyricsProcess_.waitForStarted(900)) {
			lyricsEnabled_=false;
			lyrics_->setEnabled(true);
			lyricText_->setText(tr("Could not start lyrics lookup."));
			return;
		}
		stopLyrics_->setEnabled(true);
		lyricText_->setText(tr("Searching verified time-coded lyrics… Stop available."));
	}
	void updateLyrics() {
		if (!lyricsEnabled_) return;
		if (lyricPath_.isEmpty() || lyricLoaded_) {
			if (!lyricCues_.isEmpty() && songStartMs_>0) {
				const double elapsed=(QDateTime::currentMSecsSinceEpoch()-songStartMs_+
					lyricsOffset_->value())/1000.;
				QString current;
				for (const QJsonValue &item:lyricCues_) {
					const QJsonObject cue=item.toObject();
					if (cue.value(QLatin1String("start")).toDouble()<=elapsed &&
					    cue.value(QLatin1String("end")).toDouble()>elapsed) {
						current=cue.value(QLatin1String("text")).toString();
						const QJsonObject translated=cue.value(
							QLatin1String("translations")).toObject();
						for(auto it=translated.begin();it!=translated.end();++it)
							if(it.value().isString() && !it.value().toString().isEmpty())
								current+=QLatin1String("\n[")+it.key().toUpper()+
									QLatin1String("] ")+it.value().toString();
						break;
					}
				}
				if (!current.isEmpty())
					lyricText_->setText(tr("Estimated lyric timing · %1").arg(current));
			}
			return;
		}
		QFile file(lyricPath_);
		if (!file.open(QIODevice::ReadOnly) || file.size()>250000) return;
		const auto value=QJsonDocument::fromJson(file.readAll()).object();
		if (value.value(QLatin1String("status")).toString()==QLatin1String("completed")) {
			lyricLoaded_=true;
			lyricCues_=value.value(QLatin1String("cues")).toArray();
			lyricText_->setText(tr("%1 synchronized lyric lines · estimated "
				"from DLS time; adjust offset as necessary.")
				.arg(lyricCues_.size()));
		} else if (value.value(QLatin1String("status")).toString()==QLatin1String("error")) {
			lyricLoaded_=true;
			lyricText_->setText(value.value(QLatin1String("reason")).toString().left(190));
		}
	}
	MediaWidget *player_;
	QLabel *radioCanvas_=nullptr;
	QWidget *playerHost_=nullptr;
	QVBoxLayout *playerHostLayout_=nullptr;
	QComboBox *channel_=nullptr, *driver_=nullptr, *speechLanguage_=nullptr,
		*plotKind_=nullptr, *fftPlacement_=nullptr;
	QPushButton *start_=nullptr,*stop_=nullptr,*scan_=nullptr,*record_=nullptr,
		*caption_=nullptr,
		*stopCaption_=nullptr,*lyrics_=nullptr,*stopLyrics_=nullptr,
		*slidePrev_=nullptr,*slideNext_=nullptr;
	QTreeWidget *stations_=nullptr;
	QComboBox *libraryBlock_=nullptr;
	QLineEdit *stationSearch_=nullptr;
	QLineEdit *webSearch_=nullptr,*webCountry_=nullptr,*webSource_=nullptr;
	QPushButton *webSearchButton_=nullptr,*webPlay_=nullptr,*webStop_=nullptr;
	QTreeWidget *webStations_=nullptr;
	QCheckBox *webFavoritesOnly_=nullptr;
	QLabel *webStatus_=nullptr;
	QLabel *analogStatus_=nullptr;
	QComboBox *analogBand_=nullptr;
	QDoubleSpinBox *analogFrequency_=nullptr;
	QDial *analogDial_=nullptr;
	QPushButton *analogStart_=nullptr,*analogStop_=nullptr;
	QCheckBox *directSampling_=nullptr;
	bool analogStopping_=false;
	QSet<QString> internetFavorites_;
	bool webPlaying_=false;
	QCheckBox *favoritesOnly_=nullptr;
	QLabel *libraryStatus_=nullptr;
	QSet<QString> favorites_;
	QLabel *state_=nullptr,*dls_=nullptr,*signal_=nullptr,*slide_=nullptr,
		*radioCaption_=nullptr,*lyricText_=nullptr,*plot_=nullptr;
	QCheckBox *english_=nullptr,*german_=nullptr,*turkish_=nullptr,*music_=nullptr,
		*livePlot_=nullptr,*showWidgets_=nullptr,
		*coarseCorrector_=nullptr;
	QSlider *lyricsOffset_=nullptr;
	QSpinBox *bufferMs_=nullptr,*radioOffsetMs_=nullptr;
	QCheckBox *autoSync_=nullptr,*autoRestartAudio_=nullptr;
	int lastCaptionOffsetMs_=0;
	QList<TimedRadioCue> cueQueue_;
	QLineEdit *extraTargets_=nullptr;
	QLabel *syncStatus_=nullptr;
	QProcess backend_,captionProcess_,recorder_,lyricsProcess_;
	QProcess analogDemod_{this},analogAudio_{this};
	QNetworkAccessManager network_;
	QTimer tick_;
	quint16 port_=0;
	bool scanning_=false,shuttingDown_=false,slidePending_=false,lyricLoaded_=false,
		lyricsEnabled_=false,
		plotPending_=false;
	int scanIndex_=0;
	qint64 songStartMs_=0;
	QString activeChannel_,playingKey_,lastDls_,captionPath_,lyricPath_,
		lastDetectedLanguage_;
	QMap<QString,QJsonObject> stationData_;
	QMap<QString,QString> stationChannels_;
	QJsonArray lyricCues_;
	QJsonObject lastMux_;
	QList<int> lagSamples_;
	int lastRadioChunk_=-1,displayedRadioChunk_=-1;
	qint64 lastAdjustmentMs_=0,radioCueDueMs_=0;
	QString pendingRadioCue_;
	QList<QPixmap> slideHistory_;
	QByteArray lastSlideHash_;
	QImage waterfall_;
	int slideIndex_=0;
};

#endif // TIHULU_NATIVE_RADIO_TAB_H
