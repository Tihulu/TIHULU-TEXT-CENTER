/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Native Media's one app-owned CLI. Never search interactive PATH.
 */
#ifndef TIHULU_COMPANION_PATH_H
#define TIHULU_COMPANION_PATH_H

#include <QDir>
#include <QFile>
#include <QString>
#include <sys/stat.h>
#include <unistd.h>

inline QString tihuluCompanionCliPath()
{
    const QString home = QDir::homePath();
    if (home.isEmpty()) return QString();
    QString dir = home;
    // No symlinked or group/world-writable ancestors of the public CLI.
    for (const char *part : {".local", "bin"}) {
        dir += QLatin1Char('/') + QLatin1String(part);
        struct stat st;
        if (::lstat(QFile::encodeName(dir).constData(), &st) != 0 ||
            !S_ISDIR(st.st_mode) || st.st_uid != ::geteuid() ||
            (st.st_mode & 0022) != 0)
            return QString();
    }
    const QString cli = dir + QLatin1String("/tihulu-media-standalone-cli");
    struct stat file;
    if (::lstat(QFile::encodeName(cli).constData(), &file) != 0 ||
        !S_ISREG(file.st_mode) || file.st_uid != ::geteuid() ||
        file.st_nlink != 1 || (file.st_mode & 0077) != 0 ||
        (file.st_mode & 0100) == 0)
        return QString();
    return cli;
}

#endif  // TIHULU_COMPANION_PATH_H
