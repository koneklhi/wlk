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
        hr = policy.SetDefaultEndpoint(device_id, ERole_eConsole)
        return hr >= 0
    except Exception as e:
        print(f"[audio_device] SetDefaultEndpoint 실패: {e}")
        return False


def is_vbcable_default() -> bool:
    """CABLE Input이 기본 재생 장치인지 확인한다."""
    return "CABLE" in get_default_device_name(EDataFlow_eRender)


@contextmanager
def vbcable_audio_context():
    """VBCable이 기본 장치가 아니면 임시로 설정하고 종료 시 원래 장치로 복원한다.

    Yields:
        bool: VBCable 사용 가능 여부 (설정 성공 또는 이미 설정됨)
    """
    original_render  = get_default_device_name(EDataFlow_eRender)
    original_capture = get_default_device_name(EDataFlow_eCapture)
    changed = False

    if not is_vbcable_default():
        ok_render  = set_default_device("CABLE Input",  EDataFlow_eRender)
        ok_capture = set_default_device("CABLE Output", EDataFlow_eCapture)
        changed = ok_render and ok_capture
        if changed:
            print(f"[audio_device] VBCable 설정 완료 (이전 재생: {original_render})")
        else:
            print("[audio_device] VBCable 자동 설정 실패 — Windows 소리 설정을 수동으로 변경하세요.")
    else:
        changed = True

    try:
        yield changed
    finally:
        if changed and original_render and "CABLE" not in original_render:
            set_default_device(original_render,  EDataFlow_eRender)
            set_default_device(original_capture, EDataFlow_eCapture)
            print(f"[audio_device] 오디오 장치 복원: {original_render}")
