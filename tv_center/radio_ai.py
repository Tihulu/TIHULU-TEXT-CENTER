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
from .lyrics_sync import (lookup_synced_lyrics, LiveLyricMatcher, parse_lrc,
                          aligned_karaoke_word_anchors)
from .sentence_joiner import LiveSentenceJoiner
from .radio_language import RadioLanguageLock
from .media_ai import _chunk_cues, _choose_model, _near_silent_pcm, CHUNK_SAMPLES
from .radio_capture import BoundedRadioCapture

_SID = re.compile(r"(?:0x)?[A-Fa-f0-9]{1,8}\Z")


def effective_radio_translation_enabled(market_enabled: bool,
                                        radio_requested: bool,
                                        model_name: str) -> bool:
    """Explicit radio opt-in uses installed LOCAL models only.

    Market-enabled DeepL stays under its current setting; a radio toggle
    alone cannot opt users into a remote translation service.
    """
    return bool(market_enabled or
                (radio_requested and model_name in ("argos", "nllb", "madlad",
                                                    "de_tr_direct","auto_offline")))


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
                      speaker_labels: bool=False, prefer_verified_lyrics: bool=False,
                      sentence_hops: int=3,
                      host_audio_cache_ms: int=0,
                      host_caption_offset_ms: int=0,
                      controls: str | None=None,
                      radio_translations: bool=False,
                      lyric_match_threshold: float=0.74,
                      sound_labels: bool=False):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid loopback radio port")
    if not isinstance(sid,str) or not _SID.fullmatch(sid):
        raise ValueError("Invalid welle station identifier")
    src = ("auto" if source=="auto" else language_code(source))
    destinations = tuple(dict.fromkeys(language_code(t,nllb=True)
                                       for t in targets))
    if len(destinations)>6:
        raise ValueError("Choose at most 6 translated subtitle languages")
    if type(sentence_hops) is not int or not 2 <= sentence_hops <= 5:
        raise ValueError("Radio sentence assembly must use 2–5 audio hops")
    if (type(host_audio_cache_ms) is not int or
            not 0<=host_audio_cache_ms<=60000):
        raise ValueError("Radio audio cache must be 0–60000 ms")
    if (type(host_caption_offset_ms) is not int or
            not -12000<=host_caption_offset_ms<=12000):
        raise ValueError("Radio caption offset must be ±12000 ms")
    if type(radio_translations) is not bool:
        raise ValueError("Radio translator opt-in must be boolean")
    if type(sound_labels) is not bool:
        raise ValueError("Radio sound label opt-in must be boolean")
    if (not isinstance(lyric_match_threshold,(int,float)) or
            isinstance(lyric_match_threshold,bool) or
            not 0.65<=lyric_match_threshold<=0.96):
        raise ValueError("Lyrics similarity threshold must be 65–96%")
    location=checked_runtime_output(output,prefix="tihulu-radio-captions-")
    controls_path=(checked_runtime_output(
        controls,prefix="tihulu-radio-controls-") if controls else None)
    controls_marker=None
    controls_note=""
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
         "-rw_timeout","15000000",
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
    capture=BoundedRadioCapture(ffmpeg.stdout,
        samples_per_second=CHUNK_SAMPLES,max_windows=max_chunks).start()
    last_capture_index=None
    auto_language=RadioLanguageLock()
    lyric_path=location.with_name(location.name.replace(
        "tihulu-radio-captions-","tihulu-radio-lyrics-",1))
    lyric_marker=None
    plain_matcher=None
    lyric_source_language="auto"
    lyric_target_codes=()
    lyric_translation_cache={}
    sentence_joiner=LiveSentenceJoiner(max_words=115,max_chunks=sentence_hops)
    write_runtime_json(location,{
        "status":"waiting_audio","source_language":src,
        "language_source":"pending_audio","translation_state":"listening",
        "original":"","translations":{},"chunk_index":-1,
        "note":"Connecting to local DAB audio; radio playback is independent."
    })
    try:
        while not done:
            # The independent capture thread ALWAYS drains this worker's
            # local MP3 connection, even during a slow Whisper/translation
            # pass. On overload, old *AI* windows are discarded explicitly,
            # never the main libVLC radio playback stream.
            audio_window=capture.next()
            if done or audio_window is None:
                break
            capture_index,pcm,captured_at=audio_window
            # Apply user-chosen source / output languages during playback
            # without restarting Whisper and losing presenter audio.
            # An invalid control file never disables existing languages.
            if controls_path is not None:
                try:
                    stat=controls_path.lstat()
                    marker=(stat.st_mtime_ns,stat.st_size)
                    if (stat.st_uid==os.getuid() and
                            controls_path.is_file() and
                            not controls_path.is_symlink() and
                            0<stat.st_size<=4096 and
                            marker!=controls_marker):
                        controls_marker=marker
                        payload=json.loads(controls_path.read_text(
                            encoding="utf-8"))
                        requested=payload.get("targets")
                        language=payload.get("source")
                        if not isinstance(requested,list) or len(requested)>6:
                            raise ValueError("Invalid requested output list")
                        codes=tuple(dict.fromkeys(
                            language_code(item,nllb=True)
                            for item in requested))
                        if not isinstance(language,str):
                            raise ValueError("Invalid source language")
                        chosen=("auto" if language=="auto" else
                                language_code(language))
                        destinations=codes
                        if src!=chosen:
                            src=chosen
                            auto_language=RadioLanguageLock()
                            sentence_joiner.reset()
                        requested_translation=payload.get("radio_translations")
                        if type(requested_translation) is bool:
                            radio_translations=requested_translation
                        requested_labels=payload.get("sound_labels")
                        if type(requested_labels) is bool:
                            sound_labels=requested_labels
                        requested_threshold=payload.get("lyric_match_threshold")
                        if (isinstance(requested_threshold,(float,int)) and
                                not isinstance(requested_threshold,bool) and
                                0.65<=requested_threshold<=0.96):
                            lyric_match_threshold=float(requested_threshold)
                            if plain_matcher is not None:
                                plain_matcher.set_threshold(lyric_match_threshold)
                        controls_note="live_preferences_applied"
                except (OSError,ValueError,TypeError,KeyError,
                        json.JSONDecodeError) as exc:
                    controls_note="invalid_controls_"+type(exc).__name__
            gap=(last_capture_index is not None and
                 capture_index != last_capture_index+1)
            if gap:
                # Never glue text from two non-contiguous audio windows.
                sentence_joiner.reset()
            last_capture_index=capture_index
            # The separately authorized lyrics worker writes only to a
            # private XDG_RUNTIME_DIR JSON; refresh when the song changes.
            # No additional Internet call and no second SDR owner.
            try:
                marker=(lyric_path.stat().st_mtime_ns,lyric_path.stat().st_size)
                if marker != lyric_marker and marker[1] <= 150_000:
                    lyric_marker=marker
                    payload=json.loads(lyric_path.read_text(encoding="utf-8"))
                    lines=payload.get("plain_lines",[])
                    plain_matcher=(LiveLyricMatcher(
                        lines,threshold=lyric_match_threshold)
                                   if payload.get("alignment_mode") in
                                   ("asr_lexical","timed_lrc")
                                   and isinstance(lines,list) and lines else None)
                    lyric_source_language=payload.get("source_language","auto")
                    lyric_target_codes=tuple(payload.get("translation_targets",[]))[:6]
                    lyric_translation_cache.clear()
            except (OSError,ValueError,TypeError,json.JSONDecodeError):
                if not lyric_path.is_file():
                    lyric_marker=None
                    plain_matcher=None
                    lyric_source_language="auto"
                    lyric_target_codes=()
                    lyric_translation_cache.clear()
            # Lyrics lookup itself does not recognize singing. As soon as a
            # real, authorized TXT/LRC song catalog has arrived, let Whisper
            # observe vocals for matching WITHOUT restarting the radio or
            # sidecar. On a new song / file removal restore normal speech
            # VAD automatically. Metadata alone NEVER enables vocal mode.
            music_for_matching=bool(music or plain_matcher is not None)
            translator_enabled=effective_radio_translation_enabled(
                ai.values["translation_enabled"],radio_translations,
                ai.values.get("translation_model","argos"))
            detection={}
            # DAB decoder may deliver actual near-silence. In music-mode
            # VAD is intentionally disabled, and Whisper can hallucinate
            # subtitle headings over dead air. Do not send near-silent
            # 16-bit PCM to either GPU or CPU ASR. Real speech/music above
            # the conservative floor is left untouched.
            if _near_silent_pcm(pcm):
                detection["recognition_rejected"]="near_silent_pcm"
                detection["language"]=None
                detection["confidence"]=0.0
                cues=[]
            else:
                cues=_chunk_cues(pcm,position=capture_index*5,lang=src,
                                profile=profile,backend=backend,
                                # Lyrics metadata alone cannot turn an
                                # announcer/advert into singing mode: this
                                # made ordinary speech fall through the
                                # music-oriented no-VAD path.
                                music=music_for_matching,
                                detection=detection)
            if capture_index>0:
                # Retain words crossing the genuine 1-second read overlap.
                cues=[cue for cue in cues
                      if cue.end>capture_index*5+1.0]
            original=" ".join(cue.text for cue in cues).strip()
            # Speaker identities are relative voice clusters (Speaker 1, 2...),
            # not inferred gender/age. Music-mode does NOT invoke diarization.
            speaker_turns=[]
            speaker_warning=None
            if speaker_labels and original and not music_for_matching and plain_matcher is None:
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
            if src=="auto":
                decision=auto_language.observe(candidate,confidence)
                used_language=decision.language
                language_pending=decision.pending
                language_reason=decision.reason
            else:
                used_language=src
                language_pending=False
                language_reason="manual_source_language"
            lyric_match=(plain_matcher.observe(original)
                         if plain_matcher is not None and original else None)
            sentence_state={"text":original,"complete":True,"pending":False,"chunks":0}
            if plain_matcher is None and not music_for_matching:
                sentence_state=sentence_joiner.push(
                    original, language=used_language, silent=not bool(original))
                original=sentence_state["text"]
            else:
                sentence_joiner.reset()
            # Verified lyrical wording wins only when the *heard* Whisper
            # words actually match it. DLS may continue to advertise
            # a song while the presenter/advert is speaking. Never erase
            # genuine unmatched speech merely because an old LRC file is
            # loaded or "Prefer verified lyrics" was selected.
            unverified_vocals_hidden=False
            if plain_matcher is not None and prefer_verified_lyrics and lyric_match:
                original=lyric_match["text"]
            # Use capture-clock timing, not the time Whisper + multiple
            # translators happened to finish. All cue times refer to the
            # same absolute 5s hop with a 6s PCM decoding window.
            #
            # A queued/silence-flushed sentence may span earlier windows;
            # this is an estimate of its LAST recognized word, never a
            # claim of exact per-word libVLC presentation timestamps.
            capture_epoch_ms=round(
                (time.time()+captured_at-time.monotonic())*1000)
            window_start=capture_index*5.
            heard_end=max((float(cue.end) for cue in cues),default=window_start+6.)
            heard_end=max(window_start,min(window_start+6.,heard_end))
            phrase_end_epoch_ms=int(capture_epoch_ms-
                                    round((window_start+6.-heard_end)*1000))
            # First ACTUAL GPU Whisper word, not guessed CPU chunk time.
            # A carried multi-hop sentence cannot use a later hop's start.
            first_word_epoch_ms=0
            if cues and detection.get("asr_words") and not (
                    sentence_state.get("continued") or
                    sentence_state.get("chunks",0)>1):
                heard_start=min(float(cue.start) for cue in cues)
                heard_start=max(window_start,
                                min(window_start+6.,heard_start))
                first_word_epoch_ms=int(capture_epoch_ms-round(
                    (window_start+6.-heard_start)*1000))
            # Only matched song lines may carry GPU word evidence.
            # No inferred word times for CPU, translations, DLS or LRC metadata.
            lyric_word_anchors=(aligned_karaoke_word_anchors(
                lyric_match["text"], detection.get("asr_words", []),
                capture_end_epoch_ms=capture_epoch_ms,
                window_seconds=len(pcm)/(2*CHUNK_SAMPLES))
                if lyric_match else [])

            # Publish the ORIGINAL promptly after ASR. A slow sequential
            # NLLB/MADLAD/Argos/DeepL translation must not block hearing
            # the already recognized presenter or lyric words. The next
            # write for the SAME chunk includes translations (revision 1).
            if original:
                preview_state=("language_pending" if language_pending else
                    "translator_disabled" if not translator_enabled else
                    "translating" if any(x!=used_language for x in destinations) else
                    "original_only")
                write_runtime_json(location,{
                    "status":"running",
                    "chunk_index":capture_index,
                    "caption_revision":0,
                    "original":original[:1800],
                    "source_language":used_language or "und",
                    "language_source":language_reason,
                    "language_detected":src=="auto",
                    "language_confidence":round(confidence,3),
                    "source_capture_epoch_ms":capture_epoch_ms,
                    "subtitle_audio_end_epoch_ms":phrase_end_epoch_ms,
                    "subtitle_audio_start_epoch_ms":first_word_epoch_ms,
                    "subtitle_clock_source":"welle_pcm_captured_approximate",
                    "requested_targets":list(destinations),
                    "translations":{},
                    "translation_state":preview_state,
                    "translation_note":(
                        "Translation processing; original audio shown first"
                        if preview_state=="translating" else
                        "Choose a reliable spoken language" if language_pending else
                        "Translation disabled in Model Market" if
                        preview_state=="translator_disabled" else
                        "Only source language selected"),
                    "language_pending":language_pending,
                    "control_status":controls_note,
                    "ai_audio_windows_dropped":capture.dropped_windows,
                    "ai_audio_gap":gap,
                    "timestamp":time.time(),
                })
            translated={}
            problems={}
            translation_engines={}
            requested_translation_targets=tuple(
                lang for lang in destinations if lang != used_language)
            if (original and used_language and not language_pending
                    and not unverified_vocals_hidden
                    and translator_enabled):
                from .captions import translate, translation_engine_for
                for lang in destinations:
                    if lang == used_language:
                        # Source language selected as output, not a
                        # pointless second translation of the same text.
                        continue
                    value,issue=translate(
                        original,used_language,lang)
                    actual=translation_engine_for(original,used_language,lang)
                    if value:
                        translated[lang]=value
                        if actual:
                            translation_engines[lang]=actual
                    if issue:
                        problems[lang]=issue[:180]
            # The authorized lyrics text, not DLS metadata, is the
            # translation source for matched song vocals. When automatic
            # language detection is uncertain we do NOT guess translations;
            # manual source selection can translate immediately.
            lyric_translations=(
                dict(translated)
                if lyric_match and original==lyric_match.get("text")
                   and used_language and not language_pending else {})
            if (lyric_match and translator_enabled):
                song_language=(lyric_source_language
                               if lyric_source_language!="auto" else
                               used_language if not language_pending else None)
                song_line=lyric_match.get("text","")
                if song_language and song_line and not (
                    song_language==used_language and
                    original==song_line and not language_pending):
                    # Only translate an actually HEARD/matched lyric line.
                    # An explicit song-source choice can differ from the
                    # auto-detected spoken presenter language.
                    from .captions import translate
                    for lang in lyric_target_codes:
                        if lang==song_language:
                            continue
                        key=(song_language,lang,song_line)
                        if key in lyric_translation_cache:
                            translated_line,issue=lyric_translation_cache[key]
                        else:
                            translated_line,issue=translate(song_line,song_language,lang)
                            if len(lyric_translation_cache)>=120:
                                lyric_translation_cache.clear()
                            lyric_translation_cache[key]=(translated_line,issue)
                        if translated_line:
                            lyric_translations[lang]=translated_line
                        if issue:
                            problems[lang]=str(issue)[:180]
            # Acoustic labels are independently opt-in. Whisper ORIGINAL
            # has already been published above; even a slow/failed detector
            # cannot suppress spoken captions or change lyric matching.
            sound_events=[]
            sound_note=None
            if sound_labels:
                try:
                    from .audio_classifiers import AudioLabels,detect_sound_events
                    if not AudioLabels().installed("sound"):
                        sound_note="Optional offline AST AudioSet sound model not installed"
                    elif capture.dropped_windows:
                        sound_note="Sound labels skipped under ASR backlog"
                    else:
                        sound_events=detect_sound_events(pcm)
                except (RuntimeError,OSError,ValueError,ImportError,TimeoutError) as exc:
                    sound_note="Sound classifier unavailable: "+str(exc)[:130]
            from .sound_event_captions import decorate_caption
            rendered_original=(decorate_caption(
                original,sound_events,used_language or "en")
                if original else original)
            rendered_translations={
                lang:decorate_caption(value,sound_events,lang)
                for lang,value in translated.items()}
            # Do not report an unverified translation as success. Provide
            # exact reasons for the visible untranslated original, including
            # model disabled, unknown source, or missing language packs.
            from .radio_translation_status import translation_state
            translation_info=translation_state(
                original=original, source_language=used_language,
                requested_targets=destinations, translated=translated,
                failures=problems,
                translator_enabled=translator_enabled,
                language_pending=language_pending)
            write_runtime_json(location,{
                "status":"running",
                "caption_revision":1,
                "source_language":used_language or "und",
                "language_detected":src=="auto",
                "language_confidence":round(confidence,3),
                "language_pending":language_pending,
                "language_source":language_reason,
                "translation_state":translation_info["state"],
                "radio_translation_opt_in":radio_translations,
                "translation_enabled_effective":translator_enabled,
                "translation_service":ai.values.get("translation_model","argos"),
                "translation_engines":translation_engines,
                "translation_note":translation_info["message"],
                "translation_missing_targets":translation_info["missing_targets"],
                "translation_pending_targets":translation_info["pending_targets"],
                "requested_targets":list(destinations),
                "control_status":controls_note,
                "original":rendered_original[:1800],
                "sound_events":sound_events,
                "sound_labels_source":("AST AudioSet · approximate 5s window"
                                       if sound_events else None),
                "sound_event_note":sound_note,
                "sentence_pending":bool(sentence_state.get("pending")),
                "sentence_complete":bool(sentence_state.get("complete")),
                "sentence_carry_chunks":int(sentence_state.get("chunks",0)),
                "sentence_continuation":bool(sentence_state.get("continued",False)),
                "sentence_hops_limit":sentence_hops,
                "lyric_match":lyric_match,
                "lyric_match_threshold":round(lyric_match_threshold,3),
                "lyric_match_metric":"lexical_overlap_not_sync_accuracy",
                "lyric_word_anchors":lyric_word_anchors,
                "lyric_word_clock":"gpu_whisper_pcm_estimated_not_dac"
                    if lyric_word_anchors else "line_only_no_word_evidence",
                "lyric_translations":lyric_translations,
                "lyric_translation_status":(
                    "matched_song_audio" if lyric_translations else
                    "awaiting_confident_source_language_or_installed_translator"
                    if lyric_match else "no_verified_song_line"),
                "unverified_song_asr_hidden":unverified_vocals_hidden,
                "music_detected":False,
                "lyric_match_verified":bool(lyric_match),
                "speech_preserved_when_lyrics_unmatched":bool(
                    original and plain_matcher is not None and not lyric_match),
                "lyric_alignment":("observed_ASR_approximate" if plain_matcher
                                   else "none"),
                "translations":rendered_translations,
                "translation_warnings":problems,
                "backend":backend,
                "music_mode":music_for_matching,
                "vocal_match_mode":("lyrics_catalog_vad_relaxed"
                    if plain_matcher is not None and not music else
                    "user_music_transcribe" if music else "speech_default"),
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
                # Convert to wall-clock once, based on the same local
                # monotonic reading; phone compensates for device clock skew.
                "source_capture_epoch_ms":capture_epoch_ms,
                "subtitle_audio_end_epoch_ms":phrase_end_epoch_ms,
                    "subtitle_audio_start_epoch_ms":first_word_epoch_ms,
                "subtitle_clock_source":"welle_pcm_captured_approximate",
                "subtitle_word_alignment":"Whisper cue end or PCM hop end; not DAC PTS",
                "host_audio_cache_ms":host_audio_cache_ms,
                "host_caption_offset_ms":host_caption_offset_ms,
                "host_buffer_accuracy":"requested_not_DAC_verified",
                "decoded_monotonic":time.monotonic(),
                "timestamp":time.time(),
                "station_sid":sid,
                "chunk_index":capture_index,
                "ai_audio_windows_dropped":capture.dropped_windows,
                "ai_audio_gap":gap,
                "requested_target_count":len(destinations),
                "translated_target_count":len(translated),
                "window_hop_seconds":5,
                "audio_overlap_seconds":1 if capture_index else 0})
            chunks+=1
            if max_chunks>0 and chunks>=max_chunks:
                break
    finally:
        stop()
        capture.stop()
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
        if cues and not plain_lines:
            # A timestamped LRC is also a verified text catalog, so real
            # Whisper observations can periodically recalibrate DLS timing.
            plain_lines=[cue.text for cue in cues[:150]]
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
                 "translation_targets":list(target_codes),
                 "alignment_mode":("timed_lrc" if cues else "asr_lexical"),
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


def local_lyrics_to_file(*, file: str, output: str):
    """Opt-in import of a user's local unsynced TXT or timed LRC."""
    location=checked_runtime_output(output,prefix="tihulu-radio-lyrics-")
    path=Path(file).expanduser()
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in (".txt",".lrc"):
        raise ValueError("Select a regular .txt or .lrc lyrics file (no symlinks)")
    if path.stat().st_size>180_000:
        raise ValueError("Lyrics file too large")
    data=path.read_text(encoding="utf-8-sig")
    timed=parse_lrc(data) if path.suffix.lower()==".lrc" else []
    plain=[]
    if timed:
        plain=[cue.text for cue in timed[:150]]
    else:
        for row in data.splitlines()[:350]:
            line=" ".join(row.strip().split())
            if 3<=len(line)<=240 and not (line.startswith("[") and line.endswith("]")):
                plain.append(line)
            if len(plain)>=150:
                break
    if not plain:
        raise ValueError("Local file has no usable lyric lines")
    write_runtime_json(location,{
        "status":"completed","alignment_mode":"timed_lrc" if timed else "asr_lexical",
        "source_language":"auto",
        "provenance":{"provider":"user_local_file","online_lookup":False},
        "plain_lines":plain,
        "cues":[{"start":line.start,"end":line.end,"text":line.text}
                for line in timed[:150]],
        "time_base":"LRC timestamps + observed ASR correction" if timed else
                    "No given timestamps; align verified words to actual ASR chunks"})
    return 0


def main(args=None):
    parser=argparse.ArgumentParser(description="TIHULU offline DAB radio AI / lyrics")
    subs=parser.add_subparsers(dest="action",required=True)
    live=subs.add_parser("radio-captions")
    live.add_argument("--port",type=int,required=True)
    live.add_argument("--sid",required=True)
    live.add_argument("--source",default="auto",
                      help="Auto-detect multilingual broadcast speech per chunk")
    live.add_argument("--targets",default="en,tr")
    live.add_argument("--controls",default=None,
                      help="Private XDG runtime JSON; live source/output settings")
    live.add_argument("--output",required=True)
    live.add_argument("--music",action="store_true")
    live.add_argument("--lyric-match-threshold",type=float,default=0.74,
                      help="65–96%% lyric/ASR lexical overlap minimum; not sync confidence")
    live.add_argument("--sound-labels",action="store_true",
                      help="Local AST AudioSet sound labels; optional, never replaces speech")
    live.add_argument("--radio-translations",action="store_true",
                      help="Use an installed offline translator for this radio session; "
                           "never opt into DeepL or download models")
    live.add_argument("--host-audio-cache-ms",type=int,default=0,
                      help="Host REQUESTED radio cache; not measured DAC delay")
    live.add_argument("--host-caption-offset-ms",type=int,default=0,
                      help="Native radio caption offset milliseconds")
    live.add_argument("--sentence-hops",type=int,default=3,
                      help="2–5 Whisper 5s hops; higher buffer can preserve "
                           "longer sentences before translating")
    live.add_argument("--speaker-labels",action="store_true",
                      help="Opt-in local voice clusters; not for song/music mode")
    live.add_argument("--prefer-verified-lyrics",action="store_true",
                      help="When plain lyrics metadata is loaded, hide unverified song ASR "
                           "behind a [music] marker; never invent lyrics")
    user_file=subs.add_parser("lyrics-import")
    user_file.add_argument("--file",required=True)
    user_file.add_argument("--output",required=True)
    lookup=subs.add_parser("lyrics-lookup")
    lookup.add_argument("--track",required=True)
    lookup.add_argument("--artist",required=True)
    lookup.add_argument("--output",required=True)
    lookup.add_argument("--online",action="store_true")
    lookup.add_argument("--source",default="auto")
    lookup.add_argument("--targets",default="en,de,tr")
    opts=parser.parse_args(args)
    if opts.action=="lyrics-import":
        try:
            return local_lyrics_to_file(file=opts.file,output=opts.output)
        except (OSError,ValueError,RuntimeError) as exc:
            print("Local lyrics import failed: "+str(exc)[:240],file=sys.stderr)
            return 1
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
            output=opts.output,controls=opts.controls,music=opts.music,
            speaker_labels=opts.speaker_labels,
            prefer_verified_lyrics=opts.prefer_verified_lyrics,
            sentence_hops=opts.sentence_hops,
            host_audio_cache_ms=opts.host_audio_cache_ms,
            host_caption_offset_ms=opts.host_caption_offset_ms,
            radio_translations=opts.radio_translations,
            lyric_match_threshold=opts.lyric_match_threshold,
            sound_labels=opts.sound_labels)
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print("Offline radio AI unavailable: "+str(exc)[:250],file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
