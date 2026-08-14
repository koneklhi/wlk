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

텍스트 커버 가드(RECONCILE_TEXT_COVER_GUARD_ENABLED): 위 파티션은 **순수 시간 기준**이라,
재디코딩이 같은 텍스트를 다시 방출했는데도 재앵커로 타임스탬프가 COVER_TOL 넘게 밀리면
그 tombstone을 "미커버"로 오판해 복원한다(실측 인시던트 — ko 잠금 아래 커밋된 영어 서두
"In support of"에서 'In'만 복원돼 stub 문장 "In." 중복 확정). 그래서 resolve는 컷 아래
tombstone이 관측 텍스트와 **정규화 완전일치**하면(±TEXT_COVER_SLACK_SECS) 복원을 취소하고
대체 파티션으로 흡수한다 — 단일 컷 인덱스만 아래로 확장하므로 구멍 없음 불변식은 유지된다.

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
RECONCILE_TEXT_COVER_GUARD_ENABLED: bool = True    # A안(resolve 텍스트 커버 가드)만 롤백

# ─── 상수 (잠정값 — 계측 r1의 Δstart 분포로 보정 후 확정) ───────────────────────
COVER_TOL: float = 0.5           # 커버 판정 start 근접 허용(τ — 컷 파티션에도 동일 사용)
PASS_EPS: float = 0.25           # D1: 신언어 진행도가 boundary_t + 이 값을 넘으면 마감
RECONCILE_DEADLINE_SECS: float = 3.0   # D3: arm 후 audio_time 기준 최대 대기
SAMESCRIPT_SUBZONE_SECS: float = 1.2   # 구역2 확대 범위(boundary_t 이전)
_WORD_SNAP_GAP_SECS: float = 0.3       # 공백 접두 없는 토큰의 단어 시작 판정 보조 갭
OWN_TOL: float = 0.4             # 시간 소유권 dedup의 start 근접 허용
DEDUP_RELEASE_GRACE_SECS: float = 0.5  # 조기 resolve 후 dedup/늦은 커버 유지 유예
# 텍스트 커버 가드: 텍스트가 정규화 완전일치일 때 허용하는 재앵커 이동 상한.
# 잠정값 — [TextCover] dstart 실측 분포로 보정한다(COVER_TOL보다 크게 잡는 것이 요점:
# 텍스트 동일성이라는 훨씬 강한 증거가 있으므로 시간 허용치를 넓혀도 된다).
# dstart 부호 규약은 [Restore]/[Replace]와 동일한 "tombstone start − 기준 start"이므로,
# 재앵커가 뒤로 밀린 정상 케이스에서는 음수로 찍힌다(보정 시 |dstart| 분포를 본다).
TEXT_COVER_SLACK_SECS: float = 2.5
_OBSERVED_TEXT_CAP: int = 64     # 창당 관측 텍스트 수집 상한(장창 방어 — 매칭은 선형 스캔)

# 존 라벨
ZONE1 = "zone1"
ZONE2_OPPOSITE = "zone2_opposite"
ZONE2_SAMESCRIPT = "zone2_samescript"


# dedup 매칭용 텍스트 정규화에서 양끝에서 제거할 구두점·인용부호 집합.
# 내부 문자(어퍼스트로피 "It's" 등)는 보존된다 — strip은 양끝만 깎는다.
_DEDUP_PUNCT_CHARS = ".,?!…~\"'`“”‘’()[]{}<>:;·-–—。、，！？ \t"


def _dedup_norm(text: Optional[str]) -> str:
    """시간 소유권 dedup의 텍스트 매칭 정규화: strip → 양끝 구두점 제거 → 소문자.

    순수 구두점 토큰은 빈 문자열이 되어 매칭 후보에서 제외된다.
    """
    return (text or "").strip(_DEDUP_PUNCT_CHARS).lower()


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
    # 관측된 신언어 토큰의 (start, 정규화 텍스트) — resolve의 텍스트 커버 가드 전용.
    # 순수 구두점 토큰(정규화 후 빈 문자열)은 담지 않는다(매칭 후보가 아니므로).
    observed_texts: List[tuple] = field(default_factory=list)
    resolved: bool = False
    resolve_reason: Optional[str] = None

    def observe(self, token: ASRToken) -> None:
        """신언어 토큰 관측 — 진행도 갱신 + 커버 마킹 + 텍스트 커버 가드용 텍스트 수집."""
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
        nt = _dedup_norm(token.text)
        if nt and len(self.observed_texts) < _OBSERVED_TEXT_CAP:
            self.observed_texts.append((token.start, nt))

    def d1_reached(self) -> bool:
        return (self.new_high_start is not None
                and self.new_high_start >= self.boundary_t + PASS_EPS)

    def dedup_limit(self) -> float:
        """시간 소유권 dedup·늦은 커버가 유효한 batch 시작(start) 상한.

        경계 앵커 고정: boundary_t + PASS_EPS + DEDUP_RELEASE_GRACE_SECS.
        일부러 관측 고수위(new_high_start)를 따라가지 않는다 — 고수위 추종이면
        한계가 발화 프런티어를 계속 쫓아가 "네, 네" 같은 창 밖 정상 반복까지
        dedup 대상이 되는 자기확장 구멍이 생긴다. 경계 재방출(재디코딩 창 겹침)은
        정의상 경계 부근에서 시작하므로 앵커 고정으로 충분하고, D2 조기 resolve 후
        늦은 커버 도착도 +DEDUP_RELEASE_GRACE_SECS 유예가 흡수한다.
        """
        return self.boundary_t + PASS_EPS + DEDUP_RELEASE_GRACE_SECS

    def _match_observed(self, token: ASRToken, consumed: set) -> Optional[int]:
        """텍스트 커버 가드의 매칭: 아직 소비되지 않은 관측 토큰 중 첫 일치 인덱스.

        조건 = 정규화 완전일치(접두어·부분일치 불허 — 'In'이 'Increase'를 흡수하면
        정당 단어가 사라진다) + |Δstart| <= TEXT_COVER_SLACK_SECS. 없으면 None.
        """
        if token.start is None:
            return None
        ne = _dedup_norm(token.text)
        if not ne:
            return None
        for i, (obs_start, obs_text) in enumerate(self.observed_texts):
            if i in consumed or obs_text != ne:
                continue
            if abs(obs_start - token.start) <= TEXT_COVER_SLACK_SECS:
                return i
        return None

    def resolve(self, reason: str) -> None:
        """단일 컷포인트 원자성으로 tombstone들을 대체/복원 확정한다.

        컷 T = 관측된 신언어 토큰 최소 start. 철회 토큰 start >= T−COVER_TOL 은 전부
        대체(영구), < T−COVER_TOL 은 전부 복원 — 파티션은 정렬된 start의 단일 임계라
        구멍이 없다. 컷이 하위단어 연속 중간에 떨어지면 단어 시작 방향으로 스냅해
        해당 단어 전체를 대체 쪽에 넣는다(복원 파편 잔존 = Case B 금지).
        신언어 토큰이 하나도 관측되지 않았으면 전량 복원.

        그 위에 텍스트 커버 가드가 컷을 아래로만 단조 확장한다 — 재앵커로 시간이 밀려
        미커버로 오판된 tombstone이라도 관측 텍스트와 완전일치하면 대체 쪽으로 흡수한다.
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

        if RECONCILE_TEXT_COVER_GUARD_ENABLED and cut is not None:
            # ── 텍스트 커버 가드: 컷을 아래로만 단조 확장 ──
            # 불변식: 이동하는 것은 first_replaced_idx라는 단일 임계 인덱스뿐이다 →
            # "단일 컷포인트·구멍 없음"이 구조적으로 유지되고, 비연속(중간 비일치를
            # 건너뛴) 대체가 만들어질 수 없다(Case B 파편 불가).
            consumed: set = set()
            # 이미 대체 파티션에 든 tombstone이 관측 텍스트를 먼저 소비한다 —
            # 관측 토큰 1개는 tombstone 1개의 대체만 정당화한다(실발화 반복 보호:
            # 화자가 같은 단어를 두 번 말했으면 재방출 1개가 둘 다 지우면 안 된다).
            for e in entries[first_replaced_idx:]:
                m = self._match_observed(e.token, consumed)
                if m is not None:
                    consumed.add(m)
            while first_replaced_idx > 0:
                j = first_replaced_idx - 1
                # 순수 구두점 tombstone은 look-through — 그 아래 비-구두점 단어와
                # 함께만 흡수한다(유령 "In."에서 '.'만 남는 파편 방지).
                while j > 0 and not _dedup_norm(entries[j].token.text):
                    j -= 1
                m = self._match_observed(entries[j].token, consumed)
                if m is None:
                    break   # 비일치 → 즉시 중단(그 아래가 일치해도 흡수 금지 = 구멍 금지)
                consumed.add(m)
                e = entries[j]
                obs_start = self.observed_texts[m][0]
                logger.info(
                    "[TextCover] 복원취소→대체: %r start=%.2f obs_start=%.2f dstart=%.2f "
                    "boundary_t=%.2f zone=%s",
                    e.token.text, e.token.start, obs_start, e.token.start - obs_start,
                    self.boundary_t, e.zone,
                )
                first_replaced_idx = j
                # 단어 시작 스냅 재적용 — 확장이 하위단어 연속 중간이면 단어 전체를 대체.
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
        """신규 텍스트 토큰 도착 훅 (tokens_alignment._insert_with_reattachment).

        창 활성 중엔 커버 마킹+D1 진행도. resolve 후에도 dedup_limit 유예 안이면
        늦은 커버를 반영한다 — D2 조기 resolve로 복원된 tombstone을 뒤늦게 도착한
        신언어 토큰이 커버하면 재대체(복원분 중복 방지).
        """
        if not RECONCILE_ENABLED:
            return
        w = self.window
        if w is None:
            return
        if token.detected_language != w.new_lang:
            return  # 구언어 재귀속 꼬리 등 — 창 관측 대상 아님
        if not w.resolved:
            w.observe(token)
            if w.d1_reached():
                w.resolve("d1")
            return
        # ── resolve 후 유예: 늦은 커버 → 복원분 재대체 ──
        if token.start is None or token.start > w.dedup_limit():
            return
        for e in w.entries:
            if (not e.replaced and not e.token.retracted
                    and e.token.start is not None
                    and abs(token.start - e.token.start) <= COVER_TOL):
                e.replaced = True
                e.covered = True
                e.token.retracted = True
                logger.info(
                    "[Replace] 늦은 대체(late): %r start=%.2f dstart=%.2f boundary_t=%.2f zone=%s",
                    e.token.text, e.token.start, e.token.start - token.start,
                    w.boundary_t, e.zone,
                )

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
        """D3: get_lines() 훅 — audio_time 기준 마감 캡(벽시계 금지).

        resolve된 창도 dedup 유예(dedup_limit)까지 지나면 해제한다(참조 정리).
        """
        if not RECONCILE_ENABLED:
            return
        w = self.window
        if w is None or audio_time is None:
            return
        if not w.resolved:
            if audio_time - w.boundary_t >= RECONCILE_DEADLINE_SECS:
                w.resolve("d3")
            return
        if audio_time > w.dedup_limit():
            self.window = None

    # ── 시간 소유권 dedup (시간창 + 정규화 텍스트 결합 매칭) ─────────────────

    def dedup_batch(self, run: List[ASRToken], all_tokens: List) -> List[ASRToken]:
        """활성 창 구간(+유예) 내 신규 텍스트 토큰 run에 시간 소유권 규칙을 적용한다.

        계측 r1(ytn2/bong1) 실측 정정: 순수 시간 근접(OWN_TOL) 매칭은 창 내에서
        **연속 증분 방출되는 다음 단어**(조밀 간격 0.1~0.3s < OWN_TOL)를 재방출로
        오인해 정당 신규 단어를 소실시켰다(ytn2 " There is…to be done" 소실,
        "정경두"→"경두" 손상). 그래서 매칭은 **시간창 + 정규화 텍스트**를 결합한다:

        - 매칭 쌍 (t=신규, c=창 내 live 같은언어 커밋): |t.start − c.start| <= OWN_TOL
          AND (정규화 완전일치 OR 한쪽이 다른쪽의 접두어[비공백 1자 이상]).
          정규화 = strip → 양끝 구두점 제거 → 소문자. 순수 구두점 토큰(정규화 후
          빈 문자열)은 매칭 후보에서 제외.
        - **방향 결정(배치 단위 1회, 매칭 쌍 1개 이상일 때만)**:
          ① 신규가 확장(b_max > 매칭된 committed 최대 start + OWN_TOL) → supersede:
             매칭 committed 전부 tombstone + 매칭 run에 인접(사이/직후)한
             구두점-only committed도 함께 tombstone(유령 "In."의 '.' 잔존 방지) +
             id(start) 승계(소멸 최초 start < 첫 신규 start일 때). 접두어 매칭
             허용 — committed ' 우'가 신규 ' 우선'에 흡수된다.
          ② 비확장(순수 부분 재방출) → drop: **정규화 완전일치로 매칭된 신규
             토큰만** 드롭. 접두어 매칭·비매칭 신규는 절대 드롭하지 않는다(더
             완전한 신규를 버리지 않는다).
        - 비매칭 토큰은 어느 방향에서도 건드리지 않는다 — ' is'/' remain'/
          ' reviewed'/' 정' 실측 오탐 사례가 회귀 테스트로 고정됨.
        창 구간 밖 새 오디오("네, 네" 정상 반복)는 dedup_limit 게이트로 자동 보호.
        """
        if not RECONCILE_ENABLED:
            return run
        w = self.window
        if w is None or w.new_lang is None:
            return run
        batch = [t for t in run
                 if t.start is not None and t.detected_language == w.new_lang]
        if not batch:
            return run
        b_max = max(t.start for t in batch)
        limit = w.dedup_limit()
        if min(t.start for t in batch) > limit:
            return run  # 창 구간 밖 새 오디오 — 정상 반복 보호
        committed = [
            tok for tok in all_tokens
            if not tok.is_silence() and not tok.is_boundary()
            and not getattr(tok, "retracted", False)
            and tok.detected_language == w.new_lang
            and tok.start is not None
            # 상한 = b_max + OWN_TOL: 배치 커버리지 너머의 무관한 커밋(먼 미래분) 배제.
            and (w.floor - OWN_TOL) <= tok.start <= b_max + OWN_TOL
        ]
        if not committed:
            return run

        # 매칭 쌍 수집 — (신규 t, 커밋 c, 'exact'|'prefix')
        pairs: List[tuple] = []
        for t in batch:
            nt = _dedup_norm(t.text)
            if not nt:
                continue  # 순수 구두점 신규 토큰은 매칭 후보 아님
            for c in committed:
                nc = _dedup_norm(c.text)
                if not nc:
                    continue  # 순수 구두점 커밋 토큰도 직접 매칭 대상 아님
                if abs(t.start - c.start) > OWN_TOL:
                    continue
                if nt == nc:
                    pairs.append((t, c, "exact"))
                elif nt.startswith(nc) or nc.startswith(nt):
                    pairs.append((t, c, "prefix"))
        if not pairs:
            return run

        matched_committed = {}
        for _, c, _kind in pairs:
            matched_committed[id(c)] = c
        matched_c_max = max(c.start for c in matched_committed.values())

        def _nearest(x: float, pool: List[ASRToken]) -> float:
            return min(abs(x - p.start) for p in pool)

        if b_max > matched_c_max + OWN_TOL:
            # ① supersede — 신규가 기존 커버리지 너머로 확장
            supers = list(matched_committed.values())
            # 매칭 run에 인접(사이/직후)한 구두점-only committed도 함께 소멸 —
            # 유령 접두어 "In."에서 '.'만 남는 잔존 방지. committed는 all_tokens
            # 순서를 보존하므로 직전 토큰이 매칭(또는 그 구두점 연쇄)이면 흡수.
            last_matched = False
            for c in committed:
                if id(c) in matched_committed:
                    last_matched = True
                    continue
                if last_matched and not _dedup_norm(c.text):
                    supers.append(c)
                    continue  # 구두점 연쇄 통과(사이) — last_matched 유지
                last_matched = False
            first_new = min(batch, key=lambda t: t.start)
            for tok in supers:
                tok.retracted = True
                logger.info(
                    "[TimeDedup] action=supersede text=%r start=%.2f dstart=%.2f "
                    "boundary_t=%.2f new_text=%r new_start=%.2f",
                    tok.text, tok.start, _nearest(tok.start, batch),
                    w.boundary_t, first_new.text, first_new.start,
                )
            e_min = min(tok.start for tok in supers)
            if e_min < first_new.start:
                # id(start) 승계 — 소멸 세그먼트의 최초 start를 이어받는다
                # (exp/boundary-tail-dup ⓓ-2의 cur.start = prev.start 패턴).
                logger.info(
                    "[TimeDedup] action=inherit_id new_text=%r start=%.2f dstart=%.2f boundary_t=%.2f",
                    first_new.text, e_min, first_new.start - e_min, w.boundary_t,
                )
                first_new.start = e_min
            return run

        # ② drop — 비확장(순수 부분 재방출): 완전일치 매칭 신규만 드롭
        drop_map = {}
        for t, c, kind in pairs:
            if kind == "exact":
                drop_map.setdefault(id(t), (t, abs(t.start - c.start)))
        if not drop_map:
            return run
        for t, dstart in drop_map.values():
            logger.info(
                "[TimeDedup] action=drop text=%r start=%.2f dstart=%.2f boundary_t=%.2f",
                t.text, t.start, dstart, w.boundary_t,
            )
        return [t for t in run if id(t) not in drop_map]
