/*
 * SPDX-License-Identifier: GPL-2.0-or-later
 * Safe, owner-and-inode-bound cleanup of a native DVB transport FIFO.
 * No orphan scavenging and NO symlink following.
 */
#ifndef TIHULU_OWNED_FIFO_CLEANUP_H
#define TIHULU_OWNED_FIFO_CLEANUP_H

#include <QString>
#include <QFile>
#include <QtGlobal>
#include <sys/stat.h>
#include <unistd.h>

inline bool tihuluUnlinkOwnedFifo(const QString &path, int originalReadFd,
                                 quint64 ownedDev, quint64 ownedIno)
{
    if (path.isEmpty() || originalReadFd < 0 || ownedIno == 0)
        return false;
    struct stat pathStat, fdStat;
    const QByteArray encoded = QFile::encodeName(path);
    if (::fstat(originalReadFd, &fdStat) != 0 ||
        ::lstat(encoded.constData(), &pathStat) != 0 ||
        !S_ISFIFO(pathStat.st_mode) || !S_ISFIFO(fdStat.st_mode) ||
        pathStat.st_uid != ::geteuid() || fdStat.st_uid != ::geteuid() ||
        pathStat.st_nlink != 1 || (pathStat.st_mode & 0022) != 0 ||
        static_cast<quint64>(pathStat.st_dev) != ownedDev ||
        static_cast<quint64>(pathStat.st_ino) != ownedIno ||
        fdStat.st_dev != pathStat.st_dev || fdStat.st_ino != pathStat.st_ino)
        return false;
    return ::unlink(encoded.constData()) == 0;
}

#endif  // TIHULU_OWNED_FIFO_CLEANUP_H
