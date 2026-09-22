"""Historical data synchronization for Zepp (Amazfit) into Home Assistant."""
from __future__ import annotations

import asyncio
import base64
import datetime
import logging
from typing import Any

from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    ZeppAuthError,
    async_fetch_band_data,
    async_fetch_user_events,
    decode_band_summary,
)
from .const import CONF_APPTOKEN, CONF_REGION_HOST, CONF_USERID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_sync_historical_data(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    days: int = 365,
) -> int:
    """Fetch historical band data from Zepp and import into Home Assistant Long-Term Statistics."""
    session = async_get_clientsession(hass)
    apptoken = entry_data[CONF_APPTOKEN]
    userid = str(entry_data[CONF_USERID])
    host = entry_data[CONF_REGION_HOST]
    devices = entry_data.get("devices", [])
    device_id = devices[0]["device_id"] if devices else userid
    device_id_clean = str(device_id).lower().replace(":", "")
    device_name = devices[0]["device_name"] if devices else "Amazfit"

    now = dt_util.now()
    start_date = now - datetime.timedelta(days=days)

    _LOGGER.info("Starting Zepp history sync for %s days (%s to %s)", days, start_date.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))

    # 1. Fetch band_data (Steps, Calories, Distance, Sleep, and data_hr for Heart Rate)
    chunk_size_days = 30
    cursor = start_date
    raw_days: dict[str, dict[str, Any]] = {}
    raw_hr_by_day: dict[str, bytes] = {}

    while cursor < now:
        chunk_end = min(cursor + datetime.timedelta(days=chunk_size_days), now)
        from_str = cursor.strftime("%Y-%m-%d")
        to_str = chunk_end.strftime("%Y-%m-%d")

        try:
            items = await async_fetch_band_data(
                session, host, apptoken, userid, from_str, to_str, device_type=0, query_type="detail"
            )
            for item in items:
                d_str = item.get("date_time")
                if not d_str or d_str in raw_days:
                    continue
                summary_raw = item.get("summary")
                if summary_raw:
                    decoded = decode_band_summary(summary_raw)
                    if decoded:
                        raw_days[d_str] = decoded

                d_hr = item.get("data_hr")
                if d_hr and d_str not in raw_hr_by_day:
                    try:
                        raw_hr_by_day[d_str] = base64.b64decode(d_hr)
                    except Exception:
                        pass
        except ZeppAuthError:
            _LOGGER.warning("Zepp authentication expired during history sync. Aborting historical backfill.")
            break
        except Exception as err:
            _LOGGER.warning("Error fetching Zepp history chunk %s..%s: %s", from_str, to_str, err)

        cursor = chunk_end + datetime.timedelta(days=1)
        await asyncio.sleep(0.35)

    # 2. Fetch Stress Events
    stress_by_day: dict[str, dict[str, float]] = {}
    from_ms = int(start_date.timestamp() * 1000)
    to_ms = int(now.timestamp() * 1000)
    try:
        stress_events = await async_fetch_user_events(
            session, host, apptoken, userid, "all_day_stress", from_ts=from_ms, to_ts=to_ms, limit=days + 10
        )
        for ev in stress_events:
            ts = ev.get("timestamp")
            if not ts:
                continue
            ev_date = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            avg_s = ev.get("avgStress")
            if avg_s is not None:
                try:
                    val_avg = float(avg_s)
                    val_min = float(ev.get("minStress", val_avg))
                    val_max = float(ev.get("maxStress", val_avg))
                    if val_avg > 0:
                        stress_by_day[ev_date] = {"mean": val_avg, "min": val_min, "max": val_max}
                except (ValueError, TypeError):
                    pass
    except Exception as err:
        _LOGGER.warning("Error fetching Zepp stress history: %s", err)

    # 3. Fetch PAI Events
    pai_by_day: dict[str, float] = {}
    try:
        pai_events = await async_fetch_user_events(
            session, host, apptoken, userid, "PaiHealthInfo", from_ts=from_ms, to_ts=to_ms, limit=days + 10
        )
        for ev in pai_events:
            ts = ev.get("timestamp")
            if not ts:
                continue
            ev_date = datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            total_pai = ev.get("totalPai")
            if total_pai is not None:
                try:
                    val_pai = float(total_pai)
                    if val_pai >= 0:
                        pai_by_day[ev_date] = round(val_pai, 1)
                except (ValueError, TypeError):
                    pass
    except Exception as err:
        _LOGGER.warning("Error fetching Zepp PAI history: %s", err)

    if not raw_days:
        _LOGGER.info("No historical Zepp band data retrieved")
        return 0

    _LOGGER.info(
        "Retrieved %d daily records, %d HR days, %d stress days, %d PAI days. Importing into LTS...",
        len(raw_days),
        len(raw_hr_by_day),
        len(stress_by_day),
        len(pai_by_day),
    )

    # Global/runtime sync progress tracker
    hass.data.setdefault(DOMAIN, {}).setdefault("history_sync_status", {})
    hass.data[DOMAIN]["history_sync_status"] = {
        "status": "syncing",
        "progress": 0,
        "synced_days": 0,
        "total_days": days,
        "heart_rate_points": 0,
        "last_synced_date": None,
    }

    # Sort days chronologically
    sorted_dates = sorted(raw_days.keys())

    steps_stats: list[StatisticData] = []
    distance_stats: list[StatisticData] = []
    calories_stats: list[StatisticData] = []
    sleep_score_stats: list[StatisticData] = []
    deep_sleep_stats: list[StatisticData] = []
    sleep_rhr_stats: list[StatisticData] = []
    heart_rate_stats: list[StatisticData] = []
    stress_stats: list[StatisticData] = []
    pai_stats: list[StatisticData] = []

    running_steps = 0.0
    running_distance = 0.0
    running_calories = 0.0

    for d_str in sorted_dates:
        try:
            dt = datetime.datetime.strptime(d_str, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc
            )
        except ValueError:
            continue

        day_data = raw_days[d_str]
        stp = day_data.get("stp", {})
        slp = day_data.get("slp", {})

        # 1. Activity: check for granular time slices (time 0..143 in stp["data"], each 10 mins)
        stp_slices = stp.get("data")
        if isinstance(stp_slices, list) and len(stp_slices) > 0:
            day_accum_steps = 0.0
            day_accum_distance = 0.0
            day_accum_calories = 0.0
            for s in stp_slices:
                t_idx = s.get("time", 0)
                slice_dt = dt + datetime.timedelta(minutes=t_idx * 10)
                s_step = float(s.get("step", 0))
                s_dis = float(s.get("dis", 0))
                s_cal = float(s.get("cal", 0))
                day_accum_steps += s_step
                day_accum_distance += s_dis
                day_accum_calories += s_cal
                running_steps += s_step
                running_distance += s_dis
                running_calories += s_cal
                steps_stats.append(
                    StatisticData(start=slice_dt, state=day_accum_steps, sum=running_steps)
                )
                distance_stats.append(
                    StatisticData(start=slice_dt, state=day_accum_distance, sum=running_distance)
                )
                calories_stats.append(
                    StatisticData(start=slice_dt, state=day_accum_calories, sum=running_calories)
                )
        else:
            # Fallback to daily total if slices are not available
            day_steps = float(stp.get("ttl", 0))
            running_steps += day_steps
            steps_stats.append(
                StatisticData(start=dt, state=day_steps, sum=running_steps)
            )

            day_dis = float(stp.get("dis", 0))
            running_distance += day_dis
            distance_stats.append(
                StatisticData(start=dt, state=day_dis, sum=running_distance)
            )

            day_cal = float(stp.get("cal", 0))
            running_calories += day_cal
            calories_stats.append(
                StatisticData(start=dt, state=day_cal, sum=running_calories)
            )

        # 2. Sleep metrics
        if "ss" in slp:
            score = float(slp["ss"])
            sleep_score_stats.append(
                StatisticData(start=dt, mean=score, min=score, max=score, state=score)
            )

        if "dp" in slp:
            dp = float(slp["dp"])
            deep_sleep_stats.append(
                StatisticData(start=dt, mean=dp, min=dp, max=dp, state=dp)
            )

        if "rhr" in slp and slp["rhr"] > 0:
            rhr = float(slp["rhr"])
            sleep_rhr_stats.append(
                StatisticData(start=dt, mean=rhr, min=rhr, max=rhr, state=rhr)
            )

        # 3. Heart Rate: full resolution directly as recorded by watch (per minute)
        if d_str in raw_hr_by_day:
            raw_hr = raw_hr_by_day[d_str]
            for m in range(min(1440, len(raw_hr))):
                hr_val = raw_hr[m]
                if 20 <= hr_val <= 240:
                    hr_dt = dt + datetime.timedelta(minutes=m)
                    val_float = float(hr_val)
                    heart_rate_stats.append(
                        StatisticData(
                            start=hr_dt,
                            min=val_float,
                            max=val_float,
                            mean=val_float,
                            state=val_float,
                        )
                    )

        # 4. Stress
        if d_str in stress_by_day:
            st_info = stress_by_day[d_str]
            stress_stats.append(
                StatisticData(
                    start=dt,
                    min=st_info["min"],
                    max=st_info["max"],
                    mean=st_info["mean"],
                    state=st_info["mean"],
                )
            )

        # 5. PAI
        if d_str in pai_by_day:
            p_val = pai_by_day[d_str]
            pai_stats.append(
                StatisticData(
                    start=dt,
                    min=p_val,
                    max=p_val,
                    mean=p_val,
                    state=p_val,
                )
            )

    hass.data[DOMAIN]["history_sync_status"] = {
        "status": "syncing",
        "progress": 85,
        "synced_days": len(raw_days),
        "total_days": days,
        "heart_rate_points": len(heart_rate_stats),
        "last_synced_date": sorted_dates[-1] if sorted_dates else None,
    }

    # Resolve sensor entity IDs from entity registry
    from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)

    fallback_dev_slug = device_name.lower().replace(" ", "_").replace("-", "_")

    def get_entity_id(unique_suffix: str) -> str:
        ent_id = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{device_id}_{unique_suffix}")
        if ent_id:
            return ent_id
        return f"sensor.{fallback_dev_slug}_{unique_suffix}"

    steps_eid = get_entity_id("steps")
    distance_eid = get_entity_id("distance")
    calories_eid = get_entity_id("calories")
    sleep_score_eid = get_entity_id("sleep_score")
    deep_sleep_eid = get_entity_id("deep_sleep")
    sleep_rhr_eid = get_entity_id("sleep_rhr")
    heart_rate_eid = get_entity_id("heart_rate")
    stress_eid = get_entity_id("stress")
    pai_eid = get_entity_id("pai")

    stat_definitions = [
        (steps_eid, "steps", False, True, steps_stats),
        (distance_eid, "m", False, True, distance_stats),
        (calories_eid, "kcal", False, True, calories_stats),
        (sleep_score_eid, "score", True, False, sleep_score_stats),
        (deep_sleep_eid, "min", True, False, deep_sleep_stats),
        (sleep_rhr_eid, "bpm", True, False, sleep_rhr_stats),
        (heart_rate_eid, "bpm", True, False, heart_rate_stats),
        (stress_eid, "score", True, False, stress_stats),
        (pai_eid, "PAI", True, False, pai_stats),
    ]

    for stat_id, unit, has_mean, has_sum, stats_list in stat_definitions:
        if not stats_list:
            continue
        meta = StatisticMetaData(
            has_mean=has_mean,
            has_sum=has_sum,
            name=None,
            source=RECORDER_DOMAIN,
            statistic_id=stat_id,
            unit_of_measurement=unit,
        )
        try:
            async_import_statistics(hass, meta, stats_list)
        except Exception as err:
            _LOGGER.warning("Failed importing statistics for %s: %s", stat_id, err)

    _LOGGER.info(
        "Successfully imported %d days of Zepp history (HR: %d pts, Stress: %d pts, PAI: %d pts) into Home Assistant",
        len(raw_days),
        len(heart_rate_stats),
        len(stress_stats),
        len(pai_stats),
    )

    hass.data[DOMAIN]["history_sync_status"] = {
        "status": "completed",
        "progress": 100,
        "synced_days": len(raw_days),
        "total_days": days,
        "heart_rate_points": len(heart_rate_stats),
        "last_synced_date": sorted_dates[-1] if sorted_dates else None,
    }
    return len(raw_days)
