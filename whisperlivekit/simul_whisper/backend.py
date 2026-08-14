import dataclasses
import gc
import logging
import platform
import re
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from whisperlivekit.backend_support import faster_backend_available, mlx_backend_available
from whisperlivekit.boundary_reconcile import _dedup_norm
from whisperlivekit.model_paths import detect_model_format, resolve_model_path
from whisperlivekit.simul_whisper.config import AlignAttConfig
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ASRToken, ChangeSpeaker, LanguageSwitch, Transcript
from whisperlivekit.tokens_alignment import _is_opposite_script
from whisperlivekit.warmup import load_file
from whisperlivekit.whisper import load_model, tokenizer

logger = logging.getLogger(__name__)


HAS_MLX_WHISPER = mlx_backend_available(warn_on_missing=True)
if HAS_MLX_WHISPER:
    from .mlx import MLXAlignAtt
    from .mlx_encoder import load_mlx_encoder, load_mlx_model, mlx_model_mapping
else:
    mlx_model_mapping = {}
    MLXAlignAtt = None
HAS_FASTER_WHISPER = faster_backend_available(warn_on_missing=not HAS_MLX_WHISPER)
if HAS_FASTER_WHISPER:
    from faster_whisper import WhisperModel
else:
    WhisperModel = None

MIN_DURATION_REAL_SILENCE = 2
MIN_DURATION_SHORT_LANG_RESET = 0.5

# 디코더 멈춤 복구: 오디오가 이 시간(초) 이상 전진했는데 토큰이 전혀 안 나오면
# SimulStreaming 디코더가 비-fire 상태에 빠진 것으로 보고 강제 refresh로 복구한다.
STALL_RECOVER_SEC = 10.0

# damage B(화자전환 경계 서두 유실) 수정 — new_speaker의 refresh_segment(complete=False)가
# 무조건 마지막 2청크만 남기던 고정 컷 대신, 화자전환 시각부터 현재까지의 실제 경계 오디오
# 길이만큼 유지하도록 keep_secs를 계산할 때 쓰는 상수.
# MARGIN=0.3 — 경계 직전 약간의 여유(경계 시각 추정 오차 흡수).
# MAX_KEEP=5.0 — Exp-166 keep=4.5의 방송환각 전례를 반영한 상한 — 재방출/환각 재발 방지.
_NEW_SPEAKER_KEEP_MARGIN = 0.3
_NEW_SPEAKER_MAX_KEEP = 5.0

# Exp-189: new_speaker() eager 언어감지 버스트(diar flip-flop) 쿨다운.
# 배경: Sortformer가 단일화자 파일(kor1)에서도 순간적으로 speaker 0↔1을 반복
# 오귀속하는 노이즈가 있음(Exp-188과 동일 근원 — "diarization 임베딩이 아주 짧은
# 세그먼트에서 불안정한 일반적 한계"). 매 flip마다 new_speaker()가 다시 호출되고
# eager 언어감지(detect_current_language, since_offset로 창을 좁힘)도 매번 재실행된다.
# 버스트(짧은 시간 내 연쇄 flip) 중에는 새 화자 오디오가 거의 안 쌓인 채(연쇄
# flip일수록 창이 더 좁아짐) 반복 재시도되고, 우연히 고신뢰 오탐(예: en, p=0.95→
# 1.00→0.99 연속)이 나오면 그 상태가 버스트 내내 유지·재확인되며 실제 언어
# 환각으로 이어질 수 있다(kor1 실측: R2, WER 20.5%→47.4%, "We have a lot of
# work..." 영어 환각 삽입). 직전 eager 체크로부터 이 시간 이내에 또 화자전환
# 이벤트가 오면 eager 재감지 자체를 건너뛴다(encoder forward도 생략) —
# detected_language는 그대로 None으로 리셋되므로 infer()의 표준 eager_lang_detect
# 폴백(1.5~2.0s 더 많은 표본 확보 후 판정하는 기존 안전 경로)이 대신 처리한다.
# genuine 단일 화자전환(ytn2 CASE2 등)은 쿨다운 창 안에서 재호출되지 않으므로
# 영향받지 않는다.
_EAGER_LANG_COOLDOWN_SECS = 1.5

_FOREIGN_LANG_PATTERN = re.compile(r'\(speaking in foreign language', re.IGNORECASE)

# P2: 언어-출력 스크립트 불일치 억제 게이트.
# 배경: EN→KO 전환 직후 "Thank you"류 영어 필러 환각이 KO 세그먼트 전체를 삼키는 사례가
# 반복 관측됐다(EXPERIMENTS_LOG Exp-158/159/161 등). avg_logprob(영어 최빈구문=고신뢰),
# compression_ratio(필러가 매번 변주돼 압축률 임계 미달), BatchRepeatFilter(한국어 전용
# 정규식이라 영어 필러는 진입 자체를 못함), CrossBatchFilter(완전 동일 인접단어만 제거)
# 모두 이 패턴을 못 잡는 사각지대다.
# 판정은 특정 문구 하드코딩 없이 구조적 시그니처만 사용(§3.8): detected_language와 정반대
# 스크립트로만 구성되고, 타입-토큰 비율(고유어/전체어)이 붕괴한(=반복/변주) 세그먼트만 억제.
# 반복 없는 정상 코드스위칭 전체 문장은 TTR이 높아 통과한다(오탐 방지).
_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z']+|[가-힣]+")
_SCRIPT_MISMATCH_MIN_WORDS = 6        # 이보다 적으면 통계적으로 판단 불가 → 통과(오탐 방지)
_SCRIPT_MISMATCH_TTR_THRESHOLD = 0.6  # 고유어/전체어 비율이 이 값 이하면 반복 시그니처로 판정
_SCRIPT_MISMATCH_STREAK_CAP = 40      # streak 누적 상한(무한 성장 방지)


def _is_script_mismatch_filler(text: str, detected_language) -> bool:
    """detected_language와 반대 스크립트로만 구성된 반복형 세그먼트인지 판정.

    대칭 적용(방향 무관, §3.8 일반화): ko 감지 중 영어-only 반복도, en 감지 중
    한글-only 반복도 동일 로직으로 잡는다.
    """
    if detected_language not in ("ko", "en"):
        return False
    has_hangul = bool(re.search(r'[가-힣]', text))
    has_latin = bool(re.search(r'[A-Za-z]', text))
    if detected_language == "ko":
        script_mismatch = has_latin and not has_hangul
    else:  # "en"
        script_mismatch = has_hangul and not has_latin
    if not script_mismatch:
        return False
    words = [w.lower() for w in _WORD_TOKEN_PATTERN.findall(text)]
    if len(words) < _SCRIPT_MISMATCH_MIN_WORDS:
        return False
    unique_ratio = len(set(words)) / len(words)
    return unique_ratio <= _SCRIPT_MISMATCH_TTR_THRESHOLD


# CASE3 — script-agnostic 앵커 반복(필러 storm) 게이트.
# 배경: 오프라인 oracle 확정 결과, 잔존 필러 storm(bong1 "thank you"×3, ytn2 "김정은"×4)의
# 근본원인은 모델천장이 아니라 경계 리프레시 직후 <1s 컨텍스트기아 상태에서 발생하는
# 스트리밍 세금이다. `_is_script_mismatch_filler`(P2 게이트, 위)는 "반대 스크립트 +
# TTR 붕괴" 전제라 ① 같은 스크립트(ko/ko, en/en) storm ② "앵커 토큰 1개는 정확반복,
# 주변부는 변주"라 전체 TTR은 붕괴하지 않는 storm(ytn2 "김정은"+접미부 변주 — 전체
# TTR=0.809로 문턱 통과)을 못 잡는다. 아래 게이트는 스크립트·언어 무관하게 "최근
# 방출 단어 윈도우 안에서 앵커(1~2gram)가 비정상적으로 몰려 반복되는가"만 본다
# (§3.8: 특정 문구·언어 하드코딩 금지 — 판정은 순수 반복 밀도 통계).
#
# 파라미터는 analyze_case3_hallucination.py의 오프라인 분석(문서 전체 대비 국소집중도)과
# 철학은 같지만, 스트리밍 게이트는 "문서 전체"를 알 수 없으므로 롤링 윈도우 자체가
# 관찰가능한 전부다 — concentration은 "윈도우 내 그 앵커 전체 등장 중 이 클러스터가
# 차지하는 비율"로 정의한다(문서 전체 어절 수 대비가 아님).
#
# 값 근거(유닛테스트로 검증·튜닝, tests/test_anchor_repeat_gate.py):
#   WINDOW=40 — 필러 storm은 보통 한 문장~두 문장(15~25단어) 안에서 완결되므로 40단어면
#     현재 storm 전체 + 직전 문맥까지 포괄. 너무 크면 서로 무관한 두 문단의 우연한 재등장을
#     한 클러스터로 오인할 여지가 커진다.
#   MIN_COUNT=4 — "네, 네, 알겠습니다"류 정상 강조 반복은 실측상 2~3회가 흔하다(오탐 방지
#     최우선). storm은 실측 관측(김정은×4, thank you×4)이 모두 4회 이상이라 이 값으로
#     3회 이하 정상 반복과 4회+ storm을 분리한다.
#   MAX_GAP=5 — 실측 storm은 앵커 사이에 변주 접미부가 1~5단어 끼는 구조("기자입니다"/
#     "기자가 보도합니다", 영어 실측 "Thank you very much for coming" 등 — 접미부가
#     길 때는 앵커 사이 간격이 5단어까지 벌어짐, 유닛테스트로 확인). 이보다 훨씬 크게
#     잡으면 "북한"처럼 문서 전반에 8~20단어 간격으로 자연스레 재등장하는 고유명사까지
#     하나의 클러스터로 묶여 오탐한다(유닛테스트 `test_scattered_mention_*`로 gap=8
#     기준 안전 확인).
#   MIN_CONCENTRATION=0.6 — 클러스터가 윈도우 내 그 앵커 전체 등장의 과반 이상을 차지해야
#     "국소적으로 몰림"으로 판정한다(문서 전반에 흩어진 재등장과 구분).
_ANCHOR_REPEAT_WINDOW = 40
_ANCHOR_REPEAT_MIN_COUNT = 4
_ANCHOR_REPEAT_MAX_GAP = 5
_ANCHOR_REPEAT_MIN_CONCENTRATION = 0.6


def _find_anchor_repeat_storm(
    words: List[str],
    window: int = _ANCHOR_REPEAT_WINDOW,
    min_count: int = _ANCHOR_REPEAT_MIN_COUNT,
    max_gap: int = _ANCHOR_REPEAT_MAX_GAP,
    min_concentration: float = _ANCHOR_REPEAT_MIN_CONCENTRATION,
) -> bool:
    """최근 words의 롤링 윈도우(마지막 window개)에서 1~2gram 앵커가 gap-tolerant하게
    min_count회 이상 반복되고, 그 클러스터가 윈도우 내 해당 앵커 전체 등장의
    min_concentration 비율 이상을 차지하면 True(필러 storm 판정).

    n=2(구 단위 앵커, 예 "thank you")부터 검사하고, 안 잡히면 n=1(단일 토큰 앵커,
    예 "김정은")로 내려간다. 언어·문구 하드코딩 없음 — 순수 위치 통계만 사용.
    """
    tail = words[-window:] if window > 0 else list(words)
    n_tail = len(tail)
    for n in (2, 1):
        if n_tail < n:
            continue
        occurrences: Dict[Tuple[str, ...], List[int]] = {}
        for k in range(n_tail - n + 1):
            occurrences.setdefault(tuple(tail[k:k + n]), []).append(k)
        for positions in occurrences.values():
            total = len(positions)
            if total < min_count:
                continue
            best_cluster = 1
            cluster = 1
            for prev_pos, cur_pos in zip(positions, positions[1:]):
                gap_words = cur_pos - prev_pos - n
                if gap_words <= max_gap:
                    cluster += 1
                    best_cluster = max(best_cluster, cluster)
                else:
                    cluster = 1
            if best_cluster < min_count:
                continue
            if (best_cluster / total) >= min_concentration:
                return True
    return False


# 스크립트-앵커 재감지 게이트 (GOAL_SCRIPT_ANCHOR_REDETECT — 코드스위칭 서두유실 근본수정).
# 배경: LanguageSwitch 마커는 _apply_detected_language의 is_switch일 때만 arm되는데,
# 중간 재감지 트리거 4종(짧은침묵≥0.5s·긴침묵≥2.0s·화자전환 eager·PLC=기본 None 비활성)은
# 무음·화자전환 없는 연속 코드스위칭에서 전부 미발동한다 → 구언어 고착 → 새 언어 서두
# 오디코드/유실(①) + 경계 마커 미생성으로 같은 line 접착(②). Exp-172 실측: bong1에서
# 반대 스크립트 streak 3~4단어·2배치·약 1.0s 시점에야 기존 침묵 트리거가 뒤늦게 발동 —
# 그 사이 방출분이 철회·유실됐다. 임계 기본값 N=3단어/T≈1.0s는 이 실측 근거.
# Exp-160 면역: 이 트리거는 lang_id "확률"이 아니라 "출력 스크립트의 지속 반전"에만
# 반응한다 — ytn2 스퓨리어스 전환 당시 출력은 계속 한글이었으므로 streak이 쌓이지 않아
# 미발동(순수 확률 기반 주기 체크 PLC 재도입이 아님).
# 판정은 tokens_alignment._is_opposite_script(TTR 게이트 없는 순수 스크립트) 재사용 —
# _is_script_mismatch_filler(TTR≤0.6 반복 전제)가 정상 전환을 통과시키던 사각지대를 메운다.
# 같은 스크립트 토큰이 섞이면 streak 리셋("I think 그건"류 1~2단어 정상 삽입 오탐 방어),
# 라틴/한글이 전혀 없는 토큰(숫자·기호)은 스크립트 중립으로 스킵. ko↔en 대칭(§3.8).
SCRIPT_ANCHOR_REDETECT_ENABLED = True  # 롤백 장치: False면 게이트 완전 무동작
_SCRIPT_ANCHOR_N_WORDS = 3    # 연속 반대-스크립트 단어 수 문턱 (Exp-172 실측 N=3)
_SCRIPT_ANCHOR_T_SECS = 1.0   # 반전 지속 시간 문턱 (Exp-172 실측 T≈1.0s)
_SCRIPT_ANCHOR_REDETECT_WINDOW_SECS = 2.0  # 재감지 창
_SCRIPT_ANCHOR_REDETECT_MIN_PROB = 0.90    # 재감지 확신 문턱 (미달 시 None → 미적용)

# 약어/철자낭독 가드 (GOAL_SCRIPTANCHOR_ACRONYM_GUARD — 한국어 발화 중 영문 약어 철자
# 낭독을 코드스위칭으로 오인하는 사각지대 수정). 배경: "GP·GOP 유무인 GP·GOP에 대한"
# 같은 한국어 낭독에서 디코더가 라틴 낱글자/ALL-CAPS 약어 토큰(G/P/GOP/GPGOP류)을
# 연속 방출하면 위 재감지 streak이 이를 "반대스크립트 N단어"로 오집계 → en 오전환 →
# 직전 오디오 9~12s 비가역 트림 폐기 → 복귀 전환 → 중복 재확정 폭주(kor2 실측
# WER 70~101%, Exp-179 규명). 소문자 자연 영단어(There/is/work)와 두문자 대문자
# (The/Thank)는 기존대로 streak 산입(Exp-175 코드스위칭 커버리지 보존) — 이 가드는
# "낱글자 철자낭독"·"ALL-CAPS 약어 덩어리"라는 표기 속성만으로 라틴 토큰을 증거
# 집계에서 중립 스킵한다(숫자·기호와 동일 취급 — 산입도 리셋도 안 함). 데이터 특화
# 문자열 매칭 금지(§3.8) — 길이·대소문자만 판정에 쓴다. 한글 방향(en 잠금 중 한글
# 방출)은 대소문자 개념이 없어 이 가드의 영향을 받지 않는다(비대칭 의도).
SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED = True  # 롤백 장치: False면 기존 동작(약어도 streak 산입)
_ACRONYM_MAX_SINGLE_LEN = 2     # 낱글자 철자 낭독 길이 상한 (G/P/A. 류)
_ACRONYM_MAX_ALLCAPS_LEN = 6    # 전부대문자 약어 덩어리 길이 상한 (GOP/NATO/AI/DUP 류)
_ACRONYM_LETTERS_RE = re.compile(r'[A-Za-z]')


def _is_acronym_like_latin(text: str) -> bool:
    """약어/철자 낭독처럼 생긴 라틴 토큰인지 판정 (표기 속성만 사용 — §3.8 하드코딩 금지).

    구두점·공백·숫자를 제거하고 남은 알파벳만으로 판정한다.
    ① 알파벳 길이 <= _ACRONYM_MAX_SINGLE_LEN: 낱글자 철자 낭독(`G`, `P`, `A.`류).
    ② 전부 대문자 && 알파벳 길이 <= _ACRONYM_MAX_ALLCAPS_LEN: 약어 덩어리(`GOP`, `NATO`, `AI`).
    알파벳이 전혀 없으면(빈 문자열) False — 이 함수는 라틴 토큰 판정 후에만 호출된다.
    """
    letters = ''.join(_ACRONYM_LETTERS_RE.findall(text))
    if not letters:
        return False
    if len(letters) <= _ACRONYM_MAX_SINGLE_LEN:
        return True
    return letters.isupper() and len(letters) <= _ACRONYM_MAX_ALLCAPS_LEN


class SimulStreamingOnlineProcessor:
    """Online processor for SimulStreaming ASR."""
    SAMPLING_RATE = 16000

    # 단일음절 반복 환각 억제: max_char_run >= _CHAR_RUN_THRESHOLD 인 토큰은 제거
    # _HALLUCINATION_RESET_THRESHOLD 연속 발생 시 context 리셋
    _CHAR_RUN_THRESHOLD = 4
    _HALLUCINATION_RESET_THRESHOLD = 5

    def __init__(self, asr, logfile=sys.stderr, language=None):
        self.asr = asr
        self.logfile = logfile
        self.end = 0.0
        self.buffer = []
        self._session_cfg = self._resolve_session_cfg(language)
        self.model = self._create_alignatt()
        # 시나리오 튜닝(Phase A) — asr(kwargs)로 전달된 CLI 오버라이드, 미지정 시 기존
        # 모듈 상수로 폴백(무회귀). 사용 지점에서는 getattr(self, ..., None) or CONST로
        # 재조회한다 — 테스트가 __new__로 __init__을 우회해 인스턴스를 만드는 경우에도
        # 안전한 기본값 폴백을 보장하기 위함(§backend.py 유닛테스트 관례).
        self.short_lang_reset_secs = getattr(asr, "short_lang_reset_secs", None) or MIN_DURATION_SHORT_LANG_RESET
        self.new_speaker_max_keep_secs = getattr(asr, "new_speaker_max_keep_secs", None) or _NEW_SPEAKER_MAX_KEEP
        self.script_anchor_n_words = getattr(asr, "script_anchor_n_words", None) or _SCRIPT_ANCHOR_N_WORDS
        self._last_emitted_word: str = None
        self._last_emit_end: float = 0.0  # 마지막으로 토큰을 방출한 시점의 audio end (stall 복구 baseline)
        self._consecutive_char_repeat: int = 0
        self._short_silence_check_at: float = 0.0
        self._last_eager_lang_check_end: Optional[float] = None  # Exp-189 버스트 쿨다운
        # 직전 eager 감지 결과(실패 시 None). 쿨다운으로 재감지를 건너뛴 화자전환에서
        # "언어가 그대로인가" 판정에만 재사용한다 — 쿨다운 창(_EAGER_LANG_COOLDOWN_SECS)
        # 안에서만 참조하므로 값의 노후도는 그 창 길이로 자동 상한이 걸린다.
        self._last_eager_lang_result: Optional[str] = None
        self._recent_emitted_words: List[str] = []  # 중복 방출 계측용 최근 방출 단어(정규화) tail
        # P2 스크립트 불일치 게이트: 실측(TokenTrace)상 배치가 보통 1~3 토큰 단위라
        # 한 배치만으로는 TTR 판정 표본이 부족하다 — detected_language와 반대
        # 스크립트로만 구성된 배치가 연속될 때 그 단어들을 여기 누적한다.
        self._script_mismatch_streak: List[str] = []
        # CASE3 앵커 반복 게이트: 최근 방출 단어 롤링 윈도우(스크립트 무관, 위
        # _find_anchor_repeat_storm 참고). _recent_emitted_words(최근 10개, SwitchTaxMeasure
        # 계측 전용)와 별도 상태 — 이 게이트는 40단어 윈도우가 필요해 재사용하지 않는다.
        self._anchor_repeat_window: List[str] = []
        # 스크립트-앵커 재감지 게이트: 잠긴 detected_language와 반대 스크립트로만 구성된
        # 방출 단어의 연속(streak) + 시작/끝 절대시각(T초 문턱 판정용). 상수 주석 참조.
        self._script_anchor_streak: List[str] = []
        self._script_anchor_streak_start: Optional[float] = None
        self._script_anchor_streak_end: Optional[float] = None

        if asr.tokenizer:
            self.model.tokenizer = asr.tokenizer
            self.model.state.tokenizer = asr.tokenizer

    @property
    def _last_emit_end(self) -> float:
        return self.__last_emit_end

    @_last_emit_end.setter
    def _last_emit_end(self, value: float) -> None:
        """마지막 방출 시점 audio end. decoder state의 last_emit_end로 미러한다(Exp-192).

        미러 이유: 언어전환 트림의 동적 keep(_apply_detected_language,
        align_att_base.compute_dynamic_keep)이 모델 계층에서 이 값을 읽어야 하는데
        소유자는 backend라 직접 보이지 않는다. setter 미러로 모든 기존 대입 지점
        (__init__/end_silence/new_speaker/stall 워치독/배치필터/process_iter)이
        자동 동기화된다.
        """
        self.__last_emit_end = value
        # 방어적 미러: 테스트 스텁 등 model/state가 아직 없는 인스턴스에서도 대입 자체는
        # 성공해야 한다(미러 실패 시 compute_dynamic_keep이 None 폴백으로 안전).
        model = getattr(self, "model", None)
        state = getattr(model, "state", None) if model is not None else None
        if state is not None:
            state.last_emit_end = value

    def _resolve_session_cfg(self, language):
        """세션 언어 오버라이드가 있으면 AlignAttConfig 얕은 사본을 반환한다.

        language가 None(미지정)이면 전역 cfg를 그대로 반환 — auto 기본 동작이
        객체 수준까지 변경 전과 동일하다. "auto" 문자열은 None으로 접지 않는다
        (=세션 강제 auto, 서버 --lan이 무엇이든 auto로 덮음). 번역 태스크
        (direct_english_translation)는 공유 asr.tokenizer가 전역 언어 기준으로
        model.tokenizer를 덮어써(§__init__ 아래) 세션 오버라이드와 충돌하므로
        무시하고 경고한다.
        """
        base_cfg = self.asr.cfg
        if language is None:
            return base_cfg
        if getattr(self.asr, "direct_english_translation", False) and language != base_cfg.language:
            logger.warning(
                "[SessionLang] 번역 태스크에서는 세션 언어 오버라이드 미지원 — 무시 (session=%s, global=%s)",
                language, base_cfg.language,
            )
            return base_cfg
        return dataclasses.replace(base_cfg, language=language)

    def _create_alignatt(self):
        """Create the AlignAtt decoder instance based on ASR mode."""
        cfg = self._session_cfg
        if self.asr.use_full_mlx and HAS_MLX_WHISPER:
            return MLXAlignAtt(cfg=cfg, mlx_model=self.asr.mlx_model)
        else:
            return AlignAtt(
                cfg=cfg,
                loaded_model=self.asr.shared_model,
                mlx_encoder=self.asr.mlx_encoder,
                fw_encoder=self.asr.fw_encoder,
            )

    def start_silence(self):
        tokens, processed_upto = self.process_iter(is_last=True)
        return tokens, processed_upto

    def end_silence(self, silence_duration, offset):
        """Handle silence period."""
        self.end += silence_duration
        long_silence = silence_duration >= MIN_DURATION_REAL_SILENCE
        # 시나리오 튜닝(Phase A) — CLI --short-lang-reset-secs 오버라이드, 미지정/미설정
        # (__init__ 우회 테스트 포함) 시 기존 모듈 상수로 폴백.
        short_lang_reset_secs = getattr(self, "short_lang_reset_secs", None) or MIN_DURATION_SHORT_LANG_RESET
        # 계측용(행동 비변경): 어느 분기를 타는지는 아래 if/elif와 동일 조건으로 별도 계산해
        # 로그 라벨만 만든다 — 기존 if/elif 조건식 자체는 건드리지 않는다.
        _short_cond = (
            silence_duration >= short_lang_reset_secs
            and self.model.cfg.language == "auto"
            and self.model.state.detected_language is not None
        )
        logger.info(
            "[EndSilence] dur=%.2fs branch=%s det_lang=%s lang_before_reset=%s",
            silence_duration, "long" if long_silence else ("short" if _short_cond else "none"),
            self.model.state.detected_language, self.model.state.lang_before_reset,
        )
        if not long_silence:
            gap_len = int(16000 * silence_duration)
            if gap_len > 0:
                if self.asr.use_full_mlx:
                    gap_silence = np.zeros(gap_len, dtype=np.float32)
                else:
                    gap_silence = torch.zeros(gap_len)
                self.model.insert_audio(gap_silence)
        if long_silence:
            self.model.refresh_segment(complete=True)
            logger.info(
                "[EndSilence] long-silence 리셋 직전(폐기 예정): det_lang=%s→None lang_before_reset=%s→None",
                self.model.state.detected_language, self.model.state.lang_before_reset,
            )
            # 언어 고정 세션: None 리셋 시 재감지 없어 고착 → 고정 언어 유지
            self.model.state.detected_language = (
                None if self.model.cfg.language == "auto" else self.model.cfg.language
            )
            self.model.state.lang_before_reset = None   # 긴 침묵 = 문장 경계, 전환 판정 불필요
            self.model.state.pending_retract_from = None   # 긴 침묵 = 진짜 문장 경계, 철회 arm 무효화
            self.model.state.pending_prev_language = None
            self.model.state.pending_retract_floor = None
            self.model.state.first_timestamp = None     # 재감지 조건 충족
            self.model.global_time_offset = silence_duration + offset
            self.model.state.quality_suppress_streak = 0  # 침묵 경계 넘어 streak 누적 → 엉뚱한 refresh 방지
            self._last_emitted_word = None
            self._last_emit_end = self.end
            self._consecutive_char_repeat = 0
            self._short_silence_check_at = 0.0
            self._script_mismatch_streak = []
            self._anchor_repeat_window = []
            self._reset_script_anchor_streak()
        elif (
            silence_duration >= short_lang_reset_secs
            and self.model.cfg.language == "auto"
            and self.model.state.detected_language is not None
        ):
            self._short_silence_check_at = self.end + 1.5

    def _check_short_silence_language(self):
        """짧은 pause 후 1.5s 오디오 누적 시점에 언어 재감지. 전환 확인 시 전환 프로토콜 적용.

        (버그 수정) 기존엔 create_tokenizer+init_context만 호출하고 init_tokens()를 누락해
        state.tokens[0]의 SOT 언어 토큰이 옛 언어로 잔존했다 → 감지만 되고 디코딩에 미적용.
        재작성된 _apply_detected_language 호출로 SOT 토큰 갱신 + 경계 절단 + 문장 경계 arm.
        """
        new_lang = self.model.detect_current_language(window_secs=1.5, min_prob=0.90)
        if new_lang is not None and new_lang != self.model.state.detected_language:
            logger.info(
                "[ShortSilenceLangCheck] 언어 전환 감지: %s → %s",
                self.model.state.detected_language, new_lang,
            )
            self.model._apply_detected_language(new_lang)

    def insert_audio_chunk(self, audio: np.ndarray, audio_stream_end_time):
        """Append an audio chunk to be processed by SimulStreaming."""
        self.end = audio_stream_end_time
        if self.asr.use_full_mlx:
            self.model.insert_audio(audio)
        else:
            audio_tensor = torch.from_numpy(audio).float()
            self.model.insert_audio(audio_tensor)

    def new_speaker(self, change_speaker: ChangeSpeaker):
        """Handle speaker change event.

        경계 재디코딩: held 음역을 final 확정하지 않고(flush 생략), 최근 오디오(경계 구간)를
        complete=False 로 유지해 새 화자 언어로 재디코딩한다. refresh 전에 최근 1.5s 윈도우로
        언어를 즉시 재감지하고, 성공 시 refresh 후 토크나이저를 교정한다(실패 시 None → 기존 2.0s 폴백).

        since_offset(화자전환 시각의 버퍼상대 오프셋)을 넘겨 1.5s 창이 화자전환 이전(직전 화자)
        오디오까지 무조건 포함하지 않도록 한다 — 전환 직후엔 새 화자 오디오가 아직 1.5s보다
        짧게 쌓여 있을 수 있고, 이때 창 전체를 쓰면 대부분 직전 화자 오디오라 그 언어로 오판된다
        (ytn2 CASE2 경계2: eager=en 오판 → 새 화자(KO) 문장 "Thank you" 필러 폭주로 유실).
        """
        # 1. refresh 전 버퍼로 새 화자 언어 즉시 감지 (경계 오디오가 아직 버퍼에 있음)
        # global_time_offset은 아직 change_speaker.start로 갱신되기 전(§2 아래)이므로
        # 현재 버퍼 시작의 절대 시각 그대로다 — 화자전환 절대시각과의 차이가 버퍼상대 오프셋.
        lang_locked = self.model.cfg.language != "auto"
        boundary_offset = change_speaker.start - self.model.global_time_offset
        # 쿨다운으로 재감지를 건너뛴 경우의 직전 결과. eager와 분리해 둔다 — eager에 그대로
        # 실으면 아래 _apply_detected_language까지 타서 Exp-189가 억제하려던 flip-flop 구간의
        # 토크나이저 재적용이 되살아난다. 이 값은 재디코딩 스킵 판정에만 쓴다.
        eager_cached = None
        if lang_locked:
            # 언어 고정 세션: 화자전환 시 언어 재감지 안 함(인코더 forward 절약 +
            # 오전환에 의한 세션 고정 파괴 방지). 경계 재디코딩 자체는 아래에서 유지.
            eager = None
        else:
            last_check_end = getattr(self, "_last_eager_lang_check_end", None)
            if last_check_end is not None and self.end - last_check_end < _EAGER_LANG_COOLDOWN_SECS:
                # Exp-189: diar flip-flop 버스트 억제 — 직전 eager 체크로부터 얼마
                # 안 지나 또 화자전환 이벤트가 오면 재감지를 건너뛴다(상단 상수 주석 참조).
                logger.info(
                    "[NewSpeaker] eager 언어체크 쿨다운 스킵 (마지막 체크 %.2fs 전, 문턱 %.2fs)",
                    self.end - last_check_end, _EAGER_LANG_COOLDOWN_SECS,
                )
                eager = None
                eager_cached = getattr(self, "_last_eager_lang_result", None)
            else:
                eager = self.model.detect_current_language(
                    window_secs=1.5, min_prob=0.85, since_offset=boundary_offset,
                )
                self._last_eager_lang_check_end = self.end
                # 감지 실패(None)도 그대로 저장한다 — 더 오래된 성공값이 남아 재사용되면
                # 실제보다 확신이 센 판정이 된다.
                self._last_eager_lang_result = eager
        logger.info(
            "[NewSpeaker] spk=%s→%s det_before=%s eager=%s",
            self.model.state.speaker, change_speaker.speaker,
            self.model.state.detected_language, eager,
        )
        # 1-b. 같은 언어가 확정된 화자전환은 경계 재디코딩을 건너뛴다.
        # 경계 재디코딩의 목적은 "새 화자의 언어로 다시 읽기"인데, 언어가 그대로면 그 목적이
        # 없다. 그런데도 refresh_segment는 init_tokens()로 디코더 prefix(이미 확정한 토큰)를
        # 버리면서 그 발화가 담긴 오디오는 keep_secs만큼 남겨, 다음 패스가 같은 구간을 백지에서
        # 다시 전사해 중복 방출을 만든다 — ytn2 "우선 우선"/"왕성 왕성한"이 전부 언어가 바뀌지
        # 않은(det_before=ko, eager=ko) 화자 라벨 변경 경계에서 재현됐다. 화자 귀속만 갱신하면
        # 화자전환 문장 분리는 token.speaker 변화로 그대로 실현된다.
        # 근거는 이번 eager 감지 결과, 없으면 쿨다운 직전 결과(eager_cached)를 쓴다. 후자는
        # 쿨다운 창 안에서만 존재하므로 최대 _EAGER_LANG_COOLDOWN_SECS 만큼만 낡았고, 쿨다운이
        # 없었다면 어차피 그 값이 이번 판정에 쓰였을 값이다.
        # 둘 다 None(감지 실패)이면 언어 동일을 확신할 수 없으므로 기존 재디코딩 경로를 탄다 —
        # 화자전환 창은 두 화자 음성이 섞여 확신도가 떨어지는데, 그 지점이 곧 실제 언어가
        # 바뀌는 지점일 수 있다. 잘못 스킵하면 새 화자 발화를 이전 언어로 전사해 붕괴하므로
        # (중복 1건보다 훨씬 나쁘다) 불확실할 때는 재디코딩을 택한다.
        lang_evidence = eager if eager is not None else eager_cached
        if (
            lang_evidence is not None
            and self.model.state.detected_language is not None
            and lang_evidence == self.model.state.detected_language
        ):
            logger.info(
                "[NewSpeaker] 같은 언어(%s) 확정%s — 경계 재디코딩 스킵 (중복 방출 방지)",
                lang_evidence, "" if eager is not None else " (쿨다운 직전 결과 재사용)",
            )
            self.model.speaker = change_speaker.speaker
            return
        # 2. flush 생략 + 경계 오디오 유지(complete=False) + 미확정 음역 폐기
        # damage B 수정: 고정 [-2:] 대신, 화자전환 시각(change_speaker.start)부터 현재(self.end)
        # 까지의 실제 경계 오디오 길이만큼만 유지한다 — 그래야 경계 앞쪽(새 화자 발화 서두)이
        # 정책적으로 잘려나가지 않는다. MAX_KEEP으로 상한을 두고(과거 환각 전례),
        # max(..., MARGIN)은 계획에 없는 방어적 클램프 — change_speaker.start가 self.end보다
        # 늦게 도착하는 극단 케이스(음수/0에 가까운 keep_secs)에서도 최소 여유를 보장한다.
        # 시나리오 튜닝(Phase A) — CLI --new-speaker-max-keep-secs 오버라이드, 미지정/미설정
        # (__init__ 우회 테스트 포함) 시 기존 모듈 상수로 폴백.
        new_speaker_max_keep_secs = getattr(self, "new_speaker_max_keep_secs", None) or _NEW_SPEAKER_MAX_KEEP
        keep_secs = min(self.end - change_speaker.start + _NEW_SPEAKER_KEEP_MARGIN, new_speaker_max_keep_secs)
        keep_secs = max(keep_secs, _NEW_SPEAKER_KEEP_MARGIN)
        self.model.refresh_segment(complete=False, keep_secs=keep_secs)
        self.buffer = []
        if not lang_locked:
            # 고정 세션에선 detected_language를 None으로 리셋하면 재감지가 auto 전용이라
            # 영구 None 고착 → 고정 언어를 그대로 유지한다.
            self.model.state.lang_before_reset = self.model.state.detected_language or self.model.state.lang_before_reset
            self.model.state.detected_language = None
            self.model.state.first_timestamp = None
            self.model.state.eager_lang_detect = True
        # 3. 감지 성공 시 토크나이저 즉시 교정 (refresh 후 적용)
        if eager:
            self.model._apply_detected_language(eager)
        # global_time_offset 재계산: change_speaker.start(diar 이벤트 절대시각)를 맹신하지
        # 않는다 — refresh_segment(keep_secs=...)가 실제로 유지한 버퍼 길이는 diar 이벤트
        # 시각과 정확히 일치하지 않을 수 있다(청크 단위 유지량과 diar 이벤트 시각 사이의
        # 불일치). self.end(오디오 스트림의 절대 현재 위치, insert_audio_chunk에서 매 청크
        # 갱신)에서 실제 유지된 버퍼 길이(segments_len())를 빼면 "실제 유지된 버퍼의 시작
        # 절대시각"이 정확히 나온다 — refresh_segment가 이미 실행되어 state.segments가
        # 새 keep_secs 기준으로 정리된 뒤에 계산해야 한다(순서 유지).
        new_global_time_offset = self.end - self.model.segments_len()
        logger.info(
            "[NewSpeaker] spk=%s det_after=%s (eager_applied=%s) keep_secs=%.2f "
            "kept_segments_len=%.2fs global_time_offset=%.2f",
            change_speaker.speaker, self.model.state.detected_language, bool(eager),
            keep_secs, self.model.segments_len(), new_global_time_offset,
        )
        self.model.speaker = change_speaker.speaker
        self.model.global_time_offset = new_global_time_offset
        # eager 감지가 새 언어를 확정해 위 _apply_detected_language가 _trim_segments_to_recent를
        # 호출했다면(전환 감지) cumulative_time_offset에 그 트림량이 누적된 채 남는다. 위
        # new_global_time_offset은 self.end - segments_len()로 절대 계산돼 이미 그 트림량까지
        # 반영된 값이므로, 여기서 소비하지 않고 남겨두면 *다음* refresh_segment 호출 때
        # (global_time_offset += cumulative_time_offset + discarded_len) 같은 트림량이 중복
        # 가산되어 타임스탬프가 실제보다 앞으로 밀리는 skew가 재발한다 — 절대 재계산이
        # 이미 흡수한 값이므로 여기서 리셋해 이중 반영을 막는다.
        self.model.state.cumulative_time_offset = 0.0
        self._last_emitted_word = None
        self._last_emit_end = self.end
        self._consecutive_char_repeat = 0
        self._script_mismatch_streak = []
        self._anchor_repeat_window = []
        self._reset_script_anchor_streak()

    def get_buffer(self):
        concat_buffer = Transcript.from_tokens(tokens= self.buffer, sep='')
        return concat_buffer

    @staticmethod
    def _normalize(text: str) -> str:
        """비교용 정규화: 공백 제거 + NFC 유니코드 정규화."""
        import unicodedata
        return unicodedata.normalize("NFC", text.strip())

    @staticmethod
    def _max_char_run(text: str) -> int:
        """문자열 내 최대 연속 동일 문자 수 반환. 단일음절 반복 환각 감지에 사용."""
        if not text:
            return 0
        max_run = 1
        cur_run = 1
        for i in range(1, len(text)):
            if text[i] == text[i - 1]:
                cur_run += 1
                if cur_run > max_run:
                    max_run = cur_run
            else:
                cur_run = 1
        return max_run

    def _filter_cross_batch_repetitions(self, tokens: List[ASRToken]) -> List[ASRToken]:
        """배치 경계를 넘나드는 연속 반복 토큰 제거 + 단일음절 반복 환각 억제."""
        # 배치 내 한글 단어 4회+ 반복 → cascade 환각 선제 차단
        batch_words = [self._normalize(t.text) for t in tokens if self._normalize(t.text)]
        korean_batch_words = [w for w in batch_words if re.search(r'[가-힣]', w)]
        if len(korean_batch_words) >= 4:
            counts = Counter(korean_batch_words)
            top_word, top_count = counts.most_common(1)[0]
            if top_count >= 4:
                logger.warning(
                    "[BatchRepeatFilter] 배치 내 반복 %r ×%d — 배치 드롭+리셋", top_word, top_count
                )
                self.model.refresh_segment(complete=True)
                self._last_emitted_word = None
                self._last_emit_end = self.end
                self._consecutive_char_repeat = 0
                return []
        result = []
        prev = self._last_emitted_word

        _LEADING_PUNCT = frozenset([".", "。", "!", "?", "！", "？"])
        # 직전 방출 단어가 이미 문장종료 구두점으로 끝난 진짜 중복일 때만 선두 구두점 제거.
        # 아니면 보존 — 직전 단어의 문장끝 온점을 살린다(UI 표시용).
        prev_ends_punct = bool(self._last_emitted_word) and self._last_emitted_word.rstrip()[-1:] in _LEADING_PUNCT
        if prev_ends_punct:
            while tokens and self._normalize(tokens[0].text) in _LEADING_PUNCT:
                logger.debug("[LeadingPunctFilter] 중복 선두 구두점 제거: %r", tokens[0].text)
                tokens = tokens[1:]

        for token in tokens:
            word = self._normalize(token.text)
            if not word:
                result.append(token)
                continue
            if word in ("-", "–", "—"):
                logger.debug("[DashFilter] 순수 대시 토큰 스킵: %r", word)
                continue
            stripped = word.lstrip('-').strip()
            if len(stripped) >= 4 and self._max_char_run(stripped) >= self._CHAR_RUN_THRESHOLD:
                self._consecutive_char_repeat += 1
                logger.debug("[HallucinationFilter] 단일음절반복 억제: %r (count=%d)", word, self._consecutive_char_repeat)
                if self._consecutive_char_repeat >= self._HALLUCINATION_RESET_THRESHOLD:
                    logger.warning(
                        "[HallucinationFilter] 환각 루프 임계치 초과 — context 리셋 (count=%d)",
                        self._consecutive_char_repeat,
                    )
                    self.model.refresh_segment(complete=True)
                    self._consecutive_char_repeat = 0
                    self._last_emitted_word = None
                    prev = None
                continue
            self._consecutive_char_repeat = 0
            if prev is not None and word == prev:
                logger.info("[CrossBatchFilter] 반복 제거: %r (prev=%r)", word, prev)
                continue
            result.append(token)
            prev = word
        if result:
            self._last_emitted_word = self._normalize(result[-1].text)
        return result

    def _update_script_mismatch_streak(self, decoded_text: str, seg_lang) -> bool:
        """P2 게이트의 cross-batch 누적 판정.

        실측(TokenTrace) 확인 결과 한 infer() 배치는 보통 1~3 토큰이라, 배치 1개만
        검사하면 `_is_script_mismatch_filler`의 MIN_WORDS 문턱을 거의 못 넘어 사실상
        무력화된다. 그래서 seg_lang과 반대 스크립트로만 구성된 배치가 연속될 때 그
        단어들을 self._script_mismatch_streak에 누적하고, 누적분이 반복 시그니처를
        보이면 True(드롭)를 반환한다. seg_lang과 같은 스크립트가 섞인 배치가 오면
        정상 콘텐츠 재개로 보고 streak을 리셋한다.
        """
        if seg_lang not in ("ko", "en"):
            self._script_mismatch_streak = []
            return False
        has_hangul = bool(re.search(r'[가-힣]', decoded_text))
        has_latin = bool(re.search(r'[A-Za-z]', decoded_text))
        if seg_lang == "ko":
            is_pure_mismatch = has_latin and not has_hangul
        else:  # "en"
            is_pure_mismatch = has_hangul and not has_latin
        if not is_pure_mismatch:
            self._script_mismatch_streak = []
            return False
        words = [w.lower() for w in _WORD_TOKEN_PATTERN.findall(decoded_text)]
        if not words:
            return False
        self._script_mismatch_streak.extend(words)
        if len(self._script_mismatch_streak) > _SCRIPT_MISMATCH_STREAK_CAP:
            self._script_mismatch_streak = self._script_mismatch_streak[-_SCRIPT_MISMATCH_STREAK_CAP:]
        if _is_script_mismatch_filler(' '.join(self._script_mismatch_streak), seg_lang):
            self._script_mismatch_streak = []
            return True
        return False

    def _update_anchor_repeat_window(self, decoded_text: str) -> bool:
        """CASE3 앵커 반복 게이트의 cross-batch 누적 판정(script-agnostic).

        `_update_script_mismatch_streak`과 달리 seg_lang/스크립트 불일치 전제가 없다 —
        같은 스크립트 안에서 앵커 1개만 정확반복하고 주변부가 변주되는 storm(ytn2
        "김정은"류)까지 잡기 위함이다. 이번 배치 단어를 롤링 윈도우에 잠정 추가해
        storm 여부를 검사하고, storm이면 이번 배치 단어는 윈도우에 반영하지 않은 채
        True(드롭)를 반환한다(반복 유발원을 윈도우에서 제외해 연쇄 재트리거를 줄인다).
        storm이 아니면 윈도우를 갱신하고 False.
        """
        words = [w.lower() for w in _WORD_TOKEN_PATTERN.findall(decoded_text)]
        if not words:
            return False
        candidate = (self._anchor_repeat_window + words)[-_ANCHOR_REPEAT_WINDOW:]
        if _find_anchor_repeat_storm(candidate):
            return True
        self._anchor_repeat_window = candidate
        return False

    def _reset_script_anchor_streak(self):
        self._script_anchor_streak = []
        self._script_anchor_streak_start = None
        self._script_anchor_streak_end = None

    def _update_script_anchor_streak(self, tokens: List[ASRToken]) -> bool:
        """스크립트-앵커 재감지 트리거 판정 (배치 끝 기준 누적).

        잠긴 detected_language와 반대 스크립트인 방출 토큰을 streak에 누적하고,
        배치 처리 후 streak이 N단어 또는 T초 문턱을 넘으면 True(재감지 필요).
        잠긴 스크립트가 포함된 토큰(혼합 포함)이 나오면 정상 콘텐츠 재개로 보고 리셋,
        라틴/한글이 전혀 없는 토큰(숫자·기호)은 중립으로 스킵한다. 배치 끝 기준
        판정이라 배치 내에서 문턱을 넘었다가 잠긴 스크립트로 되돌아간 경우(정상
        혼용)는 발동하지 않는다.

        약어/철자낭독 가드(GOAL_SCRIPTANCHOR_ACRONYM_GUARD): 잠긴 언어가 ko이고 반대
        스크립트(라틴) 판정된 토큰이 낱글자 철자낭독 또는 ALL-CAPS 약어 덩어리(표기
        속성 — _is_acronym_like_latin)면 증거로 세지 않는다(숫자·기호와 동일하게
        중립 스킵 — 산입도 리셋도 안 함). 소문자 자연 영단어·두문자 대문자 단어는
        기존대로 산입해 Exp-175 코드스위칭 커버리지를 유지한다.
        """
        if not SCRIPT_ANCHOR_REDETECT_ENABLED:
            return False
        lang = self.model.state.detected_language
        if self.model.cfg.language != "auto" or lang not in ("ko", "en"):
            return False
        for t in tokens:
            text = t.text or ""
            if _is_opposite_script(text, lang):
                if (
                    SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED
                    and lang == "ko"
                    and _is_acronym_like_latin(text)
                ):
                    logger.debug("[ScriptAnchorRedetect] acronym-skip: %.50s", text.strip())
                    continue  # 중립 스킵 — 산입도 리셋도 안 함(숫자·기호와 동일 취급)
                if not self._script_anchor_streak:
                    self._script_anchor_streak_start = t.start
                self._script_anchor_streak.append(text.strip())
                self._script_anchor_streak_end = t.end
                continue
            has_hangul = bool(re.search(r'[가-힣]', text))
            has_latin = bool(re.search(r'[A-Za-z]', text))
            if not has_hangul and not has_latin:
                continue  # 스크립트 중립(숫자·기호·공백) — 누적도 리셋도 안 함
            self._reset_script_anchor_streak()  # 잠긴 스크립트 포함 → 정상 콘텐츠 재개
        if not self._script_anchor_streak:
            return False
        # 시나리오 튜닝(Phase A) — CLI --script-anchor-n-words 오버라이드, 미지정/미설정
        # (__init__ 우회 테스트 포함) 시 기존 모듈 상수로 폴백.
        script_anchor_n_words = getattr(self, "script_anchor_n_words", None) or _SCRIPT_ANCHOR_N_WORDS
        if len(self._script_anchor_streak) >= script_anchor_n_words:
            return True
        return (
            self._script_anchor_streak_start is not None
            and self._script_anchor_streak_end is not None
            and self._script_anchor_streak_end - self._script_anchor_streak_start
            >= _SCRIPT_ANCHOR_T_SECS
        )

    def _apply_script_anchor_redetect(self, timestamped_words: List[ASRToken]) -> List[ASRToken]:
        """트리거 시 언어 재감지 → 다른 언어 확신 시에만 전환 적용 + 배치 드롭.

        전환 적용은 _apply_detected_language(2.5s 트림 + 마커 arm + retract arm +
        retract_floor 계산 — Exp-174 이후 기존 메커니즘)에 그대로 위임한다. 드롭한
        배치의 마커는 process_iter의 pending 가드에 의해 다음 신언어 배치 앞으로
        이연되고, 드롭한 서두는 트림이 남긴 경계 오디오 재디코딩으로 복구된다.
        refresh_segment는 호출하지 않는다(Exp-163: 재환각+정렬 교란 회귀).
        같은 언어 재확정 시 no-op + streak 리셋(Exp-169: _apply_detected_language의
        무조건 init_tokens/init_context 컨텍스트 소거로 인한 자기강화 재환각 루프 방지).
        None(불확신)이면 미적용 + streak 유지(다음 배치에서 재시도).
        """
        if not self._update_script_anchor_streak(timestamped_words):
            return timestamped_words
        streak_len = len(self._script_anchor_streak)
        streak_span = (self._script_anchor_streak_end or 0.0) - (self._script_anchor_streak_start or 0.0)
        new_lang = self.model.detect_current_language(
            window_secs=_SCRIPT_ANCHOR_REDETECT_WINDOW_SECS,
            min_prob=_SCRIPT_ANCHOR_REDETECT_MIN_PROB,
        )
        locked = self.model.state.detected_language
        if new_lang is None:
            logger.info(
                "[ScriptAnchorRedetect] streak %d단어/%.2fs 반전, 재감지 불확신(None) — 미적용·streak 유지",
                streak_len, streak_span,
            )
            return timestamped_words
        if new_lang == locked:
            logger.info(
                "[ScriptAnchorRedetect] streak %d단어/%.2fs 반전, 재감지=잠긴 언어(%s) 재확정 — no-op·streak 리셋",
                streak_len, streak_span, new_lang,
            )
            self._reset_script_anchor_streak()
            return timestamped_words
        logger.warning(
            "[ScriptAnchorRedetect] 반대스크립트 streak %d단어/%.2fs → 재감지 %s→%s — 전환 적용·배치 드롭: %.200s",
            streak_len, streak_span, locked, new_lang, ' '.join(self._script_anchor_streak),
        )
        self.model._apply_detected_language(new_lang)
        self._reset_script_anchor_streak()
        return []

    def process_iter(self, is_last=False) -> Tuple[List[ASRToken], float]:
        """
        Process accumulated audio chunks using SimulStreaming.

        Returns a tuple: (list of committed ASRToken objects, float representing the audio processed up to time).
        """
        try:
            if self._short_silence_check_at > 0 and self.end >= self._short_silence_check_at:
                self._check_short_silence_language()
                self._short_silence_check_at = 0.0

            timestamped_words = self.model.infer(is_last=is_last)

            if timestamped_words:
                logger.debug("[TokenTrace] infer→%d tokens: %s", len(timestamped_words),
                             " ".join(t.text for t in timestamped_words[:20]))
                decoded_text = ''.join(t.text for t in timestamped_words)
                if _FOREIGN_LANG_PATTERN.search(decoded_text):
                    logger.warning("[ForeignLang] '(speaking in foreign language)' 감지 → 즉시 언어재감지 트리거")
                    # new_speaker와 일관되게 현재 언어를 전환 판정 기준으로 승계한다.
                    # ForeignLang은 방금 방출이 언어혼란(garbage)임을 뜻하므로, 재감지 후 언어가
                    # 달라지면 정당한 전환 → _apply_detected_language의 prev_lang 폴백이 경계
                    # 마커/트림을 발동해야 한다. 미승계 시 prev_lang이 stale해 전환이 누락된다.
                    # 텍스트 드롭(garbage 제거)은 언어 무관 유지. 언어상태 리셋만 auto 가드
                    # — 고정 세션에서 None 리셋하면 재감지가 auto 전용이라 고착된다.
                    if self.model.cfg.language == "auto":
                        self.model.state.lang_before_reset = (
                            self.model.state.detected_language or self.model.state.lang_before_reset
                        )
                        self.model.state.detected_language = None
                        self.model.state.first_timestamp = None
                        self.model.state.eager_lang_detect = True
                        self.model.state.last_lang_switch_time = 0.0
                    # 버려지는 세그먼트 텍스트를 로깅 (단계 C 계측: 정상 텍스트가 함께 유실되는지 감시).
                    dropped = [t for t in timestamped_words if _FOREIGN_LANG_PATTERN.search(t.text)]
                    if dropped:
                        logger.warning("[ForeignLang] 드롭 텍스트: %.200s",
                                       " ".join(t.text for t in dropped))
                    timestamped_words = [t for t in timestamped_words
                                         if not _FOREIGN_LANG_PATTERN.search(t.text)]

            if timestamped_words:
                decoded_text = ''.join(t.text for t in timestamped_words)
                seg_lang = self.model.state.detected_language
                if self._update_script_mismatch_streak(decoded_text, seg_lang):
                    logger.warning(
                        "[ScriptMismatchFilter] lang=%s 반대스크립트 반복 세그먼트 드롭: %.200s",
                        seg_lang, decoded_text,
                    )
                    # ForeignLang과 동일한 재감지 arm 매커니즘을 재사용한다(신규 발명 금지).
                    # refresh_segment는 호출하지 않는다 — Exp-163에서 refresh가 정렬을 교란해
                    # catastrophic 회귀를 일으킨 전례가 있다. 드롭만 하고 언어 재감지만 arm.
                    # 드롭은 언어 무관 유지. 언어 재감지 arm만 auto 가드(고정 시 None 고착 방지).
                    if self.model.cfg.language == "auto":
                        self.model.state.lang_before_reset = (
                            self.model.state.detected_language or self.model.state.lang_before_reset
                        )
                        self.model.state.detected_language = None
                        self.model.state.first_timestamp = None
                        self.model.state.eager_lang_detect = True
                        self.model.state.last_lang_switch_time = 0.0
                    self._reset_script_anchor_streak()  # 언어 재감지 arm — 잠긴 언어 기준 streak 무효화
                    timestamped_words = []

            if timestamped_words:
                # 스크립트-앵커 재감지 게이트: ScriptMismatchFilter(TTR≤0.6 반복 전제)가
                # 통과시키는 "정상 전환"의 지속 반전을 잡는다. AnchorRepeatFilter보다 앞 —
                # 전환 확신 시 배치 드롭이 우선이고, 불확신(None) 시 배치는 그대로 흘러가
                # storm 판정을 받는다.
                timestamped_words = self._apply_script_anchor_redetect(timestamped_words)

            if timestamped_words:
                decoded_text = ''.join(t.text for t in timestamped_words)
                if self._update_anchor_repeat_window(decoded_text):
                    logger.warning(
                        "[AnchorRepeatFilter] 앵커 반복 storm 드롭(script-agnostic): %.200s",
                        decoded_text,
                    )
                    # ForeignLang/ScriptMismatchFilter와 달리 언어 재감지 arm을 하지 않는다
                    # (사이클2 실측으로 확정된 회귀 — bong1 WER 24.5%→113.3% catastrophic).
                    # 근본원인: 이 게이트는 언어전환/스크립트불일치와 무관하게 같은 언어
                    # 중간발화에서도 발동할 수 있다(bong1 실측: detected_language='en' 내내
                    # 정상 유지). 그런데 detected_language=None+eager_lang_detect=True로
                    # 재감지를 arm하면 `_detect_language_if_needed`가 곧 재감지를 트리거하고,
                    # 재감지된 언어가 이전과 같아 is_switch=False라도
                    # `_apply_detected_language`가 무조건 `init_tokens()`/`init_context()`를
                    # 호출해 디코더 컨텍스트를 매번 지운다(align_att_base.py:194-196) —
                    # 이는 이 프로젝트가 규명한 CASE3 근본원인(경계 리프레시 직후 컨텍스트기아
                    # → 저신뢰 재환각)을 게이트 스스로 반복 유발하는 자기강화 루프였다(실측
                    # 로그: 10회 드롭 각각 직후 [FirstTimestamp] 재설정 로그 확인, 그 창구
                    # 안에서 같은 문장이 매회 조금씩 길어지며 재환각 → 결국 창밖으로 escape해
                    # 무방비 폭주). 따라서 드롭만 하고 어떤 언어/컨텍스트 상태도 건드리지
                    # 않는다 — 그 다음 배치는 기존 컨텍스트를 그대로 유지한 채 자연스럽게
                    # 이어서 디코드된다.
                    # 단 스크립트-앵커 streak은 리셋한다 — 이 배치는 storm 쓰레기로 판정돼
                    # 방출되지 않으므로, "실제 방출 토큰의 반전" 전제가 깨진 누적분을 남기면
                    # 다음 배치에서 오발동한다.
                    self._reset_script_anchor_streak()
                    timestamped_words = []

            if not timestamped_words:
                # 디코더 멈춤 복구 워치독: 오디오가 STALL_RECOVER_SEC 이상 전진했는데
                # 토큰이 전혀 안 나오면 디코더가 비-fire 상태(연속 발화 30s+, 침묵 없음)에
                # 빠진 것 → 강제 refresh로 세그먼트/상태를 리셋해 복구한다.
                if not is_last and self.end - self._last_emit_end > STALL_RECOVER_SEC:
                    logger.warning(
                        "SimulStreaming stall recovery: %.1fs without output "
                        "(end=%.1fs) — forcing segment refresh.",
                        self.end - self._last_emit_end, self.end,
                    )
                    self.model.refresh_segment(complete=True)
                    self._last_emitted_word = None
                    self._last_emit_end = self.end
                    self._consecutive_char_repeat = 0
                return [], self.end

            if self.model.cfg.language == "auto" and timestamped_words[0].detected_language is None:
                self.buffer.extend(timestamped_words)
                return [], self.end

            timestamped_words = self._filter_cross_batch_repetitions(timestamped_words)

            # 언어 전환 경계 마커 삽입 (_apply_detected_language가 진짜 전환 시 arm).
            pending = getattr(self.model.state, "pending_language_switch", None)
            if pending is not None and timestamped_words:
                # 중복 방출 계측: 전환 직후 첫 배치가 직전 방출 tail(최근 5개)과 겹치는지.
                # 비교 정규화는 _dedup_norm(양끝 구두점 제거 + 소문자화) — _normalize는
                # NFC+strip뿐이라 `"In."` vs `" In"` 같은 표기차를 겹침으로 못 잡아
                # 실측 인시던트(유령 "In." 중복)를 "겹침 없음"으로 오계측했다.
                # (_dedup_norm은 boundary_reconcile에서 재사용 — 그 모듈은 timed_objects만
                #  import 하므로 순환 참조가 없다.)
                # 관측 전용 계측이다 — timestamped_words는 여기서 절대 수정하지 않는다.
                tail = self._recent_emitted_words[-5:]
                tail_norm = {n for n in (_dedup_norm(w) for w in tail) if n}
                new_words = [_dedup_norm(t.text) for t in timestamped_words]
                new_words = [w for w in new_words if w]
                overlap = sum(1 for w in new_words if w in tail_norm)
                if overlap:
                    logger.warning(
                        "[SwitchTaxMeasure] 전환 직후 배치 %d/%d 단어가 직전 tail과 겹침 (tail=%s)",
                        overlap, len(new_words), tail,
                    )
                else:
                    logger.info("[SwitchTaxMeasure] 전환 직후 배치 겹침 없음 (tail=%s)", tail)
                boundary_t = timestamped_words[0].start
                marker = LanguageSwitch(
                    start=boundary_t, end=boundary_t,
                    detected_language=self.model.state.detected_language,
                    retract_from=getattr(self.model.state, "pending_retract_from", None),
                    prev_language=getattr(self.model.state, "pending_prev_language", None),
                    retract_floor=getattr(self.model.state, "pending_retract_floor", None),
                )
                timestamped_words = [marker] + timestamped_words
                self.model.state.pending_language_switch = None
                self.model.state.pending_retract_from = None
                self.model.state.pending_prev_language = None
                self.model.state.pending_retract_floor = None
                logger.info("[LangSwitch] 문장 경계 마커 방출 @ %.2fs (lang=%s)",
                            boundary_t, self.model.state.detected_language)

            if timestamped_words:
                logger.debug("[TokenTrace] emit→%d tokens: %s", len(timestamped_words),
                             " ".join(t.text for t in timestamped_words[:20]))
                # 계측용 최근 방출 단어 tail 갱신 (마커 제외, 최근 10개 유지)
                emitted = [self._normalize(t.text) for t in timestamped_words
                           if not getattr(t, "is_boundary", None) or not t.is_boundary()]
                emitted = [w for w in emitted if w]
                if emitted:
                    self._recent_emitted_words = (self._recent_emitted_words + emitted)[-10:]
            self.buffer = []
            self._last_emit_end = self.end
            return timestamped_words, self.end
        except Exception as e:
            logger.exception(f"SimulStreaming processing error: {e}")
            return [], self.end

    def warmup(self, audio, init_prompt=""):
        """Warmup the SimulStreaming model."""
        try:
            if self.asr.use_full_mlx:
                # MLX mode: ensure numpy array
                if hasattr(audio, 'numpy'):
                    audio = audio.numpy()
            self.model.insert_audio(audio)
            self.model.infer(True)
            self.model.refresh_segment(complete=True)
            logger.info("SimulStreaming model warmed up successfully")
        except Exception as e:
            logger.exception(f"SimulStreaming warmup failed: {e}")

    def __del__(self):
        gc.collect()
        if not getattr(self.asr, 'use_full_mlx', True) and torch is not None:
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass


class SimulStreamingASR:
    """SimulStreaming backend with AlignAtt policy."""
    sep = ""

    def __init__(self, logfile=sys.stderr, **kwargs):
        self.logfile = logfile
        self.transcribe_kargs = {}

        for key, value in kwargs.items():
            setattr(self, key, value)

        if getattr(self, 'max_context_tokens', None) is None:
            self.max_context_tokens = 0

        if self.decoder_type is None:
            self.decoder_type = 'greedy' if self.beams == 1 else 'beam'

        self.fast_encoder = False
        self._resolved_model_path = None
        self.encoder_backend = "whisper"
        self.use_full_mlx = getattr(self, "use_full_mlx", False)
        preferred_backend = getattr(self, "backend", "auto")
        compatible_whisper_mlx, compatible_faster_whisper = True, True

        model_path_or_dir = self.model_path or getattr(self, 'model_dir', None)
        if model_path_or_dir:
            resolved_model_path = resolve_model_path(model_path_or_dir)
            self._resolved_model_path = resolved_model_path
            self.model_path = str(resolved_model_path)

            model_info = detect_model_format(resolved_model_path)
            compatible_whisper_mlx = model_info.compatible_whisper_mlx
            compatible_faster_whisper = model_info.compatible_faster_whisper

            if not self.use_full_mlx and not model_info.has_pytorch:
                raise FileNotFoundError(
                    f"No PyTorch checkpoint (.pt/.bin/.safetensors) found under {self.model_path}"
                )
            self.model_name = resolved_model_path.name if resolved_model_path.is_dir() else resolved_model_path.stem
        elif self.model_size is not None:
            self.model_name = self.model_size
        else:
            raise ValueError("Either model_size or model_path must be specified for SimulStreaming.")

        is_multilingual = not self.model_name.endswith(".en")

        self.encoder_backend = self._resolve_encoder_backend(
            preferred_backend,
            compatible_whisper_mlx,
            compatible_faster_whisper,
        )
        self.fast_encoder = self.encoder_backend in ("mlx-whisper", "faster-whisper")
        if self.encoder_backend == "whisper":
            self.disable_fast_encoder = True

        # MLX full decoder disabled by default — MLXAlignAtt has known issues
        # with token generation after punctuation. Users can opt-in with
        # --use-full-mlx if they want to test it.
        # if self.encoder_backend == "mlx-whisper" and platform.system() == "Darwin":
        #     if not hasattr(self, '_full_mlx_disabled'):
        #         self.use_full_mlx = True

        self.cfg = AlignAttConfig(
                tokenizer_is_multilingual= is_multilingual,
                segment_length=self.min_chunk_size,
                frame_threshold=self.frame_threshold,
                language=self.lan,
                audio_max_len=self.audio_max_len,
                audio_min_len=self.audio_min_len,
                cif_ckpt_path=self.cif_ckpt_path,
                decoder_type="beam",
                beam_size=self.beams,
                task="translate" if self.direct_english_translation else "transcribe",
                never_fire=self.never_fire,
                init_prompt=self.init_prompt,
                max_context_tokens=self.max_context_tokens,
                static_init_prompt=self.static_init_prompt,
                logprob_threshold=self.logprob_threshold,
                compression_ratio_threshold=self.compression_ratio_threshold,
                lang_restrict_koen=getattr(self, 'lang_restrict_koen', True),
                periodic_lang_check_secs=getattr(self, 'periodic_lang_check_secs', None),
                lang_detect_general_secs=getattr(self, 'lang_detect_general_secs', None),
                nonspeech_prob=getattr(self, 'no_speech_threshold', None) or 0.5,
        )

        # Set up tokenizer for translation if needed
        if self.direct_english_translation:
            self.tokenizer = self.set_translate_task()
        else:
            self.tokenizer = None

        self.mlx_encoder, self.fw_encoder, self.mlx_model = None, None, None
        self.shared_model = None

        if self.use_full_mlx and HAS_MLX_WHISPER:
            logger.info('MLX Whisper backend used.')
            if self._resolved_model_path is not None:
                mlx_model_path = str(self._resolved_model_path)
            else:
                mlx_model_path = mlx_model_mapping.get(self.model_name)
            if not mlx_model_path:
                raise FileNotFoundError(
                    f"MLX Whisper backend requested but no compatible weights found for model '{self.model_name}'."
                )
            self.mlx_model = load_mlx_model(path_or_hf_repo=mlx_model_path)
            self._warmup_mlx_model()
        elif self.encoder_backend == "mlx-whisper":
            # hybrid mode: mlx encoder + pytorch decoder
            logger.info('SimulStreaming will use MLX Whisper encoder with PyTorch decoder.')
            if self._resolved_model_path is not None:
                mlx_model_path = str(self._resolved_model_path)
            else:
                mlx_model_path = mlx_model_mapping.get(self.model_name)
            if not mlx_model_path:
                raise FileNotFoundError(
                    f"MLX Whisper backend requested but no compatible weights found for model '{self.model_name}'."
                )
            self.mlx_encoder = load_mlx_encoder(path_or_hf_repo=mlx_model_path)
            self.shared_model = self.load_model()
        elif self.encoder_backend == "faster-whisper":
            logger.info('SimulStreaming will use Faster Whisper for the encoder.')
            if self._resolved_model_path is not None:
                fw_model = str(self._resolved_model_path)
            else:
                fw_model = self.model_name
            self.fw_encoder = WhisperModel(
                fw_model,
                device='auto',
                compute_type='auto',
            )
            self.shared_model = self.load_model()
        else:
            self.shared_model = self.load_model()

    def _warmup_mlx_model(self):
        """Warmup the full MLX model."""
        warmup_audio = load_file(self.warmup_file)
        if warmup_audio is not None:
            temp_model = MLXAlignAtt(
                cfg=self.cfg,
                mlx_model=self.mlx_model,
            )
            temp_model.warmup(warmup_audio)
            logger.info("Full MLX model warmed up successfully")


    def _resolve_encoder_backend(self, preferred_backend, compatible_whisper_mlx, compatible_faster_whisper):
        choice = preferred_backend or "auto"
        if self.disable_fast_encoder:
            return "whisper"
        if choice == "whisper":
            return "whisper"
        if choice == "mlx-whisper":
            if not self._can_use_mlx(compatible_whisper_mlx):
                raise RuntimeError("mlx-whisper backend requested but MLX Whisper is unavailable or incompatible with the provided model.")
            return "mlx-whisper"
        if choice == "faster-whisper":
            if not self._can_use_faster(compatible_faster_whisper):
                raise RuntimeError("faster-whisper backend requested but Faster-Whisper is unavailable or incompatible with the provided model.")
            return "faster-whisper"
        if choice == "openai-api":
            raise ValueError("openai-api backend is only supported with the LocalAgreement policy.")
        # auto mode
        if platform.system() == "Darwin" and self._can_use_mlx(compatible_whisper_mlx):
            return "mlx-whisper"
        if self._can_use_faster(compatible_faster_whisper):
            return "faster-whisper"
        return "whisper"

    def _has_custom_model_path(self):
        return self._resolved_model_path is not None

    def _can_use_mlx(self, compatible_whisper_mlx):
        if not HAS_MLX_WHISPER:
            return False
        if self._has_custom_model_path():
            return compatible_whisper_mlx
        return self.model_name in mlx_model_mapping

    def _can_use_faster(self, compatible_faster_whisper):
        if not HAS_FASTER_WHISPER:
            return False
        if self._has_custom_model_path():
            return compatible_faster_whisper
        return True

    def load_model(self):
        model_ref = str(self._resolved_model_path) if self._resolved_model_path else self.model_name
        lora_path = getattr(self, 'lora_path', None)
        whisper_model = load_model(
            name=model_ref,
            download_root=getattr(self, 'model_cache_dir', None),
            decoder_only=self.fast_encoder,
            custom_alignment_heads=self.custom_alignment_heads,
            lora_path=lora_path,
        )
        warmup_audio = load_file(self.warmup_file)
        if warmup_audio is not None:
            warmup_audio = torch.from_numpy(warmup_audio).float()
            if self.fast_encoder:
                temp_model = AlignAtt(
                    cfg=self.cfg,
                    loaded_model=whisper_model,
                    mlx_encoder=self.mlx_encoder,
                    fw_encoder=self.fw_encoder,
                )
                temp_model.warmup(warmup_audio)
            else:
                whisper_model.transcribe(warmup_audio, language=self.lan if self.lan != 'auto' else None)
        return whisper_model

    def set_translate_task(self):
        """Set up translation task."""
        if self.cfg.language == 'auto':
            raise ValueError('Translation cannot be done with language = auto')
        return tokenizer.get_tokenizer(
            multilingual=True,
            language=self.cfg.language,
            num_languages=99,
            task="translate"
        )

    def transcribe(self, audio):
        """
        Warmup is done directly in load_model
        """
        pass
