#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproducible changes to KDE Kaffeine 2.0.19 (no second DVB tuner).

Kaffeine continues to own scanning, EPG, Teletext, stream filtering and
libVLC. Only explicit user actions start Whisper and translation.
"""
from pathlib import Path
import sys

UPSTREAM = "https://github.com/KDE/kaffeine.git"
TAG = "v2.0.19"
REVISION = "e7ea15b86dafed3b20b151cbcb080578ab8e2d5c"
PATHS = ("src/mainwindow.cpp", "src/mainwindow.h", "src/CMakeLists.txt",
         "src/dvb/dvbliveview.cpp",
         "src/dvb/dvbliveview_p.h", "src/dvb/dvbmanager.cpp", "src/dvb/dvbtab.cpp",
         "src/dvb/dvbtab.h", "src/backend-vlc/vlcmediawidget.cpp",
         "src/mediawidget.cpp", "src/mediawidget.h", "src/osdwidget.cpp",
         "src/osdwidget.h", "src/main.cpp", "src/dvb/dvbepg.cpp")

def transform(files):
    files = dict(files)
    def change(path, before, after):
        source = files[path]
        if after in source:
            return
        if source.count(before) != 1:
            raise ValueError("Unexpected Kaffeine source; patch refused: "+path+" "+repr(before[:48]))
        files[path] = source.replace(before, after)

    # Integrate DAB+ into the same Kaffeine window and its existing
    # libVLC player. The optional upstream welle-cli backend runs only
    # on deliberate Radio -> Start; no second Qt/WebUSB player window.
    main = "src/mainwindow.cpp"
    change(main, '#include "playlist/playlisttab.h"\n',
           '#include "playlist/playlisttab.h"\n#include "tihulu_radio_tab.h"\n')
    change(main, '''#endif /* HAVE_DVB == 1 */
	tabBar->setShape(QTabBar::RoundedWest);''',
           '''#endif /* HAVE_DVB == 1 */
	tabBar->addTab(QIcon::fromTheme(QLatin1String("audio-radio")),
		i18n("Radio (DAB+)"));
	tabBar->setShape(QTabBar::RoundedWest);''')
    change(main, '''#endif /* HAVE_DVB == 1 */

	currentTabIndex = StartTabId;''',
           '''#endif /* HAVE_DVB == 1 */

	// Native radio page shares Kaffeine's existing libVLC MediaWidget.
	// Its optional welle-cli backend is explicitly started and stopped.
	TabBase *radioTab = new TihuluRadioTab(mediaWidget, this);
	tabs.append(radioTab);
	stackedLayout->addWidget(radioTab);

	currentTabIndex = StartTabId;''')
    # Keep original Playback libVLC widget. Local file AI controls live
    # INSIDE its own tab; the older launched media-captions-ui remains
    # available only as an optional legacy menu entry.
    change(main, '#include "tihulu_radio_tab.h"\n',
           '#include "tihulu_radio_tab.h"\n#include "tihulu_media_panel.h"\n')
    change(main, '''	void activate() override
	{
		layout()->addWidget(mediaWidget);
		mediaWidget->setFocus();
	}

private:
	MediaWidget *mediaWidget;
};''',
           '''	void activate() override
	{
		// Insert at TOP on every activation; re-adding at the end
		// would put video UNDER the AI toolbar after the next tab switch.
		static_cast<QVBoxLayout *>(layout())->insertWidget(0, mediaWidget, 1);
		mediaWidget->setFocus();
	}
	void setLocalFile(const QUrl &url) { aiPanel->setLocalFile(url); }

private:
	MediaWidget *mediaWidget;
	TihuluMediaPanel *aiPanel;
};''')
    change(main, '''PlayerTab::PlayerTab(MediaWidget *mediaWidget_) : mediaWidget(mediaWidget_)
{
	QHBoxLayout *layout = new QHBoxLayout(this);
	layout->setContentsMargins(0, 0, 0, 0);
}''',
           '''PlayerTab::PlayerTab(MediaWidget *mediaWidget_) : mediaWidget(mediaWidget_)
{
	QVBoxLayout *layout = new QVBoxLayout(this);
	layout->setContentsMargins(0, 0, 0, 0);
	layout->setSpacing(0);
	aiPanel = new TihuluMediaPanel(mediaWidget, this);
	layout->addWidget(mediaWidget, 1);
	layout->addWidget(aiPanel, 0);
}''')
    change(main, '''	QUrl copy(url);
	actionOpenRecent->addUrl(copy);''',
           '''	QUrl copy(url);
	// Keep local video/audio player *inside* this Playback tab.
	// Its optional AI captions are generated in the bottom panel.
	playerTab->setLocalFile(copy);
	actionOpenRecent->addUrl(copy);''')
    hdrmain = "src/mainwindow.h"
    change(hdrmain, '\t\tDvbTabId = 3\n',
           '\t\tDvbTabId = 3,\n\t\tRadioTabId = 4\n')
    change(hdrmain, '\tvoid playDvb();\n',
           '\tvoid playDvb();\n\tvoid playRadio();\n')
    change(main, '''void MainWindow::configureKeys()
{''',
           '''void MainWindow::playRadio()
{
	activateTab(RadioTabId);
}

void MainWindow::configureKeys()
{''')
    change(main, '''#endif /* HAVE_DVB == 1 */
}

QAbstractButton *StartTab::addShortcut''',
           '''	button = addShortcut(i18n("&6 DAB+ Radio"),
		QIcon::fromTheme(QLatin1String("audio-radio")), this);
	button->setShortcut(Qt::Key_6);
	button->setWhatsThis(i18n("Open the native TIHULU DAB+ station library."));
	connect(button, SIGNAL(clicked()), mainWindow, SLOT(playRadio()));
	gridLayout->addWidget(button, 1, 2);
#endif /* HAVE_DVB == 1 */
}

QAbstractButton *StartTab::addShortcut''')
    # Rebuild Start as a TIHULU home screen, while retaining the
    # original Kaffeine file/CD/DVD/TV actions and shortcuts.
    change(main, '''	setBackgroundRole(QPalette::Base);
	setAutoFillBackground(true);

	QGridLayout *gridLayout = new QGridLayout(this);''',
           '''	setObjectName(QLatin1String("tihuluHome"));
	setStyleSheet(QLatin1String(
		"QWidget#tihuluHome{background:#101d2d;color:#e2f6ff}"
		"QToolButton{background:#1b3b53;color:#f3fbff;"
		"border:1px solid #366b89;border-radius:9px;"
		"min-width:186px;padding:14px}"
		"QToolButton:hover{background:#215875}"
	));
	QVBoxLayout *frame=new QVBoxLayout(this);
	frame->setContentsMargins(24,18,24,18);
	auto *heading=new QLabel(i18n("TIHULU Media Center\\n"
		"TV · Radio · Video / Audio · Offline AI"),this);
	heading->setAlignment(Qt::AlignCenter);
	heading->setStyleSheet(QLatin1String(
		"font-size:24px;font-weight:700;color:#b6f6fe;padding:12px"));
	frame->addWidget(heading,0,Qt::AlignCenter);
	QGridLayout *gridLayout = new QGridLayout();''')
    change(main, '''	gridLayout->setSpacing(15);

	QAbstractButton *button =''',
           '''	gridLayout->setSpacing(15);
	frame->addLayout(gridLayout,1);
	QAbstractButton *button =''')
    change(main, '''	gridLayout->addWidget(button, 1, 2);
#endif /* HAVE_DVB == 1 */''',
           '''	gridLayout->addWidget(button, 1, 2);
	button = addShortcut(i18n("&7 Open Media + Offline AI"),
		QIcon::fromTheme(QLatin1String("video-x-generic")),this);
	button->setShortcut(Qt::Key_7);
	connect(button,SIGNAL(clicked()),mainWindow,SLOT(open()));
	gridLayout->addWidget(button,2,0,1,3);
#endif /* HAVE_DVB == 1 */''')
    # Use a unique application ID and KConfig/SQLite user-data path.
    # This is a distinctly installed app, not the system KDE Kaffeine
    # process or a secondary window inside the existing binary.
    appmain = "src/main.cpp"
    change(appmain, '''		QStringLiteral("kaffeine"),
		i18n("Kaffeine"),''',
           '''		QStringLiteral("tihulu-media-center"),
		i18n("TIHULU Media Center"),''')
    change(appmain, '''		i18n("A media player by KDE with digital TV support."),''',
           '''		i18n("TIHULU · TV, DAB+ radio, media and offline AI; built on KDE Kaffeine."),''')
    change(appmain, '''{
	QString path = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);''',
           '''{
	// Isolate SQL and KSharedConfig BEFORE opening the database.
	setApplicationName("tihulu-media-center");
	setOrganizationName("TIHULU");
	setOrganizationDomain("tihulu.local");
	QString path = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);''')
    change(appmain, '''	app.setApplicationName("kaffeine");
	app.setOrganizationDomain("kde.org");
	app.setWindowIcon(QIcon::fromTheme(QLatin1String("kaffeine"), QIcon(":kaffeine")));''',
           '''	app.setApplicationName("tihulu-media-center");
	app.setOrganizationName("TIHULU");
	app.setOrganizationDomain("tihulu.local");
	app.setWindowIcon(QIcon::fromTheme(QLatin1String("tihulu-media-center"),
		QIcon(":kaffeine")));''')
    change(main, '''	menu = new QMenu(i18n("Kaffeine"), this);''',
           '''	menu = new QMenu(i18n("TIHULU Media Center"), this);''')
    change(main, '''	trayIcon->setToolTip(i18n("Kaffeine"));''',
           '''	trayIcon->setToolTip(i18n("TIHULU Media Center"));''')
    change(main, '''	connect(mediaWidget, SIGNAL(changeCaption(QString)), this, SLOT(setWindowTitle(QString)));''',
           '''	connect(mediaWidget, &MediaWidget::changeCaption, this,
		[this](const QString &caption) {
			setWindowTitle(caption.isEmpty() ? QStringLiteral("TIHULU Media Center")
				: caption + QStringLiteral(" — TIHULU Media Center"));
		});''')
    cmake = "src/CMakeLists.txt"
    change(cmake, 'target_link_libraries(kaffeine Qt5::Sql Qt5::X11Extras',
           'target_link_libraries(kaffeine Qt5::Network Qt5::Sql Qt5::X11Extras')
    change(main, "#include <QMainWindow>\n",
           "#include <QMainWindow>\n#include <QCoreApplication>\n"
           "#include <QProcess>\n#include <QMessageBox>\n#include <QStandardPaths>\n")
    change(main, "#include <QStandardPaths>\n",
           "#include <QStandardPaths>\n#include <QLabel>\n#include <QVBoxLayout>\n")
    change(main, '''#if HAVE_DVB == 1
	QMenu *dvbMenu = new QMenu(i18n("&Television"), this);
	menuBar->addMenu(dvbMenu);
#endif /* HAVE_DVB == 1 */
''', '''#if HAVE_DVB == 1
	QMenu *dvbMenu = new QMenu(i18n("&Television"), this);
	menuBar->addMenu(dvbMenu);
	// Keep native Kaffeine channel switching, Teletext and player unchanged.
	QMenu *aiMenu = new QMenu(i18n("TIHULU &AI"), this);
	menuBar->addMenu(aiMenu);
	QAction *marketAction = aiMenu->addAction(i18n("Whisper + Translator Market"));
	connect(marketAction, &QAction::triggered, this, [this]() {
		if (!QProcess::startDetached(QLatin1String("tihulu-tv-center"),
			QStringList() << QLatin1String("ai-market")))
			QMessageBox::warning(this, i18n("Whisper Market"),
				i18n("Install the TIHULU offline AI companion first."));
	});
	QAction *captionAction = aiMenu->addAction(i18n("Live Teletext / Whisper subtitles"));
	connect(captionAction, &QAction::triggered, this, [this]() {
		const QString runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
		if (runtime.isEmpty()) {
			QMessageBox::warning(this, i18n("Live captions"),
				i18n("XDG_RUNTIME_DIR is missing; cannot start private capture."));
			return;
		}
		const QString name = runtime + QLatin1String("/tihulu-dvb-")
			+ QString::number(QCoreApplication::applicationPid())
			+ QLatin1String(".sock");
		if (!QProcess::startDetached(QLatin1String("tihulu-tv-center"),
			QStringList() << QLatin1String("kaffeine-captions")
				<< QLatin1String("--socket") << name))
			QMessageBox::warning(this, i18n("Live captions"),
				i18n("Install the TIHULU caption companion first."));
	});
#endif /* HAVE_DVB == 1 */
''')
    # Give locally opened video/audio files the SAME managed offline
    # Whisper/translation engines via optional SRT creation dialogue.
    # No file uploads and no interference with native playback.
    change(main, '''	QAction *captionAction = aiMenu->addAction(i18n("Live Teletext / Whisper subtitles"));''',
           '''	QAction *mediaCaptionAction = aiMenu->addAction(
		i18n("Generate AI captions / lyrics for local Video or Audio..."));
	connect(mediaCaptionAction, &QAction::triggered, this, [this]() {
		const QString file = QFileDialog::getOpenFileName(
			this, i18n("Open local video or audio for offline captions"),
			QString(),
			i18n("Media files (*.mp4 *.mkv *.mov *.avi *.webm *.ts *.flac "
			     "*.mp3 *.wav *.m4a *.aac *.ogg *.opus);;All files (*)"));
		if (file.isEmpty()) return;
		// Play in THIS same window; the Playback tab includes the
		// offline GPU/translation/lyrics controls under native libVLC.
		openUrl(QUrl::fromLocalFile(file));
	});
	QAction *captionAction = aiMenu->addAction(i18n("Live Teletext / Whisper subtitles"));''')

    hdr = "src/dvb/dvbliveview_p.h"
    change(hdr, '\tQList<QByteArray> buffers;\n',
           '\tQList<QByteArray> buffers;\n'
           '\tQString tihuluCaptionSocketPath;\n\tint tihuluCaptionFd;\n')

    live = "src/dvb/dvbliveview.cpp"
    change(live, '#include <QDir>\n',
           '#include <QDir>\n#include <QCoreApplication>\n'
           '#include <sys/socket.h>\n#include <sys/un.h>\n')
    change(live, '\treadFd(-1), writeFd(-1), notifier(NULL)\n{',
           '\treadFd(-1), writeFd(-1), notifier(NULL), tihuluCaptionFd(-1)\n{')
    change(live, '\tfileName = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QLatin1String("/dvbpipe.m2t");',
           '\tconst QString runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);\n'
           '\tif (!runtime.isEmpty())\n'
           '\t\ttihuluCaptionSocketPath = runtime + QLatin1String("/tihulu-dvb-")\n'
           '\t\t\t+ QString::number(QCoreApplication::applicationPid()) + QLatin1String(".sock");\n'
           '\tfileName = runtime + QLatin1String("/dvbpipe.m2t");')
    change(live, 'DvbLiveViewInternal::~DvbLiveViewInternal()\n{\n',
           'DvbLiveViewInternal::~DvbLiveViewInternal()\n{\n'
           '\tif (tihuluCaptionFd >= 0)\n\t\t::close(tihuluCaptionFd);\n\tif (!tihuluEffectiveDelayFile.isEmpty())\n\t\tQFile::remove(tihuluEffectiveDelayFile);\n')
    change(live, '''	if (!timeShiftFile.isOpen()) {
		if (writeFd >= 0) {
			buffers.append(buffer);
''', '''	// Best-effort datagrams are dropped when no caption listener exists.
	// No blocking, no extra DVB frontend open, no effect on libVLC output.
	if (!tihuluCaptionSocketPath.isEmpty() && QFile::exists(tihuluCaptionSocketPath)) {
		if (tihuluCaptionFd < 0)
			tihuluCaptionFd = ::socket(AF_UNIX, SOCK_DGRAM | SOCK_NONBLOCK, 0);
		if (tihuluCaptionFd >= 0) {
			const QByteArray name = QFile::encodeName(tihuluCaptionSocketPath);
			sockaddr_un peer = {};
			peer.sun_family = AF_UNIX;
			if (name.size() < static_cast<int>(sizeof(peer.sun_path))) {
				qstrncpy(peer.sun_path, name.constData(), sizeof(peer.sun_path));
				for (int pos = 0; pos < buffer.size(); pos += 16 * 188) {
					const int n = qMin(16 * 188, buffer.size() - pos);
					(void)::sendto(tihuluCaptionFd, buffer.constData() + pos,
						static_cast<size_t>(n), MSG_DONTWAIT | MSG_NOSIGNAL,
						reinterpret_cast<sockaddr *>(&peer), sizeof(peer));
				}
			}
		}
	}
	if (!timeShiftFile.isOpen()) {
		if (writeFd >= 0) {
			buffers.append(buffer);
''')
    # DvbManager only forward-declares DvbConfig; the diagnostic iterates
    # QList<DvbConfig> so include the complete shared-pointer definition.
    change(live, '#include "dvbdevice.h"\n',
           '#include "dvbdevice.h"\n#include "dvbconfig.h"\n')
    # The upstream "Didn't find a device with valid settings..." message
    # conflates disconnected USB, an unassigned channel source, another
    # active consumer and permission-denied. Emit actionable *read-only*
    # source diagnostics without changing device ownership or channel DB.
    change(live, '''\tif (device == NULL) {
\t\tchannel = DvbSharedChannel();
\t\tmediaWidget->stop();

\t\tif (manager->getRecordingModel()->hasActiveRecordings()) {''',
    '''\tif (device == NULL) {
\t\tconst QString requestedSource = channel->source;
\t\tQStringList usableSources;
\t\tint connectedDvbFrontends = 0;
\t\tfor (const DvbDeviceConfig &entry : manager->getDeviceConfigs()) {
\t\t\tif (entry.device == NULL) continue;
\t\t\t++connectedDvbFrontends;
\t\t\tfor (const DvbConfig &configured : entry.configs)
\t\t\t\tif (!configured->name.isEmpty())
\t\t\t\t\tusableSources.append(configured->name);
\t\t}
\t\tqCWarning(logDvb,
\t\t\t"TIHULU no usable DVB frontend: requested channel source='%s'; "
\t\t\t"connected receivers=%d; configured channel sources='%s'. "
\t\t\t"Check Configure Television, USB ownership and access permissions.",
\t\t\tqPrintable(requestedSource), connectedDvbFrontends,
\t\t\tqPrintable(usableSources.join(QLatin1String(", "))));
\t\tchannel = DvbSharedChannel();
\t\tmediaWidget->stop();

\t\tif (manager->getRecordingModel()->hasActiveRecordings()) {''')

    # Delay *both* audio and video by buffering already-filtered TS bytes
    # before Kaffeine's existing FIFO -> libVLC. The AI tap above stays
    # pre-delay so Whisper can finish nearer to delayed playback.
    # A capped 64 MiB queue prevents uncontrolled memory growth on Pi 5.
    change(hdr, '#include <QFile>\n', '#include <QFile>\n#include <QPair>\n')
    change(hdr, '''\tQString tihuluCaptionSocketPath;
\tint tihuluCaptionFd;
''', '''\tQString tihuluCaptionSocketPath;
\tint tihuluCaptionFd;
\tQString tihuluDelayFile;
\tQString tihuluEffectiveDelayFile;
\tQList<QPair<qint64, QByteArray> > tihuluDelayed;
\tqint64 tihuluDelayedBytes = 0;
\tqint64 tihuluConfigCheckedAt = 0;
\tqint64 tihuluObservedBytes = 0;
\tqint64 tihuluObservedRate = 0;
\tqint64 tihuluDelayCooldownUntil = 0;
\tint tihuluVideoDelayMs = 0;
\tint tihuluPrimedTargetMs = -1;
\tbool tihuluDelayPrimed = false;
''')
    change(live, '#include <QCoreApplication>\n',
           '#include <QCoreApplication>\n#include <QDateTime>\n')
    change(live, '''\tfileName = runtime + QLatin1String("/dvbpipe.m2t");''',
           '''\ttihuluDelayFile = runtime + QLatin1String("/tihulu-playback-delay-")
\t\t+ QString::number(QCoreApplication::applicationPid()) + QLatin1String(".txt");
\ttihuluEffectiveDelayFile = runtime + QLatin1String("/tihulu-playback-effective-")
\t\t+ QString::number(QCoreApplication::applicationPid()) + QLatin1String(".txt");
\tfileName = runtime + QLatin1String("/dvbpipe.m2t");''')
    change(live, '''\tretryCounter = 0;
\tnotifier->setEnabled(false);''',
           '''\tretryCounter = 0;
\tnotifier->setEnabled(false);
\t// Never replay a previous channel's delayed TS after switching services.
\ttihuluDelayed.clear();
\ttihuluDelayedBytes = 0;
\ttihuluPrimedTargetMs = -1;
\ttihuluDelayPrimed = false;''')
    change(live, '''\tif (!timeShiftFile.isOpen()) {
\t\tif (writeFd >= 0) {
\t\t\tbuffers.append(buffer);
\t\t\twriteToPipe();
\t\t\tif (emptyBuffer) {''',
    '''\t// Whisper receives the original TS ABOVE, before this playback delay.
\t// A requested delay can exceed the memory-limited native FIFO. Bound the
\t// actual delay to 48 MiB of measured selected-service TS with 16 MiB
\t// headroom and publish effective/native value to the subtitle controller.
\tconst qint64 now = QDateTime::currentMSecsSinceEpoch();
\ttihuluObservedBytes += buffer.size();
\tif (now - tihuluConfigCheckedAt >= 1000) {
\t\tconst qint64 elapsed = now - tihuluConfigCheckedAt;
\t\tif (tihuluConfigCheckedAt > 0 && elapsed > 0) {
\t\t\tconst qint64 instantaneous = tihuluObservedBytes * 1000 / elapsed;
\t\t\t// Keep 75% of the prior rate when DVB bitrate falls temporarily.
\t\t\ttihuluObservedRate = qMax(instantaneous,
\t\t\t\t(tihuluObservedRate * 3) / 4);
\t\t}
\t\ttihuluObservedBytes = 0;
\t\ttihuluConfigCheckedAt = now;
\t\tQFile settings(tihuluDelayFile);
\t\tint requestedMs = 0;
\t\tif (settings.open(QIODevice::ReadOnly) && settings.size() < 16) {
\t\t\tbool ok = false;
\t\t\tconst int requested = settings.readAll().trimmed().toInt(&ok);
\t\t\tif (ok && requested >= 0 && requested <= 20000)
\t\t\t\trequestedMs = requested;
\t\t}
\t\tconst qint64 safeMs = tihuluObservedRate > 0
\t\t\t? qMin(20000LL, 48LL * 1024 * 1024 * 1000 / tihuluObservedRate)
\t\t\t: 20000LL;
\t\tconst int cappedMs = (qMin<qint64>(requestedMs, safeMs) / 500) * 500;
\t\tconst int newTargetMs = (now < tihuluDelayCooldownUntil ||
\t\t\ttimeShiftFile.isOpen()) ? 0 : cappedMs;
\t\tif (newTargetMs != tihuluPrimedTargetMs) {
\t\t\t// A new requested delay is NOT yet an applied playback
\t\t\t// timeline: waiting for 14s of input can take 14 real seconds.
\t\t\ttihuluDelayPrimed = (newTargetMs == 0);
\t\t\ttihuluPrimedTargetMs = newTargetMs;
\t\t}
\t\ttihuluVideoDelayMs = newTargetMs;
\t\tconst qint64 queuedAgeMs = tihuluDelayed.isEmpty() ? 0 :
\t\t\tqMax<qint64>(0, now - tihuluDelayed.first().first);
\t\tif (!tihuluDelayPrimed && tihuluVideoDelayMs > 0 &&
\t\t    queuedAgeMs >= tihuluVideoDelayMs - 250)
\t\t\ttihuluDelayPrimed = true;
\t\tQFile status(tihuluEffectiveDelayFile);
\t\tif (status.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
\t\t\tstatus.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
\t\t\t// request, bounded target, TS bytes/s, buffer primed flag,
\t\t\t// and observed oldest queued TS age. A target does not
\t\t\t// imply libVLC already has delayed video ready.
\t\t\tstatus.write(QByteArray::number(requestedMs) + " " +
\t\t\t\tQByteArray::number(tihuluVideoDelayMs) + " " +
\t\t\t\tQByteArray::number(tihuluObservedRate) + " " +
\t\t\t\tQByteArray::number(tihuluDelayPrimed ? 1 : 0) + " " +
\t\t\t\tQByteArray::number(queuedAgeMs));
\t\t}
\t}
\tif (!timeShiftFile.isOpen()) {
\t\tif (writeFd >= 0) {
\t\t\tconst bool queuedCurrent = (tihuluVideoDelayMs > 0);
\t\t\tif (queuedCurrent) {
\t\t\t\ttihuluDelayed.append(qMakePair(now, buffer));
\t\t\t\ttihuluDelayedBytes += buffer.size();
\t\t\t\tif (tihuluDelayedBytes > 64LL * 1024 * 1024) {
\t\t\t\t\tqCWarning(logDvb, "TIHULU playback delay exceeded 64 MiB; reverting to live for 5s");
\t\t\t\t\ttihuluVideoDelayMs = 0;
\t\t\t\t\ttihuluDelayPrimed = true;
\t\t\t\t\ttihuluPrimedTargetMs = 0;
\t\t\t\t\ttihuluDelayCooldownUntil = now + 5000;
\t\t\t\t}
\t\t\t}
\t\t\twhile (!tihuluDelayed.isEmpty() &&
\t\t\t       (tihuluVideoDelayMs == 0 ||
\t\t\t        now - tihuluDelayed.first().first >= tihuluVideoDelayMs)) {
\t\t\t\tconst QByteArray chunk = tihuluDelayed.takeFirst().second;
\t\t\t\ttihuluDelayedBytes -= chunk.size();
\t\t\t\tbuffers.append(chunk);
\t\t\t}
\t\t\tif (!queuedCurrent)
\t\t\t\tbuffers.append(buffer);
\t\t\tif (!buffers.isEmpty())
\t\t\t\twriteToPipe();
\t\t\tif (emptyBuffer) {''')
    # Kaffeine's timeshift file already implements its own media timeline;
    # never concatenate a second delayed FIFO while timeshift is enabled.
    change(live, '''\t} else {
\t\tnotifier->setEnabled(false);
\t\ttimeShiftFile.write(buffer); // FIXME avoid buffer reallocation''',
    '''\t} else {
\t\ttihuluDelayed.clear();
\t\ttihuluDelayedBytes = 0;
\t\tnotifier->setEnabled(false);
\t\ttimeShiftFile.write(buffer); // FIXME avoid buffer reallocation''')

    # Keep Kaffeine's native libVLC rendering but offer explicit recovery
    # profiles for broken VA-API/VDPAU/NVIDIA paths and bad live FIFO caching.
    # Every platform remains configurable: original Kaffeine settings take
    # priority whenever user explicitly supplies an equivalent option.
    vlc = "src/backend-vlc/vlcmediawidget.cpp"
    change(vlc, '''\tQString args = Configuration::instance()->getLibVlcArguments();
\tQStringList argList;''', '''\tQString args = Configuration::instance()->getLibVlcArguments();
\tconst QByteArray tihuluProfile = qgetenv("TIHULU_VLC_PROFILE");
\tif (tihuluProfile == "software" || tihuluProfile == "software-no-audio") {
\t\t// Explicit recovery mode MUST override saved --avcodec-hw=any.
\t\t// Otherwise libVLC still loads NVIDIA VDPAU even when the user
\t\t// requested software-no-audio, exactly as seen in the device log.
\t\tQStringList existing = args.split(QLatin1Char(' '), Qt::SkipEmptyParts);
\t\tfor (int n = existing.size() - 1; n >= 0; --n) {
\t\t\tconst QString option = existing.at(n);
\t\t\tif (option == QLatin1String("--avcodec-hw")) {
\t\t\t\tif (n+1 < existing.size()) existing.removeAt(n+1);
\t\t\t\texisting.removeAt(n);
\t\t\t} else if (option.startsWith(QLatin1String("--avcodec-hw="))) {
\t\t\t\texisting.removeAt(n);
\t\t\t}
\t\t}
\t\targs = existing.join(QLatin1Char(' '));
\t\targs.append(QLatin1String(" --avcodec-hw=none"));
\t\tif (!args.contains(QLatin1String("--file-caching")))
\t\t\targs.append(QLatin1String(" --file-caching=1500"));
\t\tif (!args.contains(QLatin1String("--no-video-title-show")))
\t\t\targs.append(QLatin1String(" --no-video-title-show"));
\t\tif (tihuluProfile == "software-no-audio" &&
\t\t    !args.contains(QLatin1String("--no-audio")))
\t\t\targs.append(QLatin1String(" --no-audio"));
\t\tqCInfo(logVlc, "TIHULU playback troubleshooting: %s; enforced libVLC: %s",
\t\t       tihuluProfile.constData(), qPrintable(args));
\t}
\tQStringList argList;''')

    # Do not silently fall back to libvlc_new(0,NULL) (which re-enables
    # NVIDIA hardware) when the user requests a software video profile.
    change(vlc, '''\t\targc = 0;
\t\tvlcInstance = libvlc_new(0, NULL);
\t\tif (vlcInstance)
\t\t\tqCInfo(logMediaWidget, "Using libVLC without arguments");''',
    '''\t\targc = 0;
\t\tconst QByteArray profile = qgetenv("TIHULU_VLC_PROFILE");
\t\tif (profile == "software" || profile == "software-no-audio") {
\t\t\tconst char *fallbackArgs[] = { "--avcodec-hw=none",
\t\t\t\t"--no-video-title-show", "--no-audio" };
\t\t\tvlcInstance = libvlc_new(
\t\t\t\tprofile == "software-no-audio" ? 3 : 2, fallbackArgs);
\t\t\tif (vlcInstance)
\t\t\t\tqCWarning(logVlc,
\t\t\t\t\t"TIHULU: extra VLC arguments rejected; safe software decoder still enforced");
\t\t} else {
\t\t\tvlcInstance = libvlc_new(0, NULL);
\t\t\tif (vlcInstance)
\t\t\t\tqCInfo(logMediaWidget, "Using libVLC without arguments");
\t\t}''')
    change(vlc, '#include <QTimer>\n',
           '#include <QTimer>\n#include <QSettings>\n')
    mediaAnchor = '\tvlcMedia = libvlc_media_new_location(vlcInstance, typeOfDevice);'
    if files[vlc].count(mediaAnchor) != 2:
        raise ValueError("Unexpected libVLC media creation count")
    files[vlc] = files[vlc].replace(mediaAnchor, mediaAnchor + '''
\t// This media-creation expression occurs in BOTH play() and CD
\t// track-change methods, but 'source' only exists in play().
\t// Inspect the actual encoded libVLC URL instead.
\tconst QByteArray localStreamUrl(typeOfDevice);
\tif (localStreamUrl.startsWith("http://127.0.0.1:") &&
\t    localStreamUrl.contains("/mp3/")) {
\t\tQSettings radioSettings(QLatin1String("TIHULU"),
\t\t\tQLatin1String("KaffeineRadio"));
\t\tconst int cacheMs=qBound(0,
\t\t\tradioSettings.value(QLatin1String("playbackBufferMs"),12000).toInt(),
\t\t\t20000);
\t\tconst QByteArray cacheOpt=QByteArray(":network-caching=")+
\t\t\tQByteArray::number(cacheMs);
\t\tlibvlc_media_add_option(vlcMedia,cacheOpt.constData());
\t} else if (localStreamUrl.startsWith("file://")) {
\t\t// Local file AI may run BEFORE playback by user request.
\t\t// This is only I/O read-ahead, not a fabricated subtitle offset.
\t\tQSettings mediaSettings(QLatin1String("TIHULU"),
\t\t\tQLatin1String("MediaPlayer"));
\t\tconst int cacheMs=qBound(0,
\t\t\tmediaSettings.value(QLatin1String("fileCacheMs"),1500).toInt(),
\t\t\t20000);
\t\tconst QByteArray cacheOpt=QByteArray(":file-caching=")+
\t\t\tQByteArray::number(cacheMs);
\t\tlibvlc_media_add_option(vlcMedia,cacheOpt.constData());
\t}
\t// Per-media option reinforces the instance-level software decode
\t// request; native television and playback controls remain unmodified.
\tconst QByteArray appliedProfile = qgetenv("TIHULU_VLC_PROFILE");
\tif (appliedProfile == "software" || appliedProfile == "software-no-audio")
\t\tlibvlc_media_add_option(vlcMedia, ":avcodec-hw=none");''')

    # Kaffeine's OsdWidget already renders ABOVE libVLC's native video
    # surface. Reuse that mechanism in a *separate* caption OSD so the
    # original channel/volume OSD and DVB Teletext continue to work.
    osdh = "src/osdwidget.h"
    change(osdh, '''\tvoid showText(const QString &text, int duration); // duration: msecs
''', '''\tvoid showText(const QString &text, int duration); // duration: msecs
\tvoid showCaption(const QString &text, bool atTop, int pixelSize, int backgroundPercent, int textPercent,
\t\tconst QString &foregroundColor, const QString &backgroundColor);
\tvoid hideCaption();
''')
    change(osdh, '''\tOsdObject *osdObject;
\tQTimer *timer;''', '''\tOsdObject *osdObject;
\tQTimer *timer;
\tbool tihuluCaptionMode = false;
\tbool tihuluCaptionTop = false;
\tint tihuluCaptionSize = 25;
\tint tihuluCaptionOpacity = 70;
\tint tihuluCaptionTextOpacity = 100;
\tQString tihuluCaptionForeground = QLatin1String("#FFFFFF");
\tQString tihuluCaptionBackground = QLatin1String("#000000");
\tQString tihuluCaptionText;''')
    osdc = "src/osdwidget.cpp"
    change(osdc, '#include <QPainter>\n', '#include <QPainter>\n#include <QRegion>\n')
    change(osdc, '''void OsdWidget::showObject(OsdObject *osdObject_, int duration)
{''',
    '''void OsdWidget::showCaption(const QString &text, bool atTop,
\tint pixelSize, int backgroundPercent, int textPercent,
\tconst QString &foregroundColor, const QString &backgroundColor)
{
\tif (text.isEmpty() || (backgroundPercent <= 0 && textPercent <= 0)) {
\t\thideCaption();
\t\treturn;
\t}
\tconst QString cleaned = text.left(1100);
\tif (tihuluCaptionMode && tihuluCaptionText == cleaned &&
\t    tihuluCaptionTop == atTop && tihuluCaptionSize == pixelSize &&
\t    tihuluCaptionOpacity == backgroundPercent &&
\t    tihuluCaptionTextOpacity == textPercent &&
\t    tihuluCaptionForeground == foregroundColor &&
\t    tihuluCaptionBackground == backgroundColor)
\t\treturn;
\ttihuluCaptionMode = true;
\ttihuluCaptionText = cleaned;
\ttihuluCaptionTop = atTop;
\ttihuluCaptionSize = qBound(16, pixelSize, 44);
\ttihuluCaptionOpacity = qBound(0, backgroundPercent, 100);
\ttihuluCaptionTextOpacity = qBound(0, textPercent, 100);
\tconst QColor chosenText(foregroundColor);
\tconst QColor chosenBackground(backgroundColor);
\ttihuluCaptionForeground = chosenText.isValid() ? foregroundColor : QLatin1String("#FFFFFF");
\ttihuluCaptionBackground = chosenBackground.isValid() ? backgroundColor : QLatin1String("#000000");
\ttimer->stop();
\tshow();
\traise();
\tupdate();
}

void OsdWidget::hideCaption()
{
\tif (tihuluCaptionMode) {
\t\ttihuluCaptionMode = false;
\t\ttihuluCaptionText.clear();
\t\tsetMask(QRegion());
\t\thide();
\t}
}

void OsdWidget::showObject(OsdObject *osdObject_, int duration)
{''')
    change(osdc, '''void OsdWidget::paintEvent(QPaintEvent *)
{
\tif (osdObject == NULL) {''',
    '''void OsdWidget::paintEvent(QPaintEvent *)
{
\tif (tihuluCaptionMode) {
\t\tQFont face = font();
\t\tface.setPixelSize(tihuluCaptionSize);
\t\tface.setBold(true);
\t\tQFontMetrics metrics(face);
\t\tconst int limit = qMax(200, width() - 56);
\t\tQRect bounds = metrics.boundingRect(
\t\t\tQRect(0, 0, limit - 24, height()),
\t\t\tQt::AlignHCenter | Qt::TextWordWrap, tihuluCaptionText);
\t\tconst int boxHeight = qMin(qMax(40, bounds.height() + 22), qMax(40, height() - 30));
\t\tQRect box((width() - limit) / 2,
\t\t\ttihuluCaptionTop ? 35 : qMax(12, height() - boxHeight - 40),
\t\t\tlimit, boxHeight);
\t\tQPainter painter(this);
\t\t// A child QWidget covering libVLC is opaque by default on some
\t\t// X11/Wayland paths. Explicitly CLEAR every repainted pixel;
\t\t// simply drawing an RGBA(0) rectangle previously left a black box.
\t\tpainter.setCompositionMode(QPainter::CompositionMode_Source);
\t\tpainter.fillRect(QWidget::rect(), Qt::transparent);
\t\tpainter.setCompositionMode(QPainter::CompositionMode_SourceOver);
\t\tpainter.setRenderHint(QPainter::Antialiasing);
\t\tif (tihuluCaptionOpacity > 0) {
\t\t\tQColor backing(tihuluCaptionBackground);
\t\t\tbacking.setAlpha(tihuluCaptionOpacity * 255 / 100);
\t\t\tpainter.setPen(Qt::NoPen);
\t\t\tpainter.setBrush(backing);
\t\t\tpainter.drawRoundedRect(box, 8, 8);
\t\t}
\t\tif (tihuluCaptionTextOpacity > 0) {
\t\t\tpainter.setFont(face);
\t\t\tQColor foreground(tihuluCaptionForeground);
\t\t\tforeground.setAlpha(tihuluCaptionTextOpacity * 255 / 100);
\t\t\tpainter.setPen(foreground);
\t\t\tpainter.drawText(box.adjusted(12, 9, -12, -9),
\t\t\t\tQt::AlignHCenter | Qt::AlignVCenter | Qt::TextWordWrap,
\t\t\t\ttihuluCaptionText);
\t\t}
\t\tsetMask(box);
\t\treturn;
\t}
\tif (osdObject == NULL) {''')

    mediah = "src/mediawidget.h"
    change(mediah, '''\tOsdWidget *osdWidget;
''', '''\tOsdWidget *osdWidget;
\tOsdWidget *tihuluCaptionWidget;
''')
    mediac = "src/mediawidget.cpp"
    change(mediac, '#include <QComboBox>\n',
           '#include <QComboBox>\n#include <QCoreApplication>\n'
           '#include <QDateTime>\n#include <QFile>\n#include <QJsonDocument>\n'
           '#include <QJsonObject>\n#include <QStandardPaths>\n')
    change(mediac, '''\tosdWidget = new OsdWidget(this);
''',
    '''\tosdWidget = new OsdWidget(this);
\t// Independent on-video subtitles; native Kaffeine OSD is untouched.
\ttihuluCaptionWidget = new OsdWidget(this);
\t// Transparent *child surface*, not only a translucent painted brush.
\t// Without these, a black video-covering rectangle can remain even
\t// when the user selects background opacity = 0%.
\ttihuluCaptionWidget->setAttribute(Qt::WA_TranslucentBackground, true);
\ttihuluCaptionWidget->setAttribute(Qt::WA_NoSystemBackground, true);
\ttihuluCaptionWidget->setAttribute(Qt::WA_OpaquePaintEvent, false);
\ttihuluCaptionWidget->setAutoFillBackground(false);
\ttihuluCaptionWidget->setAttribute(Qt::WA_TransparentForMouseEvents);
\ttihuluCaptionWidget->resize(size());
\tconst QString runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
\tif (!runtime.isEmpty()) {
\t\tconst QString captionPath = runtime + QLatin1String("/tihulu-caption-")
\t\t\t+ QString::number(QCoreApplication::applicationPid()) + QLatin1String(".json");
\t\tQTimer *captionPoll = new QTimer(this);
\t\tconnect(captionPoll, &QTimer::timeout, this, [this, captionPath]() {
\t\t\tif (source->getType() != MediaSource::Dvb) {
\t\t\t\ttihuluCaptionWidget->hideCaption();
\t\t\t\treturn;
\t\t\t}
\t\t\tQFile file(captionPath);
\t\t\tif (!file.exists() || !file.open(QIODevice::ReadOnly)) {
\t\t\t\ttihuluCaptionWidget->hideCaption();
\t\t\t\treturn;
\t\t\t}
\t\t\tQByteArray bytes = file.read(16385);
\t\t\tif (bytes.size() > 16384) {
\t\t\t\ttihuluCaptionWidget->hideCaption();
\t\t\t\treturn;
\t\t\t}
\t\t\tQJsonDocument doc = QJsonDocument::fromJson(bytes);
\t\t\tif (!doc.isObject()) {
\t\t\t\ttihuluCaptionWidget->hideCaption();
\t\t\t\treturn;
\t\t\t}
\t\t\tQJsonObject obj = doc.object();
\t\t\tif (!obj.value(QLatin1String("enabled")).toBool(false) ||
\t\t\t    obj.value(QLatin1String("expires_ms")).toDouble(0)
\t\t\t      < static_cast<double>(QDateTime::currentMSecsSinceEpoch())) {
\t\t\t\ttihuluCaptionWidget->hideCaption();
\t\t\t\treturn;
\t\t\t}
\t\t\ttihuluCaptionWidget->showCaption(
\t\t\t\tobj.value(QLatin1String("text")).toString(),
\t\t\t\tobj.value(QLatin1String("position")).toString() == QLatin1String("top"),
\t\t\t\tobj.value(QLatin1String("size")).toInt(25),
\t\t\t\tobj.value(QLatin1String("opacity")).toInt(70),
\t\t\t\tobj.value(QLatin1String("text_opacity")).toInt(100),
\t\t\tobj.value(QLatin1String("text_color")).toString(QLatin1String("#FFFFFF")),
\t\t\tobj.value(QLatin1String("background_color")).toString(QLatin1String("#000000")));
\t\t});
\t\tcaptionPoll->start(150);
\t}
''')
    change(mediac, '''\tosdWidget->resize(event->size());
\tQWidget::resizeEvent(event);''',
    '''\tosdWidget->resize(event->size());
\ttihuluCaptionWidget->resize(event->size());
\ttihuluCaptionWidget->raise();
\tQWidget::resizeEvent(event);''')

    # Use Kaffeine's OWN DVB scan engine; absolutely no w_scan_cpp,
    # dvbv5-scan background child, or second frontend ownership. These
    # multiplexes were physically detected on the original local setup.
    # The user opts into this targeted source from native Configure Television.
    manager = "src/dvb/dvbmanager.cpp"
    change(manager, '''\treturn scanSources.value(type);
}''', '''\tQStringList list = scanSources.value(type);
\tif (type == DvbT2)
\t\tlist.prepend(QLatin1String("TIHULU tested: 538 / 586 / 626 MHz"));
\treturn list;
}''')
    change(manager, '''\treturn scanData.value(scanSource);
}''', '''\t// Selectable, native Kaffeine scan source based on real DVB-T2
\t// multiplexes previously received with this adapter. Not a fake
\t// channel list, and not a replacement for Auto scan.
\tif (scanSource.first == DvbT2 &&
\t    scanSource.second == QLatin1String("TIHULU tested: 538 / 586 / 626 MHz")) {
\t\tQList<DvbTransponder> known;
\t\tconst int hz[] = { 538000000, 586000000, 626000000 };
\t\tfor (int frequency : hz) {
\t\t\t// Use Kaffeine native typed DVB-T2 properties rather than
\t\t\t// guessed scanfile text that may parse to an empty scan.
\t\t\tDvbTransponder transponder(DvbTransponderBase::DvbT2);
\t\t\tDvbT2Transponder *t2 = transponder.as<DvbT2Transponder>();
\t\t\tt2->frequency = frequency;
\t\t\tt2->bandwidth = DvbT2Transponder::Bandwidth8MHz;
\t\t\tt2->modulation = DvbT2Transponder::ModulationAuto;
\t\t\tt2->fecRateHigh = DvbTransponderBase::FecAuto;
\t\t\tt2->fecRateLow = DvbTransponderBase::FecAuto;
\t\t\tt2->transmissionMode = DvbT2Transponder::TransmissionModeAuto;
\t\t\tt2->guardInterval = DvbT2Transponder::GuardIntervalAuto;
\t\t\tt2->hierarchy = DvbT2Transponder::HierarchyAuto;
\t\t\tt2->streamId = 0; // previously tested PLP 0; other PLPs require discovery
\t\t\tknown.append(transponder);
\t\t}
\t\treturn known;
\t}
\treturn scanData.value(scanSource);
}''')
    # Keep native Kaffeine left channel sidebar + video + playback buttons.
    # Only clarify the built-in "Channels" control also opens scan.
    tab = "src/dvb/dvbtab.cpp"
    change(tab, 'i18n("Channels"), this);',
           'i18n("Channels / Antenna Scan"), this);')
    # A full frequency sweep must not silently shrink to the currently
    # playing mux. Kaffeine's original Channels dialog deliberately
    # provides "Current Transponder" when the live view owns the tuner.
    # Add an explicit, confirmation-protected full scanner instead.
    change(tab, '#include <QMenu>\n',
           '#include <QMenu>\n#include <QMessageBox>\n#include <QTimer>\n')
    change(tab, '''\tmenu->addAction(collection->addAction(QLatin1String("dvb_channels"), channelsAction));
''', '''\tmenu->addAction(collection->addAction(QLatin1String("dvb_channels"), channelsAction));
\tQAction *fullScanAction = new QAction(
\t\tQIcon::fromTheme(QLatin1String("edit-find")),
\t\ti18n("Full Antenna Scan..."), this);
\tconnect(fullScanAction, &QAction::triggered, this, &DvbTab::showFullScanDialog);
\tmenu->addAction(collection->addAction(QLatin1String("tihulu_dvb_full_scan"), fullScanAction));
''')
    change(tab, '''void DvbTab::showChannelDialog()
{
\tQDialog *dialog = new DvbScanDialog(manager, this);
''', '''void DvbTab::showFullScanDialog()
{
\t// The native DVB scanner needs exclusive tuner ownership for
\t// changing frequencies; Kaffeine's Channels editor can instead
\t// stay attached to a single currently playing transponder.
\tif (manager->getLiveView()->getDevice() != NULL) {
\t\tif (QMessageBox::question(this, i18n("Full Antenna Scan"),
\t\t\ti18n("Stop live TV temporarily to scan multiple frequencies?"),
\t\t\tQMessageBox::Yes | QMessageBox::No, QMessageBox::No) != QMessageBox::Yes)
\t\t\treturn;
\t\tmediaWidget->stop();
\t\t// Give Kaffeine's asynchronous player status updates one event
\t\t// loop turn to release the DVB frontend before the scan dialog opens.
\t\tQTimer::singleShot(100, this, [this]() { showChannelDialog(); });
\t\treturn;
\t}
\tshowChannelDialog();
}

void DvbTab::showChannelDialog()
{
\tQDialog *dialog = new DvbScanDialog(manager, this);
''')
    tabhdr = "src/dvb/dvbtab.h"
    change(tabhdr, '\tvoid showChannelDialog();',
           '\tvoid showChannelDialog();\n\tvoid showFullScanDialog();')

    # KAboutData already registers --help/--help-all/--version; avoid
    # duplicate h, help-all and v aliases observed in the user's logs.
    appmain = "src/main.cpp"
    change(appmain, '''\tapp.parser.addVersionOption();
\tapp.parser.addHelpOption();
\taboutData->setupCommandLine(&app.parser);''',
    '''\t// KAboutData registers Qt help/version aliases exactly once.
\taboutData->setupCommandLine(&app.parser);''')

    # Global EPG category tables previously executed kli18n().toString()
    # BEFORE main initialized KLocalizedString's application domain.
    # Lazy function-local statics preserve all existing translations.
    epg = "src/dvb/dvbepg.cpp"
    source_epg = files[epg]
    for name, dimensions in (
        ("contentStr", "[16][16]"),
        ("nibble1Str", "[16]"),
        ("braNibble1Str", "[16]"),
        ("braNibble2Str", "[16][16]"),
    ):
        qualifier = "const " if name != "braNibble2Str" else ""
        declaration = "static " + qualifier + "QByteArray " + name + dimensions + " = {"
        first = source_epg.find(declaration)
        if first < 0:
            raise ValueError("Missing EPG genre table: " + name)
        close = source_epg.find("};", first)
        if close < 0:
            raise ValueError("Unterminated EPG genre table: " + name)
        original = source_epg[first:close+2]
        function = ("static " + qualifier + "QByteArray (&" + name + "())" +
            dimensions + "\n{\n\tstatic " + qualifier + "QByteArray values" +
            dimensions + " = {" + original.split("= {",1)[1][:-2] +
            "};\n\treturn values;\n}")
        source_epg = source_epg[:first] + function + source_epg[close+2:]
        source_epg = source_epg.replace(name + "[nibble1]", name + "()[nibble1]")
    files[epg] = source_epg

    return files

def apply(root: Path):
    root = root.resolve(strict=True)
    source = {path: (root / path).read_text(encoding="utf-8") for path in PATHS}
    new = transform(source)
    for path in PATHS:
        (root / path).write_text(new[path], encoding="utf-8")
        print("Patched upstream Kaffeine:", path)
    # Header is original TIHULU Qt integration, not copied from welle.io.
    # Rebuilds use a detached clean upstream Kaffeine worktree.
    widget = Path(__file__).with_name("native_radio_tab.h")
    if not widget.is_file():
        raise RuntimeError("Native radio tab template missing from pinned source")
    dest = root / "src/tihulu_radio_tab.h"
    if dest.exists() and dest.read_text(encoding="utf-8") != widget.read_text(encoding="utf-8"):
        raise RuntimeError("Refusing to overwrite unrelated native radio header")
    dest.write_text(widget.read_text(encoding="utf-8"),encoding="utf-8")
    print("Installed native Kaffeine radio page:", dest)
    panel = Path(__file__).with_name("native_media_panel.h")
    if not panel.is_file():
        raise RuntimeError("In-player local media AI template is missing")
    media_dest = root / "src/tihulu_media_panel.h"
    if media_dest.exists() and media_dest.read_text(encoding="utf-8") != panel.read_text(encoding="utf-8"):
        raise RuntimeError("Refusing to overwrite unrelated native media panel")
    media_dest.write_text(panel.read_text(encoding="utf-8"),encoding="utf-8")
    print("Installed in-player offline media AI controls:",media_dest)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 patch_upstream.py /path/to/pinned/kaffeine")
    apply(Path(sys.argv[1]))
