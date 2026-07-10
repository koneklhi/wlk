# /eval-report — 최근 평가 결과를 색깔 하이라이트 HTML 리포트로 생성·열기

가장 최근 `scripts/eval.py` 산출 JSON(`.omc/benchmarks/*.json`)을 찾아
`scripts/render_eval_report.py`로 전사 vs 정답 단어 단위 diff HTML 리포트를 생성하고,
로컬 기본 브라우저로 바로 연다. 삭제=빨강 취소선, 삽입=파랑, 치환=노랑,
Case B(단어 중간 분절)=굵은 빨강 테두리, 문장별 확정 트리거 칩을 표시한다. HTML은
폰트·스크립트·CDN 없이 완전 자체완결이며 **외부(Artifact) 게시를 시도하지 않는다** —
로컬 파일 열기만 한다.

## 기본 사용법

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"

# ① 최근 수정된 벤치마크 JSON 후보 확인 (실제 수정시각 기준 — 파일명순 금지)
Get-ChildItem .omc/benchmarks/*.json |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 8 Name, LastWriteTime, @{n="KB";e={[int]($_.Length/1KB)}}

# ② 렌더 + 로컬 브라우저 열기 (합칠 JSON들을 공백으로 나열)
$out = ".omc/transcripts/eval_report_$ts.html"
.venv\Scripts\python.exe scripts/render_eval_report.py `
  .omc/benchmarks/eval_regimev2_testset_N3.json .omc/benchmarks/eval_regimev2_heldout.json `
  --output $out --title "STT 평가 리포트 $ts"
Start-Process (Resolve-Path $out).Path
```

## 실행 절차 (Claude가 따를 순서)

1. **이번 대화에서 방금 eval.py를 실행했다면** 그 `--output` JSON 경로(들)를 그대로 인자로
   쓴다(자동탐지 건너뜀). 테스트셋과 held-out을 각각 저장했다면 **둘 다** 한 번에 넘긴다.
2. 아니면 자동탐지: `Sort-Object LastWriteTime -Descending`으로 가장 최근 JSON을 기준점으로
   삼는다. **`Sort-Object Name`은 명명규칙(eval_YYYYMMDD_HHMM / eval_expNNN / eval_baseline
   / phase2_ 등 혼재)이 뒤섞여 신뢰 불가** — 반드시 LastWriteTime.
3. **여러 JSON 병합 판단**: 최신 JSON과 **수정시각이 서로 30분 이내**인 JSON을 같은 측정
   배치 후보로 본다. 아래 스니펫으로 각 후보의 내부 오디오 파일 집합·repeat·git_sha를 확인해,
   **오디오 파일 집합이 겹치지 않으면**(예: 테스트셋 bong1/ytn2/sbs1 + held-out
   ytn1/eng1/kinno) 한 리포트로 합친다. **겹치면**(같은 파일 재측정) 가장 최근 것만 쓴다.
4. 후보가 애매하면 후보 목록(파일명·시각·내부 파일·repeat)을 **사용자에게 보여주고** 무엇을
   합칠지 확인한 뒤 진행한다.
5. 선택한 JSON들을 render_eval_report.py에 **공백 구분 위치 인자**로 한 번에 넘긴다(스크립트가
   같은 오디오 basename 기준으로 회차를 병합한다). `--output`은 타임스탬프를 붙여 덮어쓰기 방지.
6. `Start-Process (Resolve-Path $out).Path`로 로컬 기본 브라우저에서 연다.
7. 생성 경로·합친 JSON 목록·파일/회차 수를 사용자에게 보고한다.

### 후보 JSON 내용 확인 스니펫 (병합 판단용)

```powershell
foreach ($f in (Get-ChildItem .omc/benchmarks/*.json |
                Sort-Object LastWriteTime -Descending | Select-Object -First 6)) {
  $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
  $audio = ($j.files | ForEach-Object { Split-Path $_.audio_file -Leaf } |
            Sort-Object -Unique) -join ", "
  "{0} | {1} | repeat={2} | sha={3} | {4}" -f `
    $f.Name, $f.LastWriteTime, $j.repeat, $j.provenance.git_sha, $audio
}
```

## 주의사항

- **Artifact 게시 금지**: 생성 HTML은 이미 완전한 `<!DOCTYPE html>` 문서라 Artifact 도구가
  자기 `<head>/<body>` 틀로 이중 래핑하면 깨진다("page not found" 재현). **로컬 열기
  (Start-Process)만** 쓴다.
- 출력은 `.omc/transcripts/`에 타임스탬프 파일로 쌓인다.
- render_eval_report.py는 whisperlivekit을 import하지 않으므로 서버·모델 로딩 없이 즉시 실행.
- 상대경로 `--output`은 실행 위치에 따라 어긋날 수 있어 브라우저 열기는 `Resolve-Path`로
  절대경로화한다.
