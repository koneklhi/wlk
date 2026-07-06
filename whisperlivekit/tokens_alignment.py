from time import time
from typing import Any, List, Optional, Tuple, Union

from whisperlivekit.timed_objects import (
    ASRToken,
    PuncSegment,
    Segment,
    Silence,
    SilentSegment,
    SpeakerSegment,
    TimedText,
)

_DEFAULT_RETENTION_SECONDS: float = 300.0

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

# 온점 토큰에서 세그먼트를 끊을 최소 음향 갭(초). 온점 뒤 다음 토큰과의 간격이
# 이보다 작으면(발화 중간 spurious 온점, 예 "very. much") 문장을 끊지 않는다.
# §3.3: 침묵(화자전환) 경계가 1순위, 온점 경계는 2순위(선택)이므로 갭 없는 온점에서
# 과분할하느니 보수적으로 유지한다. 특정 단어가 아닌 타임스탬프 갭 기준이라 일반화됨.
#
# audio_processor.py의 MIN_DURATION_REAL_SILENCE(0.4)와 반드시 같은 값이어야 한다.
# audio_processor.py가 tokens_alignment.py를 임포트하므로(순환 임포트 회피) 두 상수는
# import로 공유하지 못하고 값만 동기화한다 — 값이 어긋나면 [작은 값, 큰 값) 구간이
# "사각지대"가 된다: 그 구간의 pause는 Silence 토큰을 만들 만큼 길지는 않은데
# (< MIN_DURATION_REAL_SILENCE) 온점 분할은 발동시켜(>= 이 상수의 구값) 실제
# 침묵이 전혀 없어도 문장이 과분할된다(CASE1 4번째 경로 — Exp-166. bong1 실측
# "자빠졌/는데" 갭 0.32s가 구값 0.3 사각지대에 정확히 들어맞아 재현됨). 값을 바꾸면
# audio_processor.py의 MIN_DURATION_REAL_SILENCE도 함께 바꿀 것 — 동기화는
# tests/test_tail_reattachment.py::test_audio_processor_min_silence_matches_punct_split_gap
# 로 회귀 방지.
PUNCT_SPLIT_GAP_SECS: float = 0.4


class TokensAlignment:

    def __init__(self, state: Any, args: Any, sep: Optional[str]) -> None:
        self.state = state
        self.diarization = args.diarization

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
                self.all_tokens.append(t)
                continue
            i = len(self.all_tokens)
            while (i > 0 and self.all_tokens[i - 1].is_silence()
                   and t.start + TAIL_REATTACH_EPS < self.all_tokens[i - 1].start
                   and self.all_tokens[i - 1].start - t.start <= TAIL_REATTACH_MAX_LOOKBACK_SECS):
                i -= 1
            self.all_tokens.insert(i, t)

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

        온점 뒤에 (a) 발화 끝, (b) 침묵, (c) 실제 pause(다음 토큰과 갭>=PUNCT_SPLIT_GAP_SECS)가
        있을 때만 True. 갭 없이 이어지는 중간 온점("very. much")에서는 False → 과분할 방지.
        특정 단어가 아니라 타임스탬프 갭 기준이라 일반화된다(§3.3 온점 경계는 2순위).
        """
        tokens = self.all_tokens
        if idx + 1 >= len(tokens):
            return True  # 발화 끝
        nxt = tokens[idx + 1]
        if nxt.is_silence():
            return True
        return nxt.start - tokens[idx].end >= PUNCT_SPLIT_GAP_SECS

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
                segment_start_idx = i+1
            else:
                if token.has_punctuation() and self._punct_split_justified(i):
                    segment = PuncSegment.from_tokens(
                        tokens=self.all_tokens[segment_start_idx: i+1],
                    )
                    segments.append(segment)
                    segment_start_idx = i+1

        final_segment = PuncSegment.from_tokens(
            tokens=self.all_tokens[segment_start_idx:],
        )
        if final_segment:
            segments.append(final_segment)
        return segments

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

    def get_lines_diarization(self) -> Tuple[List[Segment], str]:
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

        segments = []
        if punctuation_segments:
            segments = [punctuation_segments[0]]
            for segment in punctuation_segments[1:]:
                if segment.speaker == segments[-1].speaker and not segments[-1].hard_boundary:
                    if segments[-1].text:
                        segments[-1].text += segment.text
                    segments[-1].end = segment.end
                    segments[-1].hard_boundary = segment.hard_boundary
                else:
                    segments.append(segment)

        # 화자 전환이 발생한 세그먼트는 확정 완료 — 마지막 세그먼트(현재 발화 중)는 제외
        for seg in segments[:-1]:
            seg.finalized = True

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

    def _apply_finalize_grace(self, segments: List[Segment], audio_time: Optional[float]) -> None:
        """침묵 직후 유예 창 안에서는 직전 텍스트 세그먼트 확정을 보류(꼬리 도착 대기).

        마지막 세그먼트가 침묵이고 그 앞이 텍스트일 때, audio_time - silence.start가
        FINALIZE_GRACE_SECS 미만이면 finalized=False로 되돌린다(유예). 경과했으면 True로
        확정한다. 후속 발화 토큰이 도착하면 마지막 세그먼트가 침묵이 아니게 되므로
        (텍스트) 즉시 확정 상태가 유지된다.
        """
        if audio_time is None or len(segments) < 2:
            return
        last = segments[-1]
        prev = segments[-2]
        if last.is_silence() and not prev.is_silence() and prev.text:
            prev.finalized = (audio_time - last.start) >= FINALIZE_GRACE_SECS

    def get_lines(
            self,
            diarization: bool = False,
            translation: bool = False,
            current_silence: Optional[Silence] = None,
            audio_time: Optional[float] = None,
        ) -> Tuple[List[Segment], str, Union[str, TimedText]]:
        """Return the formatted segments plus buffers, optionally with diarization/translation.

        Args:
            audio_time: Current audio stream position in seconds. Used as fallback
                for ongoing silence end time instead of wall-clock (which breaks
                when audio is fed faster or slower than real-time).
        """
        # Fallback for ongoing silence: prefer audio stream time over wall-clock
        _silence_now = audio_time if audio_time is not None else (time() - self.beg_loop)

        if diarization:
            segments, diarization_buffer = self.get_lines_diarization()
        else:
            diarization_buffer = ''
            for token in self.new_tokens:
                if isinstance(token, Silence):
                    if self.current_line_tokens:
                        seg = Segment.from_tokens(self.current_line_tokens)
                        if seg is not None:
                            seg.finalized = True
                            self.validated_segments.append(seg)
                        self.current_line_tokens = []

                    end_silence = token.end if token.has_ended else _silence_now
                    if self.validated_segments and self.validated_segments[-1].is_silence():
                        self.validated_segments[-1].end = end_silence
                    else:
                        self.validated_segments.append(SilentSegment(
                            start=token.start,
                            end=end_silence
                        ))
                elif token.is_boundary():
                    # 언어 전환 경계: 현재 줄을 확정해 닫되 침묵 세그먼트는 만들지 않는다.
                    if self.current_line_tokens:
                        seg = Segment.from_tokens(self.current_line_tokens)
                        if seg is not None:
                            seg.finalized = True
                            self.validated_segments.append(seg)
                        self.current_line_tokens = []
                else:
                    # 유보됐던 꼬리 토큰은 침묵 앞의 확정 세그먼트로 되붙인다(CASE1 교정).
                    if not self._reattach_tail_nondiar(token):
                        self.current_line_tokens.append(token)

            segments = list(self.validated_segments)
            if self.current_line_tokens:
                segments.append(Segment.from_tokens(self.current_line_tokens))

        # 침묵 직후 확정 유예: 유보 꼬리가 아직 도착하지 않았을 수 있으므로
        # 유예 창(FINALIZE_GRACE_SECS) 안에서는 직전 텍스트 세그먼트 확정을 보류한다.
        self._apply_finalize_grace(segments, audio_time)

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
