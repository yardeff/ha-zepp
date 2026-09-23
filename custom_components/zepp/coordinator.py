"""DataUpdateCoordinator for Zepp (Amazfit) integration."""
from __future__ import annotations

import datetime
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    CONF_SCAN_INTERVAL,
    CONF_USERID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ZeppCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch all current metrics from Zepp cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry | dict[str, Any]) -> None:
        interval_minutes = DEFAULT_SCAN_INTERVAL
        if isinstance(entry, ConfigEntry):
            self.entry: ConfigEntry | None = entry
            self.entry_data = entry.data
            interval_minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        else:
            self.entry = None
            self.entry_data = entry

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(minutes=interval_minutes),
        )

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
        now = dt_util.now()
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        now_ms = int(now.timestamp() * 1000)
        day_ago_ms = int((now - datetime.timedelta(days=2)).timestamp() * 1000)

        three_days_ago_str = (now - datetime.timedelta(days=3)).strftime("%Y-%m-%d")

        # Preserve previously fetched valid data to prevent temporary 0 dips on network latency
        result: dict[str, Any] = dict(self.data) if self.data else {
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
            "readiness_score": None,
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
        result["last_updated"] = now.isoformat()

        # 1. Band data: Steps, Distance, Calories, Sleep, and Heart Rate
        try:
            band_items = await async_fetch_band_data(
                session, self.host, self.apptoken, self.userid, three_days_ago_str, today_str, query_type="detail"
            )
            if band_items:
                # 1. Activity: strictly look for today record; NEVER leak yesterday steps into today!
                today_item = next((item for item in reversed(band_items) if item.get("date_time") == today_str), None)
                if today_item:
                    summary_raw = today_item.get("summary")
                    if summary_raw:
                        summary = decode_band_summary(summary_raw)
                        if summary:
                            if "stp" in summary:
                                stp = summary["stp"]
                                result["steps"] = int(stp.get("ttl", 0))
                                result["distance"] = int(stp.get("dis", 0))
                                result["calories"] = int(stp.get("cal", 0))
                    # Check if today_item has real-time minute data
                    act_raw = today_item.get("data")
                    if act_raw and not result.get("steps"):
                        try:
                            import base64
                            raw_act = base64.b64decode(act_raw)
                            min_steps = sum(raw_act[m * 3 + 2] for m in range(min(1440, len(raw_act) // 3)))
                            if min_steps > 0:
                                result["steps"] = min_steps
                        except Exception:
                            pass
                    self._last_steps_date = today_str
                else:
                    # Today has not synced from watch to Zepp Cloud yet.
                    # Keep previous reading if from today, otherwise 0. NEVER use yesterday's total!
                    prev_date = getattr(self, "_last_steps_date", None)
                    if prev_date == today_str and self.data and self.data.get("steps") is not None:
                        result["steps"] = self.data.get("steps", 0)
                        result["distance"] = self.data.get("distance", 0)
                        result["calories"] = self.data.get("calories", 0)
                    else:
                        result["steps"] = 0
                        result["distance"] = 0
                        result["calories"] = 0
                    self._last_steps_date = today_str

                # Step goal can be taken from the most recent available summary
                for item in reversed(band_items):
                    s_raw = item.get("summary")
                    if s_raw:
                        s_dec = decode_band_summary(s_raw)
                        if s_dec and "goal" in s_dec:
                            result["step_goal"] = int(s_dec.get("goal", 8000))
                            break

                # 2. Extract latest valid heart rate from most recent available data_hr
                for item in reversed(band_items):
                    data_hr = item.get("data_hr")
                    if data_hr:
                        try:
                            import base64
                            raw_hr = base64.b64decode(data_hr)
                            valid_hr = [val for val in raw_hr if 20 <= val <= 240]
                            if valid_hr:
                                result["heart_rate"] = valid_hr[-1]
                                result["hr_min"] = min(valid_hr)
                                result["hr_max"] = max(valid_hr)
                                result["hr_avg"] = round(sum(valid_hr) / len(valid_hr), 1)
                                break
                        except Exception as hr_err:
                            _LOGGER.debug("Error decoding data_hr: %s", hr_err)

                # Sleep analysis: inspect most recent recorded sleep session (today or yesterday)
                for item in reversed(band_items):
                    if result.get("sleep_score") is not None:
                        break
                    summary_raw = item.get("summary")
                    if summary_raw:
                        summary = decode_band_summary(summary_raw)
                        if summary and "slp" in summary:
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
                            if result["sleep_rhr"]:
                                result["resting_hr"] = result["sleep_rhr"]

                if band_items:
                    try:
                        from homeassistant.components.recorder import get_instance
                        await get_instance(self.hass).async_add_executor_job(self._sync_hourly_statistics, band_items)
                    except Exception as hist_err:
                        _LOGGER.debug("Failed backfilling hourly statistics: %s", hist_err)
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating band data: %s", err)

        # 2. Stress
        try:
            stress_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "all_day_stress", from_ts=day_ago_ms, to_ts=now_ms, limit=5
            )
            if not stress_events:
                stress_events = await async_fetch_user_events(
                    session, self.host, self.apptoken, self.userid, "all_day_stress", limit=10
                )
            if stress_events:
                for event in stress_events:
                    avg_stress = event.get("avgStress")
                    if avg_stress is not None:
                        try:
                            val = float(avg_stress)
                            if val > 0:
                                result["stress"] = round(val, 1)
                                if event.get("minStress") is not None:
                                    result["stress_min"] = float(event["minStress"])
                                if event.get("maxStress") is not None:
                                    result["stress_max"] = float(event["maxStress"])
                                break
                        except (ValueError, TypeError):
                            pass
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating stress events: %s", err)

        # 3. Blood Oxygen & Breathing Quality
        try:
            spo2_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "blood_oxygen", from_ts=day_ago_ms, to_ts=now_ms, limit=15
            )
            # Fallback to history if no events recorded in the last 24h
            if not spo2_events:
                spo2_events = await async_fetch_user_events(
                    session, self.host, self.apptoken, self.userid, "blood_oxygen", limit=20
                )

            if spo2_events:
                for event in spo2_events:
                    sub_type = event.get("subType")

                    # Check ODI breathing score
                    if sub_type == "odi":
                        if result["breathing_score"] is None and "score" in event:
                            try:
                                score_val = int(event["score"])
                                if score_val > 0:
                                    result["breathing_score"] = score_val
                            except (ValueError, TypeError):
                                pass
                        if result["odi"] is None and "odi" in event:
                            try:
                                result["odi"] = float(event["odi"])
                            except (ValueError, TypeError):
                                pass

                    # Extract SpO2 (check extra JSON and root event)
                    if result["spo2"] is None:
                        extra_raw = event.get("extra")
                        if extra_raw:
                            try:
                                ex = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
                                dec = ex.get("spo2_decrease")
                                if dec is not None and isinstance(dec, (int, float)) and 50 <= int(dec) <= 100:
                                    result["spo2"] = int(dec)
                                if result["spo2"] is None and "spo2" in ex:
                                    arr = ex["spo2"]
                                    if isinstance(arr, list) and arr:
                                        last = arr[-1]
                                        val = last.get("value") if isinstance(last, dict) else last
                                        if val is not None and 50 <= int(val) <= 100:
                                            result["spo2"] = int(val)
                            except Exception:
                                pass
                        if result["spo2"] is None:
                            val = event.get("spo2") or event.get("spo2_decrease")
                            if val is not None:
                                try:
                                    if 50 <= int(val) <= 100:
                                        result["spo2"] = int(val)
                                except (ValueError, TypeError):
                                    pass
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating SpO2 events: %s", err)

        # 3.1 Sleep Breathing Quality & Readiness from Readiness events
        try:
            readiness_events = await async_fetch_user_events(
                session, self.host, self.apptoken, self.userid, "readiness", limit=10
            )
            if readiness_events:
                for rev in readiness_events:
                    if rev.get("subType") == "watch_score":
                        # AHI Breathing Score (0-100)
                        if result["breathing_score"] is None and rev.get("ahiScore") is not None:
                            try:
                                ahi = int(rev["ahiScore"])
                                if ahi >= 0:
                                    result["breathing_score"] = ahi
                            except (ValueError, TypeError):
                                pass
                        # Readiness Score (0-100)
                        if result["readiness_score"] is None and rev.get("rdnsScore") is not None:
                            try:
                                result["readiness_score"] = int(rev["rdnsScore"])
                            except (ValueError, TypeError):
                                pass
                        break

            # Fallback: if ODI was recorded as 0.0 (0 desaturations), breathing quality is optimal (100)
            if result["breathing_score"] is None and result["odi"] == 0.0:
                result["breathing_score"] = 100
        except ZeppAuthError:
            raise
        except Exception as r_err:
            _LOGGER.debug("Error updating readiness events: %s", r_err)

        # 4. PAI
        try:
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
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating PAI events: %s", err)

        # 5. HRV rMSSD
        try:
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
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating HRV events: %s", err)

        # 6. Training Load (SPORT_LOAD)
        try:
            load_items = await async_fetch_sport_load(
                session, self.host, self.apptoken, self.userid, yesterday_str, today_str, limit=5
            )
            if load_items:
                latest_load = load_items[0]
                result["training_load_total"] = latest_load.get("wtlSum")
                result["training_load_today"] = latest_load.get("currnetDayTrainLoad")
                result["training_load_min"] = latest_load.get("wtlSumOptimalMin")
                result["training_load_max"] = latest_load.get("wtlSumOptimalMax")
        except ZeppAuthError:
            raise
        except Exception as err:
            _LOGGER.debug("Error updating sport load: %s", err)

        # 7. Weight & Scale
        try:
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
            _LOGGER.debug("Error updating weight records: %s", err)

        # 8. Device battery & status
        try:
            from .api import async_fetch_devices
            raw_devices = await async_fetch_devices(session, self.apptoken, self.userid, self.host)
            if raw_devices:
                device_batteries: dict[str, int] = {}
                for dev in raw_devices:
                    dev_id = dev.get("deviceId") or dev.get("macAddress", "").replace(":", "")
                    for raw_source in [dev.get("additionalSource"), dev.get("additionalInfo")]:
                        if not raw_source:
                            continue
                        try:
                            p = json.loads(raw_source) if isinstance(raw_source, str) else raw_source
                            if isinstance(p, dict) and "battery" in p:
                                b_val = p["battery"].get("level")
                                if b_val is not None:
                                    device_batteries[dev_id] = int(b_val)
                                    break
                        except Exception:
                            pass
                result["device_batteries"] = device_batteries
        except ZeppAuthError:
            raise
        except Exception as dev_err:
            _LOGGER.debug("Failed refreshing device batteries: %s", dev_err)

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

    def _sync_hourly_statistics(self, band_items: list[dict[str, Any]]) -> None:
        """Backfill hourly statistics into HA recorder for detailed bar charts."""
        try:
            from sqlalchemy import text
            from homeassistant.components.recorder.util import session_scope
            import base64
        except ImportError:
            return

        try:
            with session_scope(hass=self.hass) as session:
                res = session.execute(text(
                    "SELECT id, statistic_id FROM statistics_meta "
                    "WHERE statistic_id IN ('sensor.amazfit_active_steps', 'sensor.amazfit_active_distance', 'sensor.amazfit_active_calories')"
                )).fetchall()
                meta_map = {row[1]: row[0] for row in res}
                step_meta = meta_map.get("sensor.amazfit_active_steps")
                dis_meta = meta_map.get("sensor.amazfit_active_distance")
                cal_meta = meta_map.get("sensor.amazfit_active_calories")
                if not step_meta:
                    return

                for item in band_items:
                    date_str = item.get("date_time")
                    act_raw = item.get("data")
                    if not date_str or not act_raw:
                        continue

                    try:
                        raw_act = base64.b64decode(act_raw)
                    except Exception:
                        continue

                    if len(raw_act) < 3:
                        continue

                    summary_raw = item.get("summary")
                    summary = decode_band_summary(summary_raw) if summary_raw else {}
                    stp = summary.get("stp", {})
                    total_steps = int(stp.get("ttl", 0))
                    total_dis = int(stp.get("dis", 0))
                    total_cal = int(stp.get("cal", 0))

                    dis_ratio = total_dis / total_steps if total_steps > 0 else 0.726
                    cal_ratio = total_cal / total_steps if total_steps > 0 else 0.029

                    parts = [int(p) for p in date_str.split("-")]
                    day_start = dt_util.as_local(datetime.datetime(parts[0], parts[1], parts[2], 0, 0, 0))
                    day_start_ts = day_start.timestamp()

                    base_row = session.execute(text(
                        "SELECT sum FROM statistics WHERE metadata_id = :mid AND start_ts < :start_ts ORDER BY start_ts DESC LIMIT 1"
                    ), {"mid": step_meta, "start_ts": day_start_ts}).fetchone()
                    base_step_sum = float(base_row[0]) if base_row and base_row[0] is not None else 0.0

                    base_dis_row = session.execute(text(
                        "SELECT sum FROM statistics WHERE metadata_id = :mid AND start_ts < :start_ts ORDER BY start_ts DESC LIMIT 1"
                    ), {"mid": dis_meta, "start_ts": day_start_ts}).fetchone() if dis_meta else None
                    base_dis_sum = float(base_dis_row[0]) if base_dis_row and base_dis_row[0] is not None else 0.0

                    base_cal_row = session.execute(text(
                        "SELECT sum FROM statistics WHERE metadata_id = :mid AND start_ts < :start_ts ORDER BY start_ts DESC LIMIT 1"
                    ), {"mid": cal_meta, "start_ts": day_start_ts}).fetchone() if cal_meta else None
                    base_cal_sum = float(base_cal_row[0]) if base_cal_row and base_cal_row[0] is not None else 0.0

                    now_local = dt_util.now()
                    is_today = (day_start.date() == now_local.date())
                    max_hour = now_local.hour if is_today else 23

                    cum_steps = 0
                    for h in range(max_hour + 1):
                        dt_hour = day_start + datetime.timedelta(hours=h)
                        hour_ts = dt_hour.timestamp()

                        m_start = h * 60
                        m_end = (h + 1) * 60
                        if m_start < len(raw_act) // 3:
                            h_steps = sum(raw_act[m * 3 + 2] for m in range(m_start, min(m_end, len(raw_act) // 3)))
                        else:
                            h_steps = 0

                        cum_steps += h_steps
                        cum_dis = round(cum_steps * dis_ratio)
                        cum_cal = round(cum_steps * cal_ratio)

                        step_sum = base_step_sum + cum_steps
                        dis_sum = base_dis_sum + cum_dis
                        cal_sum = base_cal_sum + cum_cal

                        existing = session.execute(text(
                            "SELECT id FROM statistics WHERE metadata_id = :mid AND start_ts = :ts"
                        ), {"mid": step_meta, "ts": hour_ts}).fetchone()
                        if existing:
                            session.execute(text(
                                "UPDATE statistics SET state = :st, sum = :sm WHERE id = :id"
                            ), {"st": float(cum_steps), "sm": step_sum, "id": existing[0]})
                        else:
                            session.execute(text(
                                "INSERT INTO statistics (metadata_id, start_ts, state, sum) VALUES (:mid, :ts, :st, :sm)"
                            ), {"mid": step_meta, "ts": hour_ts, "st": float(cum_steps), "sm": step_sum})

                        if dis_meta:
                            existing_d = session.execute(text(
                                "SELECT id FROM statistics WHERE metadata_id = :mid AND start_ts = :ts"
                            ), {"mid": dis_meta, "ts": hour_ts}).fetchone()
                            if existing_d:
                                session.execute(text(
                                    "UPDATE statistics SET state = :st, sum = :sm WHERE id = :id"
                                ), {"st": float(cum_dis), "sm": dis_sum, "id": existing_d[0]})
                            else:
                                session.execute(text(
                                    "INSERT INTO statistics (metadata_id, start_ts, state, sum) VALUES (:mid, :ts, :st, :sm)"
                                ), {"mid": dis_meta, "ts": hour_ts, "st": float(cum_dis), "sm": dis_sum})

                        if cal_meta:
                            existing_c = session.execute(text(
                                "SELECT id FROM statistics WHERE metadata_id = :mid AND start_ts = :ts"
                            ), {"mid": cal_meta, "ts": hour_ts}).fetchone()
                            if existing_c:
                                session.execute(text(
                                    "UPDATE statistics SET state = :st, sum = :sm WHERE id = :id"
                                ), {"st": float(cum_cal), "sm": cal_sum, "id": existing_c[0]})
                            else:
                                session.execute(text(
                                    "INSERT INTO statistics (metadata_id, start_ts, state, sum) VALUES (:mid, :ts, :st, :sm)"
                                ), {"mid": cal_meta, "ts": hour_ts, "st": float(cum_cal), "sm": cal_sum})

                session.commit()
        except Exception as err:
            _LOGGER.debug("Error updating hourly statistics: %s", err)
