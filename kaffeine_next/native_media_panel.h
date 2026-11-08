/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Small in-player AI controls: original Video/Audio file remains in the
 * existing libVLC MediaWidget. No new Qt top-level player or file window.
 */
#ifndef TIHULU_NATIVE_MEDIA_PANEL_H
#define TIHULU_NATIVE_MEDIA_PANEL_H
#include "mediawidget.h"
#include <QCheckBox>
#include <QComboBox>
#include <QFile>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QProcess>
#include <QPushButton>
#include <QStandardPaths>
#include <QUrl>
#include <QVBoxLayout>
#include <QWidget>

class TihuluMediaPanel final:public QWidget {
public:
	explicit TihuluMediaPanel(MediaWidget *player, QWidget *parent=nullptr)
		:QWidget(parent), player_(player), process_(this)
	{
		setObjectName(QLatin1String("tihuluMediaPanel"));
		setStyleSheet(QLatin1String(
			"QWidget#tihuluMediaPanel{background:#12202c;border-top:1px solid #356078}"
			"QLabel{color:#d3e9f3}QPushButton{padding:6px}"));
		auto *v=new QVBoxLayout(this);
		v->setContentsMargins(9,5,9,6);
		v->setSpacing(4);
		auto *h=new QHBoxLayout();
		h->addWidget(new QLabel(tr("Local Video / Audio · offline AI"),this));
		file_=new QLabel(tr("Open a file from Start / File → Open"),this);
		file_->setTextInteractionFlags(Qt::TextSelectableByMouse);
		file_->setMinimumWidth(120);
		h->addWidget(file_,1);
		v->addLayout(h);
		auto *tools=new QHBoxLayout();
		language_=new QComboBox(this);
		language_->addItem(tr("Auto detect (GPU)"),QLatin1String("auto"));
		for(const QString &code:QStringList{"de","en","tr","fr","es","pl","ja","ar"})
			language_->addItem(code.toUpper(),code);
		tools->addWidget(new QLabel(tr("Speech language"),this));
		tools->addWidget(language_);
		en_=new QCheckBox(tr("EN"),this); en_->setChecked(true);
		de_=new QCheckBox(tr("DE"),this);
		tr_=new QCheckBox(tr("TR"),this); tr_->setChecked(true);
		music_=new QCheckBox(tr("Song vocals"),this);
		lyrics_=new QCheckBox(tr("Use synced .lrc"),this);
		lyricsOnline_=new QCheckBox(tr("Find lyrics online (optional)"),this);
		lyricsOnline_->setToolTip(tr("Only song title/artist metadata is sent "
			"to LRCLIB after pressing Generate, never file audio. No API key."));
		tools->addWidget(de_);
		tools->addWidget(en_);
		tools->addWidget(tr_);
		tools->addWidget(music_);
		tools->addWidget(lyrics_);
		v->addLayout(tools);
		auto *actions = new QHBoxLayout();
		actions->addWidget(lyricsOnline_);
		actions->addStretch();
		run_=new QPushButton(tr("Generate + load captions"),this);
		cancel_=new QPushButton(tr("Cancel"),this);
		cancel_->setEnabled(false);
		actions->addWidget(run_);
		actions->addWidget(cancel_);
		v->addLayout(actions);
		message_=new QLabel(tr("Caption file will attach to the same playing video/audio."),this);
		message_->setWordWrap(true);
		v->addWidget(message_);
		connect(run_,&QPushButton::clicked,this,[this](){generate();});
		connect(cancel_,&QPushButton::clicked,this,[this](){
			if(process_.state()!=QProcess::NotRunning) {
				process_.kill();
				message_->setText(tr("Subtitle generation stopped. Original playback untouched."));
			}
		});
		connect(&process_,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),
			this,[this](int exitCode,QProcess::ExitStatus exitStatus) {
				run_->setEnabled(true);
				cancel_->setEnabled(false);
				if(exitCode==0 && exitStatus==QProcess::NormalExit &&
				   !path_.isEmpty() && QFile::exists(srtPath_)) {
					player_->setSubtitle(QUrl::fromLocalFile(srtPath_));
					message_->setText(tr("Attached generated subtitles to current "
						"file playback · %1").arg(srtPath_));
				} else {
					const QString err=QString::fromUtf8(process_.readAllStandardError());
					message_->setText(tr("Offline captions unavailable: %1")
						.arg(err.left(220)));
				}
			});
	}
	void setLocalFile(const QUrl &url) {
		if(!url.isLocalFile()) return;
		const QString candidate=url.toLocalFile();
		if(!QFileInfo(candidate).isFile()) return;
		path_=candidate;
		file_->setText(QFileInfo(candidate).fileName());
		file_->setToolTip(candidate);
	}
private:
	void generate() {
		if(path_.isEmpty() || !QFileInfo(path_).isFile()) {
			message_->setText(tr("Open a local media file in TIHULU first."));
			return;
		}
		if(process_.state()!=QProcess::NotRunning) return;
		QStringList targets;
		if(de_->isChecked()) targets<<QLatin1String("de");
		if(en_->isChecked()) targets<<QLatin1String("en");
		if(tr_->isChecked()) targets<<QLatin1String("tr");
		srtPath_=QFileInfo(path_).absolutePath()+QLatin1Char('/')+
			QFileInfo(path_).completeBaseName()+QLatin1String(".srt");
		QStringList args{QLatin1String("media-captions"),
			QLatin1String("--input"),path_,
			QLatin1String("--source"),language_->currentData().toString(),
			QLatin1String("--targets"),targets.join(QLatin1Char(','))};
		if(music_->isChecked()) args<<QLatin1String("--music");
		if(lyrics_->isChecked()) args<<QLatin1String("--lyrics");
		if(lyrics_->isChecked() && lyricsOnline_->isChecked())
			args<<QLatin1String("--fetch-lyrics");
		// The CLI refuses overwriting an existing user's .srt; the
		// player can still attach that file with the native subtitle menu.
		process_.start(QLatin1String("tihulu-tv-center"),args);
		if(!process_.waitForStarted(800)){
			message_->setText(tr("Could not launch TIHULU AI worker."));
			return;
		}
		run_->setEnabled(false);
		cancel_->setEnabled(true);
		message_->setText(tr("Processing current file offline · same local "
			"GPU Whisper and translation models. Playback stays available."));
	}
	MediaWidget *player_;
	QProcess process_;
	QLabel *file_=nullptr,*message_=nullptr;
	QComboBox *language_=nullptr;
	QCheckBox *de_=nullptr,*en_=nullptr,*tr_=nullptr,*music_=nullptr,*lyrics_=nullptr,
		*lyricsOnline_=nullptr;
	QPushButton *run_=nullptr,*cancel_=nullptr;
	QString path_,srtPath_;
};
#endif
