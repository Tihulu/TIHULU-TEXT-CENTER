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
PATHS = ("src/mainwindow.cpp", "src/dvb/dvbliveview.cpp",
         "src/dvb/dvbliveview_p.h", "src/dvb/dvbmanager.cpp", "src/dvb/dvbtab.cpp",
         "src/dvb/dvbtab.h")

def transform(files):
    files = dict(files)
    def change(path, before, after):
        source = files[path]
        if after in source:
            return
        if source.count(before) != 1:
            raise ValueError("Unexpected Kaffeine source; patch refused: "+path+" "+repr(before[:48]))
        files[path] = source.replace(before, after)

    main = "src/mainwindow.cpp"
    change(main, "#include <QMainWindow>\n",
           "#include <QMainWindow>\n#include <QCoreApplication>\n"
           "#include <QProcess>\n#include <QMessageBox>\n#include <QStandardPaths>\n")
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
           '\tif (tihuluCaptionFd >= 0)\n\t\t::close(tihuluCaptionFd);\n')
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
    change(tab, '#include <QMenu>\\n',
           '#include <QMenu>\\n#include <QMessageBox>\\n')
    change(tab, '''\tmenu->addAction(collection->addAction(QLatin1String("dvb_channels"), channelsAction));
''', '''\tmenu->addAction(collection->addAction(QLatin1String("dvb_channels"), channelsAction));
\tQAction *fullScanAction = new QAction(
\t\tQIcon::fromTheme(QLatin1String("edit-find")),
\t\ti18n("Full Antenna Scan..."), this);
\tconnect(fullScanAction, SIGNAL(triggered(bool)), this, SLOT(showFullScanDialog()));
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
    return files

def apply(root: Path):
    root = root.resolve(strict=True)
    source = {path: (root / path).read_text(encoding="utf-8") for path in PATHS}
    new = transform(source)
    for path in PATHS:
        (root / path).write_text(new[path], encoding="utf-8")
        print("Patched upstream Kaffeine:", path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 patch_upstream.py /path/to/pinned/kaffeine")
    apply(Path(sys.argv[1]))
