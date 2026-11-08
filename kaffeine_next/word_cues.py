"""Subtitle word pacing against the source TV audio, never decoding completion.

Only use timestamps emitted by an actual local ASR backend. Translation word
alignment is NOT claimed; translation windows use coarse proportional reading
progress and are labelled as estimates. When timestamps are unavailable the
existing chunk queue remains the correct fallback.
"""
from __future__ import annotations


def _translation_window(text: str, progress: float, max_words: int = 9) -> str:
    tokens = str(text).split()
    if not tokens:
        return ""
    count = max(1, min(len(tokens), round(progress * len(tokens))))
    return " ".join(tokens[max(0, count-max_words):count])


def word_groups(result: dict, *, maximum_words: int = 6, maximum_span: float = 1.75):
    """Return (source-clip-relative start/end, partial caption result).

    Reject malformed or non-monotonic timestamps rather than presenting a
    guessed exact synchronization. Group word timings remain relative to the
    audio extracted from the *pre-playback-buffer* DVB capture.
    """
    words = result.get("words")
    if result.get("source") != "local_asr" or not isinstance(words, list):
        return []
    valid = []
    previous = -1.0
    for item in words[:240]:
        if not isinstance(item, dict):
            return []
        start, end, text = item.get("start"), item.get("end"), item.get("text")
        if (type(start) not in (int,float) or type(end) not in (int,float)
                or not isinstance(text,str) or not text.strip()
                or start < previous - 0.15 or start < 0 or end < start
                or end > 45 or len(text) > 100):
            return []
        previous = start
        valid.append((float(start), float(end), text.strip()))
    if not valid:
        return []
    turns = result.get("speaker_turns") or []
    def speaker_at(start, end):
        midpoint = (start+end)/2
        if not isinstance(turns,list):
            return None
        for turn in turns:
            if (isinstance(turn,dict) and type(turn.get("start")) in (int,float)
                    and type(turn.get("end")) in (int,float)
                    and turn["start"] <= midpoint <= turn["end"]):
                return str(turn.get("id") or "")[:40] or None
        return None

    groups = []
    index = 0
    while index < len(valid):
        first = index
        finish = index
        first_speaker = speaker_at(valid[first][0],valid[first][1])
        while finish + 1 < len(valid) and finish-first+1 < maximum_words and (
                valid[finish+1][1]-valid[first][0] <= maximum_span):
            next_speaker = speaker_at(valid[finish+1][0],valid[finish+1][1])
            if first_speaker and next_speaker and first_speaker != next_speaker:
                break
            finish += 1
            if valid[finish][2].endswith((".", "!", "?", "…")):
                break
        snippet = " ".join(x[2] for x in valid[first:finish+1])
        payload = dict(result)
        payload["original"] = snippet
        payload["words"] = []  # avoid nested accumulation in the UI queue
        payload["word_progress"] = {"start":first,"end":finish,"count":len(valid)}
        payload["caption_alignment"] = "ASR word timestamps"
        if first_speaker:
            # Community-1 assigns SPEAKER_00 ... only within each audio clip.
            # Keep that scope visible: do not imply stable person identity
            # or infer gender/age from voice characteristics.
            number = first_speaker.rsplit("_",1)[-1]
            speaker_number = int(number)+1 if number.isdigit() else number[:12]
            payload["speaker_label"] = f"[Speaker {speaker_number} · clip]"
        # Exact target-language word timing is not supplied by translation
        # engines. Show a short reading window rather than a 6s text dump.
        fraction = (finish + 1) / len(valid)
        payload["translations"] = {
            lang:_translation_window(message,fraction)
            for lang,message in (result.get("translations") or {}).items()
            if isinstance(message,str)}
        if payload["translations"]:
            payload["translation_alignment"] = "estimated from source-word progress"
        groups.append((valid[first][0], max(valid[finish][1],
                                           valid[first][0]+0.25), payload))
        index = finish+1
    return groups


def enqueue_word_cues(queue, result, config, captured_start, captured_end, finished):
    groups = word_groups(result)
    if not groups:
        return None
    # Audio extraction can strip leading TS packets. Never schedule past the
    # captured duration plus a small offset; fallback to the regular cue.
    duration = captured_end - captured_start
    if duration <= 0 or any(start > duration+1.0 for start,_,_ in groups):
        return None
    prior = None
    for start,end,payload in groups:
        prior = queue.add(payload, config,
                          captured_start+start,
                          captured_start+max(start+0.25,end),
                          finished)
    return prior
