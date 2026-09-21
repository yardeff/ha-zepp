"""Async client for Zepp Cloud API."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any
import urllib.parse
import aiohttp

from .const import DEFAULT_REGIONS
from .device_catalog import resolve_device_name

_LOGGER = logging.getLogger(__name__)

ZEPP_CHANNEL = "a100900101016"


class ZeppAuthError(Exception):
    """Authentication failed."""


class ZeppConnectionError(Exception):
    """Connection error to Zepp servers."""


def decode_band_summary(summary_base64: str) -> dict[str, Any]:
    """Decode base64 encoded band summary payload."""
    try:
        raw_bytes = base64.b64decode(summary_base64)
        return json.loads(raw_bytes.decode("utf-8"))
    except Exception as err:
        _LOGGER.debug("Failed decoding band summary: %s", err)
        return {}


def get_default_headers(apptoken: str) -> dict[str, str]:
    """Get standard request headers for Zepp API."""
    return {
        "apptoken": apptoken,
        "appname": "com.huami.midong",
        "appplatform": "android_phone",
        "v": "2.0",
        "vn": "9.12.5",
        "timezone": "UTC",
        "user-agent": "Zepp/9.12.5",
    }


async def async_login_web(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
    country_code: str = "AUTO",
) -> dict[str, Any]:
    """Authenticate with Zepp using webapp credentials without kicking mobile phone app."""
    # Step 1: Request access token from registrations endpoint
    step1_url = f"https://api-user.huami.com/registrations/{urllib.parse.quote(email)}/tokens"
    step1_data = {
        "password": password,
        "client_id": "HuaMi",
        "token": "access",
        "state": "REDIRECTION",
        "redirect_uri": "https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html",
        "json_response": "true",
        "app_name": "com.huami.webapp",
    }
    if country_code and country_code.upper() != "AUTO":
        step1_data["country_code"] = country_code.upper()

    step1_headers = {
        "app_name": "com.huami.webapp",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        async with session.post(
            step1_url,
            data=step1_data,
            headers=step1_headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise ZeppConnectionError(f"Step 1 failed with status {resp.status}")
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Error connecting to Zepp auth API (step 1): %s", err)
        raise ZeppConnectionError from err

    access_token = data.get("access")
    if not access_token:
        _LOGGER.warning("Zepp auth step 1 returned no access token: %s", data)
        raise ZeppAuthError(data.get("message") or "Invalid credentials")

    # Determine regional country_code
    region_code = data.get("country_code")
    if not region_code and country_code and country_code.upper() != "AUTO":
        region_code = country_code.upper()

    if not region_code:
        # Check region string returned in step 1 (e.g. us-west-2)
        reg = (data.get("region") or "").lower()
        if "us" in reg:
            region_code = "US"
        elif "eu" in reg or "de" in reg:
            region_code = "DE"
        elif "ru" in reg:
            region_code = "RU"
        elif "cn" in reg:
            region_code = "CN"
        elif "sg" in reg:
            region_code = "SG"

    if not region_code:
        # Fallback to recommendArea endpoint
        try:
            async with session.get(
                "https://account.huami.com/v1/client/recommendArea",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as area_resp:
                if area_resp.status == 200:
                    area_data = await area_resp.json(content_type=None)
                    region_code = area_data.get("region")
        except Exception:
            pass

    if not region_code:
        region_code = "US"

    _LOGGER.debug("Resolved Zepp region code: %s", region_code)

    # Step 2: Exchange access token for app_token
    step2_url = "https://account.huami.com/v2/client/login"
    step2_data = {
        "country_code": region_code,
        "app_name": "com.huami.webapp",
        "third_name": "huami",
        "grant_type": "access_token",
        "code": access_token,
        "device_id": "02:00:00:00:00:00",
        "device_model": "web",
        "app_version": "4.3.0",
        "allow_registration": "false",
        "dn": "account.huami.com,api-user.huami.com,api-mifit.huami.com,auth.huami.com,api-open.huami.com",
    }
    step2_headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    try:
        async with session.post(
            step2_url,
            data=step2_data,
            headers=step2_headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise ZeppConnectionError(f"Step 2 failed with status {resp.status}")
            data2 = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Error connecting to Zepp account API (step 2): %s", err)
        raise ZeppConnectionError from err

    if data2.get("result") != "ok":
        _LOGGER.warning("Zepp auth step 2 failed: %s", data2)
        raise ZeppAuthError(f"Login failed: {data2.get('error_code')}")

    token_info = data2.get("token_info", {})
    app_token = token_info.get("app_token")
    user_id = str(token_info.get("user_id"))

    domains = data2.get("domains", [])
    cnames = []
    for d in domains:
        c = d.get("cnames", [])
        if c and c[0]:
            cnames.append(c[0])
    cname_str = ",".join(cnames)

    return {
        "apptoken": app_token,
        "userid": user_id,
        "cname": cname_str,
    }


async def async_exchange_access_token(
    session: aiohttp.ClientSession,
    access_token: str,
    country_code: str = "AUTO",
) -> dict[str, Any]:
    """Exchange raw web access_token or token string for apptoken and user info."""
    clean_token = access_token.strip()

    # Check if input is a cookies string, key-value, or JSON containing apptoken & userid
    extracted_apptoken = None
    extracted_userid = None
    extracted_country = None

    # Try JSON
    if clean_token.startswith("{") and clean_token.endswith("}"):
        try:
            d = json.loads(clean_token)
            extracted_apptoken = d.get("apptoken") or d.get("app_token")
            extracted_userid = str(d.get("userid") or d.get("user_id") or "")
            extracted_country = d.get("country_code") or d.get("region")
        except Exception:
            pass

    # Try Cookies / key-value format (from document.cookie or DevTools)
    if not extracted_apptoken and ("apptoken=" in clean_token.lower() or "app_token=" in clean_token.lower()):
        for part in clean_token.replace("\n", ";").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                k_clean = k.strip().lower().replace("-", "_")
                v_clean = v.strip().strip('"').strip("'")
                if k_clean in ("apptoken", "app_token"):
                    extracted_apptoken = v_clean
                elif k_clean in ("userid", "user_id"):
                    extracted_userid = v_clean
                elif k_clean in ("country_code", "region"):
                    extracted_country = v_clean

    if extracted_apptoken:
        if not extracted_userid:
            raise ZeppAuthError("Found apptoken in cookies, but userid was missing. Please copy the full document.cookie string.")
        return {
            "apptoken": extracted_apptoken,
            "userid": extracted_userid,
            "cname": "",
        }

    # If user pasted a full redirect URL, extract the access parameter
    if "access=" in clean_token:
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(clean_token)
            query = urllib.parse.parse_qs(parsed.query or parsed.fragment)
            if "access" in query:
                clean_token = query["access"][0]
        except Exception:
            pass

    region_code = country_code.upper() if country_code and country_code.upper() != "AUTO" else "US"

    step2_url = "https://account.huami.com/v2/client/login"
    step2_data = {
        "country_code": region_code,
        "app_name": "com.huami.webapp",
        "third_name": "huami",
        "grant_type": "access_token",
        "code": clean_token,
        "device_id": "02:00:00:00:00:00",
        "device_model": "web",
        "app_version": "4.3.0",
        "allow_registration": "false",
        "dn": "account.huami.com,api-user.huami.com,api-mifit.huami.com,auth.huami.com,api-open.huami.com",
    }
    step2_headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    try:
        async with session.post(
            step2_url,
            data=step2_data,
            headers=step2_headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                raise ZeppConnectionError(f"Token exchange failed with status {resp.status}")
            data2 = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Error connecting to Zepp account API during token exchange: %s", err)
        raise ZeppConnectionError from err

    if data2.get("result") != "ok":
        _LOGGER.warning("Zepp token exchange failed: %s", data2)
        raise ZeppAuthError(f"Login failed: {data2.get('error_code')}")

    token_info = data2.get("token_info", {})
    app_token = token_info.get("app_token")
    user_id = str(token_info.get("user_id"))

    domains = data2.get("domains", [])
    cnames = []
    for d in domains:
        c = d.get("cnames", [])
        if c and c[0]:
            cnames.append(c[0])
    cname_str = ",".join(cnames)

    return {
        "apptoken": app_token,
        "userid": user_id,
        "cname": cname_str,
    }


def parse_region_host_from_cname(cname: str | None) -> list[str]:
    """Extract possible api-mifit hosts from cname parameter."""
    hosts = []
    if cname:
        for part in cname.split(","):
            part = part.strip()
            if not part:
                continue
            if not part.startswith("http"):
                part = f"https://{part}"
            if "api-mifit" in part:
                hosts.append(part)

    for def_host in DEFAULT_REGIONS:
        if def_host not in hosts:
            hosts.append(def_host)

    return hosts


async def async_fetch_devices(
    session: aiohttp.ClientSession,
    apptoken: str,
    userid: str,
    host: str,
) -> list[dict[str, Any]]:
    """Fetch linked devices from a specific Zepp regional host."""
    url = f"{host}/users/{userid}/devices"
    headers = get_default_headers(apptoken)
    params = {
        "enableMultiDeviceOnMultiType": ["true", "true"],
        "userid": userid,
        "channel": ZEPP_CHANNEL,
        "device": "android_32",
        "device_type": "android_phone",
        "enableMultiDevice": "true",
        "v": "2.0",
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            else:
                _LOGGER.debug("Failed fetching devices from %s: HTTP %s", host, resp.status)
    except Exception as err:
        _LOGGER.debug("Error connecting to %s: %s", host, err)

    return []


def parse_discovered_devices(devices_to_parse: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw Zepp device payloads into structured dictionary records."""
    parsed_devices = []
    for dev in devices_to_parse:
        src = dev.get("deviceSource")
        disp = dev.get("displayName")
        info_name = dev.get("deviceInfo", {}).get("name") or dev.get("deviceSourceText")
        model_name = resolve_device_name(src, disp or info_name)

        mac = dev.get("macAddress", "Unknown")
        sn = dev.get("sn", "")
        fw = dev.get("firmwareVersion", "")
        device_id = dev.get("deviceId", mac.replace(":", ""))

        # Extract hardware attributes and BLE auth key
        add_info_raw = dev.get("additionalInfo")
        auth_key = None
        bt_mac = None
        hw_ver = None
        product_id = None
        if add_info_raw:
            try:
                add_info = json.loads(add_info_raw)
                auth_key = add_info.get("auth_key")
                bt_mac = add_info.get("btmac")
                hw_ver = add_info.get("hardwareVersion")
                product_id = add_info.get("productId")
            except Exception:
                pass

        # Extract battery status if present in device payload
        battery = None
        for raw_source in [dev.get("additionalSource"), dev.get("additionalInfo")]:
            if not raw_source:
                continue
            try:
                p = json.loads(raw_source) if isinstance(raw_source, str) else raw_source
                if isinstance(p, dict) and "battery" in p:
                    b_val = p["battery"].get("level")
                    if b_val is not None:
                        battery = int(b_val)
                        break
            except Exception:
                pass

        parsed_devices.append({
            "device_id": device_id,
            "device_name": model_name,
            "device_mac": mac,
            "device_sn": sn,
            "firmware": fw,
            "device_source": src,
            "auth_key": auth_key,
            "bt_mac": bt_mac,
            "hardware_version": hw_ver,
            "product_id": product_id,
            "active_status": dev.get("activeStatus", 1 if len(devices_to_parse) == 1 else 0),
            "last_active_time": dev.get("lastActiveStatusUpdateTime") or dev.get("lastStatusUpdateTime"),
            "battery": battery,
        })

    # Sort so that actively worn device is always the first/primary device
    parsed_devices.sort(
        key=lambda d: (d.get("active_status", 0), d.get("last_active_time") or 0),
        reverse=True,
    )
    return parsed_devices


async def async_discover_zepp_devices(
    session: aiohttp.ClientSession,
    apptoken: str,
    userid: str,
    cname: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Probe regions concurrently and return active regional host and parsed device list."""
    candidate_hosts = parse_region_host_from_cname(cname)

    async def _check_host(host: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            raw = await async_fetch_devices(session, apptoken, userid, host)
            return host, raw
        except Exception:
            return host, []

    fetch_results = await asyncio.gather(*[_check_host(h) for h in candidate_hosts])
    results_map = dict(fetch_results)

    # 1. First priority: candidate order with active bindingStatus == 1 devices
    for host in candidate_hosts:
        raw_devices = results_map.get(host) or []
        active_devices = [d for d in raw_devices if d.get("bindingStatus", 1) == 1]
        if active_devices:
            return host, parse_discovered_devices(active_devices)

    # 2. Second priority: any host that returned any devices
    for host in candidate_hosts:
        raw_devices = results_map.get(host) or []
        if raw_devices:
            return host, parse_discovered_devices(raw_devices)

    default_host = candidate_hosts[0] if candidate_hosts else "https://api-mifit-ru.huami.com"
    return default_host, []


async def async_fetch_band_data(
    session: aiohttp.ClientSession,
    host: str,
    apptoken: str,
    userid: str,
    from_date: str,
    to_date: str,
    device_type: int = 0,
    query_type: str = "summary",
) -> list[dict[str, Any]]:
    """Fetch activity and sleep band data for a date range (YYYY-MM-DD)."""
    url = f"{host}/v1/data/band_data.json"
    headers = get_default_headers(apptoken)
    params = {
        "userid": userid,
        "from_date": from_date,
        "to_date": to_date,
        "query_type": query_type,
        "device_type": str(device_type),
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])
            elif resp.status == 401:
                _LOGGER.warning("Zepp API returned 401 Unauthorized for band data. Token may be expired.")
                raise ZeppAuthError("Zepp token expired (HTTP 401)")
            _LOGGER.debug("Band data request failed: HTTP %s", resp.status)
    except ZeppAuthError:
        raise
    except Exception as err:
        _LOGGER.warning("Error fetching band data from Zepp: %s", err)

    return []


async def async_fetch_user_events(
    session: aiohttp.ClientSession,
    host: str,
    apptoken: str,
    userid: str,
    event_type: str,
    sub_type: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch user-scoped events (e.g. all_day_stress, blood_oxygen, PaiHealthInfo)."""
    url = f"{host}/users/{userid}/events"
    headers = get_default_headers(apptoken)
    params: dict[str, Any] = {
        "eventType": event_type,
        "userId": userid,
        "limit": str(limit),
    }
    if sub_type:
        params["subType"] = sub_type
    if from_ts is not None:
        params["from"] = str(from_ts)
    if to_ts is not None:
        params["to"] = str(to_ts)

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            elif resp.status == 401:
                _LOGGER.warning("Zepp API returned 401 Unauthorized for user events (%s). Token may be expired.", event_type)
                raise ZeppAuthError("Zepp token expired (HTTP 401)")
    except ZeppAuthError:
        raise
    except Exception as err:
        _LOGGER.debug("Error fetching user events (%s): %s", event_type, err)

    return []


async def async_fetch_v2_events(
    session: aiohttp.ClientSession,
    host: str,
    apptoken: str,
    event_type: str,
    sub_type: str | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch v2 events (e.g. HRVRMSSD, Charge/stress_data, RespiratoryRate)."""
    url = f"{host}/v2/users/me/events"
    headers = get_default_headers(apptoken)
    params: dict[str, Any] = {
        "eventType": event_type,
        "limit": str(limit),
    }
    if sub_type:
        params["subType"] = sub_type
    if from_ts is not None:
        params["from"] = str(from_ts)
    if to_ts is not None:
        params["to"] = str(to_ts)

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            elif resp.status == 401:
                _LOGGER.warning("Zepp API returned 401 Unauthorized for v2 events (%s). Token may be expired.", event_type)
                raise ZeppAuthError("Zepp token expired (HTTP 401)")
    except ZeppAuthError:
        raise
    except Exception as err:
        _LOGGER.debug("Error fetching v2 events (%s): %s", event_type, err)

    return []


async def async_fetch_sport_load(
    session: aiohttp.ClientSession,
    host: str,
    apptoken: str,
    userid: str,
    start_day: str,
    end_day: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch WatchSportStatistics SPORT_LOAD."""
    url = f"{host}/v2/watch/users/{userid}/WatchSportStatistics/SPORT_LOAD"
    headers = get_default_headers(apptoken)
    params = {
        "startDay": start_day,
        "endDay": end_day,
        "limit": str(limit),
    }

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            elif resp.status == 401:
                _LOGGER.warning("Zepp API returned 401 Unauthorized for sport load. Token may be expired.")
                raise ZeppAuthError("Zepp token expired (HTTP 401)")
    except ZeppAuthError:
        raise
    except Exception as err:
        _LOGGER.debug("Error fetching sport load: %s", err)

    return []


async def async_fetch_weight_records(
    session: aiohttp.ClientSession,
    host: str,
    apptoken: str,
    userid: str,
    member_id: str = "-1",
    from_sec: int | None = None,
    to_sec: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch scale body composition and weight records."""
    url = f"{host}/users/{userid}/members/{member_id}/weightRecords"
    headers = get_default_headers(apptoken)
    params: dict[str, Any] = {
        "limit": str(limit),
        "isForward": "0",
    }
    if from_sec is not None:
        params["fromTime"] = str(from_sec)
    if to_sec is not None:
        params["toTime"] = str(to_sec)

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("items", [])
            elif resp.status == 401:
                _LOGGER.warning("Zepp API returned 401 Unauthorized for weight records. Token may be expired.")
                raise ZeppAuthError("Zepp token expired (HTTP 401)")
    except ZeppAuthError:
        raise
    except Exception as err:
        _LOGGER.debug("Error fetching weight records: %s", err)

    return []
