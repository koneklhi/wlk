# 코드스위칭 후속 개선 백로그 (GOAL_SCRIPT_ANCHOR_REDETECT §3.5 탐사 산출물)

> 2026-07-09, Exp-175(스크립트-앵커 재감지 게이트) 루프의 잔여 시간 탐사에서 수집한
> **잔존 실패 사례 카탈로그 + 개선 방향 제안**. 우선순위 순. 구현은 하지 않았다 — 분석·설계 제안까지만.
> 실측 근거는 Exp-175 측정 산출물(`worktrees/script-anchor-redetect/.omc/` 하위 benchmarks/transcripts/server_logs)에 있다.

## 1. 미방출형 전환 서두 유실 (non-emission front loss) — 최우선

- **증상**: 구언어 잠금 중 새 언어 발화 서두에서 디코더가 토큰을 **아예 방출하지 않아**(비-fire),
  침묵/화자전환 트리거가 늦게 도착했을 때 keep 창 밖 서두 오디오가 유실된다.
- **실측 근거**:
  - ytn2 R3(채택 N=3): 정답 "There is more work to be done, however..." → 전사 "to be done, however..."
    ("There is more work" 유실). 해당 회차 `[ScriptAnchorRedetect]` 발동 0회 — **반전 streak 자체가 생성되지 않음**.
  - sbs1 스크리닝 R1: 정답 "From a satellite image, the Republic of Korea..." → 전사 "the Republic of Korea..."부터.
    서버 로그(`server_sbs1_C_R1_20260709_085834.log:3012`) — diar `[NewSpeaker]` 도착 시점에 버퍼가 0.48s뿐
    (`keep_secs=1.53` 요청에도 `kept_segments_len=0.48s`)이라 서두 오디오가 이미 소실, en 토큰 방출 이력 없음.
- **가설**: AlignAtt가 잠긴 언어와 다른 음향에서 attention 비-fire → 방출 정지. 그 사이 오디오가
  audio_max_len 트림/직전 배치 소비로 흘러가고, 뒤늦은 트리거의 재디코딩 창(keep_secs)이 서두를 못 덮는다.
- **제안 방향**: ⓐ 전환 적용 시 재디코딩 창 하한을 "diar 경계·고정 keep"이 아니라 **마지막 방출 토큰 끝 시각**으로
  당겨 미방출 구간 전체를 덮기(`refresh_segment(keep_secs=...)` 계산부, `backend.py new_speaker` /
  `align_att_base.py _trim_segments_to_recent`). ⓑ 또는 "오디오 전진 vs 방출 정지" 짧은 워치독(1~2s급, 기존
  STALL_RECOVER_SEC=10s의 경량판)으로 비-fire 구간에서 언어 재감지를 선제 트리거.
- **예상 게이트 리스크**: 창 확대는 재방출 중복(전환 세금) 재발(Exp-166 keep 스윕 교훈: 4.5s에서 방송환각),
  경량 워치독은 정상 침묵 구간 오탐. MAX_KEEP(5.0s) 상한 유지 필수.

## 2. ①′ locked-lang 음차 환각 (스크립트-앵커 사각지대, Exp-172 실측 재확인)

- **증상**: 구언어 잠금 중 반대 언어 발화가 잠긴 언어의 음차로 환각 디코딩 — 출력 스크립트 반전이
  없어 스크립트-앵커 재감지로 원리상 포착 불가.
- **실측 근거**: bong1 R1(채택 N=3, max 36.0%): 정답 "아니 그 플라스틱 말랑말랑한 것도 만들었죠" →
  전사 "plus as a mallang mallang on what to make sure we got an answer for"(en 잠금 중 한국어를 영어 음차로).
  같은 회차 "보통" → "Potong". 빈도: bong1 3회 중 1~2회 재현(Exp-172 "plastic sorry malang"과 동일 유형).
- **가설**: turbo가 불확실 구간에서 "그럴듯한" 잠긴 언어 출력을 생성하는 경향(Exp-158 계열)과 언어 고착의 결합.
- **제안 방향**: 스크립트 반전 대신 **저신뢰 신호 조합**(avg_logprob 급락 + lang_id 확률 경합)을 보조
  재감지 트리거로 검토. 단 순수 확률 기반 주기 체크는 Exp-160에서 스퓨리어스 전환으로 기각된 전례 —
  min_prob 0.90 이상 + "저신뢰 지속" 전제 필수. 별도 설계 세션 권장.
- **예상 게이트 리스크**: ytn2 스퓨리어스 전환 → 방송클로징 환각 재발(Exp-160) — 가장 조심스러운 항목.

## 3. 세션초입 buffer 유실 (Exp-172 ⑶ 재확인)

- **증상**: 세션 시작 직후 언어 미확정 상태(감지 문턱 2.0s 대기) 동안 방출이 보류되고, 그 사이 서두가 유실.
- **실측 근거**: sbs1 채택 N=3 **3/3 전부** 정답 서두 "현지 시간 5일 미국 육군 전쟁 대학 강연에 나선
  제이비어 브런슨" 유실(R3는 "제이비어 브런슨"부터 시작 — 부분 개선이나 여전히 앞부분 소실).
  Exp-172에서 3파일 공통 확인된 기존 실패모드.
- **제안 방향**: 최초 언어 확정 시(`_apply_detected_language` 최초 감지 분기) 버퍼 전체를 재디코딩
  대상으로 유지하고 있는지 검증 — `first_timestamp` 게이트와 buffer 방출 경로(`backend.py:602` detected_language
  None 시 buffer 적재) 추적. diar-spike first_timestamp 회귀 전례([diarization-spike-first-timestamp-regression]) 주의.
- **예상 게이트 리스크**: 낮음(세션 초입 한정) — 단 워밍업/제로샷 구간 환각 재방출 가능성.

## 4. bong1 필러/웃음 환각 (C안 — AnchorRepeatFilter 사각지대, 별도 루프 대상)

- **증상**: 웃음·박수 구간에서 "Thank you"/"Ha ha" 필러 환각 + 환각 인명("That's right, Phil",
  "Good David Plylar" — Exp-174에서도 관측).
- **실측 근거**: bong1 R1(max 36.0%): "This map Thank you. Thank you So", "Ha ha Ha ha! No Oh, my God".
  `[ScriptAnchorRedetect]` 발동 0회 회차 — 이 게이트와 인과 무관(en 잠금 중 en 필러 = 스크립트 반전 없음, 스코프 밖).
- **제안 방향**: Exp-169가 남긴 "근접 시간창 내 앵커 총 등장" 재설계(가변 변주구 storm 사각지대) +
  Exp-165 결론(웃음 전용 비-ASR 분류기)의 별도 설계 — GOAL_CODESWITCH_BOUNDARY C안 루프로 분리(이 루프 스코프 밖).
- **예상 게이트 리스크**: Exp-163(후처리 드롭 무력)·Exp-169(재감지 arm 자기강화 루프) 교훈 준수 필요.

## 5. 문장 중복 재방출 (dup)

- **증상**: 재디코딩 창 겹침 시 동일 문장/구가 이중 방출. CrossBatchFilter는 "완전 동일 인접 단어"만
  제거해 문장 단위 중복은 통과.
- **실측 근거**: sbs1 R3 "사령관은 관점이 바뀌면 지리적 의미도 완전히 달라진다.고 강조했습니다" 중복(3/3 유사),
  bong1 R1 "It's just a It's just a rock", "Everyone Everyone here", "that I had the most that I had the most".
  ytn1 탐사 회차(28.2%, 발동 0회): en 전환부에서 같은 문장의 **3중 재디코딩 churn** — "I want to first thank
  Thank you very I WANT TO THANK MINISTER JUNG FOR HOSTING I'd like to thank Minister Zhang..." + ko 문장
  전체 중복("미국은 대한민국 방위에... 있습니다" ×2) — held-out에서도 dup가 WER 상승 주범임을 확인.
- **제안 방향**: 철회(retraction) 구역 규칙(Exp-171/174)을 전환 경계 외 재디코딩 일반(화자전환 refresh)으로
  확장 검토 — 재디코딩 창 시작 이후 기존 커밋 토큰과의 겹침 검사. 또는 n-gram(2~4) 단위 인접 중복 필터 확장.
- **예상 게이트 리스크**: 정상 반복 발화("네, 네")·강조 반복 오탐 — Exp-002/028/057 기존 필터와 중복 설계 금지.

---

### 참고 — 이번 루프(Exp-175)가 메운 것과 남긴 것

- **메움**: 방출형(오디코드형) 전환 반전 지속 시 재감지 트리거 부재 — 스크립트-앵커 재감지 게이트
  (발동 5건 전부 정당, 오탐 0, Exp-172 확정 유실 사례 "You don't understand" 직접 복구 실측).
- **남김**: 위 1(미방출형)·2(음차 환각)는 "방출된 반전"이 존재하지 않아 이 설계로 원리상 포착 불가 —
  별도 신호(비-fire 워치독, 저신뢰 조합)가 필요하다.
