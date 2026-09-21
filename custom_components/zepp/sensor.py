"""Sensors for Zepp (Amazfit) integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REGION_HOST, CONF_USERID, DOMAIN
from .coordinator import ZeppCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all Zepp sensors."""
    coordinator: ZeppCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entry_data = entry.data
    userid = str(entry_data[CONF_USERID])
    region_host = entry_data.get(CONF_REGION_HOST, "")
    devices = entry_data.get("devices", [])

    if not devices:
        devices = [{
            "device_id": userid,
            "device_name": "Amazfit Watch",
            "device_mac": "",
            "device_sn": "",
            "firmware": "",
            "device_source": None,
        }]

    entities: list[SensorEntity] = []

    for dev in devices:
        device_id = str(dev.get("device_id", userid))
        device_name = str(dev.get("device_name", "Amazfit Watch"))
        mac = str(dev.get("device_mac", ""))
        sn = str(dev.get("device_sn", ""))
        fw = str(dev.get("firmware", ""))

        connections = set()
        if mac and mac != "Unknown":
            connections.add((dr.CONNECTION_NETWORK_MAC, mac))

        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Amazfit",
            model=device_name,
            sw_version=fw or None,
            serial_number=sn or None,
            connections=connections,
        )

        # 1. Device Info Sensors
        entities.extend([
            ZeppWatchModelSensor(device_id, device_name, device_info, dev, region_host, userid),
            ZeppMacAddressSensor(device_id, device_name, device_info, mac),
            ZeppFirmwareSensor(device_id, device_name, device_info, fw),
            ZeppSerialSensor(device_id, device_name, device_info, sn),
        ])

        # 2. Activity Sensors
        entities.extend([
            ZeppStepsSensor(coordinator, device_id, device_name, device_info),
            ZeppDistanceSensor(coordinator, device_id, device_name, device_info),
            ZeppCaloriesSensor(coordinator, device_id, device_name, device_info),
            ZeppStepGoalSensor(coordinator, device_id, device_name, device_info),
        ])

        # 3. Sleep Sensors
        entities.extend([
            ZeppSleepScoreSensor(coordinator, device_id, device_name, device_info),
            ZeppSleepDurationSensor(coordinator, device_id, device_name, device_info),
            ZeppDeepSleepSensor(coordinator, device_id, device_name, device_info),
            ZeppLightSleepSensor(coordinator, device_id, device_name, device_info),
            ZeppRemSleepSensor(coordinator, device_id, device_name, device_info),
            ZeppAwakeSleepSensor(coordinator, device_id, device_name, device_info),
            ZeppWakeCountSensor(coordinator, device_id, device_name, device_info),
            ZeppSleepRestingHRSensor(coordinator, device_id, device_name, device_info),
        ])

        # 4. Heart & Health Sensors
        entities.extend([
            ZeppHeartRateSensor(coordinator, device_id, device_name, device_info),
            ZeppRestingHRSensor(coordinator, device_id, device_name, device_info),
            ZeppStressSensor(coordinator, device_id, device_name, device_info),
            ZeppSpO2Sensor(coordinator, device_id, device_name, device_info),
            ZeppBreathingScoreSensor(coordinator, device_id, device_name, device_info),
            ZeppPaiSensor(coordinator, device_id, device_name, device_info),
            ZeppHrvSensor(coordinator, device_id, device_name, device_info),
        ])

        # 5. Training Load
        entities.extend([
            ZeppTrainingLoadSensor(coordinator, device_id, device_name, device_info),
            ZeppDailyTrainingLoadSensor(coordinator, device_id, device_name, device_info),
        ])

        # 6. Body Composition (only instantiate if scale records exist in Zepp account)
        if coordinator.data.get("weight") is not None:
            entities.extend([
                ZeppWeightSensor(coordinator, device_id, device_name, device_info),
                ZeppBmiSensor(coordinator, device_id, device_name, device_info),
                ZeppBodyFatSensor(coordinator, device_id, device_name, device_info),
            ])

    async_add_entities(entities, update_before_add=False)


# ==================== Device Info Sensors ====================

class ZeppWatchModelSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Watch Model"
    _attr_icon = "mdi:watch"

    def __init__(self, device_id: str, device_name: str, device_info: DeviceInfo, dev_data: dict[str, Any], region_host: str, userid: str) -> None:
        self._attr_unique_id = f"{device_id}_model"
        self._attr_device_info = device_info
        self._attr_native_value = device_name
        self._extra_attrs = {
            "device_source": dev_data.get("device_source"),
            "region_host": region_host,
            "user_id": userid,
            "auth_key": dev_data.get("auth_key"),
            "bt_mac": dev_data.get("bt_mac"),
            "hardware_version": dev_data.get("hardware_version"),
            "product_id": dev_data.get("product_id"),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra_attrs


class ZeppMacAddressSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "MAC Address"
    _attr_icon = "mdi:bluetooth"

    def __init__(self, device_id: str, device_name: str, device_info: DeviceInfo, mac: str) -> None:
        self._attr_unique_id = f"{device_id}_mac"
        self._attr_device_info = device_info
        self._attr_native_value = mac or "Unknown"


class ZeppFirmwareSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Firmware Version"
    _attr_icon = "mdi:cellphone-arrow-down"

    def __init__(self, device_id: str, device_name: str, device_info: DeviceInfo, firmware: str) -> None:
        self._attr_unique_id = f"{device_id}_firmware"
        self._attr_device_info = device_info
        self._attr_native_value = firmware or "Unknown"


class ZeppSerialSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Serial Number"
    _attr_icon = "mdi:barcode"

    def __init__(self, device_id: str, device_name: str, device_info: DeviceInfo, sn: str) -> None:
        self._attr_unique_id = f"{device_id}_serial"
        self._attr_device_info = device_info
        self._attr_native_value = sn or "Unknown"


# ==================== Activity Sensors ====================

class ZeppStepsSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Steps"
    _attr_icon = "mdi:walk"
    _attr_native_unit_of_measurement = "steps"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_steps"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("steps", 0)


class ZeppDistanceSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Distance"
    _attr_icon = "mdi:map-marker-distance"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_distance"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("distance", 0)


class ZeppCaloriesSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Calories"
    _attr_icon = "mdi:fire"
    _attr_native_unit_of_measurement = "kcal"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_calories"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("calories", 0)


class ZeppStepGoalSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Step Goal"
    _attr_icon = "mdi:flag-checkered"
    _attr_native_unit_of_measurement = "steps"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_step_goal"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("step_goal", 8000)


# ==================== Sleep Sensors ====================

class ZeppSleepScoreSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sleep Score"
    _attr_icon = "mdi:sleep"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "score"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_sleep_score"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("sleep_score")


class ZeppSleepDurationSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sleep Duration"
    _attr_icon = "mdi:bed-clock"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_sleep_duration"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("sleep_duration")


class ZeppDeepSleepSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Deep Sleep"
    _attr_icon = "mdi:power-sleep"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_deep_sleep"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("deep_sleep")


class ZeppLightSleepSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Light Sleep"
    _attr_icon = "mdi:weather-night"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_light_sleep"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("light_sleep")


class ZeppRemSleepSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "REM Sleep"
    _attr_icon = "mdi:brain"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_rem_sleep"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("rem_sleep")


class ZeppAwakeSleepSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Awake Time"
    _attr_icon = "mdi:eye-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_awake_time"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("awake_time")


class ZeppWakeCountSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Wake Count"
    _attr_icon = "mdi:alarm-bell"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_wake_count"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("wake_count")


class ZeppSleepRestingHRSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sleep Resting Heart Rate"
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "bpm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_sleep_rhr"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("sleep_rhr")


# ==================== Health & Heart Sensors ====================

class ZeppHeartRateSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Heart Rate"
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "bpm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_heart_rate"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("heart_rate")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.data.get("hr_min") is not None:
            attrs["min_heart_rate"] = self.coordinator.data["hr_min"]
        if self.coordinator.data.get("hr_max") is not None:
            attrs["max_heart_rate"] = self.coordinator.data["hr_max"]
        if self.coordinator.data.get("hr_avg") is not None:
            attrs["avg_heart_rate"] = self.coordinator.data["hr_avg"]
        return attrs


class ZeppRestingHRSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Resting Heart Rate"
    _attr_icon = "mdi:heart-box"
    _attr_native_unit_of_measurement = "bpm"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_resting_hr"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("resting_hr")


class ZeppStressSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Stress Level"
    _attr_icon = "mdi:emoticon-neutral-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "score"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_stress"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("stress")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.data.get("stress_min") is not None:
            attrs["min_stress"] = self.coordinator.data["stress_min"]
        if self.coordinator.data.get("stress_max") is not None:
            attrs["max_stress"] = self.coordinator.data["stress_max"]
        return attrs


class ZeppSpO2Sensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Blood Oxygen (SpO2)"
    _attr_icon = "mdi:water-percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_spo2"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("spo2")


class ZeppBreathingScoreSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Breathing Quality"
    _attr_icon = "mdi:weather-windy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "score"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_breathing_score"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("breathing_score")


class ZeppPaiSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "PAI"
    _attr_icon = "mdi:medal-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "PAI"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_pai"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("total_pai")


class ZeppHrvSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "HRV rMSSD"
    _attr_icon = "mdi:sine-wave"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_hrv"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("hrv")


# ==================== Training Load Sensors ====================

class ZeppTrainingLoadSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Training Load (7-Day)"
    _attr_icon = "mdi:weight-lifter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_training_load"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("training_load_total")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "optimal_min": self.coordinator.data.get("training_load_min"),
            "optimal_max": self.coordinator.data.get("training_load_max"),
        }


class ZeppDailyTrainingLoadSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Daily Training Load"
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_training_load_today"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("training_load_today")


# ==================== Body Composition Sensors ====================

class ZeppWeightSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Weight"
    _attr_icon = "mdi:scale-bathroom"
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_weight"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("weight")


class ZeppBmiSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "BMI"
    _attr_icon = "mdi:human"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_bmi"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("bmi")


class ZeppBodyFatSensor(CoordinatorEntity[ZeppCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Body Fat"
    _attr_icon = "mdi:percent"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: ZeppCoordinator, device_id: str, device_name: str, device_info: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_body_fat"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("body_fat")
