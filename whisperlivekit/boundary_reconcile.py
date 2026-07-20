# -*- coding: utf-8 -*-
"""언어전환 경계 재조정(reconciliation) 계층 (Exp-192).

배경: 언어전환 경계에서 구언어 잔존 토큰을 파괴적으로 철회(pop)하면, 신언어
재디코딩이 그 구간을 다시 방출하지 못했을 때 단어가 순유실된다(배포 제보 증상 1
"반갑습니다"류 꼬리 유실). 반대로 철회를 보수적으로 하면 "미니스터." → "Minister..."
같은 이중언어 중복 확정이 남는다(증상 2 — 텍스트 dedup은 원리적으로 불가, 시간으로만
포착 가능).

이 모듈은 철회를 "복원 가능한 tombstone"(ASRToken.retracted)으로 바꾼 위에서,
경계마다 ReconcileWindow를 하나 arm 하고(활성 최대 1개 불변식) 신언어 토큰의
도착(커버)을 관찰한 뒤 마감 시점에 단일 컷포인트로 원자적으로 해소한다:

- 커버 판정 = start 근접(COVER_TOL). 토큰 end는 start+0.1 고정(가짜)이라 근접
  판정만 유효하다.
- 마감 3중: D1 = 신언어 토큰 진행도(start 고수위)가 boundary_t+PASS_EPS 통과 /
  D2 = 다음 Silence·LanguageSwitch 마커 도착(새 LanguageSwitch면 이전 창 resolve 후
  재arm) / D3 = get_lines() 훅에서 audio_time 기준 RECONCILE_DEADLINE_SECS 경과
  (벽시계 사용 금지 — tokens_alignment.get_lines의 audio_time 인자 사용, 오디오가
  실시간보다 빠르거나 느리게 주입될 때 벽시계는 깨진다).
- resolve = 단일 컷포인트 원자성: 신언어 토큰 최소 start를 컷 T로 잡고, 철회 토큰
  start >= T−τ 는 전부 대체(영구 tombstone), < T−τ 는 전부 복원(retracted=False).
  부분 복원 구멍 금지(Case B 파편 "올렸"⏎"습니다" 방지) — 컷이 연속 토큰(하위단어)
  중간이면 단어 시작 방향으로 스냅(공백 접두/토큰 간 갭 기준). 신언어 토큰이 하나도
  안 왔으면 전량 복원(유실 해결 > WER 소폭 허용).

구역2 확대(RECONCILE_SAMESCRIPT_SUBZONE_ENABLED): boundary_t−SAMESCRIPT_SUBZONE_SECS
이내의 같은 스크립트 prev_lang 토큰("미니스터")도 잠정 tombstone 한다 — 복원 보장이
생겼기 때문에 안전해진 공격적 철회. 커버되면 대체(중복 소멸), 미커버면 복원(무손실).

플래그는 전부 모듈 상수이며 호출부(tokens_alignment)가 런타임에 이 모듈 속성으로
조회한다 — 테스트에서 monkeypatch로 분기 검증 가능.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from whisperlivekit.timed_objects import ASRToken

# tokens_alignment 로거 재사용 — [Retract]/[RetractScan]과 동일 채널로 나가야
# --trace-tokens의 DEBUG 승격(basic_server) 및 기존 로그 수집 경로에 함께 잡힌다.
# (tokens_alignment를 import 하면 순환 참조가 되므로 로거 이름으로 직접 참조.)
logger = logging.getLogger("whisperlivekit.tokens_alignment")

# ─── 플래그 (모듈 상수 — 런타임 조회, monkeypatch 가능) ─────────────────────────
RECONCILE_ENABLED: bool = True   # False = 레거시 파괴적 pop 거동 재현(전체 롤백)
RECONCILE_SAMESCRIPT_SUBZONE_ENABLED: bool = True  # 구역2 확대(같은 스크립트 잠정 철회)만 롤백

# ─── 상수 (잠정값 — 계측 r1의 Δstart 분포로 보정 후 확정) ───────────────────────
COVER_TOL: float = 0.5           # 커버 판정 start 근접 허용(τ — 컷 파티션에도 동일 사용)
PASS_EPS: float = 0.25           # D1: 신언어 진행도가 boundary_t + 이 값을 넘으면 마감
RECONCILE_DEADLINE_SECS: float = 3.0   # D3: arm 후 audio_time 기준 최대 대기
SAMESCRIPT_SUBZONE_SECS: float = 1.2   # 구역2 확대 범위(boundary_t 이전)
_WORD_SNAP_GAP_SECS: float = 0.3       # 공백 접두 없는 토큰의 단어 시작 판정 보조 갭

# 존 라벨
ZONE1 = "zone1"
ZONE2_OPPOSITE = "zone2_opposite"
ZONE2_SAMESCRIPT = "zone2_samescript"


def _starts_new_word(token: ASRToken, prev_token: Optional[ASRToken]) -> bool:
    """token이 새 단어의 시작인지 판정 (하위단어 연속 여부).

    1차 신호 = 공백 접두(Whisper 토크나이저는 새 단어를 " 단어"로 방출).
    보조 신호 = 직전 토큰과의 시간 갭(_WORD_SNAP_GAP_SECS 초과면 새 단어로 간주 —
    end가 start+0.1 고정 가짜일 수 있어 보조로만 쓴다).
    """
    text = token.text or ""
    if text[:1].isspace():
        return True
    if prev_token is None:
        return True
    prev_anchor = prev_token.end if prev_token.end is not None else prev_token.start
    if prev_anchor is None or token.start is None:
        return False
    return (token.start - prev_anchor) > _WORD_SNAP_GAP_SECS


@dataclass
class TombstoneEntry:
    """arm 시점에 철회(잠정 tombstone)된 토큰 1개의 재조정 상태."""
    token: ASRToken
    zone: str
    covered: bool = False   # 신언어 토큰이 start 근접(COVER_TOL)으로 이 구간을 커버했는가
    replaced: bool = False  # resolve 결과 — True면 영구 tombstone, False면 복원됨


@dataclass
class ReconcileWindow:
    """언어전환 경계 1개의 재조정 창. BoundaryReconciler가 최대 1개만 활성 유지."""
    boundary_t: float
    floor: float
    prev_lang: Optional[str]
    new_lang: Optional[str]
    entries: List[TombstoneEntry] = field(default_factory=list)
    new_min_start: Optional[float] = None   # 관측된 신언어 토큰 최소 start(컷 T 후보)
    new_high_start: Optional[float] = None  # 관측된 신언어 토큰 start 고수위(D1 진행도)
    resolved: bool = False
    resolve_reason: Optional[str] = None

    def observe(self, token: ASRToken) -> None:
        """신언어 토큰 관측 — 진행도 갱신 + 커버 마킹."""
        if token.start is None:
            return
        if self.new_min_start is None or token.start < self.new_min_start:
            self.new_min_start = token.start
        if self.new_high_start is None or token.start > self.new_high_start:
            self.new_high_start = token.start
        for e in self.entries:
            if not e.covered and e.token.start is not None \
                    and abs(token.start - e.token.start) <= COVER_TOL:
                e.covered = True

    def d1_reached(self) -> bool:
        return (self.new_high_start is not None
                and self.new_high_start >= self.boundary_t + PASS_EPS)

    def resolve(self, reason: str) -> None:
        """단일 컷포인트 원자성으로 tombstone들을 대체/복원 확정한다.

        컷 T = 관측된 신언어 토큰 최소 start. 철회 토큰 start >= T−COVER_TOL 은 전부
        대체(영구), < T−COVER_TOL 은 전부 복원 — 파티션은 정렬된 start의 단일 임계라
        구멍이 없다. 컷이 하위단어 연속 중간에 떨어지면 단어 시작 방향으로 스냅해
        해당 단어 전체를 대체 쪽에 넣는다(복원 파편 잔존 = Case B 금지).
        신언어 토큰이 하나도 관측되지 않았으면 전량 복원.
        """
        if self.resolved:
            return
        self.resolved = True
        self.resolve_reason = reason

        entries = sorted(
            self.entries,
            key=lambda e: e.token.start if e.token.start is not None else 0.0,
        )
        cut = self.new_min_start
        if cut is None:
            first_replaced_idx = len(entries)  # 전량 복원
        else:
            threshold = cut - COVER_TOL
            first_replaced_idx = len(entries)
            for i, e in enumerate(entries):
                if e.token.start is not None and e.token.start >= threshold:
                    first_replaced_idx = i
                    break
            # 단어 시작 방향 스냅 — 컷이 하위단어 연속 중간이면 그 단어 전체를 대체.
            while (0 < first_replaced_idx < len(entries)
                   and not _starts_new_word(entries[first_replaced_idx].token,
                                            entries[first_replaced_idx - 1].token)):
                first_replaced_idx -= 1

        restored = 0
        replaced = 0
        covered = sum(1 for e in entries if e.covered)
        for i, e in enumerate(entries):
            dstart = ("%.2f" % (e.token.start - cut)) if (
                cut is not None and e.token.start is not None) else "NA"
            if i < first_replaced_idx:
                e.replaced = False
                e.token.retracted = False
                restored += 1
                logger.info(
                    "[Restore] 복원: %r start=%.2f dstart=%s boundary_t=%.2f zone=%s",
                    e.token.text, e.token.start or -1.0, dstart, self.boundary_t, e.zone,
                )
            else:
                e.replaced = True
                e.token.retracted = True  # 영구 tombstone
                replaced += 1
                logger.info(
                    "[Replace] 대체: %r start=%.2f dstart=%s boundary_t=%.2f zone=%s",
                    e.token.text, e.token.start or -1.0, dstart, self.boundary_t, e.zone,
                )
        logger.info(
            "[Reconcile] resolve reason=%s boundary_t=%.2f cut=%s covered=%d restored=%d replaced=%d",
            reason, self.boundary_t,
            ("%.2f" % cut) if cut is not None else "NA", covered, restored, replaced,
        )


class BoundaryReconciler:
    """ReconcileWindow의 수명(활성 최대 1개)과 마감 3중(D1/D2/D3)을 관리한다.

    모든 공개 메서드는 RECONCILE_ENABLED=False면 no-op — 레거시 거동 롤백 안전장치.
    """

    def __init__(self) -> None:
        self.window: Optional[ReconcileWindow] = None

    # ── 수명 ────────────────────────────────────────────────────────────────

    def arm(
        self,
        boundary_t: float,
        floor: float,
        prev_lang: Optional[str],
        new_lang: Optional[str],
        entries: List[TombstoneEntry],
    ) -> None:
        """언어전환 마커 도착 시 새 창을 연다. 이전 창이 살아 있으면 먼저 resolve(D2)."""
        if not RECONCILE_ENABLED:
            return
        if self.window is not None and not self.window.resolved:
            self.window.resolve("d2_new_boundary")
        self.window = ReconcileWindow(
            boundary_t=boundary_t, floor=floor,
            prev_lang=prev_lang, new_lang=new_lang,
            entries=sorted(entries, key=lambda e: e.token.start
                           if e.token.start is not None else 0.0),
        )
        logger.info(
            "[Reconcile] arm boundary_t=%.2f prev_lang=%s new_lang=%s floor=%.2f tombstones=%d",
            boundary_t, prev_lang, new_lang, floor, len(entries),
        )

    # ── 관측/마감 ────────────────────────────────────────────────────────────

    def observe_new_token(self, token: ASRToken) -> None:
        """신규 텍스트 토큰 도착 훅 (tokens_alignment._insert_with_reattachment)."""
        if not RECONCILE_ENABLED:
            return
        w = self.window
        if w is None or w.resolved:
            return
        if token.detected_language != w.new_lang:
            return  # 구언어 재귀속 꼬리 등 — 창 관측 대상 아님
        w.observe(token)
        if w.d1_reached():
            w.resolve("d1")

    def on_boundary_marker(self, kind: str) -> None:
        """D2: 다음 Silence/일반 LanguageSwitch 마커 도착 → 활성 창 즉시 resolve.

        retract_from이 실린 새 LanguageSwitch는 이 경로가 아니라 arm()이 처리한다
        (이전 창 resolve 후 재arm).
        """
        if not RECONCILE_ENABLED:
            return
        w = self.window
        if w is not None and not w.resolved:
            w.resolve(f"d2_{kind}")

    def check_deadline(self, audio_time: Optional[float]) -> None:
        """D3: get_lines() 훅 — audio_time 기준 마감 캡(벽시계 금지)."""
        if not RECONCILE_ENABLED:
            return
        w = self.window
        if w is None or w.resolved:
            return
        if audio_time is not None and audio_time - w.boundary_t >= RECONCILE_DEADLINE_SECS:
            w.resolve("d3")
