"""Live offline DAB+ captions and explicit, metadata-only lyrics lookup.

A Kaffeine Radio page opens and owns pinned welle-cli. This worker ONLY
reads its verified loopback MP3 stream, never opens any USB/DAB adapter,
microphone or Internet account. AI remains locally installed; no download.
The receiver UI/CLI starts this worker only on a user click.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from .ai_settings import AISettings
from .language_codes import language_code
from .lyrics_sync import lookup_synced_lyrics, LiveLyricMatcher
from .media_ai import _chunk_cues, _choose_model, CHUNK_SAMPLES

_SID = re.compile(r"(?:0x)?[A-Fa-f0-9]{1,8}\Z")


def checked_runtime_output(value: str, *, prefix: str) -> Path:
    root = Path(os.environ.get("XDG_RUNTIME_DIR", "")).expanduser()
    if (not root.is_dir() or not root.is_absolute() or root.is_symlink() or
            root.stat().st_uid != os.getuid()):
        raise RuntimeError("Private XDG_RUNTIME_DIR missing or inaccessible")
    candidate = Path(value).expanduser()
    if (not candidate.is_absolute() or candidate.is_symlink() or
            candidate.parent.resolve() != root.resolve() or
            not candidate.name.startswith(prefix) or
            not candidate.name.endswith(".json")):
        raise ValueError("Output must be a private, prefixed runtime JSON path")
    return candidate


def write_runtime_json(path: Path, payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(serialized) > 120_000:
        raise ValueError("Caption output too large")
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=".tihulu-radio-",
        delete=False) as file:
        temporary = Path(file.name)
        file.write(serialized)
    try:
        os.chmod(temporary, 0o600)
        if path.is_symlink():
            raise ValueError("Refusing to overwrite symlink")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def decode_radio_live(*, port: int, sid: str, source: str, targets: tuple[str,...],
                      output: str, music: bool=False, max_chunks: int=0,
                      speaker_labels: bool=False):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid loopback radio port")
    if not isinstance(sid,str) or not _SID.fullmatch(sid):
        raise ValueError("Invalid welle station identifier")
    src = ("auto" if source=="auto" else language_code(source))
    destinations = tuple(dict.fromkeys(language_code(t,nllb=True)
                                       for t in targets))
    if len(destinations)>6:
        raise ValueError("Choose at most 6 translated subtitle languages")
    location=checked_runtime_output(output,prefix="tihulu-radio-captions-")
    ai=AISettings()
    ai.configure_environment()
    if not ai.values["asr_enabled"]:
        raise RuntimeError("Enable the installed offline Whisper model in AI Market")
    profile,backend=_choose_model(ai)
    # Do not let a remote URL or attacker-specified radio host pass through:
    # always connect the LOCAL welle endpoint started by native Kaffeine.
    url=f"http://127.0.0.1:{port}/mp3/{sid}"
    ffmpeg=subprocess.Popen(
        ["ffmpeg","-nostdin","-hide_banner","-loglevel","error",
         "-protocol_whitelist","file,http,tcp",
         "-i",url,"-map","0:a:0","-ac","1","-ar","32000",
         "-vn","-f","s16le","pipe:1"],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)
    done=False
    def stop(_sig=None,_frame=None):
        nonlocal done
        done=True
        try:
            ffmpeg.terminate()
        except (OSError,ProcessLookupError):
            pass
    for signum in (signal.SIGTERM,signal.SIGINT):
        signal.signal(signum,stop)
    chunks=0
    latest_language=None
    candidate_language=None
    candidate_runs=0
    lyric_path=location.with_name(location.name.replace(
        "tihulu-radio-captions-","tihulu-radio-lyrics-",1))
    lyric_marker=None
    plain_matcher=None
    try:
        while not done:
            pcm=ffmpeg.stdout.read(6*CHUNK_SAMPLES*2)
            if done or len(pcm)<CHUNK_SAMPLES:
                break
            # Source is actual radio audio. Whisper emits real word positions
            # on CUDA; the output has no false claim of latency compensation.
            captured_at=time.monotonic()
            # The separately authorized lyrics worker writes only to a
            # private XDG_RUNTIME_DIR JSON; refresh when the song changes.
            # No additional Internet call and no second SDR owner.
            try:
                marker=(lyric_path.stat().st_mtime_ns,lyric_path.stat().st_size)
                if marker != lyric_marker and marker[1] <= 150_000:
                    lyric_marker=marker
                    payload=json.loads(lyric_path.read_text(encoding="utf-8"))
                    lines=payload.get("plain_lines",[])
                    plain_matcher=(LiveLyricMatcher(lines)
                                   if payload.get("alignment_mode")=="asr_lexical"
                                   and isinstance(lines,list) and lines else None)
            except (OSError,ValueError,TypeError,json.JSONDecodeError):
                if not lyric_path.is_file():
                    lyric_marker=None
                    plain_matcher=None
            detection={}
            cues=_chunk_cues(pcm,position=chunks*6,lang=src,
                            profile=profile,backend=backend,
                            music=music or plain_matcher is not None,
                            detection=detection)
            original=" ".join(cue.text for cue in cues).strip()
            # Speaker identities are relative voice clusters (Speaker 1, 2...),
            # not inferred gender/age. Music-mode does NOT invoke diarization.
            speaker_turns=[]
            speaker_warning=None
            if speaker_labels and original and not music and plain_matcher is None:
                try:
                    from .free_speakers import FreeSpeakerMarket, diarize_pcm
                    if FreeSpeakerMarket().status()["installed"]:
                        speaker_turns=diarize_pcm(pcm,channel=sid)
                    else:
                        speaker_warning="Install the optional local speaker model in AI Market"
                except (ImportError,RuntimeError,TimeoutError,OSError,ValueError) as exc:
                    speaker_warning=str(exc)[:180]
            candidate=detection.get("language")
            confidence=float(detection.get("confidence") or 0.0)
            language_pending=False
            if src=="auto":
                # One incorrect 6-second language guess must NOT flip the
                # translation source. Two consecutive high-confidence
                # detections are required before committing a switch.
                if candidate and confidence>=0.72:
                    if candidate==candidate_language:
                        candidate_runs+=1
                    else:
                        candidate_language=candidate
                        candidate_runs=1
                    if candidate_runs>=2:
                        latest_language=candidate
                    elif candidate!=latest_language:
                        language_pending=True
                else:
                    candidate_language=None
                    candidate_runs=0
                    if latest_language is None or (
                            candidate and candidate!=latest_language):
                        language_pending=True
                used_language=latest_language
            else:
                used_language=src
            lyric_match=(plain_matcher.observe(original)
                         if plain_matcher is not None and original else None)
            translated={}
            problems={}
            if (original and used_language and not language_pending
                    and ai.values["translation_enabled"]):
                from .captions import translate
                for lang in destinations:
                    if lang == used_language:
                        # Source language selected as output, not a
                        # pointless second translation of the same text.
                        continue
                    value,issue=translate(original,used_language,lang)
                    if value:
                        translated[lang]=value
                    if issue:
                        problems[lang]=issue[:180]
            write_runtime_json(location,{
                "status":"running",
                "source_language":used_language or "und",
                "language_detected":src=="auto",
                "language_confidence":round(confidence,3),
                "language_pending":language_pending,
                "language_source":("confirmed_2_chunks" if src=="auto" else "manual"),
                "original":original[:1800],
                "lyric_match":lyric_match,
                "lyric_alignment":("observed_ASR_approximate" if plain_matcher
                                   else "none"),
                "translations":translated,
                "translation_warnings":problems,
                "backend":backend,
                "music_mode":bool(music),
                "content_type":("music_lyrics_metadata" if plain_matcher is not None
                                 else "speech_or_unclassified"),
                "recognition_rejected":detection.get("recognition_rejected"),
                "speaker_turns":speaker_turns,
                "speaker_warning":speaker_warning,
                "speaker_classification":(
                    "approximate voice clustering; no age or gender inference"
                    if speaker_labels and not music else "disabled"),
                "lag_note":"Radio ASR reads original welle stream. Player caching "
                           "is an estimate, not a confirmed libVLC presentation clock.",
                "captured_monotonic":captured_at,
                "decoded_monotonic":time.monotonic(),
                "timestamp":time.time(),
                "station_sid":sid,
                "chunk_index":chunks})
            chunks+=1
            if max_chunks>0 and chunks>=max_chunks:
                break
    finally:
        stop()
        try:
            ffmpeg.wait(timeout=3)
        except subprocess.TimeoutExpired:
            ffmpeg.kill()
            ffmpeg.wait(timeout=2)
        if ffmpeg.stdout:
            ffmpeg.stdout.close()
    return {"status":"stopped","chunks":chunks}


def lyrics_lookup_to_file(*, artist:str, track:str,output:str,
                          online:bool=False, source:str="auto",
                          targets:tuple[str,...]=()):
    location=checked_runtime_output(output,prefix="tihulu-radio-lyrics-")
    try:
        cues,provenance=lookup_synced_lyrics(
            title=track,artist=artist,online=online,allow_plain=True)
        plain_lines=provenance.get("plain_lines",[]) if isinstance(provenance,dict) else []
        if not cues and not plain_lines:
            raise RuntimeError(
                "No matching lyrics ("+str(provenance.get("status"))+")")
        from .captions import translate
        source_code=("auto" if source=="auto" else language_code(source))
        target_codes=tuple(dict.fromkeys(language_code(t,nllb=True)
                                         for t in targets))[:6]
        timed=[]
        for cue in cues[:150]:
            line={"start":cue.start,"end":cue.end,
                  "text":cue.text[:700]}
            translated={}
            if source_code!="auto":
                for lang in target_codes:
                    if lang==source_code:
                        continue
                    rendered,problem=translate(cue.text,source_code,lang)
                    if rendered:
                        translated[lang]=rendered[:700]
            if translated:
                line["translations"]=translated
            timed.append(line)
        payload={"status":"completed","provenance":{
                     key:value for key,value in provenance.items()
                     if key!="plain_lines"},
                 "plain_lines":plain_lines[:150],
                 "alignment_mode":("asr_lexical" if plain_lines else "timed_lrc"),
                 "source_language":source_code,
                 "translation_note":("Choose a source language or start radio ASR "
                    "to detect it before translating lyrics"
                    if source_code=="auto" else
                    "Offline translations share original lyric timestamps; "
                    "not exact translated-word alignment"),
                 "time_base":("matched ASR chunk timestamps; no fabricated LRC times"
                              if plain_lines else
                              "approximate DLS change plus radio cache; use manual offset"),
                 "cues":timed}
        write_runtime_json(location,payload)
        return 0
    except (RuntimeError,ValueError,PermissionError,OSError) as exc:
        write_runtime_json(location,{"status":"error",
                                     "reason":str(exc)[:180]})
        return 1


def main(args=None):
    parser=argparse.ArgumentParser(description="TIHULU offline DAB radio AI / lyrics")
    subs=parser.add_subparsers(dest="action",required=True)
    live=subs.add_parser("radio-captions")
    live.add_argument("--port",type=int,required=True)
    live.add_argument("--sid",required=True)
    live.add_argument("--source",default="auto",
                      help="Auto-detect multilingual broadcast speech per chunk")
    live.add_argument("--targets",default="en,tr")
    live.add_argument("--output",required=True)
    live.add_argument("--music",action="store_true")
    live.add_argument("--speaker-labels",action="store_true",
                      help="Opt-in local voice clusters; not for song/music mode")
    lookup=subs.add_parser("lyrics-lookup")
    lookup.add_argument("--track",required=True)
    lookup.add_argument("--artist",required=True)
    lookup.add_argument("--output",required=True)
    lookup.add_argument("--online",action="store_true")
    lookup.add_argument("--source",default="auto")
    lookup.add_argument("--targets",default="en,de,tr")
    opts=parser.parse_args(args)
    if opts.action=="lyrics-lookup":
        return lyrics_lookup_to_file(
            artist=opts.artist,track=opts.track,
            output=opts.output,online=opts.online,
            source=opts.source,
            targets=tuple(x.strip() for x in opts.targets.split(",") if x.strip()))
    try:
        decode_radio_live(port=opts.port,sid=opts.sid,
            source=opts.source,
            targets=tuple(x.strip() for x in opts.targets.split(",") if x.strip()),
            output=opts.output,music=opts.music,
            speaker_labels=opts.speaker_labels)
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print("Offline radio AI unavailable: "+str(exc)[:250],file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
