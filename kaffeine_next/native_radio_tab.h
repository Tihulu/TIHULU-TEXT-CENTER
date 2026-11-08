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
#include <QFile>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHostAddress>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
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
#include <QSlider>
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
		  network_(this), tick_(this)
	{
		setParent(parent);
		auto *root = new QVBoxLayout(this);
		root->setContentsMargins(9, 9, 9, 9);
		root->setSpacing(8);
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
		start_ = new QPushButton(tr("Start receiver"), this);
		start_->setToolTip(tr("Open an actual DAB-capable RTL-SDR/Soapy device on demand."));
		stop_ = new QPushButton(tr("Stop / release SDR"), this);
		scan_ = new QPushButton(tr("Scan all blocks"), this);
		scan_->setToolTip(tr("Retunes across Band III blocks; can take minutes."));
		header->addWidget(start_);
		header->addWidget(scan_);
		header->addWidget(stop_);
		root->addLayout(header);

		state_ = new QLabel(tr("Receiver disconnected. A separate DAB-capable SDR is required; "
			"the DVB-T2 television adapter is not automatically a DAB receiver."), this);
		state_->setWordWrap(true);
		state_->setTextFormat(Qt::PlainText);
		root->addWidget(state_);

		auto *split = new QSplitter(Qt::Horizontal, this);
		stations_ = new QTreeWidget(split);
		stations_->setHeaderLabels({tr("Station"), tr("DAB block"), tr("Service ID")});
		stations_->setRootIsDecorated(false);
		stations_->setAlternatingRowColors(true);
		stations_->setSortingEnabled(true);
		stations_->setMinimumWidth(240);
		split->addWidget(stations_);

		auto *right = new QWidget(split);
		auto *rightLayout = new QVBoxLayout(right);
		rightLayout->setContentsMargins(5, 4, 5, 4);
		rightLayout->setSpacing(6);
		playerHost_ = new QWidget(right);
		playerHostLayout_ = new QVBoxLayout(playerHost_);
		playerHostLayout_->setContentsMargins(0, 0, 0, 0);
		rightLayout->addWidget(playerHost_, 3);

		auto *meta = new QHBoxLayout();
		slide_ = new QLabel(tr("No DAB slideshow"), right);
		slide_->setAlignment(Qt::AlignCenter);
		slide_->setFixedSize(185, 112);
		slide_->setStyleSheet(QLatin1String("border:1px solid #466;"));
		meta->addWidget(slide_);
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
		split->setStretchFactor(1, 2);
		root->addWidget(split, 4);

		auto *lab = new QGroupBox(tr("Offline radio AI · Whisper / translation / timed lyrics"), this);
		auto *v = new QVBoxLayout(lab);
		auto *row = new QHBoxLayout();
		speechLanguage_ = new QComboBox(lab);
		speechLanguage_->setEditable(true);
		speechLanguage_->addItems({"de","en","tr","fr","es","pl","ar","ja"});
		english_ = new QCheckBox(tr("English"), lab); english_->setChecked(true);
		turkish_ = new QCheckBox(tr("Turkish"), lab); turkish_->setChecked(true);
		music_ = new QCheckBox(tr("Transcribe singing / music vocals"), lab);
		caption_ = new QPushButton(tr("Start offline live captions"), lab);
		stopCaption_ = new QPushButton(tr("Stop AI captions"), lab);
		row->addWidget(new QLabel(tr("Source:"), lab));
		row->addWidget(speechLanguage_);
		row->addWidget(english_);
		row->addWidget(turkish_);
		row->addWidget(music_);
		row->addWidget(caption_);
		row->addWidget(stopCaption_);
		v->addLayout(row);
		radioCaption_ = new QLabel(tr("Radio AI is OFF; it never starts without your request."), lab);
		radioCaption_->setTextFormat(Qt::PlainText);
		radioCaption_->setWordWrap(true);
		v->addWidget(radioCaption_);
		auto *lyricsRow = new QHBoxLayout();
		lyrics_ = new QPushButton(tr("Find timed lyrics (optional internet)"), lab);
		lyricsOffset_ = new QSlider(Qt::Horizontal, lab);
		lyricsOffset_->setRange(-12000, 12000);
		lyricsOffset_->setValue(0);
		lyricsOffset_->setToolTip(tr("Manual lyric sync offset, milliseconds (-12s to +12s)."));
		lyricsRow->addWidget(lyrics_);
		lyricsRow->addWidget(new QLabel(tr("Lyric timing:"), lab));
		lyricsRow->addWidget(lyricsOffset_, 1);
		v->addLayout(lyricsRow);
		lyricText_ = new QLabel(tr("No synchronized lyrics loaded."), lab);
		lyricText_->setTextFormat(Qt::PlainText);
		lyricText_->setWordWrap(true);
		v->addWidget(lyricText_);
		root->addWidget(lab);

		auto *diagnostics = new QHBoxLayout();
		plotKind_ = new QComboBox(this);
		plotKind_->addItem(tr("Spectrum"), "spectrum");
		plotKind_->addItem(tr("Null spectrum"), "nullspectrum");
		plotKind_->addItem(tr("CIR / impulse response"), "impulseresponse");
		plotKind_->addItem(tr("Constellation phase"), "constellation");
		plot_ = new QLabel(tr("On-demand RF plots"), this);
		plot_->setFixedSize(330, 110);
		plot_->setAlignment(Qt::AlignCenter);
		plot_->setStyleSheet(QLatin1String("border:1px solid #456;"));
		auto *plotButton = new QPushButton(tr("Capture RF plot"), this);
		diagnostics->addWidget(plotKind_);
		diagnostics->addWidget(plotButton);
		diagnostics->addWidget(plot_, 1);
		root->addLayout(diagnostics);

		connect(start_, &QPushButton::clicked, this, [this](){ startReceiver(); });
		connect(stop_, &QPushButton::clicked, this, [this](){ stopReceiver(); });
		connect(scan_, &QPushButton::clicked, this, [this](){ beginScan(); });
		connect(stations_, &QTreeWidget::itemDoubleClicked, this,
			[this](QTreeWidgetItem *item, int){ selectStation(item); });
		connect(caption_, &QPushButton::clicked, this, [this](){ startCaptioning(); });
		connect(stopCaption_, &QPushButton::clicked, this, [this](){ stopCaptioning(); });
		connect(lyrics_, &QPushButton::clicked, this, [this](){ fetchLyrics(); });
		connect(plotButton, &QPushButton::clicked, this, [this](){ fetchPlot(); });
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
		connect(&tick_, &QTimer::timeout, this, [this](){ pollMux(); pollCaption(); updateLyrics(); });
		loadStations();
	}

	~TihuluRadioTab() override { stopReceiver(); }

	void activate() override {
		// Same Kaffeine MediaWidget and libVLC controls as Playback/Television.
		// Moving the widget between tabs does not start a second player.
		playerHostLayout_->addWidget(player_);
	}

private:
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

	void startReceiver() {
		if (active()) { state_->setText(tr("DAB+ receiver already running.")); return; }
		if (!prepared()) {
			QMessageBox::information(this,tr("Optional local DAB+ receiver"),
				tr("Install the pinned loopback-only welle-cli backend first:\n"
				   "bash ~/.local/share/tihulu-kaffeine/kaffeine_next/install_welle.sh\n"
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
		backend_.start(binaryPath(), {QLatin1String("-c"),current,
			QLatin1String("-w"),QString::number(port_)});
		if (!backend_.waitForStarted(1800)) {
			state_->setText(tr("Could not start verified welle-cli receiver."));
			return;
		}
		activeChannel_ = current;
		state_->setText(tr("Initializing local DAB+ receiver on %1…").arg(current));
		tick_.start();
	}

	void stopReceiver() {
		shuttingDown_ = true;
		scanning_ = false;
		stopCaptioning();
		tick_.stop();
		player_->stop();
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
		const auto receiver = mux.value(QLatin1String("receiver")).toObject();
		const auto hardware = receiver.value(QLatin1String("hardware")).toObject();
		const auto demod = mux.value(QLatin1String("demodulator")).toObject();
		const auto fic = demod.value(QLatin1String("fic")).toObject();
		const auto ensemble = mux.value(QLatin1String("ensemble")).toObject();
		const QString stationGroup = label(ensemble.value(QLatin1String("label")));
		signal_->setText(tr("Ensemble: %1  |  SNR: %2 dB  |  FIC errors: %3  |  Gain: %4\nSDR: %5")
			.arg(stationGroup.isEmpty()?tr("not locked"):stationGroup)
			.arg(demod.value(QLatin1String("snr")).toDouble(),0,'f',1)
			.arg(fic.value(QLatin1String("numcrcerrors")).toVariant().toString())
			.arg(hardware.value(QLatin1String("gain")).toVariant().toString())
			.arg(hardware.value(QLatin1String("name")).toString()));
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
					{serviceLabel, ch, sid});
				item->setData(0,Qt::UserRole,key);
				stations_->addTopLevelItem(item);
				stationData_[key] = service;
				stationChannels_[key] = ch;
			}
			stationData_[key] = service;
			if (key==playingKey_) {
				const QString dls = label(service.value(QLatin1String("dls"))
				                         .toObject().value(QLatin1String("label")));
				if (!dls.isEmpty() && lastDls_ != dls) {
					lastDls_=dls;
					songStartMs_=QDateTime::currentMSecsSinceEpoch();
					lyricCues_.clear();
					lyricText_->setText(tr("New DLS text. Lyrics need fresh explicit lookup."));
				}
				dls_->setText(tr("Now playing: %1\nDLS: %2").arg(serviceLabel,dls));
				requestSlide(sid);
			}
		}
		if (!stations.isEmpty())
			state_->setText(tr("DAB+ %1 · %2 total known stations · local receiver")
				.arg(ch).arg(stations_->topLevelItemCount()));
	}
	void loadStations() {
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
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
			auto *item = new QTreeWidgetItem({name,ch,sid});
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
			obj[QLatin1String("channel")]=item->text(1);
			obj[QLatin1String("sid")]=item->text(2);
			obj[QLatin1String("name")]=item->text(0);
			list.append(obj);
		}
		QSettings settings(QLatin1String("TIHULU"),QLatin1String("KaffeineRadio"));
		settings.setValue(QLatin1String("dabStationCache"),
			QJsonDocument(list).toJson(QJsonDocument::Compact));
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
			if (!ok) { state_->setText(tr("DAB retune failed.")); return; }
			activeChannel_=block;
			channel_->setCurrentText(block);
			QTimer::singleShot(3200,this,ready);
		});
	}
	void beginScan() {
		if (!active()) {
			startReceiver();
			if (!active()) return;
		}
		if (scanning_) return;
		scanning_=true;
		scanIndex_=0;
		scan_->setEnabled(false);
		state_->setText(tr("Scanning real DAB Band III frequencies…"));
		scanStep();
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
			const QString sid=item->text(2);
			const QString stream=QLatin1String("/mp3/")+sid;
			if (!QRegularExpression(QLatin1String("^/mp3/[A-Fa-f0-9x]+$"))
				.match(stream).hasMatch()) return;
			playingKey_=key;
			lastDls_.clear();
			lyricCues_.clear();
			// Kaffeine's native libVLC audio engine, same global playback controls.
			player_->play(QUrl(base()+stream));
			state_->setText(tr("Playing %1 with Kaffeine / libVLC.")
				.arg(item->text(0)));
		};
		if (activeChannel_!=block) tune(block,play);
		else play();
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
			if (image.loadFromData(bytes) && image.width()<2500 && image.height()<2500)
				slide_->setPixmap(QPixmap::fromImage(image).scaled(
					slide_->size(),Qt::KeepAspectRatio,Qt::SmoothTransformation));
		});
	}
	void fetchPlot() {
		if (!active()) { state_->setText(tr("Start a DAB receiver first.")); return; }
		const QString type=plotKind_->currentData().toString();
		if (type!=QLatin1String("spectrum") &&
		    type!=QLatin1String("nullspectrum") &&
		    type!=QLatin1String("impulseresponse") &&
		    type!=QLatin1String("constellation")) return;
		QNetworkReply *reply=network_.get(QNetworkRequest(QUrl(base()+QLatin1Char('/')+type)));
		connect(reply,&QNetworkReply::finished,this,[this,reply,type]() {
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
	void startCaptioning() {
		if (!active() || playingKey_.isEmpty()) {
			state_->setText(tr("Play a real DAB+ station before starting offline AI.")); return;
		}
		if (captionProcess_.state()!=QProcess::NotRunning) return;
		const QString sid=playingKey_.section(QLatin1Char(':'),1);
		QStringList options{QLatin1String("radio-captions"),
			QLatin1String("--port"),QString::number(port_),
			QLatin1String("--sid"),sid,
			QLatin1String("--source"),speechLanguage_->currentText()};
		QStringList targets;
		if (english_->isChecked()) targets<<QLatin1String("en");
		if (turkish_->isChecked()) targets<<QLatin1String("tr");
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
	void pollCaption() {
		if (captionPath_.isEmpty()) return;
		QFile stream(captionPath_);
		if (!stream.open(QIODevice::ReadOnly) || stream.size()>15000) return;
		const auto obj=QJsonDocument::fromJson(stream.readAll()).object();
		QString text=obj.value(QLatin1String("original")).toString();
		const auto translated=obj.value(QLatin1String("translations")).toObject();
		for (auto it=translated.begin();it!=translated.end();++it)
			if (it.value().isString())
				text+=QLatin1String("\n[")+it.key().toUpper()+
					QLatin1String("] ")+it.value().toString();
		if (!text.isEmpty())
			radioCaption_->setText(text.left(1300));
		else if (obj.contains(QLatin1String("error")))
			radioCaption_->setText(tr("Radio speech processing: %1")
				.arg(obj.value(QLatin1String("error")).toString().left(170)));
	}
	void stopCaptioning() {
		if (captionProcess_.state()!=QProcess::NotRunning) {
			captionProcess_.terminate();
			if (!captionProcess_.waitForFinished(700))
				captionProcess_.kill();
		}
		if (!captionPath_.isEmpty()) QFile::remove(captionPath_);
		captionPath_.clear();
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
		QProcess::startDetached(QLatin1String("tihulu-tv-center"),
			{QLatin1String("lyrics-lookup"),QLatin1String("--artist"),artist,
			 QLatin1String("--track"),title,QLatin1String("--output"),lyricPath_,
			 QLatin1String("--online")});
		lyricText_->setText(tr("Checking time-coded lyrics…"));
	}
	void updateLyrics() {
		if (lyricPath_.isEmpty() || lyricLoaded_) {
			if (!lyricCues_.isEmpty() && songStartMs_>0) {
				const double elapsed=(QDateTime::currentMSecsSinceEpoch()-songStartMs_+
					lyricsOffset_->value())/1000.;
				QString current;
				for (const auto &cue:lyricCues_) {
					if (cue.value(QLatin1String("start")).toDouble()<=elapsed &&
					    cue.value(QLatin1String("end")).toDouble()>elapsed) {
						current=cue.value(QLatin1String("text")).toString();
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
	QWidget *playerHost_=nullptr;
	QVBoxLayout *playerHostLayout_=nullptr;
	QComboBox *channel_=nullptr, *speechLanguage_=nullptr, *plotKind_=nullptr;
	QPushButton *start_=nullptr,*stop_=nullptr,*scan_=nullptr,*caption_=nullptr,
		*stopCaption_=nullptr,*lyrics_=nullptr;
	QTreeWidget *stations_=nullptr;
	QLabel *state_=nullptr,*dls_=nullptr,*signal_=nullptr,*slide_=nullptr,
		*radioCaption_=nullptr,*lyricText_=nullptr,*plot_=nullptr;
	QCheckBox *english_=nullptr,*turkish_=nullptr,*music_=nullptr;
	QSlider *lyricsOffset_=nullptr;
	QProcess backend_,captionProcess_;
	QNetworkAccessManager network_;
	QTimer tick_;
	quint16 port_=0;
	bool scanning_=false,shuttingDown_=false,slidePending_=false,lyricLoaded_=false;
	int scanIndex_=0;
	qint64 songStartMs_=0;
	QString activeChannel_,playingKey_,lastDls_,captionPath_,lyricPath_;
	QMap<QString,QJsonObject> stationData_;
	QMap<QString,QString> stationChannels_;
	QJsonArray lyricCues_;
};

#endif // TIHULU_NATIVE_RADIO_TAB_H
