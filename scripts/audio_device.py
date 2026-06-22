"""Windows 기본 오디오 장치 조회 및 변경 유틸리티.

comtypes를 통해 비공개 COM 인터페이스 IPolicyConfig를 직접 호출한다.
외부 도구나 추가 패키지 설치 없이 Windows 7+에서 동작한다.
"""

import ctypes
from contextlib import contextmanager
from typing import Optional

import comtypes
import comtypes.client
from comtypes import GUID, HRESULT, IUnknown, COMMETHOD

EDataFlow_eRender  = 0  # 재생 장치
EDataFlow_eCapture = 1  # 녹음 장치
ERole_eConsole     = 0  # 기본 장치 역할
ERole_eMultimedia  = 1  # 멀티미디어 롤
ERole_eCommunications = 2  # 통신 롤 (브라우저 getUserMedia가 사용)
DEVICE_STATE_ACTIVE = 1
STGM_READ = 0
VT_LPWSTR = 31  # PROPVARIANT 문자열 타입

_CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
_IID_IMMDeviceEnumerator  = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
_IID_IMMDeviceCollection  = GUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
_IID_IMMDevice            = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
_IID_IPropertyStore       = GUID("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")
_IID_IPolicyConfig        = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")
_CLSID_PolicyConfigClient = GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", ctypes.c_ulong)]


_PKEY_Device_FriendlyName = _PROPERTYKEY(
    fmtid=GUID("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"),
    pid=14,
)


class _PROPVARIANT(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [
            ("pwszVal", ctypes.c_wchar_p),
            ("punkVal", ctypes.c_void_p),
        ]

    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("value", _Union),
    ]


class _IPropertyStore(IUnknown):
    _iid_ = _IID_IPropertyStore
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount",
            (["out"], ctypes.POINTER(ctypes.c_uint), "cProps")),
        COMMETHOD([], HRESULT, "GetAt",
            (["in"], ctypes.c_uint, "iProp"),
            (["in"], ctypes.POINTER(_PROPERTYKEY), "pkey")),
        COMMETHOD([], HRESULT, "GetValue",
            (["in"], ctypes.POINTER(_PROPERTYKEY), "key"),
            (["in"], ctypes.POINTER(_PROPVARIANT), "pv")),
        COMMETHOD([], HRESULT, "SetValue",
            (["in"], ctypes.POINTER(_PROPERTYKEY), "key"),
            (["in"], ctypes.POINTER(_PROPVARIANT), "propvar")),
        COMMETHOD([], HRESULT, "Commit"),
    ]


class _IMMDevice(IUnknown):
    _iid_ = _IID_IMMDevice
    _methods_ = [
        COMMETHOD([], HRESULT, "Activate",
            (["in"], ctypes.POINTER(GUID), "iid"),
            (["in"], ctypes.c_uint, "dwClsCtx"),
            (["in"], ctypes.c_void_p, "pActivationParams"),
            (["out"], ctypes.POINTER(ctypes.c_void_p), "ppInterface")),
        COMMETHOD([], HRESULT, "OpenPropertyStore",
            (["in"], ctypes.c_uint, "stgmAccess"),
            (["out"], ctypes.POINTER(ctypes.POINTER(_IPropertyStore)), "ppProperties")),
        COMMETHOD([], HRESULT, "GetId",
            (["out"], ctypes.POINTER(ctypes.c_wchar_p), "ppstrId")),
        COMMETHOD([], HRESULT, "GetState",
            (["out"], ctypes.POINTER(ctypes.c_uint), "pdwState")),
    ]


class _IMMDeviceCollection(IUnknown):
    _iid_ = _IID_IMMDeviceCollection
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCount",
            (["out"], ctypes.POINTER(ctypes.c_uint), "pcDevices")),
        COMMETHOD([], HRESULT, "Item",
            (["in"], ctypes.c_uint, "nDevice"),
            (["out"], ctypes.POINTER(ctypes.POINTER(_IMMDevice)), "ppDevice")),
    ]


class _IMMDeviceEnumerator(IUnknown):
    _iid_ = _IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, "EnumAudioEndpoints",
            (["in"], ctypes.c_uint, "dataFlow"),
            (["in"], ctypes.c_uint, "dwStateMask"),
            (["out"], ctypes.POINTER(ctypes.POINTER(_IMMDeviceCollection)), "ppDevices")),
        COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
            (["in"], ctypes.c_uint, "dataFlow"),
            (["in"], ctypes.c_uint, "role"),
            (["out"], ctypes.POINTER(ctypes.POINTER(_IMMDevice)), "ppEndpoint")),
        COMMETHOD([], HRESULT, "GetDevice",
            (["in"], ctypes.c_wchar_p, "pwstrId"),
            (["out"], ctypes.POINTER(ctypes.POINTER(_IMMDevice)), "ppDevice")),
        COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback",
            (["in"], ctypes.c_void_p, "pClient")),
        COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback",
            (["in"], ctypes.c_void_p, "pClient")),
    ]


class _IPolicyConfig(IUnknown):
    _iid_ = _IID_IPolicyConfig
    _methods_ = [
        COMMETHOD([], HRESULT, "GetMixFormat"),
        COMMETHOD([], HRESULT, "GetDeviceFormat"),
        COMMETHOD([], HRESULT, "ResetDeviceFormat"),
        COMMETHOD([], HRESULT, "SetDeviceFormat"),
        COMMETHOD([], HRESULT, "GetProcessingPeriod"),
        COMMETHOD([], HRESULT, "SetProcessingPeriod"),
        COMMETHOD([], HRESULT, "GetShareMode"),
        COMMETHOD([], HRESULT, "SetShareMode"),
        COMMETHOD([], HRESULT, "GetPropertyValue"),
        COMMETHOD([], HRESULT, "SetPropertyValue"),
        COMMETHOD(
            [], HRESULT, "SetDefaultEndpoint",
            (["in"], ctypes.c_wchar_p, "pwstrDeviceId"),
            (["in"], ctypes.c_uint, "eRole"),
        ),
        COMMETHOD([], HRESULT, "SetEndpointVisibility"),
    ]


def _create_enumerator() -> _IMMDeviceEnumerator:
    comtypes.CoInitialize()
    return comtypes.CoCreateInstance(
        _CLSID_MMDeviceEnumerator,
        interface=_IMMDeviceEnumerator,
        clsctx=comtypes.CLSCTX_INPROC_SERVER,
    )


def _get_device_friendly_name(mm_device: _IMMDevice) -> str:
    try:
        prop_store = mm_device.OpenPropertyStore(STGM_READ)
        pv = _PROPVARIANT()
        hr = prop_store.GetValue(
            ctypes.byref(_PKEY_Device_FriendlyName),
            ctypes.byref(pv),
        )
        if hr >= 0 and pv.vt == VT_LPWSTR:
            return pv.value.pwszVal or ""
    except Exception:
        pass
    return ""


def get_default_device_name(flow: int) -> str:
    """현재 기본 오디오 장치의 이름을 반환한다. 실패 시 빈 문자열."""
    try:
        enumerator = _create_enumerator()
        device = enumerator.GetDefaultAudioEndpoint(flow, ERole_eConsole)
        return _get_device_friendly_name(device)
    except Exception:
        pass
    # sounddevice 폴백
    try:
        import sounddevice as sd
        idx = sd.default.device[1] if flow == EDataFlow_eRender else sd.default.device[0]
        return sd.query_devices(idx)["name"]
    except Exception:
        return ""


def _find_device_id(name_substring: str, flow: int) -> Optional[str]:
    """이름에 substring이 포함된 장치의 Windows 장치 ID를 반환한다."""
    try:
        enumerator = _create_enumerator()
        collection = enumerator.EnumAudioEndpoints(flow, DEVICE_STATE_ACTIVE)
        count = collection.GetCount()
        for i in range(count):
            device = collection.Item(i)
            name = _get_device_friendly_name(device)
            if name_substring.lower() in name.lower():
                return device.GetId()
    except Exception as e:
        print(f"[audio_device] 장치 검색 오류: {e}")
    return None


def set_default_device(device_name_substring: str, flow: int) -> bool:
    """이름에 substring이 포함된 장치를 기본 장치로 설정한다. 성공 시 True."""
    device_id = _find_device_id(device_name_substring, flow)
    if not device_id:
        print(f"[audio_device] 장치 없음: '{device_name_substring}' (flow={flow})")
        return False
    try:
        comtypes.CoInitialize()
        policy = comtypes.CoCreateInstance(
            _CLSID_PolicyConfigClient,
            interface=_IPolicyConfig,
            clsctx=comtypes.CLSCTX_ALL,
        )
        ok = True
        for role in (ERole_eConsole, ERole_eMultimedia, ERole_eCommunications):
            hr = policy.SetDefaultEndpoint(device_id, role)
            ok = ok and (hr >= 0)
        return ok
    except Exception as e:
        print(f"[audio_device] SetDefaultEndpoint 실패: {e}")
        return False


def verify_loopback(threshold: float = 0.01, secs: float = 0.4) -> bool:
    """CABLE Input에 톤 재생→CABLE Output 녹음하여 루프백이 실제로 오디오를 통과시키는지 검증.

    RMS가 threshold 미만이면 케이블이 무음(사망/오설정) 상태 → False.
    """
    try:
        import numpy as np
        import sounddevice as sd
        devs = sd.query_devices()

        def _pick(name_low, want_out):
            # '16ch' 변종은 제외하고 정규 CABLE Input/Output 선택
            for i, d in enumerate(devs):
                n = d["name"].lower()
                if name_low in n and "16ch" not in n:
                    if want_out and d["max_output_channels"] > 0:
                        return i
                    if not want_out and d["max_input_channels"] > 0:
                        return i
            return None

        out_idx = _pick("cable input", True)
        in_idx = _pick("cable output", False)
        if out_idx is None or in_idx is None:
            print("[audio_device] verify_loopback: CABLE Input/Output 정규 장치 없음")
            return False
        sr = 16000
        n = int(sr * secs)
        tone = (0.4 * np.sin(2 * np.pi * 440 * np.arange(n) / sr)).astype("float32").reshape(-1, 1)
        rec = sd.playrec(tone, samplerate=sr, channels=1, device=(in_idx, out_idx))
        sd.wait()
        rms = float(np.sqrt(np.mean(rec ** 2)))
        ok = rms > threshold
        print(f"[audio_device] verify_loopback: RMS={rms:.5f} -> {'OK' if ok else 'SILENT(케이블 무음)'}")
        return ok
    except Exception as e:
        print(f"[audio_device] verify_loopback 오류: {e}")
        return False


def is_vbcable_default() -> bool:
    """CABLE Input이 기본 재생 장치인지 확인한다."""
    return "CABLE" in get_default_device_name(EDataFlow_eRender)


@contextmanager
def vbcable_audio_context():
    """VBCable 재생·녹음을 모두 기본 장치로 설정(필요 시)하고 종료 시 복원한다.

    Yields:
        bool: 재생·녹음 둘 다 CABLE로 사용 가능한지 여부.
    """
    original_render  = get_default_device_name(EDataFlow_eRender)
    original_capture = get_default_device_name(EDataFlow_eCapture)

    def _is_regular_cable_input(name: str) -> bool:
        # 정규 'CABLE Input'만 통과 — 'CABLE In 16ch' 변종은 'Input' 미포함이라 자연히 제외
        low = name.lower()
        return "cable input" in low and "16ch" not in low

    render_ok  = _is_regular_cable_input(original_render)
    capture_ok = "CABLE" in original_capture
    changed = False

    if not render_ok:
        set_default_device("CABLE Input", EDataFlow_eRender)
        changed = True
    if not capture_ok:
        set_default_device("CABLE Output", EDataFlow_eCapture)
        changed = True

    # 설정 후 실제로 둘 다 CABLE인지 검증 (재생만 보고 넘어가던 버그 방지)
    # 재생은 정규 'CABLE Input'만 인정 — 'CABLE In 16ch' 변종 리셋을 차단
    render_ok  = _is_regular_cable_input(get_default_device_name(EDataFlow_eRender))
    capture_ok = "CABLE" in get_default_device_name(EDataFlow_eCapture)
    devices_ok = render_ok and capture_ok

    # 기본장치가 정규 CABLE로 잡혔어도, 실제 루프백이 오디오를 통과시키는지 자가진단
    loopback_ok = verify_loopback() if devices_ok else False
    usable = devices_ok and loopback_ok

    if usable:
        print(f"[audio_device] VBCable 준비됨 (재생/녹음 모두 CABLE, 루프백 검증 통과)")
    elif not devices_ok:
        print(f"[audio_device] VBCable 설정 실패 - 재생ok={render_ok} 녹음ok={capture_ok}. "
              f"Windows 소리 설정에서 CABLE Input(재생)·CABLE Output(녹음)을 기본으로 지정하세요.")
    else:
        print("[audio_device] [!] 루프백 무음 - VBCable이 오디오를 통과시키지 않음. 오디오 서비스 재시작/재부팅 필요. path C 측정 중단.")

    try:
        yield usable
    finally:
        if changed:
            if original_render and "CABLE" not in original_render:
                set_default_device(original_render, EDataFlow_eRender)
            if original_capture and "CABLE" not in original_capture:
                set_default_device(original_capture, EDataFlow_eCapture)
            print(f"[audio_device] 오디오 장치 복원 시도 완료")
