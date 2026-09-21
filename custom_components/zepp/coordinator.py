"""DataUpdateCoordinator for Zepp (Amazfit) integration."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ZeppAuthError,
    async_fetch_band_data,
    async_fetch_sport_load,
    async_fetch_user_events,
    async_fetch_v2_events,
    async_fetch_weight_records,
    async_login_web,
    decode_band_summary,
)
from .const import (
    CONF_APPTOKEN,
    CONF_CNAME,
    CONF_COUNTRY_CODE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION_HOST,
    CONF_USERID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=15)


class ZeppCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch all current metrics from Zepp cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry | dict[str, Any]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        if isinstance(entry, ConfigEntry):
            self.entry: ConfigEntry | None = entry
            self.entry_data = entry.data
        else:
            self.entry = None
            self.entry_data = entry

        self.apptoken: str = self.entry_data[CONF_APPTOKEN]
        self.userid: str = str(self.entry_data[CONF_USERID])
        self.host: str = self.entry_data[CONF_REGION_HOST]
        self.devices: list[dict[str, Any]] = self.entry_data.get("devices", [])

    async def _async_refresh_token(self) -> bool:
        """Attempt to re-authenticate using stored credentials."""
        if not self.entry:
            return False

        password = self.entry.data.get(CONF_PASSWORD)
        email = self.entry.data.get(CONF_EMAIL)
        country_code = self.entry.data.get(CONF_COUNTRY_CODE, "AUTO")

        if not password or not email:
            return False

        _LOGGER.info("Zepp token expired, attempting automatic re-authentication for %s", email)
        session = async_get_clientsession(self.hass)
        try:
            auth_data = await async_login_web(session, email, password, country_code=country_code)
            new_token = auth_data["apptoken"]
            self.apptoken = new_token
            new_data = {**self.entry.data, CONF_APPTOKEN: new_token}
            if auth_data.get("cname"):
                new_data[CONF_CNAME] = auth_data["cname"]
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            self.entry_data = new_data
            _LOGGER.info("Successfully refreshed Zepp token for %s", email)
            return True
        except Exception as err:
            _LOGGER.warning("Automatic re-authentication failed for %s: %s", email, err)
            return False

    async def _fetch_metrics(self) -> dict[str, Any]:
        """Fetch real-time and daily data from Zepp API."""
        session = async_get_clientsession(self.hass)
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        now_ms = int(now.timestamp() * 1000)
        day_ago_ms = int((now - datetime.timedelta(days=2)).timestamp() * 1000)

        result: dict[str, Any] = {
            "steps": 0,
            "distance": 0,
            "calories": 0,
            "step_goal": 8000,
            "sleep_score": None,
            "sleep_duration": None,
            "deep_sleep": None,
            "light_sleep": None,
            "rem_sleep": None,
            "awake_time": None,
            "wake_count": None,
            "sleep_rhr": None,
            "resting_hr": None,
            "stress": None,
            "spo2": None,
            "breathing_score": None,
            "odi": None,
            "total_pai": None,
            "hrv": None,
            "training_load_total": None,
            "training_load_today": None,
            "training_load_min": None,
            "training_load_max": None,
            "weight": None,
            "bmi": None,
            "body_fat": None,
            "muscle_mass": None,
            "body_water": None,
            "bone_mass": None,
            "heart_rate": None,
            "hr_min": None,
            "hr_max": None,
            "hr_avg": None,
            "stress_min": None,
            "stress_max": None,
            "last_updated": now.isoformat(),
        }

        try:
            # 1. Band data: Steps, Distance, Calories, Sleep, and Heart Rate
            band_items = await async_fetch_band_data(
                session, self.host, self.apptoken, self.userid, yesterday_str, today_str, query_type="detail"
            )
            if band_items:
                # Find today or most recent item
                for item in reversed(band_items):
                    summary_raw = item.get("summary")
                    if summary_raw:
                        summary = decode_band_summary(summary_raw)
                        if summary:
                            if "stp" in summary and result["steps"] == 0:
                                stp = summary["stp"]
                                result["steps"] = stp.get("ttl", 0)
                                result["distance"] = stp.get("dis", 0)
                                result["calories"] = stp.get("cal", 0)
                                if "goal" in summary:
                                    result["step_goal"] = summary["goal"]

                            if "slp" in summary and result["sleep_score"] is None:
                                slp = summary["slp"]
                                result["sleep_score"] = slp.get("ss")
                                dp = slp.get("dp", 0)
                                lt = slp.get("lt", 0)
                                dt = slp.get("dt", 0)
                                result["deep_sleep"] = dp
                                result["light_sleep"] = lt
                                result["rem_sleep"] = dt
                                result["awake_time"] = slp.get("wk")
                                result["wake_count"] = slp.get("wc")
                                result["sleep_duration"] = dp + lt + dt
                                result["sleep_rhr"] = slp.get("rhr")
                                if result["sleep_rhr"] and result["resting_hr"] is None:
                                    result["resting_hr"] = result["sleep_rhr"]

                    # Extract live heart rate from data_hr
                    data_hr = item.get("data_hr")
                    if data_hr and result["heart_rate"] is None:
                        try:
                            import base64
                            raw_hr = base64.b64decode(data_hr)
                            valid_hr = [val for val in raw_hr if 20 <= val <= 240]
                            if valid_hr:
                                result["heart_rate"] = valid_hr[-1]
                                result["hr_min"] = min(valid_hr)
                                result["hr_max"] = max(valid_hr)
                                result["hr_avg"] = round(sum(valid_hr) / len(valid_hr), 1)
                        except Exception as hr_err:
                            _LOGGER.debug("Error decoding data_hr: %s", hr_err)

            # 2. Stress
            stress_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "all_day_stress", from_ts=day_ago_ms, to_ts=now_ms, limit=5
            )
            if stress_events:
                for event in stress_events:
                    avg_stress = event.get("avgStress")
                    if avg_stress is not None:
                        try:
                            val = float(avg_stress)
                            if val > 0 and result["stress"] is None:
                                result["stress"] = round(val, 1)
                                if event.get("minStress") is not None:
                                    result["stress_min"] = float(event["minStress"])
                                if event.get("maxStress") is not None:
                                    result["stress_max"] = float(event["maxStress"])
                                break
                        except (ValueError, TypeError):
                            pass

            # 3. Blood Oxygen & Breathing Quality
            spo2_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "blood_oxygen", from_ts=day_ago_ms, to_ts=now_ms, limit=10
            )
            if spo2_events:
                for event in spo2_events:
                    sub_type = event.get("subType")
                    if sub_type == "odi":
                        if result["breathing_score"] is None and "score" in event:
                            try:
                                result["breathing_score"] = int(event["score"])
                            except (ValueError, TypeError):
                                pass
                        if result["odi"] is None and "odi" in event:
                            try:
                                result["odi"] = float(event["odi"])
                            except (ValueError, TypeError):
                                pass
                    elif sub_type == "osa_event":
                        if result["spo2"] is None and "spo2_decrease" in event:
                            try:
                                result["spo2"] = int(event["spo2_decrease"])
                            except (ValueError, TypeError):
                                pass

            # 4. PAI
            pai_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "PaiHealthInfo", from_ts=day_ago_ms, to_ts=now_ms, limit=5
            )
            if pai_events:
                latest_pai = pai_events[0]
                total_pai = latest_pai.get("totalPai")
                if total_pai is not None:
                    try:
                        result["total_pai"] = round(float(total_pai), 2)
                    except (ValueError, TypeError):
                        pass
                if result["resting_hr"] is None and "restHr" in latest_pai:
                    try:
                        result["resting_hr"] = int(latest_pai["restHr"])
                    except (ValueError, TypeError):
                        pass

            # 5. HRV rMSSD
            hrv_events = await async_fetch_v2_events(
                session, self.host, self.apptoken, "HRVRMSSD", sub_type="real_data", from_ts=day_ago_ms, to_ts=now_ms, limit=5
            )
            if hrv_events:
                latest_hrv = hrv_events[0]
                val_obj = latest_hrv.get("value", {})
                samples = val_obj.get("samples", [])
                if samples:
                    last_sample = samples[-1]
                    if "hrv" in last_sample:
                        result["hrv"] = last_sample["hrv"]

            # 6. Training Load (SPORT_LOAD)
            load_items = await async_fetch_sport_load(
                session, self.host, self.apptoken, self.userid, yesterday_str, today_str, limit=5
            )
            if load_items:
                latest_load = load_items[0]
                result["training_load_total"] = latest_load.get("wtlSum")
                result["training_load_today"] = latest_load.get("currnetDayTrainLoad")
                result["training_load_min"] = latest_load.get("wtlSumOptimalMin")
                result["training_load_max"] = latest_load.get("wtlSumOptimalMax")

            # 7. Weight & Scale
            weight_items = await async_fetch_weight_records(
                session, self.host, self.apptoken, self.userid, limit=2
            )
            if weight_items:
                latest_w = weight_items[0]
                result["weight"] = latest_w.get("weight")
                result["bmi"] = latest_w.get("bmi")
                result["body_fat"] = latest_w.get("body_fat_rate")
                result["muscle_mass"] = latest_w.get("muscle_mass")
                result["body_water"] = latest_w.get("body_water_rate")
                result["bone_mass"] = latest_w.get("bone_mass")

        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating Zepp metrics: %s", err)

        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Zepp API with automatic retry and token refresh on auth errors."""
        try:
            return await self._fetch_metrics()
        except ZeppAuthError as auth_err:
            refreshed = await self._async_refresh_token()
            if refreshed:
                try:
                    return await self._fetch_metrics()
                except Exception as err:
                    raise UpdateFailed(f"Error after re-authenticating with Zepp: {err}") from err
            raise ConfigEntryAuthFailed("Zepp authentication expired or invalid") from auth_err
        except Exception as err:
            _LOGGER.exception("Error updating Zepp coordinator: %s", err)
            raise UpdateFailed(f"Error communicating with Zepp cloud: {err}") from err
