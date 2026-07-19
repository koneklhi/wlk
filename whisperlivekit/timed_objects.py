from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

PUNCTUATION_MARKS = {'.', '!', '?', '。', '！', '？'}

def format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS.cc (centisecond precision)."""
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def format_walltime(session_start: float, offset: float) -> str:
    """세션 시작 epoch(session_start)에 offset(경과초)을 더한 실제 시각을 HH:MM:SS로 포맷."""
    return datetime.fromtimestamp(session_start + offset).strftime("%H:%M:%S")

@dataclass
class Timed:
    start: Optional[float] = 0
    end: Optional[float] = 0

@dataclass
class TimedText(Timed):
    text: Optional[str] = ''
    speaker: Optional[int] = -1
    detected_language: Optional[str] = None

    def has_punctuation(self) -> bool:
        t = self.text.strip()
        return bool(t) and t[-1] in PUNCTUATION_MARKS

    def is_within(self, other: 'TimedText') -> bool:
        return other.contains_timespan(self)

    def duration(self) -> float:
        return self.end - self.start

    def contains_timespan(self, other: 'TimedText') -> bool:
        return self.start <= other.start and self.end >= other.end

    def __bool__(self) -> bool:
        return bool(self.text)

    def __str__(self) -> str:
        return str(self.text)

@dataclass()
class ASRToken(TimedText):
    probability: Optional[float] = None

    def with_offset(self, offset: float) -> "ASRToken":
        """Return a new token with the time offset added."""
        return ASRToken(self.start + offset, self.end + offset, self.text, self.speaker, detected_language=self.detected_language, probability=self.probability)

    def is_silence(self) -> bool:
        return False

    def is_boundary(self) -> bool:
        return False


@dataclass
class Sentence(TimedText):
    pass

@dataclass
class Transcript(TimedText):
    """
    represents a concatenation of several ASRToken
    """

    @classmethod
    def from_tokens(
        cls,
        tokens: List[ASRToken],
        sep: Optional[str] = None,
        offset: float = 0
    ) -> "Transcript":
        """Collapse multiple ASR tokens into a single transcript span."""
        sep = sep if sep is not None else ' '
        text = sep.join(token.text for token in tokens)
        if tokens:
            start = offset + tokens[0].start
            end = offset + tokens[-1].end
        else:
            start = None
            end = None
        return cls(start, end, text)


@dataclass
class SpeakerSegment(Timed):
    """Represents a segment of audio attributed to a specific speaker.
    No text nor probability is associated with this segment.
    """
    speaker: Optional[int] = -1
    pass

@dataclass
class Translation(TimedText):
    pass

@dataclass
class Silence():
    start: Optional[float] = None
    end: Optional[float] = None
    duration: Optional[float] = None
    is_starting: bool = False
    has_ended: bool = False

    def compute_duration(self) -> Optional[float]:
        if self.start is None or self.end is None:
            return None
        self.duration = self.end - self.start
        return self.duration

    def is_silence(self) -> bool:
        return True

    def is_boundary(self) -> bool:
        return False


@dataclass
class LanguageSwitch:
    """디코더가 중간에 언어를 전환할 때(예: 순차통역 한→영) 침묵·화자전환 경계 없이도
    문장 경계를 만들기 위한 내부 마커. TokensAlignment에서 Silence와 동급으로 세그먼트를
    분할하되, 눈에 보이는 침묵 구간을 만들지 않고 텍스트도 없다.
    내부 신호 전용 — FrontData로 직렬화되지 않는다(분할 지점으로 소비될 뿐 세그먼트가 되지 않음)."""
    start: Optional[float] = None
    end: Optional[float] = None
    detected_language: Optional[str] = None  # 전환 후 언어
    text: str = ''  # 하류의 ''.join(t.text ...) / sep.join 호환용 빈 문자열
    retract_from: Optional[float] = None  # 철회(retraction) 재디코딩 구간 시작 절대시각
    prev_language: Optional[str] = None  # 철회 대상 판정용 — 전환 전 언어
    retract_floor: Optional[float] = None  # 철회 하한 = 재디코딩 창 시작 절대시각(트림된 버퍼 시작). 이보다 앞선 토큰은 재디코딩 불가라 철회 안 함

    def is_silence(self) -> bool:
        return False

    def is_boundary(self) -> bool:
        return True


@dataclass
class Segment(TimedText):
    """Generic contiguous span built from tokens or silence markers."""
    start: Optional[float]
    end: Optional[float]
    text: Optional[str]
    speaker: Optional[str]
    tokens: Optional[ASRToken] = None
    translation: Optional[Translation] = None
    finalized: bool = False
    finalize_trigger: Optional[str] = None

    @classmethod
    def from_tokens(
        cls,
        tokens: List[Union[ASRToken, Silence]],
        is_silence: bool = False
    ) -> Optional["Segment"]:
        """Return a normalized segment representing the provided tokens."""
        if not tokens:
            return None

        start_token = tokens[0]
        end_token = tokens[-1]
        if is_silence:
            return cls(
                start=start_token.start,
                end=end_token.end,
                text=None,
                speaker=-2
            )
        else:
            return cls(
                start=start_token.start,
                end=end_token.end,
                text=''.join(token.text for token in tokens),
                speaker=-1,
                detected_language=start_token.detected_language
            )

    def is_silence(self) -> bool:
        """True when this segment represents a silence gap."""
        return self.speaker == -2

    def to_dict(self, session_start: Optional[float] = None) -> Dict[str, Any]:
        """Serialize the segment for frontend consumption.

        session_start(에폭초)가 주어지면 start/end를 실제 벽시계 시각(HH:MM:SS)으로,
        생략되면 기존처럼 세션 상대 경과시간(H:MM:SS.cc)으로 포맷한다.
        """
        if session_start is not None:
            start_str = format_walltime(session_start, self.start)
            end_str = format_walltime(session_start, self.end)
        else:
            start_str = format_time(self.start)
            end_str = format_time(self.end)
        _dict: Dict[str, Any] = {
            'speaker': int(self.speaker) if self.speaker != -1 else 1,
            'text': self.text,
            'id': round(self.start, 3) if self.start is not None else None,  # 안정 세그먼트 식별자(세션상대 초). end가 자라거나 finalized→interim 재개방돼도 불변 — 클라이언트 dedup/React key용
            'start': start_str,
            'end': end_str,
            'finalized': self.finalized,
            'completed': self.finalized,          # React 호환 별칭
        }
        _dict['finalize_trigger'] = self.finalize_trigger    # None 이어도 항상 방출
        if self.translation:
            _dict['translation'] = self.translation
        if self.detected_language:
            _dict['detected_language'] = self.detected_language
            _dict['lang'] = self.detected_language    # React 호환 별칭
        return _dict


@dataclass
class PuncSegment(Segment):
    hard_boundary: bool = False
    punct_boundary: bool = False   # 형태소 종결 온점 분할 경계(diar 병합 생존용). 내부 전용 — to_dict 미방출.
    gate_pending: bool = False     # silence-grammar-gate 판정 보류 중(B 미도착/미귀속). 내부 전용 — to_dict 미방출.
    speaker_boundary: bool = False  # 이 침묵 분할이 화자전환으로 강제된 것(Exp-187, _gate_decide의
    # "diar_mode and next_seg.speaker != closing.speaker" split_grammar 경로)임을 표시 —
    # TriggerAssign이 silence/punctuation 대신 speaker_change로 라벨링하도록 정정. 내부 전용 — to_dict 미방출.

class SilentSegment(Segment):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.speaker = -2
        self.text = ''


@dataclass
class FrontData():
    status: str = ''
    error: str = ''
    lines: list[Segment] = field(default_factory=list)
    buffer_transcription: str = ''
    buffer_diarization: str = ''
    buffer_translation: str = ''
    remaining_time_transcription: float = 0.
    remaining_time_diarization: float = 0.

    def to_dict(self, session_start: Optional[float] = None) -> Dict[str, Any]:
        """Serialize the front-end data payload."""
        _dict: Dict[str, Any] = {
            'status': self.status,
            'lines': [line.to_dict(session_start) for line in self.lines if (line.text or line.speaker == -2)],
            'buffer_transcription': self.buffer_transcription,
            'buffer_diarization': self.buffer_diarization,
            'buffer_translation': self.buffer_translation,
            'remaining_time_transcription': self.remaining_time_transcription,
            'remaining_time_diarization': self.remaining_time_diarization,
        }
        if self.error:
            _dict['error'] = self.error
        return _dict

@dataclass
class ChangeSpeaker:
    speaker: int
    start: int

@dataclass
class State():
    """Unified state class for audio processing.

    Contains both persistent state (tokens, buffers) and temporary update buffers
    (new_* fields) that are consumed by TokensAlignment.
    """
    # Persistent state
    tokens: List[ASRToken] = field(default_factory=list)
    buffer_transcription: Transcript = field(default_factory=Transcript)
    end_buffer: float = 0.0
    end_attributed_speaker: float = 0.0
    remaining_time_transcription: float = 0.0
    remaining_time_diarization: float = 0.0

    # Temporary update buffers (consumed by TokensAlignment.update())
    new_tokens: List[Union[ASRToken, Silence]] = field(default_factory=list)
    new_translation: List[Any] = field(default_factory=list)
    new_diarization: List[Any] = field(default_factory=list)
    new_tokens_buffer: List[Any] = field(default_factory=list)  # only when local agreement
    new_translation_buffer: TimedText = field(default_factory=TimedText)
