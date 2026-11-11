# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared, opt-in timestamped subtitle/text export for TIHULU Media Center.

Works on finished SRT data from file audio/video, live TV or live radio.
Does NOT acquire an SDR, infer word timing, change playback, or process DRM.
Media mux/burn is explicitly requested and needs the installed FFmpeg.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from dataclasses import dataclass

FORMATS = frozenset({"txt", "srt", "vtt", "ass", "json", "lrc"})
STAMP = re.compile(r"^(\d+):(\d{2}):(\d{2})[,\.](\d{3})$")
RANGE = re.compile(r"^\s*(\S+)\s*-->\s*(\S+)(?:\s+.*)?$")
TRACK = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def _seconds(stamp: str) -> float:
    found = STAMP.fullmatch(stamp)
    if not found:
        raise ValueError("Unrecognized SRT timestamp")
    hh, mm, ss, ms = (int(p) for p in found.groups())
    if mm > 59 or ss > 59:
        raise ValueError("Invalid SRT timestamp")
    return hh * 3600 + mm * 60 + ss + ms / 1000


def parse_srt(source: str | Path) -> list[Cue]:
    path = Path(source).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".srt":
        raise ValueError("Expected a local SRT subtitle file")
    if path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("SRT file exceeds 30 MiB safety limit")
    data = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    result = []
    for block in re.split(r"\n\s*\n", data.strip()):
        lines = block.splitlines()
        if not lines:
            continue
        at = 1 if lines[0].strip().isdigit() else 0
        if at >= len(lines):
            continue
        match = RANGE.match(lines[at])
        if not match:
            raise ValueError("Invalid SRT cue time range")
        begin, end = (_seconds(part) for part in match.groups())
        if not (0 <= begin < end and end - begin <= 86400):
            raise ValueError("Invalid subtitle cue duration")
        text = "\n".join(lines[at + 1:]).strip()
        if text:
            result.append(Cue(begin, end, text))
        if len(result) > 100000:
            raise ValueError("Too many subtitle cues")
    if not result:
        raise ValueError("No real timestamped subtitle cues in SRT")
    return result


def _stamp(t: float, separator=",") -> str:
    ms = max(0, round(t * 1000))
    hh, rest = divmod(ms, 3600000)
    mm, rest = divmod(rest, 60000)
    ss, fraction = divmod(rest, 1000)
    return f"{hh:02}:{mm:02}:{ss:02}{separator}{fraction:03}"


def _ass_stamp(t: float) -> str:
    centiseconds = max(0, round(t * 100))
    hh, rest = divmod(centiseconds, 360000)
    mm, rest = divmod(rest, 6000)
    ss, cs = divmod(rest, 100)
    return f"{hh}:{mm:02}:{ss:02}.{cs:02}"


def render(cues: list[Cue], kind: str, *, timestamps=False, lyrics=False,
           track="original") -> str:
    if kind not in FORMATS:
        raise ValueError("Unsupported export format")
    if kind == "lrc" and not lyrics:
        raise ValueError("LRC requires an explicitly verified timed-lyrics source")
    if kind == "srt":
        return "".join(
            f"{i}\n{_stamp(c.start)} --> {_stamp(c.end)}\n{c.text}\n\n"
            for i, c in enumerate(cues, 1))
    if kind == "vtt":
        return "WEBVTT\n\n" + "".join(
            f"{_stamp(c.start, '.')} --> {_stamp(c.end, '.')}\n{c.text}\n\n"
            for c in cues)
    if kind == "txt":
        return "".join(
            (f"[{_stamp(c.start)} - {_stamp(c.end)}] " if timestamps else "")
            + c.text + "\n" for c in cues)
    if kind == "json":
        return json.dumps({
            "format": "tihulu-timed-caption-v1",
            "track": track,
            "timebase": "media_seconds",
            "word_aligned": False,
            "cues": [{"start": c.start, "end": c.end, "text": c.text}
                     for c in cues],
        }, ensure_ascii=False, indent=2) + "\n"
    if kind == "lrc":
        return "".join(
            f"[{int(c.start//60):02}:{c.start%60:05.2f}]{c.text.replace(chr(10), ' ')}\n"
            for c in cues)
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,38,&H00FFFFFF,&H0000FFFF,&H00000000,"
        "&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,40,40,40,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, "
        "MarginR, MarginV, Effect, Text\n"
    )
    def escape_ass(value):
        return (value.replace("\\", r"\\").replace("{", r"\{")
                .replace("}", r"\}").replace("\n", r"\N"))
    return header + "".join(
        f"Dialogue: 0,{_ass_stamp(c.start)},{_ass_stamp(c.end)},"
        f"Default,,0,0,0,,{escape_ass(c.text)}\n" for c in cues)


def _write_new(path: Path, content: str) -> None:
    """Exclusive creation, never overwrite the user's original or exports."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")[:90] or "TIHULU-recording"


def export_tracks(tracks: dict[str, list[Cue]], directory: str | Path,
                  name: str, formats=("txt", "srt"), *, timestamps=False,
                  verified_lyrics=False) -> list[Path]:
    folder = Path(directory).expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Select an existing export directory")
    kinds = tuple(dict.fromkeys(formats))
    if any(k not in FORMATS for k in kinds):
        raise ValueError("Unsupported export format")
    clean = _safe_name(name)
    jobs = []
    for track, cues in tracks.items():
        if not TRACK.fullmatch(track) or not cues:
            raise ValueError("Invalid track name or empty track")
        for kind in kinds:
            suffix = "" if len(tracks) == 1 and track == "combined" else "." + track
            destination = folder / f"{clean}{suffix}.{kind}"
            jobs.append((destination, render(cues, kind, timestamps=timestamps,
                                             lyrics=verified_lyrics, track=track)))
    if len(set(p for p, _ in jobs)) != len(jobs):
        raise ValueError("Duplicate export paths")
    existing = [str(p) for p, _ in jobs if p.exists()]
    if existing:
        raise FileExistsError("Will not overwrite existing files: " + ", ".join(existing[:3]))
    created = []
    try:
        for path, data in jobs:
            _write_new(path, data)
            created.append(path)
    except BaseException:
        # Delete only the new files we exclusively created in this invocation.
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return created


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", *args],
        capture_output=True, text=True, timeout=21600, check=False)
    if proc.returncode:
        raise RuntimeError("FFmpeg export failed: " + proc.stderr[-500:])


def mux_tracks(media: str | Path, tracks: dict[str, Path], destination: str | Path):
    source = Path(media).expanduser().resolve(strict=True)
    output = Path(destination).expanduser().resolve()
    if not source.is_file() or source == output or output.suffix.lower() != ".mkv":
        raise ValueError("Mux requires distinct local source and MKV output")
    if output.exists():
        raise FileExistsError("Existing media will never be overwritten")
    args = ["-i", str(source)]
    for track, path in tracks.items():
        if not TRACK.fullmatch(track):
            raise ValueError("Invalid track name")
        args += ["-i", str(Path(path).expanduser().resolve(strict=True))]
    args += ["-map", "0:v?", "-map", "0:a?"]
    for i, track in enumerate(tracks, 1):
        args += ["-map", f"{i}:0"]
    args += ["-c:v", "copy", "-c:a", "copy", "-c:s", "srt"]
    for i, track in enumerate(tracks):
        language = track.split("-", 1)[-1] if track.startswith("translation-") else "und"
        args += [f"-metadata:s:s:{i}", f"language={language}"]
    # FFmpeg's -n prevents overwriting even if another process races us.
    # Never delete output on failure: a different user/process might have
    # created the path after the preflight existence check.
    _run_ffmpeg([*args, str(output)])
    return output


def _has_video(path: Path) -> bool:
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)
    ], capture_output=True, text=True, timeout=25, check=False)
    return proc.returncode == 0 and "video" in proc.stdout.splitlines()


def burn_video(media: str | Path, subtitles: str | Path, destination: str | Path):
    source = Path(media).expanduser().resolve(strict=True)
    srt = Path(subtitles).expanduser().resolve(strict=True)
    output = Path(destination).expanduser().resolve()
    if output.exists() or output == source:
        raise FileExistsError("Existing media will never be overwritten")
    if output.suffix.lower() != ".mp4" or not _has_video(source):
        raise ValueError("Burn-in is only available for local video to MP4")
    # FFmpeg filtergraph escaping; no shell is used. Works with ordinary
    # POSIX paths. Literal filter-special characters must be escaped.
    escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace(
        "'", "\\'").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
    _run_ffmpeg(["-i", str(source), "-vf", "subtitles='" + escaped + "'",
                 "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264",
                 "-crf", "20", "-preset", "medium", "-c:a", "aac",
                 "-movflags", "+faststart", str(output)])
    return output


def run_export(*, sources: dict[str, str], destination: str, name: str,
               formats: tuple[str, ...], media=None, mux=False, burn=False,
               burn_track="original", timestamps=False, verified_lyrics=False,
               mode="live") -> list[Path]:
    if mode not in ("live", "complete"):
        raise ValueError("Processing mode must be live or complete")
    if mode == "complete" and not media:
        raise ValueError("Complete mode is for local audio/video files only")
    if (mux or burn) and not media:
        raise ValueError("Media export needs a finished local recording or file")
    if not sources:
        raise ValueError("Supply at least one real SRT subtitle track")
    tracks = {key: parse_srt(path) for key, path in sources.items()}
    outputs = export_tracks(
        tracks, destination, name, formats, timestamps=timestamps,
        verified_lyrics=verified_lyrics)
    folder = Path(destination).expanduser().resolve()
    stem = _safe_name(name)
    if mux:
        outputs.append(mux_tracks(media, {k: Path(p) for k, p in sources.items()},
                                  folder / (stem + "-subtitled.mkv")))
    if burn:
        if burn_track not in sources:
            # A single existing SRT is often labeled combined in the file
            # player; explicit multi-track selections must still be honored.
            if len(sources) == 1 and "combined" in sources:
                burn_track = "combined"
            else:
                raise ValueError("Burn-in track is not present")
        outputs.append(burn_video(media, sources[burn_track],
                                  folder / (stem + "-burned.mp4")))
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description="TIHULU timed caption/media export")
    parser.add_argument("--srt", help="Existing timed subtitle SRT")
    parser.add_argument("--track", action="append", default=[],
                        help="NAME=/path/file.srt for original/translation tracks")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--name", default="TIHULU-recording")
    parser.add_argument("--formats", default="txt,srt")
    parser.add_argument("--media", help="Local finished video/audio file")
    parser.add_argument("--mux", action="store_true")
    parser.add_argument("--burn-video", action="store_true")
    parser.add_argument("--burn-track", default="original")
    parser.add_argument("--timestamps", action="store_true")
    parser.add_argument("--verified-lyrics", action="store_true")
    parser.add_argument("--mode", choices=("live", "complete"), default="live")
    args = parser.parse_args(argv)
    sources = {}
    if args.srt:
        sources["combined"] = args.srt
    for item in args.track:
        key, sep, path = item.partition("=")
        if not sep or not TRACK.fullmatch(key) or key in sources:
            parser.error("Track must be a unique NAME=/path/file.srt")
        sources[key] = path
    try:
        created = run_export(
            sources=sources, destination=args.destination, name=args.name,
            formats=tuple(x.strip().lower() for x in args.formats.split(",") if x.strip()),
            media=args.media, mux=args.mux, burn=args.burn_video,
            burn_track=args.burn_track, timestamps=args.timestamps,
            verified_lyrics=args.verified_lyrics, mode=args.mode)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)[:500]}),
              file=sys.stderr)
        return 1
    print(json.dumps({"status": "completed", "outputs": [str(p) for p in created]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
