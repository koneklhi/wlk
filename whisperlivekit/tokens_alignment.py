import logging
import re
from time import time
from typing import Any, List, Optional, Tuple, Union

from whisperlivekit.sentence_boundary import is_genuine_sentence_end, last_word, should_split_after_silence
from whisperlivekit.simul_whisper.align_att_base import LANG_SWITCH_KEEP_SECS
from whisperlivekit.timed_objects import (
    ASRToken,
    LanguageSwitch,
    PuncSegment,
    Segment,
    Silence,
    SilentSegment,
    SpeakerSegment,
    TimedText,
)

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_SECONDS: float = float("inf")  # 로컬 패치: 세션 전체 윈도우 유지
# (upstream 기본값 300.0=5분 — 서버 메모리/CPU/대역폭이 세션 길이에 비례해 증가하는 트레이드오프 감수)

# CASE1 문장 꼬리 분리 교정 상수.
# AlignAtt가 유보한 마지막 단어(꼬리)가 재디코딩 후 Silence 마커 뒤로 들어가
# 다음 줄 첫머리로 밀리는 문제를, 꼬리의 타임스탬프를 근거로 침묵 앞으로 재귀속해 교정한다.
TAIL_REATTACH_EPS: float = 0.05   # 프레임 양자화(0.02s) 지터 방어용 여유
FINALIZE_GRACE_SECS: float = 2.0  # 침묵 직후 이만큼은 직전 세그먼트 확정 유예(유보 꼬리 도착 대기)
# AlignAtt 유보는 이론상 frame_threshold(기본 0.5s) 이내 꼬리만 만든다 — 재귀속을
# 이 범위 밖까지 허용하면(타임스탬프가 재디코딩·버퍼트림·언어전환 등으로 불안정해진
# 구간에서) 서로 무관한 발화가 잘못 병합될 위험이 있다. 정상 유보 폭의 3배 여유를 둔
# 구조적 상한이며 특정 데이터가 아니라 메커니즘 자체의 한계에 근거한다.
TAIL_REATTACH_MAX_LOOKBACK_SECS: float = 1.5

# [폐기됨 — Exp-166 FIX 1] 과거 PUNCT_SPLIT_GAP_SECS(온점 뒤 토큰 갭 기반 분할 임계값,
# 0.3→0.4로 조정했던 시도)는 근본 원인을 잘못 짚은 수정이었다. 서버로그의 "Silence of
# = 0.32s"는 backend.py의 VAD 침묵 길이일 뿐 _punct_split_justified()가 보는 토큰
# 타임스탬프 갭(nxt.start - tokens[idx].end)과는 다른 양이었다 — 이 둘을 같다고
# 가정한 게 문턱 조정이 실패한 원인이다. 소거법: 서버 응답은 매 틱 전체 재계산되는
# 풀스냅샷이라 영속 상태가 없으므로, 최종 스냅샷에 분리가 남는다는 것 자체가 최종
# all_tokens 기준으로 (a)발화 끝도 아니고 (b)Silence 토큰도 없는데 True가 나왔다는
# 뜻이었고, 그건 곧 실제 토큰 갭이 이미 문턱(0.3/0.4 무엇이든) 이상이었다는 뜻이다 —
# 즉 갭 기반 (c)분기는 갭 값을 얼마로 조정해도 원리적으로 구멍이 남는다. 그래서 갭
# 기반 분기 자체를 제거했다(아래 _punct_split_justified 참조) — 온점 분할은 이제
# (a) 발화 끝 또는 (b) 실제 Silence 토큰에서만 정당화된다. 비-diar 경로는 애초에
# 이 갭 분기가 없었으므로 이 제거로 diar/비-diar 판정 기준이 대칭화된다.

# 언어전환 경계 철회(retraction) 상수.
# TAIL_REATTACH_EPS는 재귀속 비교(양의 방향 여유, t.start + EPS < silence.start)용으로
# 용도가 달라 재사용하지 않고 별도 상수로 둔다. RETRACT_EPS/하한(LANG_SWITCH_KEEP_SECS 기반)은
# Stage 0 실측(별도 진행 중, 아직 완료 안 됨)으로 추후 보정될 잠정값이다.
RETRACT_EPS: float = 0.05

# 반대-스크립트 판정 정규식. backend.py의 _is_script_mismatch_filler(P2 게이트)가 쓰는
# 것과 동일한 패턴을 재사용한다(신규 언어별 하드코딩 금지, §3.8). 단 그쪽은 반복형 필러
# 텍스트 전체(TTR·최소단어수 게이트 포함)를 판정하는 반면, 여기는 철회 대상 토큰 하나의
# 스크립트만 보므로 TTR/word-count 게이트 없이 has_hangul/has_latin만 재사용한다.
_HANGUL_PATTERN = re.compile(r'[가-힣]')
_LATIN_PATTERN = re.compile(r'[A-Za-z]')

# 문법-조건부 침묵 경계(silence-grammar-gate) 상수.
# SILENCE_HARD_SECS: 이 이상 침묵이면 문법 판정 없이 항상 분할(안전망).
# 불변식: <= 2.0 — 이를 넘기면 backend.py 쪽 long-silence 하드리셋 구간과 겹쳐 디코더 문맥
# 연속성이 끊기므로, 병합으로 이어붙인 텍스트의 자연스러움을 더는 보증할 수 없다.
SILENCE_HARD_SECS: float = 1.2
assert SILENCE_HARD_SECS <= 2.0, "SILENCE_HARD_SECS는 backend.py long-silence 하드리셋 상한(2.0s)을 넘을 수 없다"

# PENDING_RESOLVE_CAP: 게이트가 다음 발화(B) 도착을 기다리는 최대 시간(초, silence.end 기준).
# 이 시간을 넘기면 문법 판정 없이 분할 확정(safety valve) — FINALIZE_GRACE_SECS(침묵 start 기준)와는
# 앵커·용도가 달라 별도 상수로 둔다(§확정 유예 이원화, 게이트 대상 침묵은 이 캡만 적용받는다).
PENDING_RESOLVE_CAP: float = 2.0


def _is_opposite_script(text: str, prev_lang: Optional[str]) -> bool:
    """prev_lang의 정상 스크립트와 반대 스크립트로만 구성된 텍스트인지 판정.

    혼합 스크립트(한글+라틴 공존)나 스크립트 무관 텍스트(숫자·기호만)는 False(보존).
    """
    if prev_lang not in ("ko", "en"):
        return False
    has_hangul = bool(_HANGUL_PATTERN.search(text))
    has_latin = bool(_LATIN_PATTERN.search(text))
    if prev_lang == "ko":
        return has_latin and not has_hangul
    return has_hangul and not has_latin


class TokensAlignment:

    def __init__(self, state: Any, args: Any, sep: Optional[str]) -> None:
        self.state = state
        self.diarization = args.diarization
        # 문법-조건부 침묵 경계 게이트. 기본 ON — --no-silence-grammar-gate(parse_args.py)로 롤백.
        self.gate_enabled: bool = bool(getattr(args, "silence_grammar_gate", True))
        # 침묵 안전망 문턱(초) — CLI --silence-hard-secs 오버라이드, 미지정 시 모듈 기본값 사용.
        self.silence_hard_secs: float = float(getattr(args, "silence_hard_secs", None) or SILENCE_HARD_SECS)
        assert self.silence_hard_secs <= 2.0, (
            "silence_hard_secs는 backend.py long-silence 하드리셋 상한(2.0s)을 넘을 수 없다"
        )
        # diar 경로(무상태 재계산) 플래핑 방지 메모 — 한 번 캡 만료로 분할 확정된 침묵은
        # 이후 재계산에서도 병합으로 되돌리지 않는다. 키 = round(silence.start, 2).
        self.resolved_split_silences: set = set()
        # 비-diar 경로(상태 보유) 전용 — 게이트 판정을 보류 중인 침묵(누적 span 포함).
        self._nondiar_pending_silence: Optional[Silence] = None

        self.all_tokens: List[ASRToken] = []
        self.all_diarization_segments: List[SpeakerSegment] = []
        self.all_translation_segments: List[Any] = []

        self.new_tokens: List[ASRToken] = []
        self.new_diarization: List[SpeakerSegment] = []
        self.new_translation: List[Any] = []
        self.new_translation_buffer: Union[TimedText, str] = TimedText()
        self.new_tokens_buffer: List[Any] = []
        self.sep: str = sep if sep is not None else ' '
        self.beg_loop: Optional[float] = None

        self.validated_segments: List[Segment] = []
        self.current_line_tokens: List[ASRToken] = []
        self.diarization_buffer: List[ASRToken] = []

        self.last_punctuation = None
        self.last_uncompleted_punc_segment: PuncSegment = None
        self.unvalidated_tokens: PuncSegment = []

        self._retention_seconds: float = _DEFAULT_RETENTION_SECONDS

    def update(self) -> None:
        """Drain state buffers into the running alignment context."""
        self.new_tokens, self.state.new_tokens = self.state.new_tokens, []
        self.new_diarization, self.state.new_diarization = self.state.new_diarization, []
        self.new_translation, self.state.new_translation = self.state.new_translation, []
        self.new_tokens_buffer, self.state.new_tokens_buffer = self.state.new_tokens_buffer, []

        self._insert_with_reattachment(self.new_tokens)
        self.all_diarization_segments.extend(self.new_diarization)
        self.all_translation_segments.extend(self.new_translation)
        self.new_translation_buffer = self.state.new_translation_buffer

    def _insert_with_reattachment(self, tokens: List[ASRToken]) -> None:
        """새 토큰을 all_tokens에 삽입하되, AlignAtt가 유보한 꼬리 토큰은 Silence 앞으로 재귀속.

        정상 토큰은 끝에 append(기존 동작과 동일). 텍스트 토큰의 start가 바로 앞
        Silence 마커의 start보다 앞서면(유보됐던 꼬리) 그 Silence 앞으로 이동한다.
        - 기준은 Silence.end가 아니라 **start**: 긴 침묵 후 앵커 재설정 시 직후 토큰
          start가 침묵 end보다 앞설 수 있어 end 기준은 오귀속을 낳는다.
        - is_boundary(LanguageSwitch)나 일반 토큰을 만나면 스캔 중단 — 경계 넘김 금지.
        - 연속 Silence는 각 침묵의 start와 개별 비교하며 통과한다.
        - TAIL_REATTACH_MAX_LOOKBACK_SECS 상한: 정상 유보는 항상 짧다. 타임스탬프가
          재디코딩·언어전환 등으로 불안정해진 구간에서 무관한 발화가 멀리 있는 침묵
          앞으로 잘못 병합되는 것을 막는다.
        """
        for t in tokens:
            if t.is_silence() or t.is_boundary():
                if isinstance(t, LanguageSwitch) and t.retract_from is not None:
                    self._retract_stale_language_tokens(t.retract_from, t.prev_language, t.retract_floor)
                self.all_tokens.append(t)
                continue
            i = len(self.all_tokens)
            while (i > 0 and self.all_tokens[i - 1].is_silence()
                   and t.start + TAIL_REATTACH_EPS < self.all_tokens[i - 1].start
                   and self.all_tokens[i - 1].start - t.start <= TAIL_REATTACH_MAX_LOOKBACK_SECS):
                i -= 1
            self.all_tokens.insert(i, t)

    def _retract_stale_language_tokens(self, boundary_t: float, prev_lang: Optional[str], redecode_floor: Optional[float] = None) -> None:
        """언어전환 경계에서 prev_lang으로 커밋된 잔존 토큰을 all_tokens 꼬리에서 철회.

        LanguageSwitch 마커가 실제로 방출될 때(=새 언어 토큰이 도착했을 때)만 호출된다 —
        재디코딩이 무산되면 마커 자체가 안 나오므로 아무것도 철회되지 않는다(안전한 실패 모드).

        구역 1 — token.start >= boundary_t - RETRACT_EPS: 텍스트 토큰이고
          detected_language == prev_lang이면 무조건 철회.
        구역 2 — [하한, boundary_t - RETRACT_EPS): 같은 조건 + 반대-스크립트(_is_opposite_script)
          일 때만 철회. 혼합 스크립트는 보수적으로 보존.
        하한 = redecode_floor(재디코딩 창 시작) 또는 미지정 시 boundary_t - LANG_SWITCH_KEEP_SECS - 1.0.
        역방향 스캔 중 Silence나 boundary 토큰을 만나면 즉시 중단(경계를 넘어 철회하지 않음).
        prev_lang과 반대 방향 언어로 스탬프된 토큰은 절대 건드리지 않는다.
        """
        if prev_lang is None:
            return
        # 철회 하한 = 재디코딩 창 시작. redecode_floor가 주어지면 그것을 쓴다 — 트림이
        # 잘라낸(재디코딩 불가) 서두 토큰을 철회하지 않기 위함(① 서두유실 방지, Exp-173).
        # 미지정(구 마커 하위호환) 시 기존 KEEP_SECS 기반 하한으로 폴백.
        if redecode_floor is not None:
            lower_bound = redecode_floor
        else:
            lower_bound = boundary_t - LANG_SWITCH_KEEP_SECS - 1.0
        j = len(self.all_tokens) - 1
        scanned = 0
        removed = 0
        stopped_by = "start_of_buffer"
        while j >= 0:
            token = self.all_tokens[j]
            if token.is_silence() or token.is_boundary():
                stopped_by = "silence" if token.is_silence() else "boundary"
                break
            if token.start < lower_bound:
                stopped_by = "lower_bound"
                break
            scanned += 1
            if token.detected_language == prev_lang:
                if token.start >= boundary_t - RETRACT_EPS:
                    remove = True
                else:
                    remove = _is_opposite_script(token.text, prev_lang)
                if remove:
                    logger.info(
                        "[Retract] 철회: %r start=%.2f prev_lang=%s",
                        token.text, token.start, prev_lang,
                    )
                    self.all_tokens.pop(j)
                    removed += 1
            j -= 1
        # 진단용 요약 — [Retract] 0건이 "대상 없음"인지 "Silence/하한에 조기 차단"인지
        # 구분하기 위함(Exp-171 스크리닝에서 0건 관측 후 추가). scanned=0인데
        # stopped_by="silence"면 마커 직전에 바로 침묵이 있어 애초에 스캔 자체가
        # 거의 일어나지 못한 것 — 이 비율이 높으면 Silence 정지 규칙이 과도하게
        # 보수적인지(예: 아주 짧은 Silence는 통과) 재검토가 필요하다는 신호.
        logger.info(
            "[RetractScan] boundary_t=%.2f prev_lang=%s scanned=%d removed=%d stopped_by=%s",
            boundary_t, prev_lang, scanned, removed, stopped_by,
        )

    def _prune(self) -> None:
        """Drop tokens/segments older than ``_retention_seconds`` from the latest token."""
        if not self.all_tokens:
            return

        latest = self.all_tokens[-1].end
        cutoff = latest - self._retention_seconds
        if cutoff <= 0:
            return

        def _find_cutoff(items: list) -> int:
            """Return the index of the first item whose end >= cutoff."""
            for i, item in enumerate(items):
                if item.end >= cutoff:
                    return i
            return len(items)

        idx = _find_cutoff(self.all_tokens)
        if idx:
            self.all_tokens = self.all_tokens[idx:]

        idx = _find_cutoff(self.all_diarization_segments)
        if idx:
            self.all_diarization_segments = self.all_diarization_segments[idx:]

        idx = _find_cutoff(self.all_translation_segments)
        if idx:
            self.all_translation_segments = self.all_translation_segments[idx:]

        idx = _find_cutoff(self.validated_segments)
        if idx:
            self.validated_segments = self.validated_segments[idx:]

        if self.resolved_split_silences:
            self.resolved_split_silences = {k for k in self.resolved_split_silences if k >= cutoff}

    def add_translation(self, segment: Segment) -> None:
        """Append translated text segments that overlap with a segment."""
        if segment.translation is None:
            segment.translation = ''
        for ts in self.all_translation_segments:
            if ts.is_within(segment):
                if ts.text:
                    segment.translation += ts.text + self.sep
            elif segment.translation:
                break


    def _punct_split_justified(self, idx: int) -> bool:
        """온점 토큰(all_tokens[idx])에서 세그먼트를 끊을 음향적 근거가 있는지 판정.

        온점 뒤에 (a) 발화 끝 또는 (b) 실제 Silence 토큰이 있을 때만 True. 그 외(다음
        토큰이 일반 텍스트 토큰인 모든 경우, 갭이 크든 작든)는 항상 False로 분할하지
        않는다 — 갭 기반 분기(과거 (c))는 Exp-166 FIX 1에서 제거했다(위 주석 참조).
        스트리밍 디코더가 매기는 토큰 타임스탬프 갭은 실제 음향 침묵과 별개로 벌어질
        수 있어(버퍼 트림·AlignAtt 유보 등) 신뢰 가능한 분할 근거가 못 된다 — 오직
        VAD가 실제로 검출한 침묵(Silence 토큰)과 발화 종료만 근거로 인정한다.
        """
        tokens = self.all_tokens
        if idx + 1 >= len(tokens):
            return True  # 발화 끝
        nxt = tokens[idx + 1]
        if nxt.is_silence():
            return True
        return False

    def _punct_split_here(self, idx: int, start_idx: int) -> bool:
        """온점 토큰에서 분할할지: (a)발화끝/(b)Silence[기존] 또는 (c)형태소 종결[신규].

        (c)는 온점(.。) 전용 — ?/! 는 소수점·약어 위험이 없어 (a)/(b) 경로만 유지(현행 불변).
        판별은 닫히는 세그먼트 누적 텍스트(온점 앞 어절의 스크립트·종결어미·약어)로 한다.
        """
        if self._punct_split_justified(idx):
            return True
        closing = "".join(t.text for t in self.all_tokens[start_idx: idx + 1])
        stripped = closing.rstrip()
        if not stripped or stripped[-1] not in (".", "。"):
            return False
        nxt = self.all_tokens[idx + 1] if idx + 1 < len(self.all_tokens) else None
        next_text = nxt.text if (nxt is not None and not nxt.is_silence()
                                 and not nxt.is_boundary()) else None
        return is_genuine_sentence_end(closing, next_text)

    def compute_punctuations_segments(self, tokens: Optional[List[ASRToken]] = None) -> List[PuncSegment]:
        """Group tokens into segments split by punctuation and explicit silence."""
        segments = []
        segment_start_idx = 0
        for i, token in enumerate(self.all_tokens):
            if token.is_silence():
                previous_segment = PuncSegment.from_tokens(
                        tokens=self.all_tokens[segment_start_idx: i],
                    )
                if previous_segment:
                    segments.append(previous_segment)
                segment = PuncSegment.from_tokens(
                    tokens=[token],
                    is_silence=True
                )
                segments.append(segment)
                segment_start_idx = i+1
            elif token.is_boundary():
                # 언어 전환 경계: 이전 세그먼트를 닫되 침묵 세그먼트는 만들지 않는다.
                previous_segment = PuncSegment.from_tokens(
                    tokens=self.all_tokens[segment_start_idx: i],
                )
                if previous_segment:
                    previous_segment.hard_boundary = True
                    segments.append(previous_segment)
                elif segments and segments[-1].is_silence():
                    # [SIL, LS] 순서로 빈 스팬(직전 침묵 바로 뒤 경계)일 때 hard_boundary가
                    # 소실되지 않도록 직전 침묵 PuncSegment 자체에 스탬프한다 — 이 침묵이
                    # silence-grammar-gate 3중 조건 (b)에서 항상 걸려 병합되지 않게 하기 위함.
                    segments[-1].hard_boundary = True
                segment_start_idx = i+1
            else:
                if token.has_punctuation() and self._punct_split_here(i, segment_start_idx):
                    segment = PuncSegment.from_tokens(
                        tokens=self.all_tokens[segment_start_idx: i+1],
                    )
                    segment.punct_boundary = True
                    segments.append(segment)
                    segment_start_idx = i+1

        final_segment = PuncSegment.from_tokens(
            tokens=self.all_tokens[segment_start_idx:],
        )
        if final_segment:
            segments.append(final_segment)
        return segments

    @staticmethod
    def _pending_key(silence_segment: TimedText) -> Any:
        """캡 만료 플래핑 방지 메모의 키. round(start, 2) — 프레임 지터에 안정적."""
        return round(silence_segment.start, 2) if silence_segment.start is not None else id(silence_segment)

    def _log_silence_gate(
        self, silence_start, silence_end, d_eff, last_w, next_w, speakers, langs, decision, path,
    ) -> None:
        """[SilenceGate] 태그 로그 — Stage 0 오탐 감사용. 억제되든 안 되든 모든 게이트 판정에 남긴다."""
        logger.info(
            "[SilenceGate] start=%.2f end=%.2f d_eff=%s last_word=%r next_word=%r "
            "speakers=%s langs=%s decision=%s path=%s",
            silence_start if silence_start is not None else -1.0,
            silence_end if silence_end is not None else -1.0,
            f"{d_eff:.2f}" if d_eff is not None else "?",
            last_w, next_w, speakers, langs, decision, path,
        )

    def _gate_decide(
        self,
        closing: TimedText,
        silence_seg: TimedText,
        next_seg: Optional[TimedText],
        audio_time: Optional[float],
        flush: bool,
        diar_mode: bool,
    ) -> Tuple[str, str]:
        """짧은 침묵 경계를 병합할지 분할할지 판정. 반환: (decision, resolution_path).

        decision ∈ {"merge", "split", "pending"}.
        path ∈ {"merge", "split_grammar", "split_hard", "split_cap", "split_memo", "pending"}.
        """
        d_eff = None
        if silence_seg.start is not None and silence_seg.end is not None:
            d_eff = silence_seg.end - silence_seg.start

        if d_eff is not None and d_eff >= self.silence_hard_secs:
            return "split", "split_hard"

        key = self._pending_key(silence_seg)
        if key in self.resolved_split_silences:
            return "split", "split_memo"

        b_unresolved = next_seg is None or (diar_mode and getattr(next_seg, "speaker", -1) == -1)
        if b_unresolved:
            cap_expired = (
                audio_time is not None and silence_seg.end is not None
                and (audio_time - silence_seg.end) >= PENDING_RESOLVE_CAP
            )
            if flush or cap_expired:
                self.resolved_split_silences.add(key)
                return "split", "split_cap"
            return "pending", "pending"

        # B 확정 — 병합 실행 필수 3중 조건(화자/hard_boundary/언어)을 문법 판정보다 먼저 본다.
        if silence_seg.hard_boundary or getattr(closing, "hard_boundary", False):
            return "split", "split_grammar"
        if diar_mode and next_seg.speaker != closing.speaker:
            return "split", "split_grammar"
        if closing.detected_language != next_seg.detected_language:
            return "split", "split_grammar"

        verdict = should_split_after_silence(closing.text, next_seg.text)
        if verdict is None:
            verdict = True  # B가 이미 확정됐는데 None이면 방어적으로 분할(도달하지 않아야 정상)
        return ("split", "split_grammar") if verdict else ("merge", "merge")

    def _apply_silence_grammar_gate(
        self,
        punctuation_segments: List[PuncSegment],
        audio_time: Optional[float],
        flush: bool,
    ) -> List[PuncSegment]:
        """구두점 없이 닫히려는 짧은 침묵 경계에 문법 게이트를 적용해 과분할을 억제한다.

        각 침묵 후보에 대해 merge(리스트에서 제거 — 이후 병합루프가 같은 화자 텍스트를 자연
        병합)/split(그대로 두어 기존 로직이 분할)/pending(그대로 두되 gate_pending 태그로 하류
        확정을 보류)을 결정한다. all_tokens/Silence 토큰 자체는 건드리지 않는다 — 이 리스트는
        매 틱 compute_punctuations_segments()가 새로 만드는 조립 계층 산출물이다.
        """
        if not punctuation_segments:
            return punctuation_segments
        result: List[PuncSegment] = []
        n = len(punctuation_segments)
        i = 0
        while i < n:
            seg = punctuation_segments[i]
            if not seg.is_silence():
                result.append(seg)
                i += 1
                continue

            prev_text = result[-1] if result and not result[-1].is_silence() else None
            if prev_text is None or getattr(prev_text, "punct_boundary", False):
                # 게이트 비대상: 앞에 텍스트가 없거나 이미 온점으로 진짜 종결됨(현행 유지).
                result.append(seg)
                i += 1
                continue

            # 연속 침묵 span 누적 — 다음 non-silence까지 훑는다.
            span_end_idx = i
            while span_end_idx + 1 < n and punctuation_segments[span_end_idx + 1].is_silence():
                span_end_idx += 1
            if span_end_idx == i:
                merged_silence = seg
            else:
                merged_silence = PuncSegment(
                    start=seg.start, end=punctuation_segments[span_end_idx].end, text=None, speaker=-2,
                )
                merged_silence.hard_boundary = any(
                    punctuation_segments[k].hard_boundary for k in range(i, span_end_idx + 1)
                )
            next_idx = span_end_idx + 1
            next_seg = (
                punctuation_segments[next_idx]
                if next_idx < n and not punctuation_segments[next_idx].is_silence()
                else None
            )

            decision, path = self._gate_decide(prev_text, merged_silence, next_seg, audio_time, flush, self.diarization)
            d_eff = (
                merged_silence.end - merged_silence.start
                if merged_silence.start is not None and merged_silence.end is not None else None
            )
            self._log_silence_gate(
                merged_silence.start, merged_silence.end, d_eff,
                last_word(prev_text.text), last_word(next_seg.text) if next_seg is not None else None,
                (prev_text.speaker, next_seg.speaker if next_seg is not None else None),
                (prev_text.detected_language, next_seg.detected_language if next_seg is not None else None),
                decision, path,
            )

            if decision == "merge":
                i = next_idx  # 침묵 생략 — next_seg(있다면)는 다음 반복에서 그대로 append
                continue
            if decision == "pending":
                merged_silence.gate_pending = True
                prev_text.gate_pending = True
                result.append(merged_silence)
            else:
                result.append(merged_silence)
            i = span_end_idx + 1
        return result

    def compute_new_punctuations_segments(self) -> List[PuncSegment]:
        new_punc_segments = []
        segment_start_idx = 0
        self.unvalidated_tokens += self.new_tokens
        for i, token in enumerate(self.unvalidated_tokens):
            if token.is_silence():
                previous_segment = PuncSegment.from_tokens(
                        tokens=self.unvalidated_tokens[segment_start_idx: i],
                    )
                if previous_segment:
                    new_punc_segments.append(previous_segment)
                segment = PuncSegment.from_tokens(
                    tokens=[token],
                    is_silence=True
                )
                new_punc_segments.append(segment)
                segment_start_idx = i+1
            elif token.is_boundary():
                previous_segment = PuncSegment.from_tokens(
                    tokens=self.unvalidated_tokens[segment_start_idx: i],
                )
                if previous_segment:
                    new_punc_segments.append(previous_segment)
                segment_start_idx = i+1
            else:
                if token.has_punctuation():
                    segment = PuncSegment.from_tokens(
                        tokens=self.unvalidated_tokens[segment_start_idx: i+1],
                    )
                    new_punc_segments.append(segment)
                    segment_start_idx = i+1

        self.unvalidated_tokens = self.unvalidated_tokens[segment_start_idx:]
        return new_punc_segments


    def concatenate_diar_segments(self) -> List[SpeakerSegment]:
        """Merge consecutive diarization slices that share the same speaker."""
        if not self.all_diarization_segments:
            return []
        merged = [self.all_diarization_segments[0]]
        for segment in self.all_diarization_segments[1:]:
            if segment.speaker == merged[-1].speaker:
                merged[-1].end = segment.end
            else:
                merged.append(segment)
        return merged


    @staticmethod
    def intersection_duration(seg1: TimedText, seg2: TimedText) -> float:
        """Return the overlap duration between two timed segments."""
        start = max(seg1.start, seg2.start)
        end = min(seg1.end, seg2.end)

        return max(0, end - start)

    def get_lines_diarization(
        self, audio_time: Optional[float] = None, flush: bool = False
    ) -> Tuple[List[Segment], str]:
        """Build segments when diarization is enabled and track overflow buffer."""
        diarization_buffer = ''
        punctuation_segments = self.compute_punctuations_segments()
        diarization_segments = self.concatenate_diar_segments()
        for punctuation_segment in punctuation_segments:
            if not punctuation_segment.is_silence():
                if diarization_segments and punctuation_segment.start >= diarization_segments[-1].end:
                    diarization_buffer += punctuation_segment.text
                else:
                    max_overlap = 0.0
                    max_overlap_speaker = 1
                    for diarization_segment in diarization_segments:
                        intersec = self.intersection_duration(punctuation_segment, diarization_segment)
                        if intersec > max_overlap:
                            max_overlap = intersec
                            max_overlap_speaker = diarization_segment.speaker + 1
                    punctuation_segment.speaker = max_overlap_speaker

        if self.gate_enabled:
            # 화자 배정이 끝난 뒤에 게이트를 적용 — (a)같은 화자 조건 판정에 실제 화자값이 필요.
            punctuation_segments = self._apply_silence_grammar_gate(punctuation_segments, audio_time, flush)

        segments = []
        if punctuation_segments:
            segments = [punctuation_segments[0]]
            for segment in punctuation_segments[1:]:
                if (segment.speaker == segments[-1].speaker
                        and not segments[-1].hard_boundary
                        and not getattr(segments[-1], "punct_boundary", False)):
                    if segments[-1].text:
                        segments[-1].text += segment.text
                    segments[-1].end = segment.end
                    segments[-1].hard_boundary = segment.hard_boundary
                    segments[-1].punct_boundary = getattr(segment, "punct_boundary", False)
                else:
                    closing = segments[-1]
                    if not closing.is_silence():
                        if getattr(closing, "hard_boundary", False):
                            closing.finalize_trigger = "language_switch"
                        elif segment.is_silence():
                            if getattr(closing, "gate_pending", False):
                                pass  # 게이트 보류 — trigger 미설정(하류 확정 억제, §확정 유예 이원화)
                            else:
                                closing.finalize_trigger = "punctuation" if closing.has_punctuation() else "silence"
                        elif segment.speaker != closing.speaker:
                            closing.finalize_trigger = "speaker_change"
                        elif getattr(closing, "punct_boundary", False):
                            closing.finalize_trigger = "punctuation"
                        else:
                            closing.finalize_trigger = "speaker_change"
                    segments.append(segment)

        # 화자 전환이 발생한 세그먼트는 확정 완료 — 마지막 세그먼트(현재 발화 중)는 제외
        for seg in segments[:-1]:
            seg.finalized = True

        # 게이트 보류 중인 세그먼트(텍스트·침묵 모두)는 블랭킷 확정을 되돌린다 — B 미도착/미귀속
        # 상태라 이 세그먼트가 리스트 마지막이 아니어도(예: 화자 미귀속 B가 이미 별도로 붙은 경우)
        # 확정해서는 안 된다.
        for seg in segments:
            if getattr(seg, "gate_pending", False):
                seg.finalized = False

        return segments, diarization_buffer


    def _reattach_tail_nondiar(self, token: ASRToken) -> bool:
        """비-diar 경로: 직전에 침묵으로 닫힌 텍스트 세그먼트로 꼬리 토큰을 병합.

        비-diar 경로는 all_tokens가 아니라 validated_segments를 누적한다. 침묵이 이미
        앞 줄을 확정해 커밋한 뒤(validated_segments 말미 = [텍스트, 침묵]) 유보 꼬리가
        도착하면, 그 꼬리를 앞 텍스트 세그먼트에 되붙인다.
        재귀속했으면 True(호출부가 current_line에 넣지 않음), 아니면 False.
        """
        if self.current_line_tokens or len(self.validated_segments) < 2:
            return False
        last = self.validated_segments[-1]
        prev = self.validated_segments[-2]
        if (last.is_silence() and not prev.is_silence() and prev.text
                and token.start + TAIL_REATTACH_EPS < last.start):
            prev.text = prev.text + token.text
            prev.end = max(prev.end, token.end)
            return True
        return False

    def _nondiar_punct_split_pending(self, next_token: ASRToken) -> bool:
        """비-diar: 현재 줄이 종결 온점으로 끝났고 다음 토큰이 새 문장을 열면 True(선-분할)."""
        line_text = "".join(t.text for t in self.current_line_tokens)
        s = line_text.strip()
        if not s or s[-1] not in (".", "。"):
            return False
        return is_genuine_sentence_end(line_text, getattr(next_token, "text", None))

    def _apply_finalize_grace(
        self, segments: List[Segment], audio_time: Optional[float], flush: bool = False
    ) -> None:
        """침묵 직후 유예 창 안에서는 직전 텍스트 세그먼트 확정을 보류(꼬리 도착 대기).

        마지막 세그먼트가 침묵이고 그 앞이 텍스트일 때, audio_time - silence.start가
        FINALIZE_GRACE_SECS 미만이면 finalized=False로 되돌린다(유예). 경과했으면 True로
        확정한다. 후속 발화 토큰이 도착하면 마지막 세그먼트가 침묵이 아니게 되므로
        (텍스트) 즉시 확정 상태가 유지된다. flush=True(스트림 종료 — 더 이상 꼬리가
        오지 않음)면 유예를 기다리지 않고 즉시 확정한다.
        """
        if audio_time is None or len(segments) < 2:
            return
        last = segments[-1]
        prev = segments[-2]
        if getattr(last, "gate_pending", False):
            # 게이트가 관여하는 침묵은 PENDING_RESOLVE_CAP(silence.end 기준) 별도 경로로만
            # 해소한다 — 여기서 silence.start 기준 grace로 앞질러 확정하면 §확정 유예
            # 이원화가 깨진다(B 디코드 지연 중 조기 finalized=True → 번역 오발사).
            return
        if last.is_silence() and not prev.is_silence() and prev.text:
            prev.finalized = flush or (audio_time - last.start) >= FINALIZE_GRACE_SECS
            prev.finalize_trigger = (
                ("punctuation" if prev.has_punctuation() else "silence")
                if prev.finalized else None
            )

    # ─── 비-diar 경로 헬퍼(게이트 decide-late 지원) ──────────────────────────

    def _close_current_line(self, trigger: Optional[str]) -> None:
        """current_line_tokens를 확정해 validated_segments에 커밋하고 비운다."""
        if self.current_line_tokens:
            seg = Segment.from_tokens(self.current_line_tokens)
            if seg is not None:
                seg.finalized = True
                seg.finalize_trigger = trigger
                self.validated_segments.append(seg)
            self.current_line_tokens = []

    def _current_line_text(self) -> str:
        return ''.join(t.text for t in self.current_line_tokens)

    def _extend_silence_segment_nondiar(self, start: Optional[float], end: Optional[float]) -> None:
        """validated_segments 말미에 SilentSegment를 추가하거나(없으면) 연장한다."""
        if self.validated_segments and self.validated_segments[-1].is_silence():
            self.validated_segments[-1].end = end
        else:
            self.validated_segments.append(SilentSegment(start=start, end=end))

    def _gate_intake_nondiar_silence(self, token: Silence) -> None:
        """게이트 활성 + 구두점 없이 끝난 현재 줄 뒤에 Silence 도착.

        누적 d_eff가 SILENCE_HARD_SECS를 넘기면(연속 침묵 포함) 안전망으로 즉시 분할
        확정하고, 아니면 다음 토큰(B 또는 재귀속 꼬리) 도착까지 보류(pending)한다.
        """
        pending = self._nondiar_pending_silence
        start = pending.start if pending is not None else token.start
        end = token.end
        d_eff = (end - start) if (start is not None and end is not None) else None
        closing_text = self._current_line_text()
        if d_eff is not None and d_eff >= self.silence_hard_secs:
            self._log_silence_gate(start, end, d_eff, last_word(closing_text), None,
                                    None, None, "split", "split_hard")
            self._close_current_line("silence")
            self._nondiar_pending_silence = None
            self._extend_silence_segment_nondiar(start, end)
            return
        self._nondiar_pending_silence = Silence(start=start, end=end, has_ended=True)
        self._log_silence_gate(start, end, d_eff, last_word(closing_text), None,
                                None, None, "pending", "pending")

    def _handle_nondiar_silence(self, token: Silence, silence_now: float) -> None:
        if self.current_line_tokens:
            already_punctuated = TimedText(text=self._current_line_text()).has_punctuation()
            if self.gate_enabled and not already_punctuated:
                self._gate_intake_nondiar_silence(token)
                return
            self._close_current_line("punctuation" if already_punctuated else "silence")

        end_silence = token.end if token.has_ended else silence_now
        self._extend_silence_segment_nondiar(token.start, end_silence)

    def _handle_nondiar_boundary(self) -> None:
        """언어 전환 경계: 보류 중인 게이트가 있으면 hard_boundary로 즉시 분할 확정."""
        if self._nondiar_pending_silence is not None:
            pending = self._nondiar_pending_silence
            d_eff = (
                pending.end - pending.start
                if (pending.start is not None and pending.end is not None) else None
            )
            self._log_silence_gate(pending.start, pending.end, d_eff, last_word(self._current_line_text()),
                                    None, None, None, "split", "split_grammar")
            self._nondiar_pending_silence = None
        # 언어 전환 경계는(기존 동작대로) 침묵 세그먼트를 만들지 않는다.
        self._close_current_line("language_switch")

    def _resolve_nondiar_pending(self, token: ASRToken) -> None:
        """decide-late: 도착한 토큰이 재귀속 꼬리(start < silence.start)인지 새 발화 B인지
        구분해, B라면 문법 게이트로 병합/분할을 판정한다(§decide-late 원칙)."""
        pending = self._nondiar_pending_silence
        if (token.start is not None and pending.start is not None
                and token.start + TAIL_REATTACH_EPS < pending.start):
            # 재귀속된 꼬리 — 원래 이 줄에 속한다. 현재 줄로 흡수하고 게이트는 계속 보류.
            self.current_line_tokens.append(token)
            d_eff = (
                pending.end - pending.start
                if (pending.start is not None and pending.end is not None) else None
            )
            self._log_silence_gate(pending.start, pending.end, d_eff, last_word(self._current_line_text()),
                                    token.text, None, None, "pending", "pending")
            return

        closing_text = self._current_line_text()
        closing_lang = self.current_line_tokens[0].detected_language if self.current_line_tokens else None
        same_lang = closing_lang == token.detected_language
        verdict = should_split_after_silence(closing_text, token.text)
        if verdict is None:
            verdict = True  # 방어적 기본값 — 도달 시 next_text는 이미 확정 상태라야 정상
        decision = "split" if (not same_lang or verdict) else "merge"
        path = "split_grammar" if decision == "split" else "merge"
        d_eff = (
            pending.end - pending.start
            if (pending.start is not None and pending.end is not None) else None
        )
        self._log_silence_gate(pending.start, pending.end, d_eff, last_word(closing_text), last_word(token.text),
                                None, (closing_lang, token.detected_language), decision, path)

        self._nondiar_pending_silence = None
        if decision == "split":
            self._close_current_line("silence")
            self._extend_silence_segment_nondiar(pending.start, pending.end)
        self.current_line_tokens.append(token)

    def _handle_nondiar_text(self, token: ASRToken) -> None:
        if self._nondiar_pending_silence is not None:
            self._resolve_nondiar_pending(token)
            return
        # 유보됐던 꼬리 토큰은 침묵 앞의 확정 세그먼트로 되붙인다(CASE1 교정).
        if not self._reattach_tail_nondiar(token):
            # 형태소 종결 온점 분할: 직전 줄이 종결 온점으로 끝났고 이 토큰이
            # 발화를 이으면, 새 토큰을 넣기 전에 현재 줄을 확정해 닫는다.
            if self.current_line_tokens and self._nondiar_punct_split_pending(token):
                self._close_current_line("punctuation")
            self.current_line_tokens.append(token)

    def _check_nondiar_pending_cap(self, audio_time: Optional[float], flush: bool) -> None:
        """PENDING_RESOLVE_CAP(또는 flush) 만료 시 보류 중인 게이트를 분할로 강제 해소."""
        pending = self._nondiar_pending_silence
        if pending is None:
            return
        cap_expired = (
            audio_time is not None and pending.end is not None
            and (audio_time - pending.end) >= PENDING_RESOLVE_CAP
        )
        if not (flush or cap_expired):
            return
        d_eff = (
            pending.end - pending.start
            if (pending.start is not None and pending.end is not None) else None
        )
        self._log_silence_gate(pending.start, pending.end, d_eff, last_word(self._current_line_text()), None,
                                None, None, "split", "split_cap")
        self._close_current_line("silence")
        self._extend_silence_segment_nondiar(pending.start, pending.end)
        self._nondiar_pending_silence = None

    def get_lines(
            self,
            diarization: bool = False,
            translation: bool = False,
            current_silence: Optional[Silence] = None,
            audio_time: Optional[float] = None,
            flush: bool = False,
        ) -> Tuple[List[Segment], str, Union[str, TimedText]]:
        """Return the formatted segments plus buffers, optionally with diarization/translation.

        Args:
            audio_time: Current audio stream position in seconds. Used as fallback
                for ongoing silence end time instead of wall-clock (which breaks
                when audio is fed faster or slower than real-time).
            flush: 스트림 종료 시 True — silence-grammar-gate가 보류 중인 판정을
                (다음 발화가 더는 오지 않으므로) 즉시 분할로 강제 해소한다.
        """
        # Fallback for ongoing silence: prefer audio stream time over wall-clock
        _silence_now = audio_time if audio_time is not None else (time() - self.beg_loop)

        if diarization:
            segments, diarization_buffer = self.get_lines_diarization(audio_time=audio_time, flush=flush)
        else:
            diarization_buffer = ''
            for token in self.new_tokens:
                if isinstance(token, Silence):
                    self._handle_nondiar_silence(token, _silence_now)
                elif token.is_boundary():
                    self._handle_nondiar_boundary()
                else:
                    self._handle_nondiar_text(token)

            self._check_nondiar_pending_cap(audio_time, flush)

            segments = list(self.validated_segments)
            if self.current_line_tokens:
                segments.append(Segment.from_tokens(self.current_line_tokens))

        # 침묵 직후 확정 유예: 유보 꼬리가 아직 도착하지 않았을 수 있으므로
        # 유예 창(FINALIZE_GRACE_SECS) 안에서는 직전 텍스트 세그먼트 확정을 보류한다.
        self._apply_finalize_grace(segments, audio_time, flush)

        if current_silence:
            end_silence = current_silence.end if current_silence.has_ended else _silence_now
            if segments and segments[-1].is_silence():
                segments[-1] = SilentSegment(start=segments[-1].start, end=end_silence)
            else:
                segments.append(SilentSegment(
                    start=current_silence.start,
                    end=end_silence
                ))
        if translation:
            [self.add_translation(segment) for segment in segments if not segment.is_silence()]

        self._prune()

        return segments, diarization_buffer, self.new_translation_buffer.text
