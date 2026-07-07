"""Abstract base class for AlignAtt streaming decoders (PyTorch & MLX)."""
import logging
from abc import ABC, abstractmethod

import torch

from whisperlivekit.timed_objects import ASRToken
from whisperlivekit.whisper import DecodingOptions, tokenizer

from .config import AlignAttConfig

DEC_PAD = 50257
LANG_SWITCH_KEEP_SECS = 2.5  # 언어 전환 시 유지할 최근 오디오(초): 감지창 2.0s + 완충 0.5s

# QG 억제가 구두점/공백만 담고 있으면 refresh streak에 산입하지 않기 위한 문자 집합.
# 실단어가 하나도 없는 억제는 버퍼 폐기(단어 유실) 위험을 감수할 만한 garbage가 아니다.
_PUNCT_ONLY_CHARS = frozenset({'.', '?', '!', '。', '！', '？', ',', ';', ':'})

logger = logging.getLogger(__name__)


class AlignAttBase(ABC):
    """
    Abstract base class for AlignAtt streaming decoders.

    Provides shared logic for both PyTorch and MLX implementations:
    - Properties (speaker, global_time_offset)
    - Pure-Python methods (warmup, trim_context, refresh_segment, etc.)
    - Template infer() with abstract hooks for tensor-specific operations
    - Post-decode logic (token splitting, timestamped word building)

    Subclasses must implement ~20 abstract methods for tensor-specific ops.
    """

    # === Properties ===

    @property
    def speaker(self):
        return self.state.speaker

    @speaker.setter
    def speaker(self, value):
        self.state.speaker = value

    @property
    def global_time_offset(self):
        return self.state.global_time_offset

    @global_time_offset.setter
    def global_time_offset(self, value):
        self.state.global_time_offset = value

    # === Constructor helpers ===

    def _base_init(self, cfg: AlignAttConfig, model):
        """Common initialization — call from subclass __init__."""
        self.model = model
        self.cfg = cfg
        self.decode_options = DecodingOptions(
            language=cfg.language,
            without_timestamps=True,
            task=cfg.task,
        )
        self.tokenizer_is_multilingual = cfg.tokenizer_is_multilingual
        self.max_text_len = model.dims.n_text_ctx
        self.num_decoder_layers = len(model.decoder.blocks)
        if cfg.max_context_tokens is None:
            self.max_context_tokens = self.max_text_len
        else:
            self.max_context_tokens = cfg.max_context_tokens

    def _init_state_common(self, cfg: AlignAttConfig):
        """Common state initialization — call from subclass _init_state."""
        self.create_tokenizer(cfg.language if cfg.language != "auto" else None)
        self.state.tokenizer = self.tokenizer
        self.state.detected_language = cfg.language if cfg.language != "auto" else None
        self.state.global_time_offset = 0.0
        self.state.last_attend_frame = -cfg.rewind_threshold
        self.state.speaker = -1

    # === Shared concrete methods ===

    def warmup(self, audio):
        try:
            self.insert_audio(audio)
            self.infer(is_last=True)
            self.refresh_segment(complete=True)
            logger.info("Model warmed up successfully")
        except Exception as e:
            logger.exception(f"Model warmup failed: {e}")

    def create_tokenizer(self, language=None):
        self.tokenizer = tokenizer.get_tokenizer(
            multilingual=self.tokenizer_is_multilingual,
            language=language,
            num_languages=self.model.num_languages,
            task=self.decode_options.task,
        )
        self.state.tokenizer = self.tokenizer

    def trim_context(self):
        logger.info("Trimming context")
        c = len(self.state.context.as_token_ids()) - len(self.state.context.prefix_token_ids)
        logger.info(f"Context text: {self.state.context.as_text()}")
        l = sum(t.shape[1] for t in self.state.tokens) + c
        after = 0 if self.cfg.static_init_prompt is None else len(self.cfg.static_init_prompt)
        while c > self.max_context_tokens or l > self.max_text_len - 20:
            t = self.state.context.trim_words(after=after)
            l -= t
            c -= t
            logger.debug(f"len {l}, c {c}, max_context_tokens {self.max_context_tokens}")
            if t == 0:
                break
        logger.info(f"Context after trim: {self.state.context.text} (len: {l})")

    def refresh_segment(self, complete=False):
        logger.debug("Refreshing segment:")
        # 버퍼를 버리기 전에 절대 시간 앵커를 승계한다. global_time_offset은 버퍼 pos 0의
        # 실제 스트림 시각이므로, 버려지는 오디오 길이만큼 앞으로 밀지 않으면 mid-stream
        # refresh(QualityGate·환각필터·stall) 후 토큰 타임스탬프가 과소평가돼 문장경계 F1이
        # 붕괴한다. long_silence/new_speaker 경로는 직후 global을 명시적으로 재설정하므로
        # 이 승계가 덮어써져 무해하다.
        old_segments_len = self.segments_len()
        self.init_tokens()
        self.state.last_attend_frame = -self.cfg.rewind_threshold
        self.init_context()
        logger.debug(f"Context: {self.state.context}")
        if not complete and len(self.state.segments) > 2:
            self.state.segments = self.state.segments[-2:]
        else:
            logger.debug("removing all segments.")
            self.state.segments = []
        discarded_len = old_segments_len - self.segments_len()
        self.state.global_time_offset += self.state.cumulative_time_offset + discarded_len
        self.state.cumulative_time_offset = 0.0
        self.state.log_segments += 1
        self.state.pending_incomplete_tokens = []
        self.state.pending_retries = 0

    def segments_len(self):
        return sum(s.shape[0] for s in self.state.segments) / 16000

    def _apply_minseglen(self):
        segments_len = self.segments_len()
        if segments_len < self.cfg.audio_min_len:
            logger.debug("waiting for next segment")
            return False
        return True

    def _clean_cache(self):
        self.state.clean_cache()

    def debug_print_tokens(self, tokens):
        for i in range(min(self.cfg.beam_size, tokens.shape[0])):
            logger.debug(self.tokenizer.decode_with_timestamps(tokens[i].tolist()))

    # === Language detection ===

    def _trim_segments_to_recent(self, keep_secs: float) -> float:
        """버퍼 앞쪽의 옛 오디오를 제거하고 최근 ~keep_secs 초만 남긴다.

        insert_audio()의 audio_max_len 트리밍(simul_whisper.py)과 동일 방식 — 언어 전환 후
        다음 infer()가 버퍼 전체가 아니라 **전환 경계 오디오만** 재디코딩하도록 해 이미 방출된
        구(phrase)의 재방출(전환 세금)을 원천 차단한다. 제거한 만큼 cumulative_time_offset을
        누적해 남은 프레임의 절대 타임스탬프 정합성을 유지한다. 제거한 총 초를 반환.
        """
        removed_total = 0.0
        segments_len = self.segments_len()
        while len(self.state.segments) > 1 and segments_len > keep_secs:
            removed_len = self.state.segments[0].shape[0] / 16000
            segments_len -= removed_len
            removed_total += removed_len
            self.state.cumulative_time_offset += removed_len
            self.state.segments = self.state.segments[1:]
        if removed_total > 0:
            logger.debug("[LangSwitch] 전환 전 오디오 %.2fs 절단 (유지 %.2fs)",
                         removed_total, self.segments_len())
        return removed_total

    def _apply_detected_language(self, lang: str, skip_trim: bool = False):
        """토크나이저를 lang으로 교체하고 디코더 상태를 리셋. 일반/eager/주기/짧은침묵 감지 공유.

        진짜 중간 전환(이전 언어가 있고 다를 때)일 때만 버퍼를 경계 구간으로 절단해 재방출을
        막고, process_iter가 방출할 LanguageSwitch 문장 경계를 arm 한다. 최초 감지(이전 None)나
        skip_trim=True(예: refresh 직후 버퍼가 이미 짧음)일 때는 절단·경계 arm을 하지 않는다.
        """
        prev_lang = self.state.detected_language or self.state.lang_before_reset
        self.state.lang_before_reset = None  # consume-once
        is_switch = prev_lang is not None and prev_lang != lang

        if is_switch and not skip_trim:
            self._trim_segments_to_recent(LANG_SWITCH_KEEP_SECS)

        self.create_tokenizer(lang)
        self.init_tokens()
        self.init_context()
        self.state.last_attend_frame = -self.cfg.rewind_threshold
        self.state.detected_language = lang

        if is_switch:
            # 다음 새 언어 토큰 앞에 process_iter가 경계 마커를 삽입하도록 arm.
            self.state.pending_language_switch = self.state.global_time_offset + self.segments_len()

        logger.info("[LangSwitch] 토크나이저 적용: %s (prev=%s, switch=%s, skip_trim=%s)",
                    lang, prev_lang, is_switch, skip_trim)

    def _detect_language_if_needed(self, encoder_feature):
        if (
            self.cfg.language == "auto"
            and self.state.detected_language is None
        ):
            if self.state.first_timestamp:
                seconds_since_start = self.segments_len() - self.state.first_timestamp
            elif self.state.eager_lang_detect:
                # eager(화자전환) 경로만 first_timestamp 없이 오디오 누적량 기준으로 빠르게 감지
                seconds_since_start = self.segments_len()
            else:
                # diar-off silence 경로: first_timestamp 설정 전엔 감지 보류 (Exp-093 안정 동작 — 잦은 _apply_detected_language 리셋으로 인한 반복 폭주 방지)
                logger.debug(
                    "[LangDetectDeferred] 감지 보류: first_timestamp=None, eager_lang_detect=False (segments_len=%.2fs)",
                    self.segments_len(),
                )
                return
            # 화자전환 직후엔 1.5s+확신도≥0.85로 빠른 감지 — 잘못된 언어 고착 방지
            threshold = 1.5 if self.state.eager_lang_detect else 2.0
            if seconds_since_start >= threshold:
                language_tokens, language_probs = self.lang_id(encoder_feature)
                top_lan, p = max(language_probs[0].items(), key=lambda x: x[1])
                logger.info(f"Detected language: {top_lan} with p={p:.4f}")
                # eager 모드: 1.5s~2.0s 사이에서 p>=0.85 일 때만 조기 적용
                # 2.0s 이후엔 확신도 무관 적용(기존 동작 보존)
                if self.state.eager_lang_detect and p < 0.85 and seconds_since_start < 2.0:
                    logger.info("[EagerLang] p=%.4f < 0.85 at %.1fs, waiting for 2.0s gate", p, seconds_since_start)
                else:
                    self._apply_detected_language(top_lan)
                    self.state.eager_lang_detect = False
                    logger.info(f"Tokenizer language: {self.tokenizer.language}")

    def _maybe_periodic_lang_check(self, audio_end_secs: float) -> None:
        """주기적 언어 재감지 — diar-off에서 언어 고착 방지."""
        check_interval = self.cfg.periodic_lang_check_secs
        if check_interval is None:
            return
        if self.state.detected_language is None:
            return
        if audio_end_secs - self.state.last_lang_switch_time < 3.0:
            return
        if audio_end_secs - self.state.last_periodic_lang_check < check_interval:
            return
        self.state.last_periodic_lang_check = audio_end_secs
        new_lang = self.detect_current_language(window_secs=2.0, min_prob=0.90)
        if new_lang and new_lang != self.state.detected_language:
            logger.info("[PeriodicLang] %s→%s (%.1fs 간격 감지)",
                        self.state.detected_language, new_lang, check_interval)
            self._apply_detected_language(new_lang)
            self.state.last_lang_switch_time = audio_end_secs

    @torch.no_grad()
    def detect_current_language(self, window_secs: float = 1.5, min_prob: float = 0.90):
        """최근 window_secs 초 오디오의 언어를 감지해 반환. 확신도 min_prob 미만이면 None.

        no_grad 필수: 이 경로의 self._encode()는 infer()/lang_id()와 달리 no_grad 밖에서
        호출된다(process_iter → _check_short_silence_language / new_speaker eager 감지).
        grad 추적 시 turbo 인코더(807M·32층) forward가 autograd 그래프·활성값을 보존해
        forward가 ~160배 느려지고(0.2s→32s) VRAM 압박으로 실시간 파이프라인이 멈춘다.
        base(74M)는 값이 싸 잠복했으나 turbo에서 stall로 표면화됐다.
        """
        if not self.state.segments:
            return None
        try:
            window_samples = int(window_secs * 16000)
            all_audio = self._concat_segments()
            recent = all_audio[-window_samples:] if len(all_audio) > window_samples else all_audio
            encoder_feature, _ = self._encode(recent)
            _, language_probs = self.lang_id(encoder_feature)
            probs = language_probs[0] if isinstance(language_probs, list) else language_probs
            top_lan, p = max(probs.items(), key=lambda x: x[1])
            logger.info("[ShortSilenceLangCheck] 최근 %.1fs → %s (p=%.2f)", window_secs, top_lan, p)
            return top_lan if p >= min_prob else None
        except Exception as e:
            logger.debug("[ShortSilenceLangCheck] 감지 실패: %s", e)
            return None

    # === Template infer() ===

    def infer(self, is_last=False):
        """Main inference — template method calling abstract hooks for tensor ops."""
        new_segment = True

        if len(self.state.segments) == 0:
            logger.debug("No segments, nothing to do")
            return []
        if not self._apply_minseglen():
            logger.debug(f"applied minseglen {self.cfg.audio_min_len} > {self.segments_len()}.")
            return []

        input_segments = self._concat_segments()
        encoder_feature, content_mel_len = self._encode(input_segments)
        self._evaluate(encoder_feature)

        self._detect_language_if_needed(encoder_feature)
        self.trim_context()
        current_tokens = self._current_tokens()

        fire_detected = self.fire_at_boundary(encoder_feature[:, :content_mel_len, :])

        sum_logprobs = self._init_sum_logprobs()
        completed = False
        token_len_before = current_tokens.shape[1]
        l_absolute_timestamps = []
        accumulated_cross_attns = []

        audio_duration_s = self.segments_len()
        max_tokens = max(50, int(audio_duration_s * 15 * 1.5))
        tokens_produced = 0
        most_attended_frame = None

        while not completed and current_tokens.shape[1] < self.max_text_len:
            tokens_produced += 1
            if tokens_produced > max_tokens:
                logger.warning(
                    f"[Loop Detection] Too many tokens ({tokens_produced}) "
                    f"for {audio_duration_s:.2f}s audio. Breaking."
                )
                current_tokens = current_tokens[:, :token_len_before]
                break

            tokens_for_logits = current_tokens if new_segment else current_tokens[:, -1:]
            logits, cross_attns = self._get_logits_and_cross_attn(
                tokens_for_logits, encoder_feature
            )
            self._evaluate(logits)

            accumulated_cross_attns.append(cross_attns)
            if len(accumulated_cross_attns) > 16:
                accumulated_cross_attns = accumulated_cross_attns[-16:]

            if new_segment and self._check_no_speech(logits):
                break

            logits = logits[:, -1, :]

            if new_segment:
                logits = self._suppress_blank_tokens(logits)
            new_segment = False

            logits = self._apply_token_suppression(logits)
            logits = self._apply_dry_penalty(logits, current_tokens)
            current_tokens, completed = self._update_tokens(
                current_tokens, logits, sum_logprobs
            )
            self._evaluate(current_tokens)

            logger.debug(f"Decoding completed: {completed}")
            self.debug_print_tokens(current_tokens)

            attn = self._process_cross_attention(accumulated_cross_attns, content_mel_len)
            frames_list, most_attended_frame = self._get_attended_frames(attn)

            absolute_timestamps = [
                (frame * 0.02 + self.state.cumulative_time_offset)
                for frame in frames_list
            ]
            l_absolute_timestamps.append(absolute_timestamps[0])
            logger.debug(f"Absolute timestamps: {absolute_timestamps}")

            if completed:
                current_tokens = current_tokens[:, :-1]
                break

            # Rewind check
            if (
                not is_last
                and self.state.last_attend_frame - most_attended_frame
                > self.cfg.rewind_threshold
            ):
                if current_tokens.shape[1] > 1 and self._is_special_token(current_tokens):
                    logger.debug("omit rewinding from special tokens")
                    self.state.last_attend_frame = most_attended_frame
                else:
                    logger.debug(
                        f"[rewind detected] current: {most_attended_frame}, "
                        f"last: {self.state.last_attend_frame}"
                    )
                    self.state.last_attend_frame = -self.cfg.rewind_threshold
                    current_tokens = self._rewind_tokens()
                    break
            else:
                self.state.last_attend_frame = most_attended_frame

            if content_mel_len - most_attended_frame <= (
                4 if is_last else self.cfg.frame_threshold
            ):
                logger.debug(
                    f"attention reaches the end: {most_attended_frame}/{content_mel_len}"
                )
                current_tokens = current_tokens[:, :-1]
                break

        # Post-decode: split tokens and build timestamped words
        tokens_to_split = self._tokens_to_list(current_tokens, token_len_before)
        if self.state.pending_incomplete_tokens:
            logger.debug(
                f"[UTF-8 Fix] Prepending {len(self.state.pending_incomplete_tokens)} "
                f"pending tokens: {self.state.pending_incomplete_tokens}"
            )
            tokens_to_split = self.state.pending_incomplete_tokens + tokens_to_split

        new_hypothesis, split_words, split_tokens = self._split_tokens(
            tokens_to_split, fire_detected, is_last
        )

        num_generated = max(0, current_tokens.shape[1] - token_len_before)
        if not is_last and self._quality_gate(new_hypothesis, sum_logprobs, num_generated):
            self._on_quality_suppressed(new_hypothesis)
            return []
        self.state.quality_suppress_streak = 0

        new_tokens_tensor = self._make_new_tokens_tensor(new_hypothesis)
        self.state.tokens.append(new_tokens_tensor)
        logger.info(f"Output: {self.tokenizer.decode(new_hypothesis)}")

        self._clean_cache()

        if len(l_absolute_timestamps) >= 2 and self.state.first_timestamp is None:
            self.state.first_timestamp = l_absolute_timestamps[0]
            logger.info(
                "[FirstTimestamp] 최초 설정: %.3fs (segments_len=%.2fs)",
                self.state.first_timestamp, self.segments_len(),
            )

        timestamped_words = self._build_timestamped_words(
            split_words, split_tokens, l_absolute_timestamps
        )
        self._handle_pending_tokens(split_words, split_tokens)

        # 절대 스트림 시각 — 버퍼상대(segments_len 단독)는 트림마다 리셋돼 간격 미충족
        self._maybe_periodic_lang_check(self.state.global_time_offset + self.segments_len())
        return timestamped_words

    # === Post-decode shared helpers ===

    def _split_tokens(self, tokens_list, fire_detected, is_last):
        """Split token list into words. Returns (hypothesis, split_words, split_tokens)."""
        if fire_detected or is_last:
            new_hypothesis = tokens_list
            split_words, split_tokens = self.tokenizer.split_to_word_tokens(new_hypothesis)
        else:
            split_words, split_tokens = self.tokenizer.split_to_word_tokens(tokens_list)
            if len(split_words) > 1:
                new_hypothesis = [i for sublist in split_tokens[:-1] for i in sublist]
            else:
                new_hypothesis = []
        return new_hypothesis, split_words, split_tokens

    def _build_timestamped_words(self, split_words, split_tokens, l_absolute_timestamps):
        """Build list of timestamped ASRToken from split words."""
        timestamped_words = []
        timestamp_idx = 0
        replacement_char = "\ufffd"

        for word, word_tokens in zip(split_words, split_tokens):
            if replacement_char in word:
                # Incomplete UTF-8 word (e.g. "미�": 미 complete, next syllable's bytes
                # truncated at the chunk boundary). Do NOT emit the cleaned partial ("미"):
                # _handle_pending_tokens holds the incomplete token for retry and the next
                # chunk re-emits the FULL word ("미디어") exactly once. Emitting the partial
                # here is what produced leading-fragment duplication ("미 미디어").
                logger.debug(f"[UTF-8 Filter] Skipping incomplete (held for retry): {repr(word)}")
                timestamp_idx += len(word_tokens)
                continue

            try:
                current_timestamp = l_absolute_timestamps[timestamp_idx]
            except IndexError:
                logger.warning(
                    f"Timestamp index {timestamp_idx} out of range, using last timestamp"
                )
                current_timestamp = (
                    l_absolute_timestamps[-1] if l_absolute_timestamps else 0.0
                )
            timestamp_idx += len(word_tokens)

            timestamp_entry = ASRToken(
                start=round(current_timestamp, 2),
                end=round(current_timestamp + 0.1, 2),
                text=word,
                speaker=self.state.speaker,
                detected_language=self.state.detected_language,
            ).with_offset(self.state.global_time_offset)
            timestamped_words.append(timestamp_entry)

        return timestamped_words

    def _handle_pending_tokens(self, split_words, split_tokens):
        """Handle incomplete UTF-8 tokens for next chunk."""
        MAX_PENDING_TOKENS = 10
        MAX_PENDING_RETRIES = 2
        replacement_char = "\ufffd"

        if split_words and replacement_char in split_words[-1]:
            self.state.pending_retries += 1
            if self.state.pending_retries > MAX_PENDING_RETRIES:
                logger.warning(
                    f"[UTF-8 Fix] Dropping {len(split_tokens[-1])} incomplete tokens "
                    f"after {MAX_PENDING_RETRIES} retries (won't resolve)"
                )
                self.state.pending_incomplete_tokens = []
                self.state.pending_retries = 0
            elif len(split_tokens[-1]) <= MAX_PENDING_TOKENS:
                self.state.pending_incomplete_tokens = split_tokens[-1]
                logger.debug(
                    f"[UTF-8 Fix] Holding {len(self.state.pending_incomplete_tokens)} "
                    f"incomplete tokens for next chunk (retry {self.state.pending_retries})"
                )
            else:
                logger.warning(
                    f"[UTF-8 Fix] Skipping {len(split_tokens[-1])} tokens "
                    f"(exceeds limit of {MAX_PENDING_TOKENS}, likely hallucination)"
                )
                self.state.pending_incomplete_tokens = []
                self.state.pending_retries = 0
        else:
            self.state.pending_incomplete_tokens = []
            self.state.pending_retries = 0

    # === Repetition penalty ===

    def _apply_dry_penalty(self, logits, current_tokens):
        """DRY penalty v0: penalize tokens that would extend a verbatim repetition.
        See https://github.com/oobabooga/text-generation-webui/pull/5677

        Scans the decoded sequence for positions where the current suffix already
        appeared --> for each such match, the token that followed it in the past is
        penalised exponentially with the match length
        """
        eot = self.tokenizer.eot
        seq = current_tokens[0].tolist()
        if len(seq) < 5:
            return logits

        last = seq[-1]
        if last >= eot:
            return logits

        penalties = {}
        for i in range(len(seq) - 2, -1, -1):
            if seq[i] != last:
                continue
            next_tok = seq[i + 1]
            if next_tok >= eot:
                continue

            length = 1
            while length < 50:
                j, k = i - length, len(seq) - 1 - length
                if j < 0 or k <= i:
                    break
                if seq[j] != seq[k] or seq[j] >= eot:
                    break
                length += 1

            if next_tok not in penalties or length > penalties[next_tok]:
                penalties[next_tok] = length

        if penalties:
            max_len = max(penalties.values())
            if max_len >= 4:
                logger.debug(f"[DRY] penalising {len(penalties)} tokens (longest match: {max_len})")
            for tok, length in penalties.items():
                if length >= 2:
                    logits[:, tok] = logits[:, tok] - 1.0 * 2.0 ** (length - 2)

        return logits

    def _quality_gate(self, hypothesis, sum_logprobs, num_generated):
        """avg-logprob 또는 compression-ratio 기준으로 저품질 세그먼트 억제."""
        lp_thr = self.cfg.logprob_threshold
        cr_thr = self.cfg.compression_ratio_threshold
        if lp_thr is None and cr_thr is None:
            return False
        if not hypothesis:
            return False
        if lp_thr is not None and num_generated > 0:
            avg_lp = self._sum_logprobs_value(sum_logprobs) / num_generated
            if avg_lp < lp_thr:
                # 억제된 텍스트를 함께 로깅 (단계 C 계측: 정상 한국어가 잘못 버려지는 비율 산출용).
                # 디코드는 warning 경로에서만 수행 → 드묾, 성능 영향 미미.
                text = self.tokenizer.decode(hypothesis).strip()
                logger.warning("[QualityGate] avg_logprob %.3f < %.3f — suppressing: %.200s", avg_lp, lp_thr, text)
                return True
        if cr_thr is not None:
            from whisperlivekit.whisper.utils import compression_ratio
            text = self.tokenizer.decode(hypothesis).strip()
            if text:
                cr = compression_ratio(text)
                if cr > cr_thr:
                    logger.warning("[QualityGate] compression_ratio %.2f > %.2f — suppressing: %.200s", cr, cr_thr, text)
                    return True
        return False

    def _is_punct_only(self, hypothesis) -> bool:
        """디코드된 hypothesis가 공백/구두점만인지(실단어 없음) 판정."""
        if not hypothesis:
            return True
        bare = self.tokenizer.decode(hypothesis).replace(" ", "").strip()
        if not bare:
            return True
        return set(bare) <= _PUNCT_ONLY_CHARS

    def _on_quality_suppressed(self, hypothesis=None):
        """품질 게이트 억제 처리 — 연속 N회 억제 시 context refresh.

        억제 자체(clean_cache·억제 동작)는 항상 수행하되, 억제된 hypothesis가
        구두점/공백-only면 refresh streak에 **산입하지 않는다**. refresh_segment는
        버퍼를 폐기해 다음 문장 첫 음절까지 유실시키므로, 실단어가 포함된 garbage가
        연속될 때만 발동해야 한다(Exp-154 QG 안전성 보존).
        """
        self._clean_cache()
        if hypothesis is not None and self._is_punct_only(hypothesis):
            logger.debug("[QualityGate] 구두점/공백-only 억제 — refresh streak 미산입")
            return
        streak = getattr(self.state, "quality_suppress_streak", 0) + 1
        self.state.quality_suppress_streak = streak
        reset_after = self.cfg.quality_gate_reset_after
        if reset_after and streak >= reset_after:
            logger.warning("[QualityGate] %d consecutive suppressions — refresh_segment", streak)
            self.refresh_segment(complete=True)
            self.state.quality_suppress_streak = 0

    # === Abstract methods — subclass must implement ===

    @abstractmethod
    def _init_state(self, cfg: AlignAttConfig):
        """Initialize per-session decoder state."""
        ...

    @abstractmethod
    def init_tokens(self):
        """Initialize token sequence with framework-specific tensors."""
        ...

    @abstractmethod
    def init_context(self):
        """Initialize context buffer with framework-specific TokenBuffer."""
        ...

    @abstractmethod
    def insert_audio(self, segment=None):
        """Insert audio segment into buffer."""
        ...

    @abstractmethod
    def _current_tokens(self):
        """Build current token tensor for decoding."""
        ...

    @abstractmethod
    def fire_at_boundary(self, feature):
        """Check if we should fire at word boundary."""
        ...

    @abstractmethod
    def lang_id(self, encoder_features):
        """Language detection from encoder features. Returns (tokens, probs)."""
        ...

    @abstractmethod
    def _concat_segments(self):
        """Concatenate audio segments into single array/tensor."""
        ...

    @abstractmethod
    def _encode(self, input_segments):
        """Encode audio. Returns (encoder_feature, content_mel_len)."""
        ...

    @abstractmethod
    def _init_sum_logprobs(self):
        """Create zero sum_logprobs tensor for beam search."""
        ...

    @abstractmethod
    def _sum_logprobs_value(self, sum_logprobs):
        """Extract scalar float from sum_logprobs for avg-logprob quality gate."""
        ...

    @abstractmethod
    def _get_logits_and_cross_attn(self, tokens, encoder_feature):
        """Get logits and cross-attention from decoder. Returns (logits, cross_attns)."""
        ...

    @abstractmethod
    def _check_no_speech(self, logits):
        """Check no_speech probability at start of segment. Returns True to break."""
        ...

    @abstractmethod
    def _suppress_blank_tokens(self, logits):
        """Suppress blank/EOT tokens at segment start. Returns modified logits."""
        ...

    @abstractmethod
    def _apply_token_suppression(self, logits):
        """Apply general token suppression. Returns modified logits."""
        ...

    @abstractmethod
    def _update_tokens(self, current_tokens, logits, sum_logprobs):
        """Update tokens via decoder. Returns (current_tokens, completed)."""
        ...

    @abstractmethod
    def _process_cross_attention(self, accumulated_cross_attns, content_mel_len):
        """Process cross-attention for alignment. Returns attention tensor."""
        ...

    @abstractmethod
    def _get_attended_frames(self, attn):
        """Get most attended frames. Returns (frames_as_python_list, first_frame_int)."""
        ...

    @abstractmethod
    def _is_special_token(self, current_tokens):
        """Check if second-to-last token is a special token (>= DEC_PAD)."""
        ...

    @abstractmethod
    def _rewind_tokens(self):
        """Concatenate state tokens for rewind. Returns token tensor."""
        ...

    @abstractmethod
    def _tokens_to_list(self, current_tokens, start_col):
        """Extract tokens as Python list from start_col onwards."""
        ...

    @abstractmethod
    def _make_new_tokens_tensor(self, hypothesis):
        """Create tensor from hypothesis token list, repeated for beam search."""
        ...

    @abstractmethod
    def _evaluate(self, tensor):
        """Evaluate lazy tensor (mx.eval for MLX, no-op for PyTorch)."""
        ...
