"""Generate APIGuard -e and -g headers for iOS."""

from __future__ import annotations

import json
import os
import random
import string
import time
from dataclasses import dataclass, field
from typing import Any

from southwest_checker.apiguard.headers import encode_e, encode_g, encode_tag

HEADER_PREFIX = "X-dUblrIiu-"
DEFAULT_ROTATED_HEADER = "x-nGEtusDen"


def _rand_alnum(n: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def _slash_escape(s: str) -> str:
    return s.replace("/", "\\/")


@dataclass
class IOSDeviceProfile:
    osn: str = "ios"
    osv: str = "26.6.2"
    api: str = "26.6.2"
    hwn: str = "iPhone"
    sdk: str = "4.7.2"
    cid: str = "ios_config"
    app_version: str = "13.20.2"
    bundle_id: str = "com.southwest.iphoneprod"
    device_model: str = "iPhone15,3"
    install_id: str = "644C0AC95B27F6C4"
    sig_hash: str = "124755628032"
    kid: str = ""
    pid: str = ""
    uptime: str = "375603"
    battery: str = "100"
    adv_id: str = "N/A"
    req_header_count: int = 6
    signal_store_len: int = 1715


@dataclass
class EngineState:
    spa: str = "537277"
    kag: str = "539188"
    mpa: str = "537276"
    mpi: str = "8"
    spi: str = "8"
    bio: str = "200"
    bxs: str = "6dd3be4427498ba26867289b336e37c81bd0e4a0884d1a7fcbe996d490b4f6eb"
    age: str = "64975"
    mod: str = "conn"
    eid: list = field(default_factory=list)
    tag_samples: tuple[str, str] = ("11660,1781236290,1781236290", "11798,1781236293,1781236293")
    tag_status_hex: str = "2000a05"


@dataclass
class RequestContext:
    uri: str
    hdr: str = DEFAULT_ROTATED_HEADER
    now_ms: int = 0


def build_tag(profile: IOSDeviceProfile, engine: EngineState, now_ms: int) -> tuple[str, str]:
    nonce = f"{now_ms // 1000}-{_rand_alnum(32)}"
    inner = json.dumps(
        {
            "nonce": nonce,
            "sig": [
                profile.device_model,
                engine.tag_samples[0],
                engine.tag_samples[1],
                engine.tag_status_hex,
            ],
        },
        separators=(",", ":"),
    )
    return encode_tag(inner)


def build_sig(profile: IOSDeviceProfile, now_ms: int) -> str:
    sig = [
        profile.device_model,
        profile.sig_hash,
        profile.install_id,
        profile.bundle_id,
        profile.app_version,
        profile.uptime,
        profile.battery,
        profile.adv_id,
        str(now_ms),
        profile.req_header_count,
        profile.signal_store_len,
        profile.install_id[:8],
    ]
    return _slash_escape(json.dumps(sig))


def build_sensor_string(
    profile: IOSDeviceProfile,
    engine: EngineState,
    ctx: RequestContext,
    tag: tuple[str, str],
) -> str:
    ordered = {
        "eid": _slash_escape(json.dumps(engine.eid)),
        "mod": engine.mod,
        "spa": engine.spa,
        "kid": profile.kid,
        "mpi": engine.mpi,
        "bio": engine.bio,
        "pid": profile.pid,
        "osn": profile.osn,
        "spi": engine.spi,
        "uri": ctx.uri,
        "kag": engine.kag,
        "sig": build_sig(profile, ctx.now_ms),
        "osv": profile.osv,
        "hdr": ctx.hdr,
        "api": profile.api,
        "sdk": profile.sdk,
        "bxs": engine.bxs,
        "hwn": profile.hwn,
        "age": engine.age,
        "cid": profile.cid,
        "mpa": engine.mpa,
        "tag": list(tag),
    }
    return _slash_escape(json.dumps(ordered, separators=(",", ":")))


def build_g_signal(profile: IOSDeviceProfile, engine: EngineState, now_ms: int) -> bytes:
    nonce = f"{now_ms // 1000}-{_rand_alnum(32)}"
    signal = {
        "signalCvmIOSSysJailbreakDetection": {"jailbreak": "0"},
        "signalCvmIOSBuildProperties": {
            "appVersion": profile.app_version,
            "deviceModel": profile.hwn,
            "sdkVersion": profile.sdk,
            "deviceModelNumber": profile.device_model,
            "deviceBrand": "Apple",
            "appBundleName": profile.bundle_id,
            "intAppVersion": "0",
            "cfBundleInfo": f"CFNetwork/Southwest Darwin/{profile.app_version}",
            "appInstallId": profile.install_id,
            "osVersion": f"Version {profile.osv} (Build 23G90)",
            "osType": "ios",
        },
        "signalCvmCommonNonce": {"nonce": nonce},
        "signalCvmIOSBundle": {"sdkType": "static"},
        "signalCvmExtra": [
            {"key": "kernelId", "value": profile.kid},
            {"key": "nonce", "value": _rand_alnum(16)},
            {"key": "all_keys", "value": f"{random.randint(0, 0xFFFFFFFF):08x}"},
            {"key": "flag", "value": f"{random.randint(0, 0xFFFFFFFF):08x}"},
            {"key": "time", "value": f"{random.random():.6f}"},
            {"key": "timeh", "value": f"{random.randint(0, 0xFFFFFFFF):08x}"},
            {"key": "provision", "value": f"{random.randint(0, 0xFFFFFFFF):08x}"},
            {"key": "common", "value": f"{random.randint(0, 0xFFFFFFFF):08x}"},
        ],
        "signalCvmCommonIntegrator": {
            "timestamp": "N/A",
            "shieldProduct": "N/A",
            "shieldVersion": "N/A",
            "sdkVersion": "N/A",
        },
        "signalCvmIOSProvisioning": {"provision": "N/A"},
        "signalCvmIOSDeviceOrSim": {"deviceOrSim": "true"},
        "signalCvmIOSLocaleInfo": {
            "currency": "USD",
            "country": "US",
            "timezone": "-4",
            "language": "en",
        },
        "signalCvmIOSSdkHardware": {
            "timestamp": str(now_ms),
            "availableStorage": "4245008384",
            "numCores": "6",
            "totalRam": "5909987328",
            "uptimeSinceBoot": profile.uptime,
        },
        "signalCvmIOSisRunningOnMac": {"isOnMac": "false"},
        "signalCvmIOSHardwareInfo": {
            "cpuType": "16777228",
            "model": "D74AP",
            "cpuCount": "6",
            "device": profile.device_model,
        },
    }
    return json.dumps(signal, separators=(",", ":")).encode("utf-8")


def generate_e_header(
    profile: IOSDeviceProfile,
    engine: EngineState,
    ctx: RequestContext,
) -> str:
    tag = build_tag(profile, engine, ctx.now_ms)
    sensor = build_sensor_string(profile, engine, ctx, tag).encode("latin1")
    return encode_e(sensor)


def generate_g_header(
    profile: IOSDeviceProfile,
    engine: EngineState,
    now_ms: int,
) -> str:
    signal = build_g_signal(profile, engine, now_ms)
    return encode_g(signal)
