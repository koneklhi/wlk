const isExtension = typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL;
if (isExtension) {
  document.documentElement.classList.add('is-extension');
}
const isWebContext = !isExtension;

let isRecording = false;
let websocket = null;
let recorder = null;
let chunkDuration = 100;
let websocketUrl = "ws://localhost:8000/asr";
let userClosing = false;
let wakeLock = null;
let startTime = null;
let timerInterval = null;
let audioContext = null;
let analyser = null;
let microphone = null;
let workletNode = null;
let recorderWorker = null;
let waveCanvas = document.getElementById("waveCanvas");
let waveCtx = waveCanvas.getContext("2d");
let animationFrame = null;
let waitingForStop = false;
let lastReceivedData = null;
let lastSignature = null;
// 확정(finalized)된 줄 누적 기록. key=line.id(안정 세그먼트 식별자=세션상대 시작초, 문자열화), value=원본 line 객체.
// 서버는 lines[]를 세션 전체 무제한 유지하고(과거 5분 슬라이딩 윈도우 → 무제한, master 606ecac),
// 클라이언트는 델타를 누적해 serverLines 미러로 그 전체를 들고 있으므로,
// 이 누적은 필수가 아니라 중복 안전장치다(pause/resume 격리·저장 payload 조립에도 쓰인다).
let finalizedHistory = new Map();
// 서버-권위 lines[] 미러. 델타 프로토콜(기본)에서 snapshot/diff를 적용해 재구성한 결과이며,
// full 모드(?mode=full)에서는 사용하지 않는다(메시지가 이미 전체 스냅샷).
let serverLines = [];
let serverProtocol = null;     // "delta" | "full" — config 메시지가 알려주는 실제 적용 프로토콜
// 증분 렌더 상태: 화면에 그려진 줄과 1:1. [{html, nodes:[Node,...]}]
// html이 그대로면 그 줄의 DOM은 건드리지 않는다(앞부분 재렌더 비용 제거의 핵심).
let renderedLines = [];
let isPaused = false;          // teardown 됐지만 기록 유지, "시작"으로 재개 대기 중
let committedLines = [];       // 이전 pause 사이클들의 확정 줄을 순서대로 "얼린" append-only 배열. id 충돌에서 격리하는 핵심 장치.
let stopIntent = null;         // 'pause' | 'fullstop' | null — 현재 진행 중인 teardown/EOS가 끝나면 무엇을 할지
let availableMicrophones = [];
let selectedMicrophoneId = null;
let serverUseAudioWorklet = null;
let configReadyResolve;
const configReady = new Promise((r) => (configReadyResolve = r));
let outputAudioContext = null;
let audioSource = null;

waveCanvas.width = 60 * (window.devicePixelRatio || 1);
waveCanvas.height = 30 * (window.devicePixelRatio || 1);
waveCtx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

const statusText = document.getElementById("status");
const startButton = document.getElementById("startButton");
const pauseButton = document.getElementById("pauseButton");
const stopButton = document.getElementById("stopButton");
const recordingInfo = document.getElementById("recordingInfo");
const saveTranscriptButton = document.getElementById("saveTranscriptButton");
const chunkSelector = document.getElementById("chunkSelector");
const websocketInput = document.getElementById("websocketInput");
const websocketDefaultSpan = document.getElementById("wsDefaultUrl");
const linesTranscriptDiv = document.getElementById("linesTranscript");
const timerElement = document.querySelector(".timer");
const themeRadios = document.querySelectorAll('input[name="theme"]');
const microphoneSelect = document.getElementById("microphoneSelect");
const languageSelect = document.getElementById("languageSelect");

const settingsToggle = document.getElementById("settingsToggle");
const settingsDiv = document.querySelector(".settings");

// if (isExtension) {
//   chrome.runtime.onInstalled.addListener((details) => {
//     if (details.reason.search(/install/g) === -1) {
//       return;
//     }
//     chrome.tabs.create({
//       url: chrome.runtime.getURL("welcome.html"),
//       active: true
//     });
//   });
// }

const translationIcon = `<svg xmlns="http://www.w3.org/2000/svg" height="12px" viewBox="0 -960 960 960" width="12px" fill="#5f6368"><path d="m603-202-34 97q-4 11-14 18t-22 7q-20 0-32.5-16.5T496-133l152-402q5-11 15-18t22-7h30q12 0 22 7t15 18l152 403q8 19-4 35.5T868-80q-13 0-22.5-7T831-106l-34-96H603ZM362-401 188-228q-11 11-27.5 11.5T132-228q-11-11-11-28t11-28l174-174q-35-35-63.5-80T190-640h84q20 39 40 68t48 58q33-33 68.5-92.5T484-720H80q-17 0-28.5-11.5T40-760q0-17 11.5-28.5T80-800h240v-40q0-17 11.5-28.5T360-880q17 0 28.5 11.5T400-840v40h240q17 0 28.5 11.5T680-760q0 17-11.5 28.5T640-720h-76q-21 72-63 148t-83 116l96 98-30 82-122-125Zm266 129h144l-72-204-72 204Z"/></svg>`
const silenceIcon = `<svg xmlns="http://www.w3.org/2000/svg" style="vertical-align: text-bottom;" height="14px" viewBox="0 -960 960 960" width="14px" fill="#5f6368"><path d="M514-556 320-752q9-3 19-5.5t21-2.5q66 0 113 47t47 113q0 11-1.5 22t-4.5 22ZM40-200v-32q0-33 17-62t47-44q51-26 115-44t141-18q26 0 49.5 2.5T456-392l-56-54q-9 3-19 4.5t-21 1.5q-66 0-113-47t-47-113q0-11 1.5-21t4.5-19L84-764q-11-11-11-28t11-28q12-12 28.5-12t27.5 12l675 685q11 11 11.5 27.5T816-80q-11 13-28 12.5T759-80L641-200h39q0 33-23.5 56.5T600-120H120q-33 0-56.5-23.5T40-200Zm80 0h480v-32q0-14-4.5-19.5T580-266q-36-18-92.5-36T360-320q-71 0-127.5 18T140-266q-9 5-14.5 14t-5.5 20v32Zm240 0Zm560-400q0 69-24.5 131.5T829-355q-12 14-30 15t-32-13q-13-13-12-31t12-33q30-38 46.5-85t16.5-98q0-51-16.5-97T767-781q-12-15-12.5-33t12.5-32q13-14 31.5-13.5T829-845q42 51 66.5 113.5T920-600Zm-182 0q0 32-10 61.5T700-484q-11 15-29.5 15.5T638-482q-13-13-13.5-31.5T633-549q6-11 9.5-24t3.5-27q0-14-3.5-27t-9.5-25q-9-17-8.5-35t13.5-31q14-14 32.5-13.5T700-716q18 25 28 54.5t10 61.5Z"/></svg>`;
const languageIcon = `<svg xmlns="http://www.w3.org/2000/svg" height="12" viewBox="0 -960 960 960" width="12" fill="#5f6368"><path d="M480-80q-82 0-155-31.5t-127.5-86Q143-252 111.5-325T80-480q0-83 31.5-155.5t86-127Q252-817 325-848.5T480-880q83 0 155.5 31.5t127 86q54.5 54.5 86 127T880-480q0 82-31.5 155t-86 127.5q-54.5 54.5-127 86T480-80Zm0-82q26-36 45-75t31-83H404q12 44 31 83t45 75Zm-104-16q-18-33-31.5-68.5T322-320H204q29 50 72.5 87t99.5 55Zm208 0q56-18 99.5-55t72.5-87H638q-9 38-22.5 73.5T584-178ZM170-400h136q-3-20-4.5-39.5T300-480q0-21 1.5-40.5T306-560H170q-5 20-7.5 39.5T160-480q0 21 2.5 40.5T170-400Zm216 0h188q3-20 4.5-39.5T580-480q0-21-1.5-40.5T574-560H386q-3 20-4.5 39.5T380-480q0 21 1.5 40.5T386-400Zm268 0h136q5-20 7.5-39.5T800-480q0-21-2.5-40.5T790-560H654q3 20 4.5 39.5T660-480q0 21-1.5 40.5T654-400Zm-16-240h118q-29-50-72.5-87T584-782q18 33 31.5 68.5T638-640Zm-234 0h152q-12-44-31-83t-45-75q-26 36-45 75t-31 83Zm-200 0h118q9-38 22.5-73.5T376-782q-56 18-99.5 55T204-640Z"/></svg>`
const speakerIcon = `<svg xmlns="http://www.w3.org/2000/svg" height="16px" style="vertical-align: text-bottom;" viewBox="0 -960 960 960" width="16px" fill="#5f6368"><path d="M480-480q-66 0-113-47t-47-113q0-66 47-113t113-47q66 0 113 47t47 113q0 66-47 113t-113 47ZM160-240v-32q0-34 17.5-62.5T224-378q62-31 126-46.5T480-440q66 0 130 15.5T736-378q29 15 46.5 43.5T800-272v32q0 33-23.5 56.5T720-160H240q-33 0-56.5-23.5T160-240Zm80 0h480v-32q0-11-5.5-20T700-306q-54-27-109-40.5T480-360q-56 0-111 13.5T260-306q-9 5-14.5 14t-5.5 20v32Zm240-320q33 0 56.5-23.5T560-640q0-33-23.5-56.5T480-720q-33 0-56.5 23.5T400-640q0 33 23.5 56.5T480-560Zm0-80Zm0 400Z"/></svg>`;

const TRIGGER_LABELS = { silence: "침묵", punctuation: "종결", language_switch: "언어전환", speaker_change: "화자전환" };

function getWaveStroke() {
  const styles = getComputedStyle(document.documentElement);
  const v = styles.getPropertyValue("--wave-stroke").trim();
  return v || "#000";
}

let waveStroke = getWaveStroke();
function updateWaveStroke() {
  waveStroke = getWaveStroke();
}

function applyTheme(pref) {
  if (pref === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  } else if (pref === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  updateWaveStroke();
}

// Persisted theme preference
const savedThemePref = localStorage.getItem("themePreference") || "system";
applyTheme(savedThemePref);
if (themeRadios.length) {
  themeRadios.forEach((r) => {
    r.checked = r.value === savedThemePref;
    r.addEventListener("change", () => {
      if (r.checked) {
        localStorage.setItem("themePreference", r.value);
        applyTheme(r.value);
      }
    });
  });
}

// React to OS theme changes when in "system" mode
const darkMq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
const handleOsThemeChange = () => {
  const pref = localStorage.getItem("themePreference") || "system";
  if (pref === "system") updateWaveStroke();
};
if (darkMq && darkMq.addEventListener) {
  darkMq.addEventListener("change", handleOsThemeChange);
} else if (darkMq && darkMq.addListener) {
  // deprecated, but included for Safari compatibility
  darkMq.addListener(handleOsThemeChange);
}

async function enumerateMicrophones() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach(track => track.stop());

    const devices = await navigator.mediaDevices.enumerateDevices();
    availableMicrophones = devices.filter(device => device.kind === 'audioinput');

    populateMicrophoneSelect();
    console.log(`Found ${availableMicrophones.length} microphone(s)`);
  } catch (error) {
    console.error('Error enumerating microphones:', error);
    statusText.textContent = "Error accessing microphones. Please grant permission.";
  }
}

function populateMicrophoneSelect() {
  if (!microphoneSelect) return;

  microphoneSelect.innerHTML = '<option value="">Default Microphone</option>';

  availableMicrophones.forEach((device, index) => {
    const option = document.createElement('option');
    option.value = device.deviceId;
    option.textContent = device.label || `Microphone ${index + 1}`;
    microphoneSelect.appendChild(option);
  });

  const savedMicId = localStorage.getItem('selectedMicrophone');
  if (savedMicId && availableMicrophones.some(mic => mic.deviceId === savedMicId)) {
    microphoneSelect.value = savedMicId;
    selectedMicrophoneId = savedMicId;
  }
}

function handleMicrophoneChange() {
  selectedMicrophoneId = microphoneSelect.value || null;
  localStorage.setItem('selectedMicrophone', selectedMicrophoneId || '');

  const selectedDevice = availableMicrophones.find(mic => mic.deviceId === selectedMicrophoneId);
  const deviceName = selectedDevice ? selectedDevice.label : 'Default Microphone';

  console.log(`Selected microphone: ${deviceName}`);
  statusText.textContent = `Microphone changed to: ${deviceName}`;

  if (isRecording) {
    statusText.textContent = "Switching microphone... Please wait.";
    // 마이크 교체는 완전중단이 아니라 일시중단→재개로 처리해 화면 기록을 유지한다.
    pauseRecording().then(() => {
      setTimeout(() => {
        startOrResume();
      }, 1000);
    });
  }
}

// 소스 언어 선택 지속(localStorage). 마이크 select와 동일 패턴:
// 페이지 로드 시 저장값 복원, change 시 저장.
// 마이크와 달리 옵션이 HTML에 정적으로 있으므로 즉시 복원 가능(동적 populate 불필요).
function restoreLanguageSelection() {
  if (!languageSelect) return;
  const savedLang = localStorage.getItem('selectedLanguage');
  if (savedLang && [...languageSelect.options].some((o) => o.value === savedLang)) {
    languageSelect.value = savedLang;
  }
}

function handleLanguageChange() {
  if (!languageSelect) return;
  const value = languageSelect.value || "auto";
  localStorage.setItem('selectedLanguage', value);

  const labelMap = { auto: "자동 (Auto)", ko: "한국어 (Korean)", en: "English" };
  console.log(`Selected source language: ${value}`);
  // 언어는 다음 연결부터 적용된다(마이크처럼 즉시 재연결하지 않음 — 녹음 중엔 select가 비활성).
  statusText.textContent = `Source language: ${labelMap[value] || value} (applies on next connection)`;
}

// Helpers
function fmt1(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(1) : x;
}

let host, port, protocol;
port = 8000;
if (isExtension) {
    host = "localhost";
    protocol = "ws";
} else {
    host = window.location.hostname || "localhost";
    port = window.location.port;
    protocol = window.location.protocol === "https:" ? "wss" : "ws";
}
const defaultWebSocketUrl = `${protocol}://${host}${port ? ":" + port : ""}/asr`;

// Populate default caption and input
if (websocketDefaultSpan) websocketDefaultSpan.textContent = defaultWebSocketUrl;
websocketInput.value = defaultWebSocketUrl;
websocketUrl = defaultWebSocketUrl;

// Optional chunk selector (guard for presence)
if (chunkSelector) {
  chunkSelector.addEventListener("change", () => {
    chunkDuration = parseInt(chunkSelector.value);
  });
}

// WebSocket input change handling
websocketInput.addEventListener("change", () => {
  const urlValue = websocketInput.value.trim();
  if (!urlValue.startsWith("ws://") && !urlValue.startsWith("wss://")) {
    statusText.textContent = "Invalid WebSocket URL (must start with ws:// or wss://)";
    return;
  }
  websocketUrl = urlValue;
  statusText.textContent = "WebSocket URL updated. Ready to connect.";
});

// 클릭 시점까지 확정된 누적 전사 + 최신 미확정 줄을 저장 payload로 변환.
// 저장 버튼 클릭 핸들러와 활성/비활성 상태 판정(updateSaveButtonState) 양쪽에서 재사용한다.
function buildTranscriptPayload() {
  return [...committedLines, ...finalizedHistory.values(), ...((lastReceivedData && lastReceivedData.lines) || []).filter((l) => !l.finalized)]
    .filter((l) => l.speaker !== -2 && (l.text || l.translation))
    .map((l) => ({ speaker: l.speaker, text: (l.text || "").trim(), translation: (l.translation || "").trim() || undefined }));
}

function updateSaveButtonState() {
  saveTranscriptButton.disabled = buildTranscriptPayload().length === 0;
}

// 최종 WebSocket URL 조립: 언어 select 값과 출력 프로토콜을 쿼리파라미터로 병합한다.
// - websocketUrl 전역(입력필드 표시값)은 오염시키지 않고 지역 최종 URL만 만든다.
// - auto = language 파라미터 생략(delete), ko/en = language=<값> 설정(드롭다운이 이김).
// - mode=delta를 명시적으로 붙인다. 서버 기본값은 full(델타 미대응 클라이언트 무수정 호환)이므로,
//   델타를 구현한 이 UI가 opt-in해야 증분 전송을 받는다. 단 사용자가 입력필드에 mode를 직접
//   적었다면 그 값을 존중한다(?mode=full 로 구 동작 비교·디버깅 가능).
// - 사용자가 websocketInput으로 이미 쿼리스트링을 넣었을 수 있어 URL+URLSearchParams로 파싱·병합.
function buildWebSocketUrl() {
  const langValue = languageSelect ? (languageSelect.value || "auto") : "auto";
  try {
    // ws://·wss:// 는 브라우저 URL이 지원하는 special scheme이라 정상 파싱된다.
    const url = new URL(websocketUrl);
    if (langValue === "ko" || langValue === "en") {
      url.searchParams.set("language", langValue);
    } else {
      // auto: 규약상 파라미터를 완전히 제거(빈 값이 아니라 delete).
      url.searchParams.delete("language");
    }
    if (!url.searchParams.has("mode")) {
      url.searchParams.set("mode", "delta");
    }
    return url.toString();
  } catch (e) {
    // 비정상/상대 URL 대비 문자열 폴백(정상 ws://·wss:// 에선 도달하지 않음).
    console.warn("WebSocket URL 파싱 실패, 문자열 폴백 사용:", e);
    let base = websocketUrl;
    if ((langValue === "ko" || langValue === "en") && !/[?&]language=/.test(base)) {
      base += (base.includes("?") ? "&" : "?") + "language=" + langValue;
    }
    if (!/[?&]mode=/.test(base)) {
      base += (base.includes("?") ? "&" : "?") + "mode=delta";
    }
    return base;
  }
}

function setupWebSocket() {
  return new Promise((resolve, reject) => {
    const finalWebSocketUrl = buildWebSocketUrl();
    // 새 연결에는 서버가 새 DiffTracker를 붙여 snapshot(seq=1)부터 다시 보내므로 서버 미러를 비운다.
    serverLines = [];
    console.log("Connecting to WebSocket:", finalWebSocketUrl);
    try {
      websocket = new WebSocket(finalWebSocketUrl);
    } catch (error) {
      statusText.textContent = "Invalid WebSocket URL. Please check and try again.";
      reject(error);
      return;
    }

    websocket.onopen = () => {
      statusText.textContent = "Connected to server.";
      resolve();
    };

    websocket.onclose = async () => {
      if (userClosing) {
        if (waitingForStop) {
          statusText.textContent = "Processing finalized or connection closed.";
          if (lastReceivedData) {
          renderLinesWithBuffer(
              lastReceivedData.lines || [],
              lastReceivedData.buffer_diarization || "",
              lastReceivedData.buffer_transcription || "",
              lastReceivedData.buffer_translation || "",
              0,
              0,
              true
            );
          }
        }
      } else {
        statusText.textContent = "Disconnected from the WebSocket server. (Check logs if model is loading.)";
        if (isRecording) {
          await teardownCapture();
          isPaused = true; // 기록은 유지한 채 일시중단 상태로 전환 — "시작"으로 이어서 재개 가능
        }
      }
      isRecording = false;
      waitingForStop = false;
      userClosing = false;
      lastReceivedData = null;
      websocket = null;
      updateUI();
    };

    websocket.onerror = () => {
      statusText.textContent = "Error connecting to WebSocket.";
      reject(new Error("Error connecting to WebSocket"));
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "config") {
        serverUseAudioWorklet = !!data.useAudioWorklet;
        statusText.textContent = serverUseAudioWorklet
          ? "Connected. Using AudioWorklet (PCM)."
          : "Connected. Using MediaRecorder (WebM).";
        // 실제 적용된 WebSocket 출력 프로토콜(기본 delta = snapshot 1회 + 이후 diff).
        // 구 서버는 protocol 없이 mode만 보내므로 폴백, 둘 다 없으면 full로 간주(하위호환).
        serverProtocol = data.protocol || data.mode || "full";
        console.log(`Server WebSocket protocol: ${serverProtocol}`);
        // 백엔드가 config에 language 필드를 실으면 실제 적용된 소스 언어를 로그로 확인(하위호환: 없으면 무시).
        if (data.language !== undefined) {
          console.log(`Server applied source language: ${data.language}`);
        }
        if (configReadyResolve) configReadyResolve();
        return;
      }

      if (data.type === "ready_to_stop") {
        console.log("Ready to stop received, finalizing display and closing WebSocket.");

        // 완전중단은 fullStop()이 이미 즉시 자체적으로 초기화+소켓 종료를 마쳤으므로,
        // 뒤늦게 도착한 ready_to_stop은 아무 상태도 건드리지 않고 조용히 무시한다.
        if (stopIntent === "fullstop") {
          stopIntent = null;
          return;
        }

        waitingForStop = false;

        if (lastReceivedData) {
          renderLinesWithBuffer(
            lastReceivedData.lines || [],
            lastReceivedData.buffer_diarization || "",
            lastReceivedData.buffer_transcription || "",
            lastReceivedData.buffer_translation || "",
            0,
            0,
            true
          );
        }

        if (stopIntent === "pause") {
          isPaused = true;
          statusText.textContent = "일시 중단됨. 시작을 누르면 이어서 녹음합니다.";
        } else {
          statusText.textContent = "Finished processing audio! Ready to record again.";
        }

        // 자동 저장은 하지 않는다 — 저장은 사용자가 저장 버튼을 눌렀을 때만 수행한다(buildTranscriptPayload 참조).
        updateSaveButtonState();
        updateUI();

        if (websocket) {
          websocket.close();
        }
        stopIntent = null;
        return;
      }

      // 델타 프로토콜(기본): snapshot 1회 + 이후 diff. 서버-권위 미러(serverLines)에 적용해
      // full 스냅샷과 동일한 모양의 상태 객체로 정규화한 뒤, 아래 렌더 경로를 그대로 태운다.
      // full 모드(?mode=full)의 기존 스키마(type 없음) 메시지는 그대로 통과한다(하위호환).
      const state =
        data.type === "snapshot" || data.type === "diff" ? applyServerDelta(data) : data;

      lastReceivedData = state;

      const {
        lines = [],
        buffer_transcription = "",
        buffer_diarization = "",
        buffer_translation = "",
        remaining_time_transcription = 0,
        remaining_time_diarization = 0,
        status = "active_transcription",
      } = state;

      renderLinesWithBuffer(
        lines,
        buffer_diarization,
        buffer_transcription,
        buffer_translation,
        remaining_time_diarization,
        remaining_time_transcription,
        false,
        status
      );
    };
  });
}

// ── 델타 프로토콜 재구성 (순수 로직) ────────────────────────────────────────
// 서버는 매 메시지 전체 lines[]를 보내지 않고 snapshot 1회 + 이후 diff만 보낸다(기본 프로토콜).
// diff의 new_lines는 "append 대상"이 아니라 **공통 prefix 이후의 꼬리 전체**다 — 백엔드가
// 최근 줄을 소급 수정(reconcile/침묵게이트 재개방, ~8초 내)하면 그 줄부터 다시 실린다.
// 따라서 append가 아니라 **꼬리 교체**로 재구성해야 중복이 생기지 않는다.
//   prune → common = n_lines - new_lines.length → lines.slice(0, common).concat(new_lines) → n_lines 검증
// >>> DELTA_RECONSTRUCTION_BEGIN (아래 함수는 DOM/전역에 의존하지 않는 순수 함수 — 단위 검증 대상)
function reconstructLines(prevLines, msg) {
  if (msg.type === "snapshot") {
    return { lines: Array.isArray(msg.lines) ? msg.lines.slice() : [], desync: false };
  }
  let lines = prevLines.slice();
  if (msg.lines_pruned) {
    lines.splice(0, msg.lines_pruned);
  }
  const newLines = msg.new_lines || [];
  const common = Math.max(0, (msg.n_lines || 0) - newLines.length);
  lines = lines.slice(0, common).concat(newLines);
  return { lines, desync: lines.length !== (msg.n_lines || 0) };
}
// <<< DELTA_RECONSTRUCTION_END

// snapshot/diff 메시지를 serverLines에 적용하고, full 스냅샷과 동일한 모양의 상태 객체로 정규화한다.
function applyServerDelta(msg) {
  const { lines, desync } = reconstructLines(serverLines, msg);
  serverLines = lines;
  if (desync) {
    console.warn(
      `[delta] 동기화 불일치: 재구성 ${lines.length}줄 != 서버 n_lines ${msg.n_lines} (seq=${msg.seq}). 재연결이 필요합니다.`
    );
    statusText.textContent = "전사 스트림 동기화 오류 — 재연결이 필요할 수 있습니다.";
  }
  return {
    status: msg.status,
    error: msg.error,
    lines: serverLines,
    buffer_transcription: msg.buffer_transcription || "",
    buffer_diarization: msg.buffer_diarization || "",
    buffer_translation: msg.buffer_translation || "",
    remaining_time_transcription: msg.remaining_time_transcription || 0,
    remaining_time_diarization: msg.remaining_time_diarization || 0,
  };
}

// ── 증분 렌더 ────────────────────────────────────────────────────────────────
// 화면을 통째로(innerHTML) 갈아끼우지 않고, 줄 단위 HTML이 바뀐 지점부터만 DOM을 교체한다.
// 줄 하나가 만드는 노드는 1개가 아닐 수 있으므로(<p>…<div class=textcontent>…</div></p>는
// HTML 파서가 <p>/<div>/<p>로 쪼갠다) 줄마다 노드 "묶음"을 들고 다닌다.
function clearTranscriptDom() {
  linesTranscriptDiv.innerHTML = "";
  renderedLines = [];
  lastSignature = "";
}

function reconcileTranscriptDom(htmls) {
  // 앞에서부터 HTML이 동일한 구간은 건너뛴다 — 이 구간의 DOM 노드는 전혀 건드리지 않는다.
  let common = 0;
  while (common < htmls.length && common < renderedLines.length && renderedLines[common].html === htmls[common]) {
    common++;
  }
  // 공통 구간 이후(=바뀐 꼬리)만 제거하고 다시 만든다.
  for (let i = renderedLines.length - 1; i >= common; i--) {
    for (const node of renderedLines[i].nodes) {
      if (node.parentNode) node.parentNode.removeChild(node);
    }
  }
  renderedLines.length = common;
  if (common === htmls.length) return;

  const fragment = document.createDocumentFragment();
  for (let i = common; i < htmls.length; i++) {
    const tpl = document.createElement("template");
    tpl.innerHTML = htmls[i];
    const nodes = Array.from(tpl.content.childNodes);
    renderedLines.push({ html: htmls[i], nodes });
    for (const node of nodes) fragment.appendChild(node);
  }
  linesTranscriptDiv.appendChild(fragment);
}

function renderLinesWithBuffer(
  lines,
  buffer_diarization,
  buffer_transcription,
  buffer_translation,
  remaining_time_diarization,
  remaining_time_transcription,
  isFinalizing = false,
  current_status = "active_transcription"
) {
  if (current_status === "no_audio_detected") {
    // 안내 문구로 통째 교체. 증분 렌더 상태를 비워, 이후 정상 스냅샷이 오면 전부 다시 그리게 한다
    // (lastSignature도 무효화 — 안 그러면 직전과 같은 lines가 오면 조기 return되어 안내 문구가 남는다).
    clearTranscriptDom();
    reconcileTranscriptDom([
      "<p style='text-align: center; color: var(--muted); margin-top: 20px;'><em>No audio detected...</em></p>",
    ]);
    return;
  }

  // 확정된 줄은 history에 누적하고, 화면엔 history + 아직 미확정인 최신 줄만 합쳐서 그린다.
  // (서버는 lines[]를 무제한 유지·재전송하므로 이 누적은 중복 안전장치 — 전체 교체 렌더만으로도 유지됨.)
  for (const ln of (lines || [])) {
    if (ln.finalized && (ln.text || ln.speaker === -2)) {
      // id(안정 세그먼트 식별자=세션상대 시작초)만 키로 사용: 문법게이트 재조립 시 end는 늘어나도 첫 토큰 시작 시각은 불변이므로 growing-prefix가 같은 항목을 덮어쓴다. 1초 벽시계 문자열과 달리 같은-초 충돌 없음.
      finalizedHistory.set(`${ln.id}`, ln);
    }
  }
  // 미확정(진행중) 줄과 id가 같은 확정 이력 항목은 화면에서 가린다.
  // 백엔드가 침묵으로 조기 확정한 세그먼트를, 이후 마침표 철회 등으로 같은 id(첫 토큰 시작초)에서
  // 계속 이어 전사(재개방)하면 확정판(짧음)과 진행중판(성장)이 같은 id로 공존해
  // 중복 표시된다. 진행중 줄이 그 세그먼트의 현재 진실이므로 stale 확정판을 가린다
  // (진행중 줄이 다시 확정되면 같은 id 키로 덮어써져 자연 정리된다).
  const interimLines = (lines || []).filter((l) => !l.finalized);
  const interimIds = new Set(interimLines.map((l) => `${l.id}`));
  const mergedLines = [
    // 이전 pause 사이클에서 "얼린" 확정 줄. 새 세션의 id(세션상대 시작초, 0부터 재시작)와
    // 우연히 같아도 숨기면 안 되므로 interimIds 필터를 적용하지 않는다.
    ...committedLines,
    ...[...finalizedHistory.values()].filter((l) => !interimIds.has(`${l.id}`)),
    ...interimLines,
  ];
  updateSaveButtonState();

  const showLoading = !isFinalizing && (lines || []).some((it) => it.speaker == 0);
  const showTransLag = !isFinalizing && remaining_time_transcription > 0;
  const showDiaLag = !isFinalizing && !!buffer_diarization && remaining_time_diarization > 0;
  const signature = JSON.stringify({
    lines: mergedLines.map((it) => ({ speaker: it.speaker, text: it.text, translation: it.translation, start: it.start, end: it.end, detected_language: it.detected_language, finalize_trigger: it.finalize_trigger, finalized: it.finalized })),
    buffer_transcription: buffer_transcription || "",
    buffer_diarization: buffer_diarization || "",
    buffer_translation: buffer_translation,
    status: current_status,
    showLoading,
    showTransLag,
    showDiaLag,
    isFinalizing: !!isFinalizing,
  });
  if (lastSignature === signature) {
    const t = document.querySelector(".lag-transcription-value");
    if (t) t.textContent = fmt1(remaining_time_transcription);
    const d = document.querySelector(".lag-diarization-value");
    if (d) d.textContent = fmt1(remaining_time_diarization);
    const ld = document.querySelector(".loading-diarization-value");
    if (ld) ld.textContent = fmt1(remaining_time_diarization);
    return;
  }
  lastSignature = signature;

  // When there are no committed lines yet but buffer text exists (common with
  // slow backends like voxtral on MPS), render the buffer as a standalone line.
  const effectiveLines = mergedLines.length === 0 && (buffer_transcription || buffer_diarization)
    ? [{ speaker: 1, text: "" }]
    : mergedLines;

  // 줄 하나의 마크업 생성 로직(클래스·표시 규칙)은 그대로 유지한다 — 결과 HTML 문자열 배열을 만들고,
  // 이 배열을 직전 렌더와 비교해 바뀐 꼬리만 DOM에 반영한다(reconcileTranscriptDom).
  const lineHtmls = effectiveLines
    .map((item, idx) => {
      let timeInfo = "";
      if (item.start !== undefined && item.end !== undefined) {
        timeInfo = ` ${item.start} - ${item.end}`;
      }

      let speakerLabel = "";
      if (item.speaker === -2) {
        speakerLabel = `<span class="silence">${silenceIcon}<span id='timeInfo'>${timeInfo}</span></span>`;
      } else if (item.speaker == 0 && !isFinalizing) {
        speakerLabel = `<span class='loading'><span class="spinner"></span><span id='timeInfo'><span class="loading-diarization-value">${fmt1(
          remaining_time_diarization
        )}</span> second(s) of audio are undergoing diarization</span></span>`;
      } else if (item.speaker !== 0) {
        const speakerNum = `<span class="speaker-badge">${item.speaker}</span>`;
        speakerLabel = `<span id="speaker">${speakerIcon}${speakerNum}<span id='timeInfo'>${timeInfo}</span></span>`;

        if (item.detected_language) {
          speakerLabel += `<span class="label_language">${languageIcon}<span>${item.detected_language}</span></span>`;
        }

        if (item.finalize_trigger && TRIGGER_LABELS[item.finalize_trigger] && item.speaker !== -2) {
          speakerLabel += `<span class="label_trigger trigger-${item.finalize_trigger}">${TRIGGER_LABELS[item.finalize_trigger]}</span>`;
        }
      }

      let currentLineText = item.text || "";

      if (idx === effectiveLines.length - 1) {
        if (!isFinalizing && item.speaker !== -2) {
            speakerLabel += `<span class="label_transcription"><span class="spinner"></span>Transcription lag <span id='timeInfo'><span class="lag-transcription-value">${fmt1(
              remaining_time_transcription
            )}</span>s</span></span>`;

          if (buffer_diarization && remaining_time_diarization) {
            speakerLabel += `<span class="label_diarization"><span class="spinner"></span>Diarization lag<span id='timeInfo'><span class="lag-diarization-value">${fmt1(
              remaining_time_diarization
            )}</span>s</span></span>`;
          }
        }

        if (buffer_diarization) {
          if (isFinalizing) {
            currentLineText +=
              (currentLineText.length > 0 && buffer_diarization.trim().length > 0 ? " " : "") + buffer_diarization.trim();
          } else {
            currentLineText += `<span class="buffer_diarization">${buffer_diarization}</span>`;
          }
        }
        if (buffer_transcription) {
          if (isFinalizing) {
            currentLineText +=
              (currentLineText.length > 0 && buffer_transcription.trim().length > 0 ? " " : "") +
              buffer_transcription.trim();
          } else {
            currentLineText += `<span class="buffer_transcription">${buffer_transcription}</span>`;
          }
        }
      }
      let translationContent = "";
      if (item.translation) {
        translationContent += item.translation.trim();
      }
      if (idx === effectiveLines.length - 1 && buffer_translation) {
        const bufferPiece = isFinalizing
          ? buffer_translation
          : `<span class="buffer_translation">${buffer_translation}</span>`;
        translationContent += translationContent ? `${bufferPiece}` : bufferPiece;
      }
      if (translationContent.trim().length > 0) {
        currentLineText += `
            <div>
                <div class="label_translation">
                    ${translationIcon}
                    <span class="translation_text">${translationContent}</span>
                </div>
            </div>`;
      }

      return currentLineText.trim().length > 0 || speakerLabel.length > 0
        ? `<p>${speakerLabel}<br/><div class='textcontent' data-trigger='${item.finalize_trigger || ""}'>${currentLineText}</div></p>`
        : `<p>${speakerLabel}<br/></p>`;
    });

  reconcileTranscriptDom(lineHtmls);
  const transcriptContainer = document.querySelector('.transcript-container');
  if (transcriptContainer) {
    transcriptContainer.scrollTo({ top: transcriptContainer.scrollHeight, behavior: "smooth" });
  }
}

function updateTimer() {
  if (!startTime) return;

  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const minutes = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const seconds = (elapsed % 60).toString().padStart(2, "0");
  timerElement.textContent = `${minutes}:${seconds}`;
}

function drawWaveform() {
  if (!analyser) return;

  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteTimeDomainData(dataArray);

  waveCtx.clearRect(
    0,
    0,
    waveCanvas.width / (window.devicePixelRatio || 1),
    waveCanvas.height / (window.devicePixelRatio || 1)
  );
  waveCtx.lineWidth = 1;
  waveCtx.strokeStyle = waveStroke;
  waveCtx.beginPath();

  const sliceWidth = (waveCanvas.width / (window.devicePixelRatio || 1)) / bufferLength;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const v = dataArray[i] / 128.0;
    const y = (v * (waveCanvas.height / (window.devicePixelRatio || 1))) / 2;

    if (i === 0) {
      waveCtx.moveTo(x, y);
    } else {
      waveCtx.lineTo(x, y);
    }

    x += sliceWidth;
  }

  waveCtx.lineTo(
    waveCanvas.width / (window.devicePixelRatio || 1),
    (waveCanvas.height / (window.devicePixelRatio || 1)) / 2
  );
  waveCtx.stroke();

  animationFrame = requestAnimationFrame(drawWaveform);
}

async function startRecording(resume = false) {
  if (resume) {
    // 직전 세션의 확정 줄을 committedLines에 "얼려서" 옮긴다 — 새 세션의 finalizedHistory는 항상 빈 상태로
    // 시작하므로, 새 세션이 매기는 line.id(0부터 재시작)가 committedLines와 절대 같은 Map에서 충돌하지 않는다.
    for (const ln of finalizedHistory.values()) {
      committedLines.push(ln);
    }
  } else {
    // fresh 시작: 완전 초기화
    committedLines = [];
    clearTranscriptDom();
    lastReceivedData = null;
  }
  finalizedHistory.clear();
  lastSignature = "";
  updateSaveButtonState();
  try {
    try {
      wakeLock = await navigator.wakeLock.request("screen");
    } catch (err) {
      console.log("Error acquiring wake lock.");
    }

    let stream;
    
    // chromium extension. in the future, both chrome page audio and mic will be used
    if (isExtension) {
      try {
        stream = await new Promise((resolve, reject) => {
          chrome.tabCapture.capture({audio: true}, (s) => {
            if (s) {
              resolve(s);
            } else {
              reject(new Error('Tab capture failed or not available'));
            }
          });
        });
        
        try {
          outputAudioContext = new (window.AudioContext || window.webkitAudioContext)();
          audioSource = outputAudioContext.createMediaStreamSource(stream);
          audioSource.connect(outputAudioContext.destination);
        } catch (audioError) {
          console.warn('could not preserve system audio:', audioError);
        }
        
        statusText.textContent = "Using tab audio capture.";
      } catch (tabError) {
        console.log('Tab capture not available, falling back to microphone', tabError);
        const audioConstraints = selectedMicrophoneId
          ? { audio: { deviceId: { exact: selectedMicrophoneId }, autoGainControl: false, noiseSuppression: false, echoCancellation: false } }
          : { audio: { autoGainControl: false, noiseSuppression: false, echoCancellation: false } };
        stream = await navigator.mediaDevices.getUserMedia(audioConstraints);
        statusText.textContent = "Using microphone audio.";
      }
    } else if (isWebContext) {
      const audioConstraints = selectedMicrophoneId
        ? { audio: { deviceId: { exact: selectedMicrophoneId }, autoGainControl: false, noiseSuppression: false, echoCancellation: false } }
        : { audio: { autoGainControl: false, noiseSuppression: false, echoCancellation: false } };
      stream = await navigator.mediaDevices.getUserMedia(audioConstraints);
    }

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    microphone = audioContext.createMediaStreamSource(stream);
    microphone.connect(analyser);

    if (serverUseAudioWorklet) {
      if (!audioContext.audioWorklet) {
        throw new Error("AudioWorklet is not supported in this browser");
      }
      await audioContext.audioWorklet.addModule("/web/pcm_worklet.js");
      workletNode = new AudioWorkletNode(audioContext, "pcm-forwarder", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1 });
      microphone.connect(workletNode);

      recorderWorker = new Worker("/web/recorder_worker.js");
      recorderWorker.postMessage({
        command: "init",
        config: {
          sampleRate: audioContext.sampleRate,
        },
      });

      recorderWorker.onmessage = (e) => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          websocket.send(e.data.buffer);
        }
      };

      workletNode.port.onmessage = (e) => {
        const data = e.data;
        const ab = data instanceof ArrayBuffer ? data : data.buffer;
        recorderWorker.postMessage(
          {
            command: "record",
            buffer: ab,
          },
          [ab]
        );
      };
    } else {
      try {
        recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      } catch (e) {
        recorder = new MediaRecorder(stream);
      }
      recorder.ondataavailable = (e) => {
        if (websocket && websocket.readyState === WebSocket.OPEN) {
          if (e.data && e.data.size > 0) {
            websocket.send(e.data);
          }
        }
      };
      recorder.start(chunkDuration);
    }

    startTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);
    drawWaveform();

    isRecording = true;
    isPaused = false;
    updateUI();
  } catch (err) {
    if (window.location.hostname === "0.0.0.0") {
      statusText.textContent =
        "Error accessing microphone. Browsers may block microphone access on 0.0.0.0. Try using localhost:8000 instead.";
    } else {
      statusText.textContent = "Error accessing microphone. Please allow microphone access.";
    }
    console.error(err);
  }
}

// 로컬 오디오/미디어 리소스 정리만 담당(순수 teardown). websocket EOS 전송·userClosing/waitingForStop
// 설정·finalizedHistory 처리는 호출자(pauseRecording/fullStop/onclose)가 각자 책임진다.
async function teardownCapture() {
  if (wakeLock) {
    try {
      await wakeLock.release();
    } catch (e) {
      // ignore
    }
    wakeLock = null;
  }

  if (recorder) {
    try {
      recorder.stop();
    } catch (e) {
    }
    recorder = null;
  }

  if (recorderWorker) {
    recorderWorker.terminate();
    recorderWorker = null;
  }

  if (workletNode) {
    try {
      workletNode.port.onmessage = null;
    } catch (e) {}
    try {
      workletNode.disconnect();
    } catch (e) {}
    workletNode = null;
  }

  if (microphone) {
    microphone.disconnect();
    microphone = null;
  }

  if (analyser) {
    analyser = null;
  }

  if (audioContext && audioContext.state !== "closed") {
    try {
      await audioContext.close();
    } catch (e) {
      console.warn("Could not close audio context:", e);
    }
    audioContext = null;
  }

  if (audioSource) {
    audioSource.disconnect();
    audioSource = null;
  }

  if (outputAudioContext && outputAudioContext.state !== "closed") {
    outputAudioContext.close()
    outputAudioContext = null;
  }

  if (animationFrame) {
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }

  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  timerElement.textContent = "00:00";
  startTime = null;
}

// 일시중단: teardown하되 화면의 전사 기록(finalizedHistory)은 그대로 유지한다.
// 서버측 EOS 응답(ready_to_stop)이 도착하면 isPaused=true로 전환되고, 이후 "시작"을
// 누르면 startRecording(resume=true)이 finalizedHistory를 committedLines로 얼려 이어붙인다.
async function pauseRecording() {
  stopIntent = "pause";
  userClosing = true;
  waitingForStop = true;

  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(new ArrayBuffer(0));
    statusText.textContent = "일시 중단 처리 중...";
  }

  await teardownCapture();

  isRecording = false;
  updateUI();
}

// 완전중단: teardown하고 화면의 전사 기록을 완전히 비운다. 기록을 버리므로 서버의
// ready_to_stop 응답을 기다리지 않고 즉시 초기화 후 소켓도 닫는다.
async function fullStop() {
  stopIntent = "fullstop";
  const wasRecording = isRecording;

  if (wasRecording) {
    userClosing = true;
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(new ArrayBuffer(0));
    }
    await teardownCapture();
  }

  finalizedHistory.clear();
  committedLines = [];
  serverLines = [];
  clearTranscriptDom();
  lastReceivedData = null;
  isPaused = false;
  isRecording = false;
  waitingForStop = false;

  if (websocket) {
    try { websocket.close(); } catch (e) {}
    websocket = null;
  }

  updateSaveButtonState();
  updateUI();
  statusText.textContent = "전사 기록이 초기화되었습니다.";
}

// "시작" 버튼 핸들러: isPaused 상태였다면 이어서 재개(resume), 아니면 새로 시작한다.
async function startOrResume() {
  if (waitingForStop) {
    console.log("Waiting for stop, early return");
    return;
  }
  const resume = isPaused;
  console.log(resume ? "Resuming after pause" : "Connecting to WebSocket");
  try {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      await configReady;
      await startRecording(resume);
    } else {
      await setupWebSocket();
      await configReady;
      await startRecording(resume);
    }
  } catch (err) {
    statusText.textContent = "Could not connect to WebSocket or access mic. Aborted.";
    console.error(err);
  }
}

function updateUI() {
  // 3버튼(시작/일시중단/완전중단) 활성 상태 + 상태 문구를 현재 상태(PROCESSING/RECORDING/PAUSED/IDLE)에 맞게 갱신한다.
  if (recordingInfo) recordingInfo.classList.toggle("active", isRecording);
  // 언어는 연결 시점에만 적용되므로 녹음/처리/일시중단 중에는 변경 잠금(완전중단 후 복원).
  if (languageSelect) languageSelect.disabled = isRecording || waitingForStop || isPaused;

  if (waitingForStop) {
    // PROCESSING: 3버튼 모두 비활성.
    startButton.disabled = true;
    pauseButton.disabled = true;
    stopButton.disabled = true;
    if (
      statusText.textContent !== "Recording stopped. Processing final audio..." &&
      statusText.textContent !== "일시 중단 처리 중..."
    ) {
      statusText.textContent = "Please wait for processing to complete...";
    }
  } else if (isRecording) {
    // RECORDING: 시작 비활성, 일시중단/완전중단 활성.
    startButton.disabled = true;
    pauseButton.disabled = false;
    stopButton.disabled = false;
    statusText.textContent = "";
  } else if (isPaused) {
    // PAUSED: 시작(이어서)·완전중단 활성, 일시중단 비활성.
    startButton.disabled = false;
    pauseButton.disabled = true;
    stopButton.disabled = false;
    statusText.textContent = "일시 중단됨 — 시작을 누르면 이어서 녹음합니다.";
  } else {
    // IDLE: 시작만 활성.
    startButton.disabled = false;
    pauseButton.disabled = true;
    stopButton.disabled = true;
    if (
      statusText.textContent !== "Finished processing audio! Ready to record again." &&
      statusText.textContent !== "Processing finalized or connection closed." &&
      statusText.textContent !== "전사 기록이 초기화되었습니다."
    ) {
      statusText.textContent = "Click to start transcription";
    }
  }
}

startButton.addEventListener("click", startOrResume);
pauseButton.addEventListener("click", pauseRecording);
stopButton.addEventListener("click", fullStop);

if (microphoneSelect) {
  microphoneSelect.addEventListener("change", handleMicrophoneChange);
}
if (languageSelect) {
  languageSelect.addEventListener("change", handleLanguageChange);
  // 옵션이 정적이므로 즉시 복원 가능(스크립트는 body 끝에서 로드 → 요소 존재 보장).
  restoreLanguageSelection();
}
document.addEventListener('DOMContentLoaded', async () => {
  try {
    await enumerateMicrophones();
  } catch (error) {
    console.log("Could not enumerate microphones on load:", error);
  }
});
navigator.mediaDevices.addEventListener('devicechange', async () => {
  console.log('Device change detected, re-enumerating microphones');
  try {
    await enumerateMicrophones();
  } catch (error) {
    console.log("Error re-enumerating microphones:", error);
  }
});


settingsToggle.addEventListener("click", () => {
settingsDiv.classList.toggle("visible");
settingsToggle.classList.toggle("active");
});

saveTranscriptButton.addEventListener("click", async () => {
  const payload = buildTranscriptPayload();
  if (!payload.length) return;
  saveTranscriptButton.disabled = true;
  try {
    const res = await fetch("/api/save-transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: payload }),
    });
    const data = await res.json();
    statusText.textContent = `전사 기록 저장됨: ${data.path}`;
  } catch (e) {
    console.error("전사 저장 실패:", e);
    statusText.textContent = "전사 저장 실패. 콘솔을 확인하세요.";
  } finally {
    updateSaveButtonState();
  }
});

if (isExtension) {
  async function checkAndRequestPermissions() {
    const micPermission = await navigator.permissions.query({
      name: "microphone",
    });

    const permissionDisplay = document.getElementById("audioPermission");
    if (permissionDisplay) {
      permissionDisplay.innerText = `MICROPHONE: ${micPermission.state}`;
    }

    // if (micPermission.state !== "granted") {
    //   chrome.tabs.create({ url: "welcome.html" });
    // }

    const intervalId = setInterval(async () => {
      const micPermission = await navigator.permissions.query({
        name: "microphone",
      });
      if (micPermission.state === "granted") {
        if (permissionDisplay) {
          permissionDisplay.innerText = `MICROPHONE: ${micPermission.state}`;
        }
        clearInterval(intervalId);
      }
    }, 100);
  }

  void checkAndRequestPermissions();
}
