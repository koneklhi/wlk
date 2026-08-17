import logging
import re
from time import time
from typing import Any, List, Optional, Tuple, Union

from whisperlivekit import boundary_reconcile
from whisperlivekit.boundary_reconcile import (
    ZONE1,
    ZONE2_OPPOSITE,
    ZONE2_SAMESCRIPT,
    BoundaryReconciler,
    TombstoneEntry,
)
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

# [SkipProbe] 관측 전용 상수 (거동 무변경 — 로깅 범위만 제한한다).
# 철회 스캔이 lower_bound/silence에서 멈춘 뒤, 그 아래를 이 범위까지만 들여다보고 로깅한다.
# 경로 A(유령 미철회, 실측 84%)의 look-below 폭을 데이터로 정하기 위한 계측이며,
# 상한을 두는 이유는 장창에서 로그가 폭주하지 않게 하기 위함이다.
_SKIP_PROBE_MAX: int = 5              # 경계 1개당 로깅할 최대 후보 수
_SKIP_PROBE_WINDOW_SECS: float = 4.0  # boundary_t 기준 이보다 오래된 토큰은 보지 않는다

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

# MIN_SPEAKER_ATTRIBUTION_SECS(Exp-188): 화자 귀속을 신뢰하는 최소 텍스트 세그먼트 길이(초).
# diarization 백엔드(Sortformer 등)는 아주 짧은 세그먼트(한 음절/한 단어)에서 화자 임베딩이
# 불안정해 순간적으로 오귀속하는 일반적 한계가 있다(diarization 문헌 공통 현상 — 특정
# 언어·데이터 특화 아님). 이 문턱보다 짧은 세그먼트가 직전 확정 화자와 다른 화자로
# max-overlap 판정되면, 그 판정을 신뢰하지 않고 직전 화자를 승계한다 — 노이즈성 화자
# 플립이 문법-조건부 게이트(_gate_decide)의 화자불일치 강제분할(Case B)을 유발하는 것을
# 방지한다(kor1 실측 "강"⏎"요" 절단, Exp-186/188 규명). 정상적인 화자전환(다화자 파일의
# 실제 화자교대)은 대개 이 문턱보다 긴 발화이므로 영향받지 않는다.
MIN_SPEAKER_ATTRIBUTION_SECS: float = 0.5


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
        # 시나리오 튜닝(Phase A) — CLI 오버라이드, 미지정 시 기존 모듈 상수로 폴백(무회귀).
        self.pending_resolve_cap_secs: float = float(
            getattr(args, "pending_resolve_cap_secs", None) or PENDING_RESOLVE_CAP
        )
        self.min_speaker_attribution_secs: float = float(
            getattr(args, "min_speaker_attribution_secs", None) or MIN_SPEAKER_ATTRIBUTION_SECS
        )
        self.finalize_grace_secs: float = float(
            getattr(args, "finalize_grace_secs", None) or FINALIZE_GRACE_SECS
        )
        # diar 경로(무상태 재계산) 플래핑 방지 메모 — 한 번 캡 만료로 분할 확정된 침묵은
        # 이후 재계산에서도 병합으로 되돌리지 않는다. 키 = round(silence.start, 2).
        self.resolved_split_silences: set = set()
        # 비-diar 경로(상태 보유) 전용 — 게이트 판정을 보류 중인 침묵(누적 span 포함).
        self._nondiar_pending_silence: Optional[Silence] = None

        self.all_tokens: List[ASRToken] = []
        self.all_diarization_segments: List[SpeakerSegment] = []
        self.all_translation_segments: List[Any] = []

        # 언어전환 경계 재조정 계층(Exp-192). 플래그(RECONCILE_ENABLED)는 메서드
        # 내부에서 런타임 조회되므로 인스턴스는 항상 만들어 둔다.
        self.reconciler: BoundaryReconciler = BoundaryReconciler()

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
        idx = 0
        n = len(tokens)
        while idx < n:
            t = tokens[idx]
            if t.is_silence() or t.is_boundary():
                if isinstance(t, LanguageSwitch) and t.retract_from is not None:
                    self._retract_stale_language_tokens(
                        t.retract_from, t.prev_language, t.retract_floor,
                        new_lang=t.detected_language,
                    )
                else:
                    # D2: 다음 Silence/일반 LanguageSwitch 마커 도착 → 활성 재조정 창 마감.
                    # (retract_from이 실린 새 LanguageSwitch는 위 철회 경로에서 arm이
                    #  이전 창 resolve 후 재arm 한다.)
                    self.reconciler.on_boundary_marker(
                        "silence" if t.is_silence() else "language_switch"
                    )
                self.all_tokens.append(t)
                idx += 1
                continue
            # 연속 텍스트 토큰 run 수집 — 시간 소유권 dedup은 배치(run) 커버리지로
            # 방향(①드롭/②supersede)을 판정해야 하므로 run 단위로 적용한다.
            run: List[ASRToken] = [t]
            idx += 1
            while idx < n and not (tokens[idx].is_silence() or tokens[idx].is_boundary()):
                run.append(tokens[idx])
                idx += 1
            run = self.reconciler.dedup_batch(run, self.all_tokens)
            for tok in run:
                i = len(self.all_tokens)
                while i > 0:
                    prev = self.all_tokens[i - 1]
                    if getattr(prev, "retracted", False):
                        # tombstone 투명 통과 — 레거시(파괴적 pop)에서는 존재하지 않던 토큰이므로
                        # 재귀속 walk의 판정에 참여시키지 않는다(거동 동일 보존).
                        i -= 1
                        continue
                    if (prev.is_silence()
                            and tok.start + TAIL_REATTACH_EPS < prev.start
                            and prev.start - tok.start <= TAIL_REATTACH_MAX_LOOKBACK_SECS):
                        i -= 1
                        continue
                    break
                self.all_tokens.insert(i, tok)
                # 재조정 창 관측: 신언어 토큰 도착 → 커버 마킹 + D1 진행도 마감 판정
                # (resolve 후 유예 구간에서는 늦은 커버 재대체).
                self.reconciler.observe_new_token(tok)

    def _retract_stale_language_tokens(
        self,
        boundary_t: float,
        prev_lang: Optional[str],
        redecode_floor: Optional[float] = None,
        new_lang: Optional[str] = None,
    ) -> None:
        """언어전환 경계에서 prev_lang으로 커밋된 잔존 토큰을 all_tokens 꼬리에서 철회.

        철회는 파괴적 pop이 아니라 retracted=True(tombstone) 마킹이다 — 토큰은
        all_tokens에 남고 파생 뷰(compute_punctuations_segments)에서만 숨는다.
        철회분은 TombstoneEntry로 재조정 창(BoundaryReconciler.arm)에 등록되어,
        신언어 토큰이 해당 구간을 커버하면 대체(영구), 못 덮으면 복원(un-retract)된다.
        RECONCILE_ENABLED=False면 레거시 파괴적 pop 거동을 그대로 재현한다(전체 롤백).
        LanguageSwitch 마커가 실제로 방출될 때(=새 언어 토큰이 도착했을 때)만 호출된다 —
        재디코딩이 무산되면 마커 자체가 안 나오므로 아무것도 철회되지 않는다(안전한 실패 모드).

        구역 1 — token.start >= boundary_t - RETRACT_EPS: 텍스트 토큰이고
          detected_language == prev_lang이면 무조건 철회.
        구역 2 — [하한, boundary_t - RETRACT_EPS): 같은 조건 + 반대-스크립트(_is_opposite_script)
          면 철회(zone2_opposite). 추가로 재조정 활성 + RECONCILE_SAMESCRIPT_SUBZONE_ENABLED면
          boundary_t - SAMESCRIPT_SUBZONE_SECS 이내 같은 스크립트 토큰("미니스터")도 잠정
          철회(zone2_samescript) — 복원 보장 위에서만 안전한 공격적 철회.
        하한 = redecode_floor(재디코딩 창 시작) 또는 미지정 시 boundary_t - LANG_SWITCH_KEEP_SECS - 1.0.
        역방향 스캔 중 Silence나 boundary 토큰을 만나면 즉시 중단(경계를 넘어 철회하지 않음).
        prev_lang과 반대 방향 언어로 스탬프된 토큰은 절대 건드리지 않는다.
        """
        if prev_lang is None:
            return
        reconcile_on = boundary_reconcile.RECONCILE_ENABLED
        subzone_on = reconcile_on and boundary_reconcile.RECONCILE_SAMESCRIPT_SUBZONE_ENABLED
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
        zone_counts = {ZONE1: 0, ZONE2_OPPOSITE: 0, ZONE2_SAMESCRIPT: 0}
        entries: List[TombstoneEntry] = []
        stopped_by = "start_of_buffer"
        stopped_at_idx: Optional[int] = None
        while j >= 0:
            token = self.all_tokens[j]
            if getattr(token, "retracted", False):
                # 이미 tombstone된 토큰은 투명 통과 — 레거시(pop)에서는 리스트에 없던
                # 토큰이므로 scanned/removed 카운트에 넣지 않는다(의미 보존).
                j -= 1
                continue
            if token.is_silence() or token.is_boundary():
                stopped_by = "silence" if token.is_silence() else "boundary"
                stopped_at_idx = j
                break
            if token.start < lower_bound:
                stopped_by = "lower_bound"
                stopped_at_idx = j
                break
            scanned += 1
            if token.detected_language == prev_lang:
                zone = None
                if token.start >= boundary_t - RETRACT_EPS:
                    zone = ZONE1
                elif _is_opposite_script(token.text, prev_lang):
                    zone = ZONE2_OPPOSITE
                elif (subzone_on
                        and token.start >= boundary_t - boundary_reconcile.SAMESCRIPT_SUBZONE_SECS):
                    # 구역2 확대: 같은 스크립트 prev_lang 토큰의 잠정 철회 — 신언어가
                    # 커버하면 이중언어 중복("미니스터."→"Minister...")이 소멸하고,
                    # 못 덮으면 resolve에서 복원되므로 순유실이 없다.
                    zone = ZONE2_SAMESCRIPT
                if zone is not None:
                    # gap_prev = 직전 텍스트 토큰과의 간격. 판정에는 쓰지 않고 resolve의
                    # [Restore]/[Replace] 로그로 흘려보내 2차 판별자 분포를 수집한다.
                    prev_tok = self._prev_text_token(j)
                    gap_prev = (
                        token.start - prev_tok.start
                        if prev_tok is not None and prev_tok.start is not None
                        else -1.0
                    )
                    logger.info(
                        "[Retract] 철회: %r start=%.2f prev_lang=%s zone=%s gap_prev=%.2f",
                        token.text, token.start, prev_lang, zone, gap_prev,
                    )
                    if reconcile_on:
                        token.retracted = True
                        entries.append(TombstoneEntry(token=token, zone=zone, gap_prev=gap_prev))
                    else:
                        self.all_tokens.pop(j)  # 레거시 파괴적 철회(롤백 거동)
                    zone_counts[zone] += 1
                    removed += 1
            j -= 1
        # 진단용 요약 — [Retract] 0건이 "대상 없음"인지 "Silence/하한에 조기 차단"인지
        # 구분하기 위함(Exp-171 스크리닝에서 0건 관측 후 추가). scanned=0인데
        # stopped_by="silence"면 마커 직전에 바로 침묵이 있어 애초에 스캔 자체가
        # 거의 일어나지 못한 것 — 이 비율이 높으면 Silence 정지 규칙이 과도하게
        # 보수적인지(예: 아주 짧은 Silence는 통과) 재검토가 필요하다는 신호.
        # zones 필드는 말미 추가라 기존 [RetractScan] 파서(search 기반)와 호환된다.
        logger.info(
            "[RetractScan] boundary_t=%.2f prev_lang=%s scanned=%d removed=%d stopped_by=%s "
            "zones=z1:%d,z2opp:%d,z2same:%d",
            boundary_t, prev_lang, scanned, removed, stopped_by,
            zone_counts[ZONE1], zone_counts[ZONE2_OPPOSITE], zone_counts[ZONE2_SAMESCRIPT],
        )
        self._log_skipped_retract_candidates(
            stopped_by, stopped_at_idx, boundary_t, prev_lang, lower_bound,
        )
        if reconcile_on:
            # 재조정 창 arm — 철회 0건이어도 창은 연다(시간 소유권 dedup이 경계 구간
            # 재방출 중복을 잡으려면 창 컨텍스트가 필요). 활성 창이 있으면 arm이
            # 먼저 resolve 한다(활성 최대 1개 불변식).
            self.reconciler.arm(
                boundary_t=boundary_t, floor=lower_bound,
                prev_lang=prev_lang, new_lang=new_lang, entries=entries,
            )

    def _log_skipped_retract_candidates(
        self,
        stopped_by: str,
        stopped_at_idx: Optional[int],
        boundary_t: float,
        prev_lang: Optional[str],
        lower_bound: float,
    ) -> None:
        """관측 전용 — 철회 스캔이 중단된 지점 아래의 prev_lang 후보를 로깅한다(거동 무변경).

        경로 A(유령이 아예 철회되지 않음, 실측 84%)의 원인은 이 스캔이 lower_bound/silence에서
        멈춰 유령에 도달조차 못 하는 것이다. look-below 폭(BELOW_FLOOR_LOOKBACK_SECS)을 데이터로
        정하려면 "중단 지점 바로 아래에 어떤 prev_lang 토큰이, 하한에서 얼마나 떨어져 있었나"가
        필요하다. gap_prev(직전 구언어 토큰과의 간격)는 §7.2 2차 판별자 후보의 분포 수집용이다.
        """
        if stopped_at_idx is None or prev_lang is None:
            return
        if not logger.isEnabledFor(logging.INFO):
            return
        emitted = 0
        j = stopped_at_idx
        while j >= 0 and emitted < _SKIP_PROBE_MAX:
            token = self.all_tokens[j]
            if getattr(token, "retracted", False):
                j -= 1
                continue
            if token.is_silence() or token.is_boundary():
                # 중단 사유가 silence였다면 그 침묵 자체는 건너뛰고 그 아래를 계속 본다.
                if emitted == 0 and stopped_by == "silence" and j == stopped_at_idx:
                    j -= 1
                    continue
                break
            if token.start is None or boundary_t - token.start > _SKIP_PROBE_WINDOW_SECS:
                break
            if token.detected_language == prev_lang:
                prev_tok = self._prev_text_token(j)
                gap_prev = (
                    token.start - prev_tok.start
                    if prev_tok is not None and prev_tok.start is not None
                    else -1.0
                )
                logger.info(
                    "[SkipProbe] stopped_by=%s text=%r start=%.2f below_floor=%.2f "
                    "gap_prev=%.2f opposite=%s boundary_t=%.2f prev_lang=%s",
                    stopped_by, token.text, token.start, lower_bound - token.start,
                    gap_prev, _is_opposite_script(token.text, prev_lang), boundary_t, prev_lang,
                )
                emitted += 1
            j -= 1

    def _prev_text_token(self, idx: int) -> Optional[ASRToken]:
        """idx 바로 앞의 텍스트 토큰(침묵·경계 제외). 없으면 None."""
        k = idx - 1
        while k >= 0:
            t = self.all_tokens[k]
            if not t.is_silence() and not t.is_boundary():
                return t
            k -= 1
        return None

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


    def _punct_split_justified(self, tokens: List[ASRToken], idx: int) -> bool:
        """온점 토큰(tokens[idx])에서 세그먼트를 끊을 음향적 근거가 있는지 판정.

        tokens는 호출자(compute_punctuations_segments)가 만든 가시(비-retracted) 토큰
        리스트다 — tombstone 토큰이 판정에 끼어들지 않도록 인자로 받는다(내부 전용).
        온점 뒤에 (a) 발화 끝 또는 (b) 실제 Silence 토큰이 있을 때만 True. 그 외(다음
        토큰이 일반 텍스트 토큰인 모든 경우, 갭이 크든 작든)는 항상 False로 분할하지
        않는다 — 갭 기반 분기(과거 (c))는 Exp-166 FIX 1에서 제거했다(위 주석 참조).
        스트리밍 디코더가 매기는 토큰 타임스탬프 갭은 실제 음향 침묵과 별개로 벌어질
        수 있어(버퍼 트림·AlignAtt 유보 등) 신뢰 가능한 분할 근거가 못 된다 — 오직
        VAD가 실제로 검출한 침묵(Silence 토큰)과 발화 종료만 근거로 인정한다.
        """
        if idx + 1 >= len(tokens):
            return True  # 발화 끝
        nxt = tokens[idx + 1]
        if nxt.is_silence():
            return True
        return False

    def _punct_split_here(self, tokens: List[ASRToken], idx: int, start_idx: int) -> bool:
        """온점 토큰에서 분할할지: (a)발화끝/(b)Silence[기존] 또는 (c)형태소 종결[신규].

        tokens는 가시 토큰 리스트(위 _punct_split_justified와 동일 — 내부 전용).
        (c)는 온점(.。) 전용 — ?/! 는 소수점·약어 위험이 없어 (a)/(b) 경로만 유지(현행 불변).
        판별은 닫히는 세그먼트 누적 텍스트(온점 앞 어절의 스크립트·종결어미·약어)로 한다.
        """
        if self._punct_split_justified(tokens, idx):
            return True
        closing = "".join(t.text for t in tokens[start_idx: idx + 1])
        stripped = closing.rstrip()
        if not stripped or stripped[-1] not in (".", "。"):
            return False
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
        next_text = nxt.text if (nxt is not None and not nxt.is_silence()
                                 and not nxt.is_boundary()) else None
        return is_genuine_sentence_end(closing, next_text)

    def compute_punctuations_segments(self) -> List[PuncSegment]:
        """Group tokens into segments split by punctuation and explicit silence.

        단일 초크포인트: retracted(tombstone) 토큰은 여기서 한 번만 걸러진다 — 본문
        전체(인덱스 슬라이스 포함)가 가시(visible) 리스트만 사용하므로, 철회/복원은
        all_tokens의 retracted 플래그 토글만으로 파생 뷰에 반영된다.
        """
        visible = [t for t in self.all_tokens if not getattr(t, "retracted", False)]
        segments = []
        segment_start_idx = 0
        for i, token in enumerate(visible):
            if token.is_silence():
                previous_segment = PuncSegment.from_tokens(
                        tokens=visible[segment_start_idx: i],
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
                    tokens=visible[segment_start_idx: i],
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
                if token.has_punctuation() and self._punct_split_here(visible, i, segment_start_idx):
                    segment = PuncSegment.from_tokens(
                        tokens=visible[segment_start_idx: i+1],
                    )
                    segment.punct_boundary = True
                    segments.append(segment)
                    segment_start_idx = i+1

        final_segment = PuncSegment.from_tokens(
            tokens=visible[segment_start_idx:],
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

        if (d_eff is not None and d_eff >= self.silence_hard_secs
                and should_split_after_silence(
                    closing.text, next_seg.text if next_seg is not None else None) is not False):
            return "split", "split_hard"

        key = self._pending_key(silence_seg)
        if key in self.resolved_split_silences:
            return "split", "split_memo"

        b_unresolved = next_seg is None or (diar_mode and getattr(next_seg, "speaker", -1) == -1)
        if b_unresolved:
            cap_expired = (
                audio_time is not None and silence_seg.end is not None
                and (audio_time - silence_seg.end) >= self.pending_resolve_cap_secs
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
                # Exp-187: 이 분할이 (문법상 미종결이어도) 화자전환 때문에 강제된 것인지
                # 표시한다 — _gate_decide의 speaker-mismatch 분기(split_grammar)와 동일 조건.
                # TriggerAssign이 이 침묵을 무조건 silence/punctuation으로 라벨링하던 것을
                # 정정해 speaker_change 우선순위(docs/SENTENCE_FINALIZATION_LOGIC.md §3.4)를
                # 실제로 반영하기 위함.
                if (
                    self.diarization
                    and next_seg is not None
                    and getattr(next_seg, "speaker", -1) != -1
                    and getattr(prev_text, "speaker", -1) != -1
                    and next_seg.speaker != prev_text.speaker
                ):
                    merged_silence.speaker_boundary = True
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
        prev_resolved_speaker: Optional[int] = None
        for punctuation_segment in punctuation_segments:
            if not punctuation_segment.is_silence():
                if diarization_segments and punctuation_segment.start >= diarization_segments[-1].end:
                    diarization_buffer += punctuation_segment.text
                else:
                    max_overlap = 0.0
                    max_overlap_speaker = 1
                    max_overlap_segment = None
                    for diarization_segment in diarization_segments:
                        intersec = self.intersection_duration(punctuation_segment, diarization_segment)
                        if intersec > max_overlap:
                            max_overlap = intersec
                            max_overlap_speaker = diarization_segment.speaker + 1
                            max_overlap_segment = diarization_segment
                    # Exp-188: 승자 diar 세그먼트 자체의 길이로 귀속 신뢰도를 판단한다(ASR
                    # 텍스트 세그먼트 길이가 아님 — 정상적인 짧은 발화/단어도 흔해 그 길이로는
                    # 노이즈와 구분 불가). concatenate_diar_segments()가 동일화자 연속 조각만
                    # 병합하므로, 진짜 화자전환은 보통 여러 조각에 걸쳐 이 문턱보다 길게
                    # 남는 반면, Sortformer의 순간적 오분류(blip)는 앞뒤 동일화자 조각 사이에
                    # 낀 짧은 조각 하나로 고립된다(kor1 실측 "강"⏎"요" 절단, Exp-186/188).
                    diar_seg_dur = (
                        max_overlap_segment.end - max_overlap_segment.start
                        if max_overlap_segment is not None
                        and max_overlap_segment.start is not None and max_overlap_segment.end is not None
                        else None
                    )
                    if (
                        prev_resolved_speaker is not None
                        and max_overlap_speaker != prev_resolved_speaker
                        and diar_seg_dur is not None
                        and diar_seg_dur < self.min_speaker_attribution_secs
                    ):
                        # 짧게 고립된 diar 세그먼트의 화자 귀속 노이즈 — 직전 확정 화자 승계.
                        logger.debug(
                            "[SpeakerAttribution] branch=short_segment_override diar_seg_dur=%.2f "
                            "raw_speaker=%s prev_speaker=%s text=%r",
                            diar_seg_dur, max_overlap_speaker, prev_resolved_speaker, punctuation_segment.text,
                        )
                        punctuation_segment.speaker = prev_resolved_speaker
                    else:
                        punctuation_segment.speaker = max_overlap_speaker
                    prev_resolved_speaker = punctuation_segment.speaker

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
                            logger.debug(
                                "[TriggerAssign] branch=hard_boundary trigger=%s hard_boundary=%s "
                                "closing_speaker=%s segment_speaker=%s",
                                closing.finalize_trigger, getattr(closing, "hard_boundary", False),
                                closing.speaker, segment.speaker,
                            )
                        elif segment.is_silence():
                            if getattr(closing, "gate_pending", False):
                                logger.debug(
                                    "[TriggerAssign] branch=gate_pending trigger=None(보류) is_silence=%s "
                                    "gate_pending=%s closing_speaker=%s",
                                    segment.is_silence(), getattr(closing, "gate_pending", False), closing.speaker,
                                )
                                pass  # 게이트 보류 — trigger 미설정(하류 확정 억제, §확정 유예 이원화)
                            elif getattr(segment, "speaker_boundary", False):
                                # Exp-187: 이 침묵 분할은 화자전환이 강제한 것(_gate_decide
                                # split_grammar, speaker-mismatch)이다 — silence/punctuation으로
                                # 흡수하지 않고 speaker_change 우선순위를 반영한다
                                # (docs/SENTENCE_FINALIZATION_LOGIC.md §3.4: language_switch >
                                # speaker_change > punctuation > silence).
                                closing.finalize_trigger = "speaker_change"
                                logger.debug(
                                    "[TriggerAssign] branch=silence_speaker_boundary trigger=%s "
                                    "speaker_boundary=%s closing_speaker=%s",
                                    closing.finalize_trigger, getattr(segment, "speaker_boundary", False),
                                    closing.speaker,
                                )
                            else:
                                closing.finalize_trigger = "punctuation" if closing.has_punctuation() else "silence"
                                logger.debug(
                                    "[TriggerAssign] branch=silence trigger=%s is_silence=%s "
                                    "has_punctuation=%s closing_speaker=%s",
                                    closing.finalize_trigger, segment.is_silence(),
                                    closing.has_punctuation(), closing.speaker,
                                )
                        elif segment.speaker != closing.speaker:
                            closing.finalize_trigger = "speaker_change"
                            logger.debug(
                                "[TriggerAssign] branch=speaker_change trigger=%s closing_speaker=%s "
                                "segment_speaker=%s punct_boundary=%s",
                                closing.finalize_trigger, closing.speaker, segment.speaker,
                                getattr(closing, "punct_boundary", False),
                            )
                        elif getattr(closing, "punct_boundary", False):
                            closing.finalize_trigger = "punctuation"
                            logger.debug(
                                "[TriggerAssign] branch=punct_boundary trigger=%s punct_boundary=%s "
                                "closing_speaker=%s segment_speaker=%s",
                                closing.finalize_trigger, getattr(closing, "punct_boundary", False),
                                closing.speaker, segment.speaker,
                            )
                        else:
                            closing.finalize_trigger = "speaker_change"
                            logger.debug(
                                "[TriggerAssign] branch=else(fallback) trigger=%s closing_speaker=%s "
                                "segment_speaker=%s punct_boundary=%s",
                                closing.finalize_trigger, closing.speaker, segment.speaker,
                                getattr(closing, "punct_boundary", False),
                            )
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
            elapsed = audio_time - last.start
            prev.finalized = flush or elapsed >= self.finalize_grace_secs
            prev.finalize_trigger = (
                ("punctuation" if prev.has_punctuation() else "silence")
                if prev.finalized else None
            )
            logger.debug(
                "[FinalizeGrace] finalized=%s flush=%s elapsed=%.3f grace_secs=%.3f trigger=%s",
                prev.finalized, flush, elapsed, self.finalize_grace_secs, prev.finalize_trigger,
            )

    # ─── 비-diar 경로 헬퍼(게이트 decide-late 지원) ──────────────────────────

    def _close_current_line(self, trigger: Optional[str]) -> None:
        """current_line_tokens를 확정해 validated_segments에 커밋하고 비운다."""
        if self.current_line_tokens:
            seg = Segment.from_tokens(self.current_line_tokens)
            if seg is not None:
                seg.finalized = True
                seg.finalize_trigger = trigger
                logger.debug(
                    "[CloseLine] trigger=%s text_preview=%r",
                    trigger, (seg.text or "")[:40],
                )
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
        if (d_eff is not None and d_eff >= self.silence_hard_secs
                and should_split_after_silence(closing_text, None) is not False):
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
            and (audio_time - pending.end) >= self.pending_resolve_cap_secs
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

        # D3: 재조정 창 마감 캡 — audio_time 기준(벽시계 금지, 위 fallback 주석과 동일
        # 이유). 세그먼트 조립 전에 호출해 복원/대체가 이번 틱 파생 뷰에 반영되게 한다.
        self.reconciler.check_deadline(audio_time)

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
