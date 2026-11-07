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
         "src/dvb/dvbliveview_p.h")

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
