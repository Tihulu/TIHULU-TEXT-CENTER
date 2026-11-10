"""Regression checks for stable live DAB caption timing and independent lyrics.

No real SDR, DAC, radio internet access or Qwen weights. CI verifies
invariants; live on-air audio sync still requires hardware verification.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
WORKER=(ROOT/"tv_center/radio_ai.py").read_text(encoding="utf-8")
TV=(ROOT/"kaffeine_next/captions_overlay.py").read_text(encoding="utf-8")


def section(text,first,last):
    a=text.index(first)
    return text[a:text.index(last,a)]


class EstCaptionContinuityTests(unittest.TestCase):
    def test_tv_word_timing_bypass_and_two_hop_speech(self):
        self.assertIn('source_word_timed = (',TV)
        self.assertIn('self.sentence_joiner = LiveSentenceJoiner(max_words=90,max_chunks=2)',TV)
        self.assertIn('source_word_timed=bool(detection.get("asr_words"))',WORKER)
        self.assertIn('and not source_word_timed',WORKER)
        self.assertIn('prefer_readable=True',WORKER)
        self.assertIn('max_chunks=min(sentence_hops,2)',WORKER)
        self.assertIn('live.add_argument("--sentence-hops",type=int,default=2',WORKER)

    def test_no_second_est_countdown_after_fixed_user_offset(self):
        panel=section(UI,"void displayDueRadioCues(qint64 now) {","void pollCaption() {")
        self.assertNotIn("EST. caption in ~%1 ms",panel)
        self.assertNotIn("next.dueMs-next.queuedMs",panel)
        self.assertIn("Whisper ready · fixed audio cache",panel)
        self.assertIn("cueQueue_.size()==1 && now-lastCaptionVisibleMs_<350",panel)
        self.assertIn("cueQueue_.first().dueMs<=now",panel)
        source=section(UI,"void pollCaption() {","void stopCaptioning() {")
        self.assertIn("wordEpoch+activePlaybackCacheMs_+radioOffsetMs_->value()",source)
        self.assertIn("requestedDue-radioOffsetMs_->value()",source)
        self.assertIn("const qint64 due=qMax(now,requestedDue);",source)
        self.assertNotIn("due+radioOffsetMs_->value()",source)

    def test_offset_change_moves_pending_cues_only_once(self):
        self.assertIn("const int adjustment=newOffset-lastCaptionOffsetMs_;",UI)
        self.assertIn("lastCaptionOffsetMs_=newOffset;",UI)
        self.assertIn("for(auto &cue:cueQueue_) cue.dueMs+=adjustment;",UI)
        self.assertIn('saved.setValue(QLatin1String("captionOffsetMs")',UI)
        self.assertIn("karaokeDue=qMax(now,due-",UI)
        self.assertIn("radioOffsetMs_->value()+lyricsOffset_->value()",UI)

    def test_live_asr_does_not_wait_for_karaoke(self):
        caption=section(UI,"void displayDueRadioCues(qint64 now) {","void pollCaption() {")
        self.assertIn("showRadioCanvasCaption(cue.text)",caption)
        self.assertNotIn("lastVerifiedLyricMs_",caption)
        poll=section(UI,"void pollCaption() {","void stopCaptioning() {")
        self.assertIn("if(newChunk)",poll)
        self.assertIn("radioCanvasCaption_->setText(updated);",poll)
        self.assertIn("radioCanvasCaption_->setVisible(true);",poll)
        assert 'original=lyric_match["text"]' not in WORKER
        lyrics=section(UI,"void updateLyrics() {","MediaWidget *player_")
        self.assertNotIn("radioCanvasCaption_->setVisible(false)",lyrics)

    def test_lyrics_refresh_result_not_blocked_by_150_translations(self):
        search=section(WORKER,"def lyrics_lookup_to_file(","def local_lyrics_to_file(")
        self.assertIn("lookup_synced_lyrics(",search)
        self.assertIn('"status":"completed"',search)
        self.assertNotIn("from .captions import translate",search)
        self.assertIn("for cue in cues[:150]",search)
        self.assertIn("write_runtime_json(location,payload)",search)
        ui=section(UI,"void pollLyricsRefreshResult() {","void fetchLyrics(bool automatic=false)")
        self.assertIn("publishLiveRadioLyricsCatalog(value)",ui)
        self.assertIn("Lyrics Refresh completed",ui)

    def test_caption_worker_recovers_without_restarting_radio(self):
        recovery=section(UI,"void scheduleCaptionRecovery() {","void startCaptioning() {")
        self.assertIn("checkCaptionRecovery()",recovery)
        self.assertIn("captionRecoveryFailures_",recovery)
        self.assertIn("quickAi_->isChecked()",recovery)
        self.assertIn("playingKey_.isEmpty()",recovery)
        self.assertNotIn("player_->play(",recovery)
        self.assertNotIn("stopReceiver(",recovery)
        finished=section(UI,"connect(&captionProcess_,QOverload<int,QProcess::ExitStatus>::of(",
                         "connect(lyrics_, &QPushButton::clicked")
        self.assertIn("scheduleCaptionRecovery();",finished)
        self.assertNotIn("quickAi_->setChecked(false)",finished)

    def test_radio_auto_buffer_never_mutates_sound_or_worker(self):
        # TV transcription is stable precisely because Whisper workload
        # does not select/reopen audio playback buffer on its own.
        auto=section(UI,
                     'connect(autoSync_,&QCheckBox::toggled',
                     'auto *captionActions=new QHBoxLayout()')
        self.assertIn('radioAutoBufferEnabled',auto)
        self.assertNotIn('quickBuffer_->setChecked(true)',auto)
        self.assertNotIn('setBufferDisplayMs(',auto)
        self.assertNotIn('applyRadioBuffer(',auto)
        toggle=section(UI,
                       'connect(quickAi_,&QCheckBox::toggled',
                       'connect(caption_, &QPushButton::clicked')
        self.assertNotIn('autoSync_->setChecked(true)',toggle)
        self.assertIn('startCaptioning();',toggle)
        self.assertLess(toggle.index('startCaptioning();'),
                        toggle.index('lyricsOnlineConsentAsked'))
        self.assertIn('captionSource_->setCurrentIndex(asr);',toggle)
        estimate=section(UI,
                         'if(autoSync_->isChecked() && lagSamples_.size()>=4',
                         '// Use the first real GPU word')
        self.assertIn('Suggested audio cache',estimate)
        self.assertNotIn('setBufferDisplayMs(recommended)',estimate)
        self.assertNotIn('applyRadioBuffer();',estimate)
        self.assertNotIn('radioBufferDesiredMs',estimate)

    def test_worker_start_is_not_false_successful_asr_chunk(self):
        start=section(UI,'void startCaptioning() {','void clearKaraokeLine() {')
        self.assertNotIn('lastCaptionUpdateMs_=QDateTime::currentMSecsSinceEpoch()',start)
        recovery=section(UI,'void scheduleCaptionRecovery() {','void startCaptioning() {')
        self.assertIn('captionRecoveryLastAttemptMs_',recovery)
        self.assertIn('lastCaptionUpdateMs_>captionRecoveryLastAttemptMs_',recovery)
        self.assertIn('captionRecoveryFailures_',recovery)

    def test_dls_debounce_does_not_throw_away_first_good_track(self):
        pending=section(UI,"void commitPendingDlsSong(","void stopLyrics() {")
        self.assertIn("QTimer::singleShot(remaining,this",pending)
        self.assertIn("now-pendingSongSinceMs_<8000",pending)
        self.assertIn("pendingSongObservations_<2",pending)
        self.assertIn("lastAcceptedSongHint_=acceptedSong",pending)


if __name__=="__main__":
    unittest.main()
