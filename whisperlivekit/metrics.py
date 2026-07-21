"""Lightweight ASR evaluation metrics — no external dependencies.

Provides WER (Word Error Rate) computation via word-level Levenshtein distance,
text normalization, and word-level timestamp accuracy metrics with greedy alignment.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


def normalize_text(text: str) -> str:
    """Normalize text for WER comparison: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    # Normalize unicode (e.g., accented chars to composed form)
    text = unicodedata.normalize("NFC", text)
    # Remove punctuation (keep letters, numbers, spaces, hyphens within words)
    text = re.sub(r"[^\w\s\-']", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_wer(reference: str, hypothesis: str) -> Dict:
    """Compute Word Error Rate using word-level Levenshtein edit distance.

    Args:
        reference: Ground truth transcription.
        hypothesis: Predicted transcription.

    Returns:
        Dict with keys: wer, substitutions, insertions, deletions, ref_words, hyp_words.
        WER can exceed 1.0 if there are more errors than reference words.
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    n = len(ref_words)
    m = len(hyp_words)

    if n == 0:
        return {
            "wer": 0.0 if m == 0 else float(m),
            "substitutions": 0,
            "insertions": m,
            "deletions": 0,
            "ref_words": 0,
            "hyp_words": m,
        }

    # DP table: dp[i][j] = (edit_distance, substitutions, insertions, deletions)
    dp = [[(0, 0, 0, 0) for _ in range(m + 1)] for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = (i, 0, 0, i)
    for j in range(1, m + 1):
        dp[0][j] = (j, 0, j, 0)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                sub = dp[i - 1][j - 1]
                ins = dp[i][j - 1]
                dele = dp[i - 1][j]

                sub_cost = (sub[0] + 1, sub[1] + 1, sub[2], sub[3])
                ins_cost = (ins[0] + 1, ins[1], ins[2] + 1, ins[3])
                del_cost = (dele[0] + 1, dele[1], dele[2], dele[3] + 1)

                dp[i][j] = min(sub_cost, del_cost, ins_cost, key=lambda x: x[0])

    dist, subs, ins, dels = dp[n][m]
    return {
        "wer": dist / n,
        "substitutions": subs,
        "insertions": ins,
        "deletions": dels,
        "ref_words": n,
        "hyp_words": m,
    }


def _align_ops(ref_words: List[str], hyp_words: List[str]) -> List[Tuple[str, Optional[int], Optional[int]]]:
    """Levenshtein 정렬 backtrace를 (연산, 정답 인덱스, 가설 인덱스) 리스트로 반환한다.

    ``_align_words``가 오랫동안 내부에서만 계산하고 버리던 연산 시퀀스를 그대로 노출한 것이다
    (DP·backtrace 본문은 이동만 했고 로직 변경 없음). 인덱스가 함께 실려 있으므로 호출부가
    "어떤 정답 단어가 어떤 가설 단어로 치환됐는지"를 직접 조회할 수 있다.

    Args:
        ref_words: 정답 단어 리스트.
        hyp_words: 가설 단어 리스트.

    Returns:
        ``[(op, ref_idx, hyp_idx), ...]`` (정방향). ``op`` ∈ {"match", "sub", "del", "ins"}.
        ``del``이면 ``hyp_idx``가 None, ``ins``이면 ``ref_idx``가 None이다.

    Note:
        backtrace 동점 우선순위(diagonal > up(del) > left(ins))는 고정 규약이다 —
        compute_segmentation·compute_speaker_sentence_segmentation의 기존 F1 수치가
        이 결정론에 의존하므로 바꾸면 안 된다.
    """
    n = len(ref_words)
    m = len(hyp_words)

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    # Backtrace (n,m)→(0,0). 동점 우선순위 고정: diagonal > up(del) > left(ins).
    ops: List[Tuple[str, Optional[int], Optional[int]]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            ops.append(("match", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops.append(("sub", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("del", i - 1, None))
            i -= 1
        else:
            ops.append(("ins", None, j - 1))
            j -= 1
    ops.reverse()
    return ops


def _align_words(ref_words: List[str], hyp_words: List[str]) -> List[int]:
    """Levenshtein 정렬 backtrace로 각 가설 경계 위치를 정답 단어 공간에 투영한다.

    Args:
        ref_words: 정답 단어 리스트.
        hyp_words: 가설 단어 리스트.

    Returns:
        길이 ``len(hyp_words)+1`` 배열. 각 가설 경계 위치 j(0..m)를 정답 위치 i(0..n)로 투영.
    """
    hyp_to_ref = [0] * (len(hyp_words) + 1)
    ci = cj = 0
    for op, _ri, _hj in _align_ops(ref_words, hyp_words):
        if op in ("match", "sub"):
            ci += 1
            cj += 1
        elif op == "del":
            ci += 1
        else:  # ins
            cj += 1
        hyp_to_ref[cj] = ci
    return hyp_to_ref


# 스크립트(문자 체계) 판정 패턴. whisperlivekit/tokens_alignment.py의 _HANGUL_PATTERN /
# _LATIN_PATTERN과 동일한 패턴을 **로컬로 재정의**한다 — 평가 모듈(metrics.py)은 "외부 의존성
# 없음"이 설계 원칙이라 런타임 모듈을 import하지 않는다(모듈 최상단 독스트링). 두 정의가
# 갈라지지 않는지는 tests/test_metrics_language_mismatch.py의 드리프트 가드가 검증한다.
_HANGUL_PATTERN = re.compile(r"[가-힣]")
_LATIN_PATTERN = re.compile(r"[A-Za-z]")


def _word_script(word: str) -> str:
    """단어 하나의 문자 체계를 판정한다.

    Returns:
        "KO"(한글만) | "EN"(라틴만) | "MIX"(둘 다 포함) | "NEU"(숫자·기호 등 둘 다 없음).
        MIX/NEU는 언어 뒤집힘 판정에서 제외되는 중립 범주다.
    """
    has_ko = bool(_HANGUL_PATTERN.search(word))
    has_en = bool(_LATIN_PATTERN.search(word))
    if has_ko and has_en:
        return "MIX"
    if has_ko:
        return "KO"
    if has_en:
        return "EN"
    return "NEU"


def compute_language_mismatch(reference: str, hypothesis: str) -> Dict:
    """언어 불일치율(LMR) — 정답 단어가 반대 스크립트로 "뒤집혀" 전사된 비율을 측정한다.

    한국어 발화가 영어로 전사되는 "언어잠금" 실패(예: `누가 주인공일까` → `Who is the one`)는
    WER에서는 다른 오류와 섞여 희석되고, 삽입(insertion) 기반 지표로는 잡히지 않는다 —
    이것은 **치환(substitution)**이기 때문이다. 그래서 Levenshtein 정렬의 ``sub`` 연산만 골라
    정답/가설 단어의 스크립트(한글/라틴, 유니코드 판정 — 모델 불필요·결정적)를 비교한다.

    지표 정의::

        LMR_ko     = |{sub: ref=KO ∧ hyp=EN}| / |{ref word: KO}|   (주지표)
        LMR_en     = |{sub: ref=EN ∧ hyp=KO}| / |{ref word: EN}|   (부작용 감시)
        LMR_wer_pp = (ko→en + en→ko) / |ref words|                 (WER 귀속 %p)

    분모를 방향별로 분리하는 이유: 전체 정답 단어로 나누면 KO가 27%뿐인 bong1 같은 데이터에서
    신호가 3.6배 희석된다. ``lmr_wer_pp``만은 WER과 분모를 공유해 "이 실패가 WER 몇 %p를
    차지하는가"를 덧셈 가능한 양으로 준다.

    **이 지표는 하한(lower bound)이다.** 정렬이 치환 대신 ``del``+``ins`` 쌍으로 갈라진
    피해(예: 뒤집힌 구간의 길이가 크게 달라진 경우)는 잡히지 않는다. "정확한 총량"이 아니라
    "적어도 이만큼"으로 해석해야 한다. 그 갈라진 피해의 크기는 ``*_del``·``ins_*`` 카운트와
    ``max_ins_run``/``ins_runs_ge3``(반복 환각 근사)로 별도 관찰한다.

    Args:
        reference: 정답 텍스트. **비언어 태그((웃음) 등)는 호출부(scripts/eval.py 파서)에서
            이미 제거된 상태를 전제**한다 — 여기서 다시 제거하지 않는다(이중 적용 금지).
        hypothesis: 전사(가설) 텍스트.

    Returns:
        Dict — 주요 키:
          - ``lmr_ko`` / ``lmr_en``: float 또는 **None**(해당 스크립트 정답 단어가 0개일 때.
            0.0이 아니다 — 0.0은 "측정했는데 다 틀림"으로 오독된다).
          - ``lmr_wer_pp``: float (정답 단어 0개면 0.0).
          - ``ko_ref_words`` / ``en_ref_words`` / ``ref_words``: 분모들.
          - ``ko_ok`` / ``ko_to_ko`` / ``ko_to_en`` / ``ko_del``: KO 정답 단어의 행방 4분할.
            불변식 ``ko_ok + ko_to_ko + ko_to_en + ko_del == ko_ref_words``가 성립한다
            (따라서 ``ko_to_ko``는 "치환됐지만 EN으로 뒤집히지는 않은 것" — 가설이 KO인 경우뿐
            아니라 MIX/NEU인 경우까지 포함하는 잔여 버킷이다). EN도 동일 구조.
          - ``ins_ko`` / ``ins_en`` / ``ins_neu``: 삽입된 가설 단어의 스크립트별 개수
            (MIX는 ``ins_neu``에 합산).
          - ``max_ins_run`` / ``ins_runs_ge3``: 연속 삽입 런의 최대 길이 / 길이≥3 런 개수.
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    ref_scripts = [_word_script(w) for w in ref_words]
    hyp_scripts = [_word_script(w) for w in hyp_words]

    ko_ref_words = sum(1 for s in ref_scripts if s == "KO")
    en_ref_words = sum(1 for s in ref_scripts if s == "EN")

    counts = {
        "ko_ok": 0, "ko_to_ko": 0, "ko_to_en": 0, "ko_del": 0,
        "en_ok": 0, "en_to_en": 0, "en_to_ko": 0, "en_del": 0,
        "ins_ko": 0, "ins_en": 0, "ins_neu": 0,
    }
    max_ins_run = 0
    ins_runs_ge3 = 0
    cur_ins_run = 0

    for op, ri, hj in _align_ops(ref_words, hyp_words):
        if op == "ins":
            cur_ins_run += 1
            hs = hyp_scripts[hj]
            if hs == "KO":
                counts["ins_ko"] += 1
            elif hs == "EN":
                counts["ins_en"] += 1
            else:  # MIX/NEU
                counts["ins_neu"] += 1
            continue

        # ins 런 종료 지점에서 런 통계 마감.
        if cur_ins_run:
            max_ins_run = max(max_ins_run, cur_ins_run)
            if cur_ins_run >= 3:
                ins_runs_ge3 += 1
            cur_ins_run = 0

        rs = ref_scripts[ri] if ri is not None else None
        if rs not in ("KO", "EN"):
            continue  # MIX/NEU 정답 단어는 방향 판정 대상이 아니다.
        prefix = "ko" if rs == "KO" else "en"
        opposite = "EN" if rs == "KO" else "KO"

        if op == "match":
            counts[f"{prefix}_ok"] += 1
        elif op == "del":
            counts[f"{prefix}_del"] += 1
        else:  # sub
            if hyp_scripts[hj] == opposite:
                counts[f"{prefix}_to_{opposite.lower()}"] += 1
            else:
                counts[f"{prefix}_to_{prefix}"] += 1

    if cur_ins_run:  # 마지막 연산이 ins로 끝난 경우.
        max_ins_run = max(max_ins_run, cur_ins_run)
        if cur_ins_run >= 3:
            ins_runs_ge3 += 1

    n_ref = len(ref_words)
    flips = counts["ko_to_en"] + counts["en_to_ko"]
    return {
        "lmr_ko": counts["ko_to_en"] / ko_ref_words if ko_ref_words else None,
        "lmr_en": counts["en_to_ko"] / en_ref_words if en_ref_words else None,
        "lmr_wer_pp": flips / n_ref if n_ref else 0.0,
        "ko_ref_words": ko_ref_words,
        "en_ref_words": en_ref_words,
        "ref_words": n_ref,
        **counts,
        "max_ins_run": max_ins_run,
        "ins_runs_ge3": ins_runs_ge3,
    }


def _dominant_script(scripts: List[str]) -> Optional[str]:
    """KO/EN 단어 개수를 세어 지배 스크립트를 판정한다(동수·둘 다 0이면 None)."""
    ko = sum(1 for s in scripts if s == "KO")
    en = sum(1 for s in scripts if s == "EN")
    if ko == en:
        return None
    return "KO" if ko > en else "EN"


def compute_language_flip_events(ref_sentences: List, hypothesis: str) -> List[Dict]:
    """정답 문장 단위로 "지배 스크립트가 통째로 뒤집힌" 이벤트를 뽑는다.

    각 정답 문장의 단어 span을 Levenshtein 정렬의 ref→hyp 투영으로 사영해 대응 가설 구간을
    얻고, 양쪽의 지배 스크립트(KO/EN 다수결)가 서로 반대이면 이벤트로 기록한다.

    **정성 리포트 전용 지표다 — 채택/기각 게이트로 쓰면 안 된다.** bong1의 경우 KO 지배 문장이
    22문장 중 7개뿐이라 이벤트 수의 해상도가 낮고(회차 median 1.5건) 1건 차이가 그대로 큰
    비율 변동으로 보이기 때문이다. 정량 판정은 ``compute_language_mismatch``의 LMR을 쓴다.

    Args:
        ref_sentences: 정답 문장 리스트. 각 원소는 ``str`` 또는
            ``{"text": str, "speaker": str}`` dict(화자 정보를 함께 싣고 싶을 때).
        hypothesis: 전사(가설) 텍스트 전체.

    Returns:
        ``[{"ref_script", "hyp_script", "ref_words", "ref_text"(, "speaker")}, ...]``.
        ``ref_words``는 해당 정답 문장의 단어 수(int)다.
    """
    items = []
    for s in ref_sentences:
        if isinstance(s, dict):
            items.append((s.get("text") or "", s.get("speaker")))
        else:
            items.append((s, None))
    kept = [(t, spk) for t, spk in items if normalize_text(t).split()]
    if not kept:
        return []

    ref_words, bounds = _flatten_sentences([t for t, _ in kept])
    starts = [0] + list(bounds)
    ends = list(bounds) + [len(ref_words)]

    hyp_words = normalize_text(hypothesis).split()

    # ref 위치 i(0..n) → hyp 위치 j(0..m) 투영 (_align_words의 방향 반대판).
    ref_to_hyp = [0] * (len(ref_words) + 1)
    ci = cj = 0
    for op, _ri, _hj in _align_ops(ref_words, hyp_words):
        if op in ("match", "sub"):
            ci += 1
            cj += 1
        elif op == "del":
            ci += 1
        else:  # ins
            cj += 1
        ref_to_hyp[ci] = cj

    events: List[Dict] = []
    for (text, speaker), a, b in zip(kept, starts, ends):
        ref_script = _dominant_script([_word_script(w) for w in ref_words[a:b]])
        if ref_script is None:
            continue
        hj0, hj1 = ref_to_hyp[a], ref_to_hyp[b]
        hyp_script = _dominant_script([_word_script(w) for w in hyp_words[hj0:hj1]])
        if hyp_script is None or hyp_script == ref_script:
            continue
        event = {
            "ref_script": ref_script,
            "hyp_script": hyp_script,
            "ref_words": b - a,
            "ref_text": text,
        }
        if speaker is not None:
            event["speaker"] = speaker
        events.append(event)
    return events


def _flatten_sentences(sentences: List[str]):
    """문장 리스트를 단어 스트림 + 문장 경계 위치 리스트로 펼친다.

    각 문장 끝을 경계로 기록하되, 텍스트 전체의 끝(마지막 문장 뒤)은 경계가 아니므로 제외한다.
    """
    words: List[str] = []
    bounds: List[int] = []
    for s in sentences:
        w = normalize_text(s).split()
        if not w:
            continue
        words.extend(w)
        bounds.append(len(words))
    bounds = bounds[:-1]  # 텍스트 끝은 경계가 아님
    return words, bounds


def _match_boundaries(projected: List[int], ref_bounds: List[int], tolerance: int) -> set:
    """투영된 가설 경계를 정답 경계에 그리디(첫 매치 우선)로 매칭한다.

    Args:
        projected: 가설 경계들을 정답 단어 공간에 투영한 위치 리스트(``projected[j]`` = hyp_bounds[j]의 투영).
        ref_bounds: 정답 경계 위치 리스트.
        tolerance: 매칭 허용 오차(단어 수).

    Returns:
        매칭에 성공한 가설 경계의 인덱스 집합(``projected``/``hyp_bounds`` 기준 인덱스).
    """
    used_ref = [False] * len(ref_bounds)
    matched_hyp_indices: set = set()
    for hi, p in enumerate(projected):
        for k, rb in enumerate(ref_bounds):
            if not used_ref[k] and abs(rb - p) <= tolerance:
                used_ref[k] = True
                matched_hyp_indices.add(hi)
                break
    return matched_hyp_indices


def _boundary_prf(matched: int, n_ref: int, n_hyp: int):
    """매칭 개수 + 정답/가설 경계 개수로부터 (precision, recall, f1)을 계산한다."""
    if not n_ref and not n_hyp:
        return 1.0, 1.0, 1.0
    precision = matched / n_hyp if n_hyp else 0.0
    recall = matched / n_ref if n_ref else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def _flatten_blocks(blocks: List[dict]):
    """화자 블록 리스트를 단어 스트림 + (화자경계 위치 리스트, 문장경계 위치 리스트)로 펼친다.

    화자경계 = 블록의 마지막 문장 뒤(다음 블록으로의 전환 지점) — 블록 "전환 횟수" 기준이라
    같은 화자 id가 비인접 재등장해도 매번 별도 경계로 센다. 문장경계 = 같은 블록 내부의
    문장-문장 사이. 텍스트 전체의 끝(마지막 블록의 마지막 문장 뒤)은 경계가 아니므로 제외한다.

    Args:
        blocks: ``[{"speaker": str, "sentences": [str, ...]}, ...]`` (문서 순서).

    Returns:
        (words, speaker_bounds, sentence_bounds) 튜플.
    """
    words: List[str] = []
    tagged: List[tuple] = []  # (word 위치, "speaker" | "sentence")
    for block in blocks:
        sentences = block.get("sentences", [])
        n_sent = len(sentences)
        for si, s in enumerate(sentences):
            w = normalize_text(s).split()
            if not w:
                continue
            words.extend(w)
            category = "speaker" if si == n_sent - 1 else "sentence"
            tagged.append((len(words), category))
    tagged = tagged[:-1]  # 텍스트 끝은 경계가 아님(마지막 기록은 항상 "speaker" 카테고리였을 것)
    speaker_bounds = [p for p, c in tagged if c == "speaker"]
    sentence_bounds = [p for p, c in tagged if c == "sentence"]
    return words, speaker_bounds, sentence_bounds


def compute_segmentation(
    ref_sentences: List[str],
    hyp_sentences: List[str],
    tolerance: int = 1,
) -> Dict:
    """문장 경계 분리 정확도를 단어 정렬 기반 F1로 측정한다.

    정답·가설 문장을 단어 스트림으로 펼치고 문장 끝 위치를 경계로 표시한 뒤,
    Levenshtein 정렬로 가설 경계를 정답 단어 공간에 투영해 ±tolerance 단어 이내면 매칭한다.

    Args:
        ref_sentences: 정답 문장 리스트 (각 원소가 한 문장).
        hyp_sentences: 가설 문장 리스트 (각 원소가 확정된 한 문장).
        tolerance: 경계 매칭 허용 오차(단어 수).

    Returns:
        Dict with keys: f1, precision, recall, ref_sentences, hyp_sentences, matched_boundaries.
    """
    ref_words, ref_bounds = _flatten_sentences(ref_sentences)
    hyp_words, hyp_bounds = _flatten_sentences(hyp_sentences)

    hyp_to_ref = _align_words(ref_words, hyp_words)
    projected = [hyp_to_ref[b] for b in hyp_bounds]

    matched_idx = _match_boundaries(projected, ref_bounds, tolerance)
    matched = len(matched_idx)
    precision, recall, f1 = _boundary_prf(matched, len(ref_bounds), len(hyp_bounds))

    return {
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "ref_sentences": len([s for s in ref_sentences if normalize_text(s).split()]),
        "hyp_sentences": len([s for s in hyp_sentences if normalize_text(s).split()]),
        "matched_boundaries": matched,
    }


def compute_speaker_sentence_segmentation(
    blocks: List[dict],
    hyp_sentences: List[str],
    tolerance: int = 1,
) -> Dict:
    """화자분리 F1(1순위)·문장분리 F1(3순위)을 하나의 공유 정렬로 동시에 산출한다.

    blocks(화자 턴 헤더 + 문장별 줄바꿈 신형식 정답을 파싱한 결과)를 단어 스트림으로 펼쳐
    화자경계·문장경계 두 집합을 얻고, hyp_sentences도 한 번만 펼쳐 정답 단어 공간에 정렬한다.
    이 "공유 정렬"을 두 경계 집합에 각각 매칭해 독립적인 precision/recall/f1을 낸다.

    precision 분모(=이 지표의 "가설 경계 수")는 전체 hyp 경계 수가 아니라, 그 경계가
    반대쪽 경계 유형에도 매칭되지 않은("설명되지 않은") 경계만 포함한다 — 화자경계에 붙어야 할
    hyp 분리가 문장경계에도 우연히 걸쳐 있다고 화자 precision을 깎지 않기 위함이다(반대도 동일).
    즉 한쪽 경계로 "설명되는" over-split은 그 자체로는 나쁜 것이 아니고(문장 내부 분리는
    nice-to-have), 이유가 아예 없는(어느 경계에도 안 걸리는) over-split만 두 지표 모두의
    precision을 깎는다. 이렇게 해야 두 지표가 서로 독립적으로 "제 역할"만 평가한다.

    Args:
        blocks: parse_speaker_sentence_reference()가 반환한 "blocks" 리스트,
            즉 ``[{"speaker": str, "sentences": [str, ...]}, ...]``.
        hyp_sentences: STT가 확정한 줄(문장) 리스트. compute_segmentation의 hyp_sentences와 동일 형태.
        tolerance: 경계 매칭 허용 오차(단어 수).

    Returns:
        {
          "speaker": {"f1": float, "precision": float, "recall": float,
                      "matched_boundaries": int, "ref_boundaries": int, "hyp_boundaries": int},
          "sentence": (동일 형태) 또는 None — 정답의 블록 내부 문장경계가 0개(모든 블록이
                      단일 문장, 예 ytn2)이면 문장분리 F1은 해당 없음이므로 None을 반환한다
                      (0.0이 아님 — 0.0은 "측정했는데 다 틀림"이라는 뜻이 되어 버려 오독을 유발한다).
        }
    """
    ref_words, speaker_bounds, sentence_bounds = _flatten_blocks(blocks)
    hyp_words, hyp_bounds = _flatten_sentences(hyp_sentences)

    hyp_to_ref = _align_words(ref_words, hyp_words)
    projected = [hyp_to_ref[b] for b in hyp_bounds]

    speaker_matched_idx = _match_boundaries(projected, speaker_bounds, tolerance)
    sentence_matched_idx = _match_boundaries(projected, sentence_bounds, tolerance)
    n_hyp = len(hyp_bounds)
    unexplained = set(range(n_hyp)) - speaker_matched_idx - sentence_matched_idx

    speaker_matched = len(speaker_matched_idx)
    speaker_hyp_boundaries = speaker_matched + len(unexplained)
    sp_precision, sp_recall, sp_f1 = _boundary_prf(speaker_matched, len(speaker_bounds), speaker_hyp_boundaries)
    speaker_result = {
        "f1": sp_f1,
        "precision": sp_precision,
        "recall": sp_recall,
        "matched_boundaries": speaker_matched,
        "ref_boundaries": len(speaker_bounds),
        "hyp_boundaries": speaker_hyp_boundaries,
    }

    sentence_result = None
    if sentence_bounds:
        sentence_matched = len(sentence_matched_idx)
        sentence_hyp_boundaries = sentence_matched + len(unexplained)
        se_precision, se_recall, se_f1 = _boundary_prf(
            sentence_matched, len(sentence_bounds), sentence_hyp_boundaries
        )
        sentence_result = {
            "f1": se_f1,
            "precision": se_precision,
            "recall": se_recall,
            "matched_boundaries": sentence_matched,
            "ref_boundaries": len(sentence_bounds),
            "hyp_boundaries": sentence_hyp_boundaries,
        }

    return {"speaker": speaker_result, "sentence": sentence_result}


def compute_timestamp_accuracy(
    predicted: List[Dict],
    reference: List[Dict],
) -> Dict:
    """Compute timestamp accuracy by aligning predicted words to reference words.

    Uses greedy left-to-right alignment on normalized text. For each matched pair,
    computes the start-time delta (predicted - reference).

    Args:
        predicted: List of dicts with keys: word, start, end.
        reference: List of dicts with keys: word, start, end.

    Returns:
        Dict with keys: mae_start, max_delta_start, median_delta_start,
        n_matched, n_ref, n_pred. Returns None values if no matches found.
    """
    if not predicted or not reference:
        return {
            "mae_start": None,
            "max_delta_start": None,
            "median_delta_start": None,
            "n_matched": 0,
            "n_ref": len(reference),
            "n_pred": len(predicted),
        }

    # Normalize words for matching
    pred_norm = [normalize_text(p["word"]) for p in predicted]
    ref_norm = [normalize_text(r["word"]) for r in reference]

    # Greedy left-to-right alignment
    deltas_start = []
    ref_idx = 0
    for p_idx, p_word in enumerate(pred_norm):
        if not p_word:
            continue
        # Scan forward in reference to find a match (allow small skips)
        search_limit = min(ref_idx + 3, len(ref_norm))
        for r_idx in range(ref_idx, search_limit):
            if ref_norm[r_idx] == p_word:
                delta = predicted[p_idx]["start"] - reference[r_idx]["start"]
                deltas_start.append(delta)
                ref_idx = r_idx + 1
                break

    if not deltas_start:
        return {
            "mae_start": None,
            "max_delta_start": None,
            "median_delta_start": None,
            "n_matched": 0,
            "n_ref": len(reference),
            "n_pred": len(predicted),
        }

    abs_deltas = [abs(d) for d in deltas_start]
    sorted_abs = sorted(abs_deltas)
    n = len(sorted_abs)
    if n % 2 == 1:
        median = sorted_abs[n // 2]
    else:
        median = (sorted_abs[n // 2 - 1] + sorted_abs[n // 2]) / 2

    return {
        "mae_start": sum(abs_deltas) / len(abs_deltas),
        "max_delta_start": max(abs_deltas),
        "median_delta_start": median,
        "n_matched": len(deltas_start),
        "n_ref": len(reference),
        "n_pred": len(predicted),
    }
