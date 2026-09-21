# Zepp for Home Assistant

Custom integration connecting Zepp and Amazfit smartwatches and fitness bands to Home Assistant via official cloud APIs.

Compatible with all smartwatch and band models synced through the official **Zepp** mobile application (not Zepp Life or Mi Fitness).

---

## Overview

The integration provides real-time health telemetry, athletic load analysis, sleep stage tracking, and full historical statistics backfilling into Home Assistant.

### Key Technical Characteristics

- **Session Isolation:** Authenticates via an independent web platform identifier (`com.huami.webapp`). The official Zepp mobile application on Android/iOS remains logged in and functioning normally.
- **Dual Authentication Support:**
  - Direct account authentication via email and password with fully automatic background token renewal.
  - Federated sign-in (Google, Apple ID, Xiaomi Account) via browser session tokens, backed by Home Assistant's native re-authentication framework.
- **Long-Term Statistics (LTS) Integration:** Native support for the Home Assistant Recorder statistics engine. Historical data is backfilled into long-term tables for multi-year trend analysis without bloating daily state history.
- **High-Density Sensor Suite:** Real-time biometrics, detailed sleep stage breakdowns, cardiovascular statistics, and training load.

---

## Sensor Entities and Telemetry

The integration dynamically generates entities based on the hardware and features registered to your Zepp account.

### 1. Activity and Daily Progress

| Sensor | Entity Suffix | State Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| Steps | `_steps` | `total_increasing` | steps | Total steps recorded today |
| Distance | `_distance` | `total_increasing` | m | Cumulative distance traversed today |
| Calories | `_calories` | `total_increasing` | kcal | Cumulative energy expended today |
| Step Goal | `_step_goal` | None | steps | Configured daily step objective |

### 2. Sleep Architecture and Respiration

| Sensor | Entity Suffix | State Class | Unit | Attributes / Notes |
| :--- | :--- | :--- | :--- | :--- |
| Sleep Score | `_sleep_score` | `measurement` | score | Overall sleep quality index (0-100) |
| Sleep Duration | `_sleep_duration` | `measurement` | min | Total recorded sleep time |
| Deep Sleep | `_deep_sleep` | `measurement` | min | Stage 3 / slow-wave sleep duration |
| Light Sleep | `_light_sleep` | `measurement` | min | N1 and N2 sleep duration |
| REM Sleep | `_rem_sleep` | `measurement` | min | Rapid Eye Movement phase duration |
| Awake Time | `_awake_time` | `measurement` | min | Interrupted wakefulness during sleep period |
| Wake Count | `_wake_count` | `measurement` | None | Number of awakening events |
| Sleep Resting HR | `_sleep_rhr` | `measurement` | bpm | Basal heart rate measured during sleep |

### 3. Cardiovascular and Autonomic Metrics

| Sensor | Entity Suffix | State Class | Unit | Extra Attributes |
| :--- | :--- | :--- | :--- | :--- |
| Heart Rate | `_heart_rate` | `measurement` | bpm | `min_heart_rate`, `max_heart_rate`, `avg_heart_rate` |
| Resting Heart Rate | `_resting_hr` | `measurement` | bpm | Daily resting heart rate baseline |
| Stress Level | `_stress` | `measurement` | score | `min_stress`, `max_stress` (0-100 scale) |
| Blood Oxygen ($SpO_2$) | `_spo2` | `measurement` | % | Peripheral capillary oxygen saturation |
| Breathing Quality | `_breathing_score` | `measurement` | score | Nighttime breathing analysis score |
| PAI | `_pai` | `measurement` | PAI | 7-day rolling Personal Activity Intelligence score |
| HRV rMSSD | `_hrv` | `measurement` | ms | Root mean square of successive differences |

### 4. Athletic Load and Recovery

| Sensor | Entity Suffix | State Class | Unit | Extra Attributes |
| :--- | :--- | :--- | :--- | :--- |
| Training Load (7-Day) | `_training_load` | `measurement` | None | `optimal_min`, `optimal_max` |
| Daily Training Load | `_training_load_today` | `measurement` | None | Training stress accumulated during current day |

### 5. Hardware Metadata and Diagnostics

| Sensor | Entity Suffix | Extra Attributes |
| :--- | :--- | :--- |
| Watch Model | `_model` | `hardware_version`, `product_id`, `auth_key`, `bt_mac`, `region_host`, `user_id` |
| MAC Address | `_mac` | Network hardware address of the wearable |
| Firmware Version | `_firmware` | Device operating system / firmware build string |
| Serial Number | `_serial` | Factory hardware serial number |

---

## System Architecture

### 1. Web Session Isolation

Standard mobile app logins invalidate prior sessions upon new authentication requests. To prevent kicking out the mobile app, the integration authenticates under an isolated web platform identifier (`com.huami.webapp`). This allows the mobile Zepp app to maintain its primary Bluetooth connection and background sync routines uninterrupted.

### 2. Multi-Regional Cloud Routing

Zepp hosts account data across geographically distributed server clusters (including Global / Worldwide, Europe, Russia & CIS, North America, and Asia-Pacific). During initial setup, the integration queries the user profile service, resolves the target cluster according to account locality, and routes subsequent requests directly to that region.

### 3. Authentication Lifecycle and Self-Healing

- **Direct Accounts:** Tokens expire periodically. When an API endpoint responds with HTTP 401 (`invalid token`), the coordinator catches the error, initiates an automatic re-login handshake using stored credentials, persists the refreshed token in the Home Assistant configuration entry, and retries the data fetch seamlessly.
- **Federated Accounts (Google / Apple / Mi):** Because external identity providers do not expose raw passwords, session expiration triggers `ConfigEntryAuthFailed`. Home Assistant flags the integration with a native re-authentication prompt, allowing the administrator to paste fresh browser cookies directly.

### 4. Polling Pipeline

The integration updates live sensor states on a standard 15-minute polling interval, retrieving aggregate daily progress, intraday heart rate stream decodings, and latest health events with minimal network overhead.

---

## Services

### `zepp.sync_history`

Backfills historical sensor metrics directly into Home Assistant's Long-Term Statistics database (`statistics` and `statistics_short_term` tables).

This service imports past data across arbitrary time horizons without generating massive volumes of transient state change events.

#### Service Data Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `days` | integer | No | `365` | Number of past days to query and import (e.g. `30`, `365`, `1825`). |

#### Example Automation / Action

```yaml
action: zepp.sync_history
data:
  days: 365
```

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant interface.
2. Navigate to **Integrations**, click the overflow menu (three vertical dots), and select **Custom repositories**.
3. Enter `https://github.com/yarchefis/ha-zepp` in the **Repository** field.
4. Set **Type** to `Integration` and click **Add**.
5. Search for `Zepp`, click **Download**, and restart Home Assistant.

### Method 2: Manual Deployment

1. Download the latest source release archive.
2. Extract the `custom_components/zepp` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings -> Devices & Services -> Add Integration**.
2. Search for **Zepp** and select it.
3. Follow the guided instructions presented in the setup dialog corresponding to your login type (Direct Credentials or Browser Cookies).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for full details and legal disclaimers.

Copyright (c) 2026 yardev

