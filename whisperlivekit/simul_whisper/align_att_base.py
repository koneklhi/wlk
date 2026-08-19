"""Abstract base class for AlignAtt streaming decoders (PyTorch & MLX)."""
import logging
from abc import ABC, abstractmethod
from typing import Optional

import torch

from whisperlivekit.timed_objects import ASRToken
from whisperlivekit.whisper import DecodingOptions, tokenizer

from .config import AlignAttConfig

DEC_PAD = 50257
LANG_SWITCH_KEEP_SECS = 2.5  # 언어 전환 시 유지할 최근 오디오(초): 감지창 2.0s + 완충 0.5s

# 동적 keep (Exp-192 커밋5): 언어전환 트림의 keep을 "마지막 방출 지점 이후 미방출
# 오디오" 길이에 맞춰 가변화한다 — 고정 2.5s 재절단이 확장 창을 무효화해 신언어
# 서두("In support of these"류)가 재디코딩 범위 밖으로 잘려나가는 유실을 막는다.
# keep = clamp(버퍼끝 절대시각 − last_emit_end + margin, LANG_SWITCH_KEEP_SECS, MAX).
# 상한 5.0s: Exp-166 전례(고정 keep 4.5s에서 방송클로징 환각) 감시 대상 — 동적이라
# 노출 빈도는 낮고 재조정 dedup+QG가 백스톱이지만 상한으로 캡한다.
# last_emit_end는 backend.py(SimulStreamingOnlineProcessor._last_emit_end)가 소유하며
# decoder state의 last_emit_end 미러 필드로 전달된다(모델 계층에서 직접 안 보임).
LANG_SWITCH_DYNAMIC_KEEP_ENABLED = True  # False = 고정 2.5s(기존 동작) — 짝지음 A/B 롤백 플래그
LANG_SWITCH_KEEP_MAX_SECS = 5.0
LANG_SWITCH_KEEP_MARGIN_SECS = 0.3


def compute_dynamic_keep(buffer_end_abs: Optional[float], last_emit_end: Optional[float]) -> float:
    """언어전환 트림 keep(초)을 계산한다 — 순수 함수(유닛 고정용).

    last_emit_end가 None(미설정/미러 부재)이면 기존 고정값 LANG_SWITCH_KEEP_SECS 폴백.
    """
    if last_emit_end is None or buffer_end_abs is None:
        return LANG_SWITCH_KEEP_SECS
    keep = buffer_end_abs - last_emit_end + LANG_SWITCH_KEEP_MARGIN_SECS
    return min(max(keep, LANG_SWITCH_KEEP_SECS), LANG_SWITCH_KEEP_MAX_SECS)

# 세션 초입 언어 프로브 (콜드스타트 데드락 해소): --lan auto에서 first_timestamp(첫 토큰 커밋)
# 설정 전엔 감지가 무기한 보류되는데, 미감지 토크나이저 기본값 <|en|>으로 한국어 단독 음성을
# 디코드하면 garbage → QualityGate 억제 → 커밋 불가 → first_timestamp 영원히 None(데드락).
# 그 사이 refresh/리셋이 서두 오디오를 반복 폐기해 세션 서두 25~71초가 통유실됐다(kor1).
# 2.0s 누적 시 lang_id로 감지를 시도하되 p>=MIN_PROB일 때만 적용 — 미달이면 계속 보류(재시도).
SESSION_START_LANG_PROBE_ENABLED = True  # False = 완전 기존 동작(무기한 보류) — 짝지음 A/B 롤백 플래그
SESSION_START_LANG_MIN_PROB = 0.85  # 프로브 적용 확신도 게이트(틀린 언어 커밋 방지, 무조건 적용 폴백 없음)

# held/UTF-8 방출 계층 seam 수렴 수정 (연속발화 단어 유실, 예 "이러한 플랫폼을 구축하는"→
# "이러한 구축하는"): ① 스테일 pending 재-prepend가 phantom 중간 U+FFFD를 만들어 무공백
# 한국어에서 구 전체가 한 단어로 묶여 skip-소멸(+mojibake 누적), ② 중간 위치 U+FFFD 단어가
# builder에선 skip되는데 handler는 마지막 단어만 hold해 영구 유실되는 계약 불일치를 고친다.
SEAM_CONVERGENCE_FIX_ENABLED = True  # False = 완전 기존 동작 — 짝지음 A/B 측정용 롤백 플래그

# 커밋 계층 UTF-8 위생 (Direction A — 클린 커밋 절단): AlignAtt 스트리밍이 음절 중간에서
# 배치를 커밋하면 마지막 토큰이 반토막 U+FFFD가 되어 디코더 컨텍스트를 오염시킨다. 방출/hold
# 경로는 seam 수정으로 이미 첫 U+FFFD에서 멈추지만 커밋 경로(:869 tokens.append)만 반토막을
# 넘어 전진해 high-water mark를 오염 → 완성 바이트가 재디코딩 못 되고 MAX_PENDING_RETRIES 소진
# 후 드롭(음절/단어 영구 유실). 커밋 직전 new_hypothesis를 첫 U+FFFD 단어 앞 클린 프리픽스로
# 절단(순수 subtractive)해 mark를 깨끗이 유지 → 다음 청크가 그 오디오를 오염 없는 컨텍스트로
# 재디코딩. SEAM_CONVERGENCE_FIX_ENABLED=True와 함께 동작(게이트가 stale 반토막 정리 담당).
CONTEXT_CLEAN_COMMIT_ENABLED = True  # False = 완전 기존 동작 — 짝지음 A/B 롤백 플래그

# 일반(비-eager) 언어감지 누적 오디오 문턱(초). 화자전환 eager 경로의 1.5s와는 별도 —
# CLI --lang-detect-general-secs(cfg.lang_detect_general_secs)로 오버라이드 가능(시나리오
# 튜닝 Phase A). cfg 쪽이 숫자가 아니면(None 미지정·테스트 목객체 등) 이 상수로 폴백한다.
LANG_DETECT_GENERAL_SECS = 2.0

# QG 억제가 구두점/공백만 담고 있으면 refresh streak에 산입하지 않기 위한 문자 집합.
# 실단어가 하나도 없는 억제는 버퍼 폐기(단어 유실) 위험을 감수할 만한 garbage가 아니다.
_PUNCT_ONLY_CHARS = frozenset({'.', '?', '!', '。', '！', '？', ',', ';', ':'})

# ── 경계 보호 보존형 refresh (Exp-177 Type B 삼킴 제거) ────────────────────────
# QG streak refresh의 목적은 "환각 루프를 끊는 것"이지 "오디오를 버리는 것"이 아니다.
# 그런데 언어/화자 전환 직후엔 구언어 토크나이저가 새 언어 오디오를 garbage로 읽어 억제가
# 쉽게 3연속 성립하고, 그때 폐기되는 버퍼가 곧 **새 문장의 서두 오디오**라 비가역 유실이
# 된다(재디코딩으로 복구 불가). 문맥 없이 재시작한 디코더가 그 자리를 환각으로 채우므로
# "첫 어절 유실"과 "환각 폭주"는 같은 사건의 앞뒷면이다.
# 대책: 경계 보호창 이내의 **첫** streak 도달에서만 오디오를 보존하고 디코더 상태(토큰·
# 컨텍스트·attend)만 리셋해, 뒤이어 도착하는 오디오와 함께 서두를 재디코딩할 기회를 남긴다.
# 같은 경계에서 재차 도달하면 기존 폐기로 폴백 → 환각 루프 안전망(Exp-028/154 계열) 유지.
# 보호창 밖·재시도 소진 시 동작은 현행과 100% 동일하므로 비회귀가 구조적으로 보장된다.
BOUNDARY_QG_PRESERVE_ENABLED = True  # False = 완전 기존 동작 — 짝지음 A/B 롤백 플래그
BOUNDARY_PROTECT_SECS = 5.0          # 경계 이벤트로부터 이 시간 이내의 streak만 보호
# 보존 직후 언어 재프로브 창(초) 상한 — garbage 원인이 "오디오 난이도"가 아니라 "언어 오판"일
# 때를 커버한다. detect_current_language는 이미 @torch.no_grad라 신규 forward 경로가 아니다.
BOUNDARY_QG_REPROBE_WINDOW = 2.5
BOUNDARY_QG_REPROBE_MIN_PROB = 0.85
# 동일언어 확인(예 ko→ko)일 때도 보존할지.
#
# **True 고정 권장 — False는 실측으로 기각됐다.** "언어가 이미 옳은데 QG가 3연속 억제한
# 구간은 음성 자체가 어려운 것이니 보존해봐야 환각만 는다"는 가설로 False를 측정했으나
# (짝지음 N=3, 4파일 median 합):
#     OFF  삽입 37 / 삭제 46 (합 83)
#     True 삽입 44 / 삭제 26 (합 70)   ← 최선
#     False삽입 50 / 삭제 51 (합 101)  ← 최악 (양쪽 다 악화)
# 동일언어 보존도 실제로 단어를 복구하고 있었고, 빼자 버퍼 폐기 → 유실 + 문맥 없는
# 재시작 → 환각이라는 원래 실패 사슬이 되살아났다(bong1 삭제 10→38, ytn1 삽입 7→16).
# 즉 "보존이 환각을 만든다"가 아니라 "폐기가 유실과 환각을 **함께** 만든다"가 맞다.
BOUNDARY_QG_PRESERVE_ON_SAME_LANG = True

# ── SOT 위치 사후분포 계측 (계측 전용 — 디코딩 행동 변경 0) ─────────────────────
# infer()의 첫 forward는 new_segment일 때 전체 토큰 시퀀스를 넣으므로 logits shape이
# [beam, T, V]다. 위치 sot_pos(= <|sot|> 토큰 위치)의 logits는 "다음 토큰 = 언어 토큰"
# 분포이고, 이는 lang_id(encoder_feature)가 별도 forward(x=[[sot]])로 계산하는 값과
# 수학적으로 동일하다. 즉 **추가 forward 0회**로 언어 사후분포를 읽을 수 있다.
# 이 계측은 값을 읽어 로깅만 한다 — 분기·반환값·텐서를 일절 바꾸지 않는다.
# False면 계측 자체가 돌지 않는다(짝지음 A/B 롤백 스위치).
SOT_LANG_PROBE_ENABLED = True
# 세션 요약(LangDriftStats) 집계용 문턱 — 카운팅 전용이며 어떤 동작에도 관여하지 않는다.
SOT_PROBE_MISMATCH_P = 0.9      # 잠긴 언어의 반대쪽 재정규화 확률이 이 이상 → mismatch 후보
SOT_PROBE_RESID_HIGH = 0.5      # 비정규화 언어질량 잔차가 이 이상 → off-manifold 후보
SOT_PROBE_TRANSLATE_HIGH = 0.1  # task 위치 <|translate|> 확률이 이 이상 → 이상탐지 후보

# ── Stage 1 섀도우 게이트 (계측 전용 — would_fire 로깅만, 실제 언어 재감지 트리거 없음) ──
# SOT 프로브(위)가 계산하는 p_opp(잠긴 언어의 반대쪽 재정규화 확률)에 게이트를 씌웠을 때
# 실제로 몇 번 발동하는지를 재는 계측이다(언어잠금-Stage0 §"안 B"). 게이트를 전부 통과해도
# `_apply_detected_language`를 절대 호출하지 않는다 — 로깅만. False면 계측 자체가 돌지
# 않는다(짝지음 A/B 롤백 스위치).
STAGE1_SHADOW_ENABLED = True   # 짝지음 A/B 롤백 스위치
STAGE1_TAU = 0.97              # p_opp 문턱
STAGE1_MIN_SEGLEN = 2.0        # 최소 버퍼 — 가장 중요(Exp-189 고신뢰 오탐 배제)
STAGE1_MIN_BATCHES = 3         # 연속 K
STAGE1_MIN_DURATION = 0.8      # 지속 T (10Hz라 K만으론 0.3s) — 1.0에서 완화(bong1 참양성이
                               # dur=0.96s로 40ms 차이로 막혔음. ko 오탐군은 G3(seglen≥2.0)가
                               # 전담 차단하므로 T 완화가 오탐 보호를 깎지 않는다)
STAGE1_COOLDOWN_SECS = 3.0     # last_lang_switch_time 재사용

logger = logging.getLogger(__name__)


def _fmt_prob(v) -> str:
    """key=value 로그용 확률 포맷 — None은 nan으로 찍어 파서가 항상 같은 필드를 본다."""
    return "nan" if v is None else f"{v:.6f}"


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

    def refresh_segment(self, complete=False, keep_secs: Optional[float] = None):
        """세그먼트 버퍼를 리프레시한다.

        keep_secs: None(기본값)이면 기존 동작(고정 마지막 2청크 유지, complete=False +
        len<=2일 땐 전체 폐기) 그대로. 지정하면 complete=False일 때 뒤에서부터 세그먼트를
        누적해 총 길이(초)가 keep_secs 이상이 될 때까지 유지한다(화자전환 경계처럼 폐기량을
        정밀 제어해야 하는 호출부용 — new_speaker 참고).
        """
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
        if not complete and keep_secs is not None:
            kept = []
            total = 0.0
            for seg in reversed(self.state.segments):
                kept.append(seg)
                total += seg.shape[0] / 16000
                if total >= keep_secs:
                    break
            kept.reverse()
            self.state.segments = kept
        elif not complete and len(self.state.segments) > 2:
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
        logger.info(
            "[RefreshSegment] complete=%s lang=%s discarded=%.2fs kept=%.2fs",
            complete, self.state.detected_language, discarded_len, self.segments_len(),
        )
        # Stage 1 섀도우 게이트 증거 리셋 — 버퍼가 잘리므로 이전 seglen 누적 증거는 무효.
        # samelang 머지(Exp-196) 이후 이 한 곳이 refresh·new_speaker 전체재디코딩·긴침묵을
        # 모두 커버한다(동일언어 화자전환 skip 경로는 refresh_segment를 안 부르지만 버퍼도
        # 언어도 안 바꾸므로 리셋이 원래 불필요하다).
        self._stage1_shadow_reset_evidence()

    def segments_len(self):
        return sum(s.shape[0] for s in self.state.segments) / 16000

    def _current_stream_time(self) -> float:
        """현재 버퍼 끝의 절대 스트림 시각(초).

        global + cumulative + 버퍼길이 = 트림/refresh에 불변인 스트림 시계다.
        `_trim_segments_to_recent`는 잘라낸 만큼 cumulative에 누적하고, `refresh_segment`는
        `global += cumulative + discarded` 후 cumulative를 0으로 되돌리므로 두 경로 모두
        이 합을 보존한다 — 경계 이벤트 시각과 streak 도달 시각을 같은 자로 재려면 이 시계를
        써야 한다(버퍼 상대 길이 단독은 트림마다 리셋돼 간격이 무의미해진다).
        """
        return (self.state.global_time_offset
                + self.state.cumulative_time_offset
                + self.segments_len())

    def mark_boundary_event(self, at: Optional[float] = None):
        """언어/화자 전환 경계 발생을 스탬프하고 보존 예산을 되살린다.

        at: 호출부가 스트림 절대시각을 이미 알고 있으면(backend의 self.end) 그 값을 쓴다.
        미지정 시 현재 버퍼 끝 시각으로 스탬프한다.
        """
        self.state.last_boundary_event_at = (
            at if at is not None else self._current_stream_time()
        )
        self.state.qg_preserve_used = False

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
            keep_secs = LANG_SWITCH_KEEP_SECS
            if LANG_SWITCH_DYNAMIC_KEEP_ENABLED:
                # 버퍼끝 절대시각 = global + cumulative + 현재 버퍼 길이 (토큰 절대
                # 타임스탬프 계산식과 동일 좌표계 — infer의 frame*0.02+cumulative,
                # with_offset(global) 참조). 트림 전에 계산해야 한다.
                buffer_end_abs = (self.state.global_time_offset
                                  + self.state.cumulative_time_offset
                                  + self.segments_len())
                last_emit_end = getattr(self.state, "last_emit_end", None)
                keep_secs = compute_dynamic_keep(buffer_end_abs, last_emit_end)
                logger.info(
                    "[LangSwitch] dynamic keep=%.2fs (buffer_end=%.2f last_emit_end=%s)",
                    keep_secs, buffer_end_abs,
                    ("%.2f" % last_emit_end) if last_emit_end is not None else "None",
                )
            self._trim_segments_to_recent(keep_secs)

        self.create_tokenizer(lang)
        self.init_tokens()
        self.init_context()
        self.state.last_attend_frame = -self.cfg.rewind_threshold
        self.state.detected_language = lang

        if is_switch:
            # 다음 새 언어 토큰 앞에 process_iter가 경계 마커를 삽입하도록 arm.
            self.state.pending_language_switch = self.state.global_time_offset + self.segments_len()
            # retract_from은 pending_language_switch와 동일 절대시각(재디코딩 구간 시작점) —
            # process_iter가 마커를 방출할 때 이 시각 기준으로 구언어 잔존 토큰을 철회한다.
            self.state.pending_retract_from = self.state.pending_language_switch
            self.state.pending_prev_language = prev_lang
            # 재디코딩 창 시작(=현재 트림된 버퍼의 절대 시작). 철회는 이 시각 이후 토큰만
            # 대상으로 한다 — 트림이 잘라낸 서두 토큰은 재디코딩으로 재현될 수 없어(① 서두유실)
            # 철회하면 순유실이 된다. pending_language_switch(버퍼 END) − segments_len() = 버퍼 START.
            self.state.pending_retract_floor = self.state.pending_language_switch - self.segments_len()
            # 경계 보호창 arm — 이 직후 구간의 QG streak은 서두 오디오를 폐기하지 않고 보존한다.
            self.mark_boundary_event()

        logger.info("[LangSwitch] 토크나이저 적용: %s (prev=%s, switch=%s, skip_trim=%s)",
                    lang, prev_lang, is_switch, skip_trim)
        # Stage 1 섀도우 게이트 증거 리셋 — 언어가 바뀌면(또는 최초 감지) 이전 증거는 무효.
        self._stage1_shadow_reset_evidence()

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
                # 세션 초입 언어 프로브: first_timestamp 설정 전 무기한 보류(Exp-093)는
                # <|en|> 기본 토크나이저 → garbage → QG 억제 → 커밋 불가의 데드락을 만든다.
                # 2.0s 누적 시 감지를 시도하되 고확신(p>=MIN_PROB)일 때만 적용 — 미달이면
                # 다음 infer 사이클에서 재시도(무조건 적용 폴백 없음; p 미달이 지속되면
                # 기존 커밋 기반 경로가 그대로 폴백으로 작동한다).
                if SESSION_START_LANG_PROBE_ENABLED and self.segments_len() >= 2.0:
                    _, language_probs = self.lang_id(encoder_feature)
                    top_lan, p = max(language_probs[0].items(), key=lambda x: x[1])
                    if p >= SESSION_START_LANG_MIN_PROB:
                        logger.info(
                            "[SessionStartLangProbe] 세션 초입 감지 적용: %s (p=%.4f, segments_len=%.2fs)",
                            top_lan, p, self.segments_len(),
                        )
                        self._apply_detected_language(top_lan)
                    else:
                        logger.debug(
                            "[SessionStartLangProbe] p=%.4f < %.2f — 보류, 다음 사이클 재시도 (top=%s, segments_len=%.2fs)",
                            p, SESSION_START_LANG_MIN_PROB, top_lan, self.segments_len(),
                        )
                    return
                # 프로브 비활성 또는 2.0s 미만: 기존 보류 동작 (Exp-093 안정 동작 — 잦은 _apply_detected_language 리셋으로 인한 반복 폭주 방지)
                logger.debug(
                    "[LangDetectDeferred] 감지 보류: first_timestamp=None, eager_lang_detect=False (segments_len=%.2fs)",
                    self.segments_len(),
                )
                return
            # 화자전환 직후엔 1.5s+확신도≥0.85로 빠른 감지 — 잘못된 언어 고착 방지
            # general(비-eager) 문턱만 cfg.lang_detect_general_secs로 오버라이드 가능 —
            # isinstance 가드는 cfg가 숫자가 아닌 값(None·테스트 Mock 등)일 때 기존 상수로
            # 안전하게 폴백하기 위함(무회귀).
            general_secs = getattr(self.cfg, "lang_detect_general_secs", None)
            if not isinstance(general_secs, (int, float)):
                general_secs = LANG_DETECT_GENERAL_SECS
            threshold = 1.5 if self.state.eager_lang_detect else general_secs
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
        if self.cfg.language != "auto":
            return
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
    def detect_current_language(self, window_secs: float = 1.5, min_prob: float = 0.90,
                                 since_offset: float | None = None):
        """최근 window_secs 초 오디오의 언어를 감지해 반환. 확신도 min_prob 미만이면 None.

        since_offset: 지정하면 버퍼 시작(pos 0) 기준 상대 초 이전의 오디오는 감지에서
        배제한다(하한만 당김 — window_secs 상한 캡은 그대로 유지). 화자전환처럼 버퍼 내
        특정 이벤트 이후 오디오만 봐야 하는 경우에 쓴다: 이벤트 직후엔 새로 쌓인 오디오가
        window_secs보다 짧을 수 있는데, since_offset 없이 무조건 마지막 window_secs를 자르면
        이벤트 이전(예: 직전 화자) 오디오가 섞여 오판할 수 있다(ytn2 CASE2 경계2 — 화자전환
        eager 감지가 아직 대부분 이전 화자 오디오인 1.5s 창을 봐서 새 화자 언어를 놓친 사례).
        미지정 시 기존 동작(마지막 window_secs) 그대로 하위호환 유지.

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
            total_samples = len(all_audio)
            start_idx = max(0, total_samples - window_samples)
            if since_offset is not None:
                since_idx = max(0, int(since_offset * 16000))
                start_idx = max(start_idx, min(since_idx, total_samples))
            if start_idx >= total_samples:
                return None
            recent = all_audio[start_idx:]
            encoder_feature, _ = self._encode(recent)
            _, language_probs = self.lang_id(encoder_feature)
            probs = language_probs[0] if isinstance(language_probs, list) else language_probs
            top_lan, p = max(probs.items(), key=lambda x: x[1])
            passed = p >= min_prob
            logger.info(
                "[ShortSilenceLangCheck] 최근 %.1fs → %s (p=%.4f, thr=%.2f, %s)",
                window_secs, top_lan, p, min_prob, "PASS" if passed else "FAIL",
            )
            return top_lan if passed else None
        except Exception as e:
            logger.debug("[ShortSilenceLangCheck] 감지 실패: %s", e)
            return None

    # === SOT 위치 사후분포 계측 (계측 전용 — 행동 변경 없음) ===

    def _read_sot_posteriors(self, logits) -> Optional[dict]:
        """첫 forward logits에서 SOT/task 위치 사후분포를 읽는다 — 기본은 미지원(None).

        base 기본 구현이 None인 이유: MLX 경로가 첫 forward에서 전 위치 logits를
        반환하는지 미확인이라 안전 폴백이 필요하다. PyTorch(AlignAtt)만 오버라이드한다.
        구현체는 반드시 **logits를 in-place로 건드리지 않아야** 한다(호출 직후
        infer()가 같은 텐서를 logits[:, -1, :]로 재사용한다).
        """
        return None

    def _sot_probe_stats(self) -> dict:
        """세션 누적 계측 카운터 — 인스턴스(=세션) 단위로 lazy 생성한다."""
        stats = getattr(self, "_sot_lang_probe_stats", None)
        if stats is None:
            stats = {
                "probes": 0,
                "locked_ko": 0,
                "locked_en": 0,
                "locked_none": 0,
                "mismatch_candidates": 0,
                "high_resid": 0,
                "high_translate": 0,
                "max_resid": 0.0,
                "max_p_translate": 0.0,
            }
            self._sot_lang_probe_stats = stats
        return stats

    def _log_sot_lang_probe(self, logits) -> None:
        """[SotLangProbe] DEBUG 로그 1줄 + 세션 카운터 누적. 로깅 외 부작용 없음."""
        if not SOT_LANG_PROBE_ENABLED:
            return
        try:
            self._sot_lang_probe_impl(logits)
        except Exception as e:  # 계측 실패가 디코딩을 절대 막지 않게 한다
            logger.debug("[SotLangProbe] 산출 실패(무시): %s", e)

    def _sot_lang_probe_impl(self, logits) -> None:
        info = self._read_sot_posteriors(logits)
        if info is None:
            return

        stats = self._sot_probe_stats()
        stats["probes"] += 1
        locked = self.state.detected_language
        if locked == "ko":
            stats["locked_ko"] += 1
        elif locked == "en":
            stats["locked_en"] += 1
        else:
            stats["locked_none"] += 1

        p_ko = info.get("p_ko")
        p_en = info.get("p_en")
        resid = info.get("resid")
        p_translate = info.get("p_translate")

        # Stage 1 섀도우 게이트(계측 전용) — locked/p_ko/p_en을 그대로 재사용한다.
        # getattr 방어: 이 메서드를 SimpleNamespace 이중체(fake)에 types.MethodType으로
        # 부분 바인딩해 재사용하는 기존 SOT 프로브 단위테스트(test_sot_lang_probe.py)가
        # 이 신규 훅 부재로 깨지지 않게 한다 — 실제 AlignAtt 인스턴스는 항상 보유한다.
        stage1_gate = getattr(self, "_stage1_shadow_gate", None)
        if stage1_gate is not None:
            stage1_gate(locked, p_ko, p_en)

        # mismatch 후보 = 잠긴 언어의 "반대쪽" 재정규화 확률이 문턱 이상 (적용은 하지 않는다)
        if locked == "en" and p_ko is not None and p_ko >= SOT_PROBE_MISMATCH_P:
            stats["mismatch_candidates"] += 1
        elif locked == "ko" and p_en is not None and p_en >= SOT_PROBE_MISMATCH_P:
            stats["mismatch_candidates"] += 1
        if resid is not None:
            stats["max_resid"] = max(stats["max_resid"], resid)
            if resid >= SOT_PROBE_RESID_HIGH:
                stats["high_resid"] += 1
        if p_translate is not None:
            stats["max_p_translate"] = max(stats["max_p_translate"], p_translate)
            if p_translate >= SOT_PROBE_TRANSLATE_HIGH:
                stats["high_translate"] += 1

        if not logger.isEnabledFor(logging.DEBUG):
            return
        # t_abs는 토큰 절대 타임스탬프와 동일 좌표계 (global + cumulative + 현재 버퍼 길이).
        t_abs = (self.state.global_time_offset
                 + self.state.cumulative_time_offset
                 + self.segments_len())
        lang_locked = getattr(self.cfg, "language", "auto") != "auto"
        logger.debug(
            "[SotLangProbe] t_abs=%.2f batch=%d locked=%s seglen=%.2f "
            "p_ko=%s p_en=%s p_abs_ko=%s p_abs_en=%s resid=%s H_lang=%s "
            "p_translate=%s p_transcribe=%s p_nospeech=%s lang_locked=%s",
            t_abs, stats["probes"], locked, self.segments_len(),
            _fmt_prob(p_ko), _fmt_prob(p_en),
            _fmt_prob(info.get("p_abs_ko")), _fmt_prob(info.get("p_abs_en")),
            _fmt_prob(resid), _fmt_prob(info.get("H_lang")),
            _fmt_prob(p_translate), _fmt_prob(info.get("p_transcribe")),
            _fmt_prob(info.get("p_nospeech")), lang_locked,
        )

    def _log_lang_drift_stats(self) -> None:
        """[LangDriftStats] WARNING 세션 요약 — 발동/관측 카운트를 남긴다.

        probes=0도 명시적으로 1회 찍는다(0-firing 회차 = 노이즈 대조군 식별용).
        카운터가 직전 요약 이후 변하지 않았으면 중복 출력을 생략한다 — 값은 누적이라
        직전 라인이 이미 최종 합계를 담고 있다(is_last는 침묵마다 호출돼 잦다).
        """
        if not SOT_LANG_PROBE_ENABLED:
            return
        try:
            stats = self._sot_probe_stats()
            last = getattr(self, "_sot_lang_probe_last_summary", None)
            if last is not None and last == stats["probes"]:
                return
            self._sot_lang_probe_last_summary = stats["probes"]
            logger.warning(
                "[LangDriftStats] probes=%d locked_ko=%d locked_en=%d locked_none=%d "
                "mismatch_candidates=%d high_resid=%d high_translate=%d "
                "max_resid=%.4f max_p_translate=%.4f lang_locked=%s",
                stats["probes"], stats["locked_ko"], stats["locked_en"], stats["locked_none"],
                stats["mismatch_candidates"], stats["high_resid"], stats["high_translate"],
                stats["max_resid"], stats["max_p_translate"],
                getattr(getattr(self, "cfg", None), "language", "auto") != "auto",
            )
        except Exception as e:  # 계측 실패가 디코딩을 절대 막지 않게 한다
            logger.debug("[LangDriftStats] 요약 실패(무시): %s", e)

    # === Stage 1 섀도우 게이트 (계측 전용) ===

    def _stage1_shadow_state(self) -> dict:
        """Stage 1 섀도우 게이트 증거/세션 상태 — `_sot_probe_stats()`와 동일한 인스턴스
        (세션) 단위 lazy 생성 패턴을 따른다.

        count/first_t/lang = G1~G4를 만족한 연속 증거(G5 판정용, refresh_segment·
        _apply_detected_language에서 리셋됨). would_fire/blocked_by = 세션 누적 통계
        ([Stage1ShadowStats] 요약용) — DecoderState에 필드를 추가하지 않는다(섀도우는
        디코더 상태가 아니라 계측이다).
        """
        state = getattr(self, "_stage1_shadow_gate_state", None)
        if state is None:
            state = {
                "count": 0,
                "first_t": None,
                "lang": None,
                "would_fire": 0,
                "blocked_by": {"g1": 0, "g2": 0, "g3": 0, "g4": 0, "g5": 0, "g6": 0, "g7": 0},
            }
            self._stage1_shadow_gate_state = state
        return state

    def _stage1_shadow_reset_evidence(self) -> None:
        """증거(count/first_t/lang) 리셋 — refresh_segment()·_apply_detected_language()에서 호출.

        섀도우 상태가 아직 생성되지 않았으면(계측 비활성 등) 아무 것도 하지 않는다 —
        여기서 lazy 생성을 유발해 부작용을 만들지 않기 위함이다.
        """
        state = getattr(self, "_stage1_shadow_gate_state", None)
        if state is None:
            return
        state["count"] = 0
        state["first_t"] = None
        state["lang"] = None

    def _stage1_shadow_gate(self, locked, p_ko, p_en) -> None:
        """[Stage1Shadow] would_fire 계측 진입점.

        게이트를 전부 통과해도 `_apply_detected_language`를 절대 호출하지 않는다 — 순수
        로깅(섀도우 모드). False면 계측 자체가 돌지 않는다(짝지음 A/B 롤백 스위치).
        """
        if not STAGE1_SHADOW_ENABLED:
            return
        try:
            self._stage1_shadow_gate_impl(locked, p_ko, p_en)
        except Exception as e:  # 계측 실패가 디코딩을 절대 막지 않게 한다
            logger.debug("[Stage1Shadow] 산출 실패(무시): %s", e)

    def _stage1_shadow_gate_impl(self, locked, p_ko, p_en) -> None:
        st = self._stage1_shadow_state()

        # G1: auto 세션만(ko/en 고정 세션은 원천 차단 — 인계서 §4 기각 조건)
        if getattr(self.cfg, "language", "auto") != "auto":
            st["blocked_by"]["g1"] += 1
            return
        # G2: "잠긴 언어의 반대쪽"이 성립하려면 언어가 이미 감지돼 있어야 한다
        if self.state.detected_language is None:
            st["blocked_by"]["g2"] += 1
            return

        seglen = self.segments_len()
        # G3: 최소 버퍼 길이 — 가장 중요(Exp-189/195 고신뢰 오탐이 전부 짧은 버퍼에서 발생)
        if seglen < STAGE1_MIN_SEGLEN:
            st["blocked_by"]["g3"] += 1
            self._stage1_shadow_reset_evidence()
            return

        if locked == "en":
            p_opp = p_ko
        elif locked == "ko":
            p_opp = p_en
        else:
            p_opp = None

        # G4: p_opp 문턱
        if p_opp is None or p_opp < STAGE1_TAU:
            st["blocked_by"]["g4"] += 1
            self._stage1_shadow_reset_evidence()
            return

        # t_abs는 SOT 프로브·토큰 절대 타임스탬프와 동일 좌표계
        t_abs = (self.state.global_time_offset
                 + self.state.cumulative_time_offset
                 + seglen)

        # G1~G4 만족 → 증거 누적(언어가 바뀌면 새 증거로 취급)
        if st["lang"] != locked:
            st["count"] = 0
            st["first_t"] = None
        st["lang"] = locked
        if st["count"] == 0:
            st["first_t"] = t_abs
        st["count"] += 1
        duration = t_abs - st["first_t"]

        # G5: 연속 K & 지속 T(둘 다 필요 — 10Hz라 K만으론 T 미달)
        if st["count"] < STAGE1_MIN_BATCHES or duration < STAGE1_MIN_DURATION:
            st["blocked_by"]["g5"] += 1
            return
        # G6: 쿨다운(직전 실제 언어전환 이후 최소 경과)
        if t_abs - self.state.last_lang_switch_time < STAGE1_COOLDOWN_SECS:
            st["blocked_by"]["g6"] += 1
            return
        # G7: 진행 중인 전환·eager 감지가 없어야 한다
        if self.state.pending_language_switch is not None or self.state.eager_lang_detect:
            st["blocked_by"]["g7"] += 1
            return

        st["would_fire"] += 1
        logger.warning(
            "[Stage1Shadow] would_fire=True lang=%s p_opp=%.4f t=%.2f seglen=%.2f k=%d dur=%.2f",
            locked, p_opp, t_abs, seglen, st["count"], duration,
        )

    def _log_stage1_shadow_stats(self) -> None:
        """[Stage1ShadowStats] WARNING 세션 요약 — would_fire·게이트별 차단 카운트.

        기존 `[LangDriftStats]` 포맷은 건드리지 않는다(analyze_sot_lang_probe.py 파서
        호환 유지 — 별도 로그 태그로 낸다). would_fire=0 회차도 명시적으로 1회 찍는다
        (0-firing = 노이즈 대조군 식별용, `_log_lang_drift_stats`와 동일 관례). 중복 억제는
        `_log_lang_drift_stats`의 `probes`(총 호출수)처럼 **총 호출 수**(would_fire + 게이트별
        차단 합)가 직전과 동일할 때만 건너뛴다 — would_fire만 비교하면 would_fire=0인 채
        blocked_by만 계속 누적되는(가장 흔한) 세션에서 최종 누적치가 로그에 전혀 반영되지
        않는다(실측 발견: bong1/ytn2/sbs1/ytn1 4파일 전부 회차 1개로 멈춰 이후 누적분 유실).
        """
        if not STAGE1_SHADOW_ENABLED:
            return
        try:
            st = self._stage1_shadow_state()
            b = st["blocked_by"]
            total_calls = st["would_fire"] + sum(b.values())
            last = getattr(self, "_stage1_shadow_last_summary", None)
            if last is not None and last == total_calls:
                return
            self._stage1_shadow_last_summary = total_calls
            logger.warning(
                "[Stage1ShadowStats] would_fire=%d blocked_g1=%d blocked_g2=%d blocked_g3=%d "
                "blocked_g4=%d blocked_g5=%d blocked_g6=%d blocked_g7=%d",
                st["would_fire"], b["g1"], b["g2"], b["g3"], b["g4"], b["g5"], b["g6"], b["g7"],
            )
        except Exception as e:  # 계측 실패가 디코딩을 절대 막지 않게 한다
            logger.debug("[Stage1ShadowStats] 요약 실패(무시): %s", e)

    # === Template infer() ===

    def infer(self, is_last=False):
        """Main inference — template method calling abstract hooks for tensor ops."""
        if is_last:
            self._log_lang_drift_stats()
            self._log_stage1_shadow_stats()
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

            # 계측 전용: 첫 forward(new_segment)의 [beam, T, V] logits에서 SOT/task 위치
            # 사후분포를 읽어 로깅만 한다. 텐서를 수정하지 않고(구현체가 clone 후 계산)
            # 분기·반환값·상태에도 관여하지 않는다 — 아래 no_speech 판정은 그대로다.
            if new_segment:
                self._log_sot_lang_probe(logits)

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
        tokens_to_split = self._merge_pending_tokens(tokens_to_split)

        new_hypothesis, split_words, split_tokens = self._split_tokens(
            tokens_to_split, fire_detected, is_last
        )

        num_generated = max(0, current_tokens.shape[1] - token_len_before)
        if not is_last and self._quality_gate(new_hypothesis, sum_logprobs, num_generated):
            self._on_quality_suppressed(new_hypothesis)
            return []
        self.state.quality_suppress_streak = 0

        commit_hypothesis = self._clean_commit_hypothesis(
            new_hypothesis, split_words, split_tokens
        )
        new_tokens_tensor = self._make_new_tokens_tensor(commit_hypothesis)
        self.state.tokens.append(new_tokens_tensor)
        logger.info(f"Output: {self.tokenizer.decode(commit_hypothesis)}")

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

    def _merge_pending_tokens(self, new_tokens):
        """Prepend held incomplete UTF-8 tokens, guarded by a seam convergence gate.

        Gate (SEAM_CONVERGENCE_FIX_ENABLED): if decode(pending + new) still contains
        U+FFFD while decode(new) alone is clean, the held bytes can never converge with
        this chunk's re-decoded tokens (stale seam). Re-prepending them would glue a
        phantom U+FFFD into the first new word — in spaceless Korean the whole phrase
        becomes ONE word, gets skipped downstream, and mojibake accumulates across
        retries. Discard the stale pending and process the fresh tokens as-is.
        A legitimate continuation (e.g. held "미�" + the trailing bytes of "디어")
        decodes to U+FFFD on its own, so the gate does NOT fire there and the
        hold-then-reemit-full-word design from Exp-087 (which fixed the "미 미디어"
        leading-fragment duplication) is preserved.
        """
        pending = self.state.pending_incomplete_tokens
        if not pending:
            return new_tokens
        if SEAM_CONVERGENCE_FIX_ENABLED and new_tokens:
            replacement_char = "�"
            if (
                replacement_char in self.tokenizer.decode(pending + new_tokens)
                and replacement_char not in self.tokenizer.decode(new_tokens)
            ):
                logger.debug(
                    f"[UTF-8 Fix] Discarding stale pending (seam divergence): {pending}"
                )
                self.state.pending_incomplete_tokens = []
                self.state.pending_retries = 0
                return new_tokens
        logger.debug(
            f"[UTF-8 Fix] Prepending {len(pending)} pending tokens: {pending}"
        )
        return pending + new_tokens

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

    def _clean_commit_hypothesis(self, new_hypothesis, split_words, split_tokens):
        """커밋용 hypothesis를 첫 U+FFFD(반토막 음절) 단어 앞 클린 프리픽스로 절단한다.

        순수 subtractive — 길이를 늘리지 않는다. new_hypothesis(fire/is_last면 전체 청크,
        비-fire면 마지막 단어 제외)와 split_words/split_tokens는 같은 순서라, 첫 U+FFFD 단어
        인덱스 앞까지의 토큰이 new_hypothesis의 프리픽스가 된다. 반토막을 커밋에서 제외해
        high-water mark를 깨끗이 유지 → 다음 청크가 해당 오디오를 오염 없는 컨텍스트로 재디코딩.
        (_handle_pending_tokens의 U+FFFD 검출 idiom 재사용 — 새 tokenizer 호출·재디코딩 없음.)
        """
        if not CONTEXT_CLEAN_COMMIT_ENABLED:
            return new_hypothesis
        replacement_char = "�"
        incomplete_idx = next(
            (i for i, w in enumerate(split_words) if replacement_char in w), None
        )
        if incomplete_idx is None:
            return new_hypothesis
        clean_prefix = [t for toks in split_tokens[:incomplete_idx] for t in toks]
        # clean_prefix는 new_hypothesis의 프리픽스(둘 다 같은 순서 리스트). 더 짧을 때만 절단 —
        # 비-fire·U+FFFD가 마지막 단어면 clean_prefix == new_hypothesis라 no-op.
        if len(clean_prefix) < len(new_hypothesis):
            return clean_prefix
        return new_hypothesis

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
                if SEAM_CONVERGENCE_FIX_ENABLED:
                    # Contract alignment with _handle_pending_tokens: stop emission at the
                    # FIRST incomplete word. Clean words after it are deferred to the next
                    # chunk (held together for retry) instead of emitted now — the old
                    # skip-and-continue emitted them while only the LAST word was ever
                    # held, so a mid-position incomplete word was silently lost forever.
                    # Still no partial emission: that would reintroduce the Exp-087
                    # "미 미디어" duplication this skip+hold design fixed.
                    logger.debug(
                        f"[UTF-8 Filter] Halting emission at incomplete word "
                        f"(held for retry): {repr(word)}"
                    )
                    break
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

        if SEAM_CONVERGENCE_FIX_ENABLED:
            # Contract alignment with _build_timestamped_words (which halts emission at
            # the first incomplete word): hold everything from the FIRST U+FFFD word on,
            # not just the last word. The old last-word-only check leaked mid-position
            # incomplete words \u2014 skipped by the builder but never held, hence lost.
            # Deferred clean words after the seam are re-emitted with the next chunk,
            # keeping the exactly-once contract from Exp-087 ("\ubbf8 \ubbf8\ub514\uc5b4" fix).
            incomplete_idx = next(
                (i for i, w in enumerate(split_words) if replacement_char in w), None
            )
            held_tokens = (
                [t for toks in split_tokens[incomplete_idx:] for t in toks]
                if incomplete_idx is not None
                else None
            )
        else:
            held_tokens = (
                split_tokens[-1]
                if split_words and replacement_char in split_words[-1]
                else None
            )

        if held_tokens is not None:
            self.state.pending_retries += 1
            if self.state.pending_retries > MAX_PENDING_RETRIES:
                logger.warning(
                    f"[UTF-8 Fix] Dropping {len(held_tokens)} incomplete tokens "
                    f"after {MAX_PENDING_RETRIES} retries (won't resolve)"
                )
                self.state.pending_incomplete_tokens = []
                self.state.pending_retries = 0
            elif len(held_tokens) <= MAX_PENDING_TOKENS:
                self.state.pending_incomplete_tokens = held_tokens
                logger.debug(
                    f"[UTF-8 Fix] Holding {len(self.state.pending_incomplete_tokens)} "
                    f"incomplete tokens for next chunk (retry {self.state.pending_retries})"
                )
            else:
                logger.warning(
                    f"[UTF-8 Fix] Skipping {len(held_tokens)} tokens "
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
                logger.warning(
                    "[QualityGate] avg_logprob %.3f < %.3f — suppressing (lang=%s): %.200s",
                    avg_lp, lp_thr, self.state.detected_language, text,
                )
                return True
        if cr_thr is not None:
            from whisperlivekit.whisper.utils import compression_ratio
            text = self.tokenizer.decode(hypothesis).strip()
            if text:
                cr = compression_ratio(text)
                if cr > cr_thr:
                    logger.warning(
                        "[QualityGate] compression_ratio %.2f > %.2f — suppressing (lang=%s): %.200s",
                        cr, cr_thr, self.state.detected_language, text,
                    )
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
            logger.warning(
                "[QualityGate] %d consecutive suppressions — refresh_segment (lang=%s)",
                streak, self.state.detected_language,
            )
            if self._try_preserving_refresh():
                self.state.quality_suppress_streak = 0
                return
            self.refresh_segment(complete=True)
            self.state.quality_suppress_streak = 0

    def _try_preserving_refresh(self) -> bool:
        """경계 보호창 내 첫 streak이면 오디오를 보존한 채 상태만 리셋. 처리했으면 True.

        False를 반환하면 호출부가 기존 폐기(complete=True) 경로를 그대로 탄다 — 보호창 밖·
        재시도 소진·버퍼 없음·플래그 OFF가 전부 여기에 해당해 비회귀가 보장된다.
        """
        if not BOUNDARY_QG_PRESERVE_ENABLED:
            return False
        buffered = self.segments_len()
        if buffered <= 0:
            # 보존할 오디오 자체가 없음(직전 refresh 직후 등). 발동 감사에서 이 경로가
            # 무로그로 빠지면 "streak 수 − 보존 수"가 설명되지 않으므로 명시적으로 남긴다.
            # warning 레벨 필수: 서버 root 로거가 WARNING이라 info는 --trace-tokens 없이는
            # 조용히 사라진다(basic_server.py의 trace_tokens 분기 참조 — 같은 함정으로
            # Exp-171 [RetractScan]이 0건으로 오인될 뻔했다).
            logger.warning("[QGPreserve] 버퍼 비어 있음 — 보존 대상 없음(기존 폐기 경로)")
            return False
        if getattr(self.state, "qg_preserve_used", False):
            # 같은 경계에서 이미 한 번 보존했는데 또 garbage → 재디코딩으로도 못 푸는
            # 구간이다. 무한 재디코딩 루프를 막기 위해 기존 폐기로 폴백한다.
            logger.warning("[QGPreserve] 보존 재시도 소진 — 기존 폐기로 폴백 (buffered=%.2fs)", buffered)
            return False
        boundary_at = getattr(self.state, "last_boundary_event_at", 0.0)
        now = self._current_stream_time()
        since = now - boundary_at
        # boundary_at > 0.0 게이트: last_boundary_event_at 기본값 0.0은 "세션 초입, 아직 실제
        # 경계 이벤트(화자/언어 전환) 없음"을 뜻한다(decoder_state.py 설계의도). 이 상태에서는
        # Δt 상한을 적용하지 않는다 — 그렇지 않으면 콜드스타트 streak 형성이 느릴 때(예:
        # quality_gate_reset_after가 높거나 디코드 사이클이 느릴 때) BOUNDARY_PROTECT_SECS를
        # 넘겨 보호에서 빠지고, 언어 재확신 없는 구폐기로 폴백해 콜드스타트 언어오감지가 그대로
        # 지속된다(실측 재현: Δt=5.62s·6.15s에서 발동). qg_preserve_used 1회성 가드가 이미 위에서
        # 무한 재시도를 막고 있으므로, 이 게이트는 "첫 실제 경계 이후"에만 Δt 상한을 적용한다.
        if boundary_at > 0.0 and since > BOUNDARY_PROTECT_SECS:
            # warning 레벨 필수 — 위 빈-버퍼 분기 주석 참조(root 로거 WARNING).
            logger.warning(
                "[QGPreserve] 보호창 밖(Δt=%.2fs > %.2fs) — 기존 폐기 유지",
                since, BOUNDARY_PROTECT_SECS,
            )
            return False

        # 언어 확신 게이트 — refresh 전에(원본 버퍼로) 프로브한다.
        # 오디오를 살려두는 것은 "그 오디오를 옳은 언어로 다시 읽을 수 있을 때"만 이득이다.
        # 언어 잠금이 틀린 채 보존하면 재디코딩이 한국어 구간을 영어로 번역해 뱉는다
        # (은닉 번역 — bong1 짝지음 N=3에서 LMR +22.8pp로 실측). 기존 폐기는 단어를
        # 죽이는 대신 그 오언어 출력도 함께 버리고 있었으므로, 확신이 없으면 폐기가 낫다.
        probed = self._probe_language_for_preserve()
        if probed is None:
            logger.warning(
                "[QGPreserve] 언어 확신 실패(p<%.2f) — 기존 폐기로 폴백 (buffered=%.2fs)",
                BOUNDARY_QG_REPROBE_MIN_PROB, buffered,
            )
            return False
        if not BOUNDARY_QG_PRESERVE_ON_SAME_LANG and probed == self.state.detected_language:
            # 언어는 이미 옳았는데 garbage가 3연속 → 언어 문제가 아니다. 보존해도 같은
            # 오디오를 다시 헤맬 뿐이라 환각만 늘린다(상단 상수 주석의 실측 근거 참조).
            logger.warning(
                "[QGPreserve] 동일언어(%s) 확인 — 언어 문제 아님, 기존 폐기로 폴백 (buffered=%.2fs)",
                probed, buffered,
            )
            return False

        # 오디오 전량 보존 + 디코더 상태만 리셋. keep_secs=버퍼 전체 길이라 refresh_segment의
        # 유지 루프가 모든 세그먼트를 남긴다(신규 폐기 경로를 만들지 않고 기존 함수 재사용).
        self.refresh_segment(complete=False, keep_secs=buffered)
        self.state.qg_preserve_used = True
        logger.warning(
            "[QGPreserve] 경계 보호 보존 refresh — Δt=%.2fs lang=%s→%s preserved=%.2fs",
            since, self.state.detected_language, probed, self.segments_len(),
        )
        if probed != self.state.detected_language:
            # skip_trim=True 필수 — 기본 경로는 _trim_segments_to_recent로 버퍼를 keep_secs
            # (2.5~5.0s)까지 잘라내는데, 그러면 방금 보존하기로 결정한 서두 오디오를 곧바로
            # 되버리는 자기모순이 된다. 경계 arm(LanguageSwitch 마커)도 생략한다 — 이건
            # 발화 경계가 아니라 QG 복구 중 토크나이저 교정이다.
            self._apply_detected_language(probed, skip_trim=True)
        return True

    def _probe_language_for_preserve(self):
        """보존 직전 언어 확신 프로브. 확신 시 언어 코드, 실패 시 None.

        detect_current_language는 이미 @torch.no_grad라 신규 forward 경로가 아니다
        (turbo 인코더 grad 추적 성능 절벽 회피 — Exp-158).
        """
        window = min(self.segments_len(), BOUNDARY_QG_REPROBE_WINDOW)
        if window <= 0:
            return None
        return self.detect_current_language(
            window_secs=window, min_prob=BOUNDARY_QG_REPROBE_MIN_PROB,
        )

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
