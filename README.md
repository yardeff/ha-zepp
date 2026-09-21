# Zepp (Amazfit) for Home Assistant

[English](README.md) | [Русский](README.ru.md)

Production-grade Home Assistant custom integration connecting **Zepp and Amazfit smartwatches and fitness bands** through official cloud APIs.

Provides real-time biometric telemetry, cardiovascular analytics, sleep architecture stages, training load computation, hardware diagnostics, and full historical Long-Term Statistics (LTS) backfilling.

> [!IMPORTANT]
> **Ecosystem Scope:**
> This integration exclusively supports smartwatches and fitness bands operating within the official **Zepp** mobile application ecosystem on iOS and Android. Devices operating under legacy Zepp Life (Mi Fit) or Mi Fitness (Xiaomi Wear) accounts communicate with separate cloud infrastructure and are not supported.

---

## Architecture Overview

```
+---------------------------------------------------------------------------------+
|                                WEARABLE HARDWARE                                |
|  Amazfit Smartwatches & Fitness Bands (Balance, Active, T-Rex, GTR, GTS, Bip)   |
+---------------------------------------------------------------------------------+
                                        |
                                        | Bluetooth Low Energy (BLE)
                                        v
+---------------------------------------------------------------------------------+
|                               MOBILE COMPANION                                  |
|               Official Zepp Application (iOS / Android)                         |
|               Periodically flushes cached buffers to cloud                      |
+---------------------------------------------------------------------------------+
                                        |
                                        | HTTPS / REST (Isolated Platform Token)
                                        v
+---------------------------------------------------------------------------------+
|                              ZEPP CLOUD CLUSTERS                                |
|   Geographically Routed: RU (api-mifit-ru), EU (de2), US (us2), SG, CN          |
+---------------------------------------------------------------------------------+
                                        |
                                        | Cloud Polling (15m Interval + Manual Button)
                                        v
+---------------------------------------------------------------------------------+
|                        HOME ASSISTANT CORE INTEGRATION                          |
|                                                                                 |
|  [DataUpdateCoordinator]                                                        |
|    +-- Isolated Metric Exception Handlers (Fault-Tolerant Parsing)              |
|    +-- Automatic Token Refresh & Reauth Flow Handling                           |
|    +-- Multi-Device Discovery & Active Wrist Prioritization                     |
|                                                                                 |
|  [Entities & Platforms]                                                         |
|    +-- Sensor Platform: 22+ Continuous & Cumulative Biometric Metrics           |
|    +-- Button Platform: Instant Manual Synchronization                          |
|    +-- Diagnostics Platform: Sanitized JSON System State Export                 |
|    +-- Services Platform: Bulk Historical Recorder LTS Importer                 |
+---------------------------------------------------------------------------------+
```

---

## Key Technical Features

* **Complete Session Isolation:**
  Authenticates against the official cloud using the dedicated web platform identifier (`com.huami.webapp`). Your primary mobile Zepp app on iOS or Android remains permanently logged in and operates without session eviction or disruption.

* **Multi-Cluster Geo-Routing:**
  Automatically probes all global Zepp and Huami regional endpoints (`api-mifit-ru`, `api-mifit-de2`, `api-mifit-us2`, `api-mifit-sg2`, `api-mifit-cn3`) during discovery and binds communication strictly to the cluster where your wearable hardware is physically registered.

* **Dual Authentication Methods:**
  * **Direct Credentials:** Native Email & Password handshake with background token renewal and automated credential persistence.
  * **Browser Session Extraction:** Seamless support for Google, Apple ID, Xiaomi Account, and federated social logins via browser cookies, supported by Home Assistant's native Reauthentication UI.

* **Active Multi-Device Prioritization:**
  If multiple wearables are registered to an account (e.g., a daily watch and a rugged outdoor watch), the integration dynamically identifies and prioritizes the currently worn device (`activeStatus == 1`), generating separate hardware-linked device registries without entity ID collisions.

* **Fault-Tolerant Metric Isolation:**
  Every data stream (heart rate, sleep, stress, SpO2, PAI, HRV, athletic load, battery, scale) is parsed within independent exception boundaries. If a budget or older wearable model lacks specific hardware sensors (such as HRV or continuous stress), other telemetry metrics continue updating without interruption.

* **Long-Term Statistics (LTS) Backfill:**
  Native integration with the Home Assistant Recorder engine. Imports up to five years of historical metrics directly into database statistics tables (`statistics` and `statistics_short_term`) without generating intermediate state changes.

* **Zero Midnight Statistics Drift:**
  Step counters enforce strict date boundary isolation (`date_time == today_str`), preventing accumulator corruption or negative delta spikes during midnight resets in Home Assistant Energy and Activity dashboards.

---

## Entity Catalog

### 1. Device Information & Hardware Metadata

| Sensor | Entity ID Suffix | Device Class | Unit | Description / Attributes |
| :--- | :--- | :--- | :--- | :--- |
| **Watch Model** | `_model` | None | String | Hardware model name. Attributes: `hardware_version`, `product_id`, `auth_key`, `bt_mac`, `region_host`, `user_id` |
| **Battery Level** | `_battery` | `battery` | `%` | Real-time device battery percentage |
| **MAC Address** | `_mac` | None | String | Hardware Bluetooth MAC address |
| **Firmware Version**| `_firmware` | None | String | Installed operating system build version |
| **Serial Number** | `_serial` | None | String | Factory hardware serial number |

> [!TIP]
> **Bluetooth Auth Key for Local Tracking:**
> The `_model` sensor exposes the device's 32-character AES `auth_key` in its extra state attributes. This key can be used with ESPHome, passive BLE monitors, or BTHome proxies for local presence detection without pairing conflicts.

### 2. Activity & Cumulative Movement

| Sensor | Entity ID Suffix | State Class | Device Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Steps** | `_steps` | `total_increasing` | None | steps | Total steps accumulated today |
| **Distance** | `_distance` | `total_increasing` | `distance` | m | Total distance traversed today |
| **Calories** | `_calories` | `total_increasing` | None | kcal | Active metabolic energy expended today |
| **Step Goal** | `_step_goal` | None | None | steps | User-configured daily step target |

### 3. Sleep Architecture & Respiration

| Sensor | Entity ID Suffix | State Class | Unit | Description / Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **Sleep Score** | `_sleep_score` | `measurement` | score | Overall algorithmic sleep quality index (0-100) |
| **Sleep Duration** | `_sleep_duration` | `measurement` | min | Total recorded sleep duration |
| **Deep Sleep** | `_deep_sleep` | `measurement` | min | Slow-wave Stage 3 sleep duration |
| **Light Sleep** | `_light_sleep` | `measurement` | min | Stage 1 and Stage 2 light sleep duration |
| **REM Sleep** | `_rem_sleep` | `measurement` | min | Rapid Eye Movement stage duration |
| **Awake Time** | `_awake_time` | `measurement` | min | Duration of nocturnal awake periods |
| **Wake Count** | `_wake_count` | `measurement` | None | Number of distinct awakening events during sleep |
| **Sleep Resting HR**| `_sleep_rhr` | `measurement` | bpm | Basal resting heart rate recorded during sleep |

### 4. Cardiovascular & Autonomic Biometrics

| Sensor | Entity ID Suffix | State Class | Unit | Description / Attributes |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate** | `_heart_rate` | `measurement` | bpm | Latest heart rate reading. Attributes: `min_heart_rate`, `max_heart_rate`, `avg_heart_rate` |
| **Resting Heart Rate**| `_resting_hr`| `measurement` | bpm | Daily resting heart rate baseline |
| **Stress Level** | `_stress` | `measurement` | score | Continuous stress level (0-100 scale). Attributes: `min_stress`, `max_stress` |
| **Blood Oxygen (SpO2)**| `_spo2` | `measurement` | `%` | Peripheral capillary oxygen saturation |
| **Breathing Quality** | `_breathing_score` | `measurement` | score | Nocturnal respiratory stability index |
| **PAI** | `_pai` | `measurement` | PAI | 7-day rolling Personal Activity Intelligence score |
| **HRV rMSSD** | `_hrv` | `measurement` | ms | Heart rate variability root mean square of successive differences |

### 5. Athletic Training Load

| Sensor | Entity ID Suffix | State Class | Description / Attributes |
| :--- | :--- | :--- | :--- |
| **Training Load (7-Day)** | `_training_load` | `measurement` | Rolling 7-day acute athletic load. Attributes: `optimal_min`, `optimal_max` |
| **Daily Training Load** | `_training_load_today` | `measurement` | Athletic training stress accumulated during the current calendar day |

### 6. Interactive Controls (Button Platform)

| Button Entity | Entity ID Suffix | Device Class | Description |
| :--- | :--- | :--- | :--- |
| **Sync Now** | `_sync_now` | `update` | Triggers an immediate cloud poll without waiting for the scheduled 15-minute timer |

---

## Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed and operational.
2. In the Home Assistant sidebar, navigate to **HACS -> Integrations**.
3. Click the overflow menu in the top right corner (three vertical dots) and choose **Custom repositories**.
4. Configure the repository:
   * **Repository:** `https://github.com/yardeff/ha-zepp`
   * **Type:** `Integration`
5. Click **Add**, locate **Zepp (Amazfit)** in the list, and select **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest source code archive from the GitHub repository.
2. Extract the archive and copy the directory `custom_components/zepp/` into your Home Assistant configuration directory:
   ```text
   <homeassistant-config>/custom_components/zepp/
   ```
3. Restart Home Assistant.

---

## Configuration

In Home Assistant, navigate to **Settings -> Devices & Services -> Add Integration** and search for **Zepp (Amazfit)**.

Choose the authentication procedure matching how your Zepp account was created:

```
                      +-----------------------------+
                      | How did you sign up in Zepp? |
                      +-----------------------------+
                                     |
                 +-------------------+-------------------+
                 |                                       |
       [Email & Direct Password]               [Google / Apple / Mi / Social]
                 |                                       |
                 v                                       v
         Use Method A (Direct)                 Use Method B (Browser Cookies)
       1-step email & pass input             Interactive web login + cookie copy
```

### Method A: Direct Zepp Account (Email & Password)

1. Select **Direct Zepp Account (Email & Password)**.
2. Enter your Zepp registration email address and password.
3. Keep the region set to **Auto-detect / Worldwide (Recommended)** (or select your specific country).
4. Click **Submit**. Home Assistant will authenticate, probe regional servers, and bind your devices automatically.

---

### Method B: Social Login (Google, Apple ID, Mi Account, Third-Party)

Users who sign in to Zepp using third-party identity providers do not possess a direct Huami password. Follow these steps to obtain a session token via the official web platform:

1. Open the official login portal in your desktop browser:  
   **[Zepp Web Sign-In Portal](https://user.zepp.com/universalLogin/index.html#/login?project_name=watchface&project_redirect_uri=https%3A%2F%2Fwatchface.zepp.com%2Fcreate&platform_app=com.huami.webapp&specify_lang=en)**
2. Authenticate using your **Google**, **Apple ID**, or **Mi Account**.
3. Upon successful login, the portal redirects to the Zepp Developer / Watchface interface. This redirection confirms an active web session.
4. Press `F12` (or right-click anywhere and select **Inspect**) to open Browser Developer Tools, then switch to the **Console** tab.
5. Paste the following command into the Console and press `Enter`:

```javascript
copy(document.cookie); console.log('%c[SUCCESS] Cookies copied to clipboard!', 'background: #22c55e; color: #000; font-size: 14px; font-weight: bold; padding: 4px;');
```

6. Return to Home Assistant, select **Browser Cookies**, press `Ctrl+V` to paste the credentials into the input field, and click **Submit**.

---

## Services

### `zepp.sync_history`

Performs bulk ingestion of historical wearable records directly into the Home Assistant Long-Term Statistics (LTS) database engine. 

```yaml
action: zepp.sync_history
data:
  days: 365
```

#### Service Fields

* **`days`** *(integer, optional, default: 365)*:  
  Number of retrospective days to retrieve and process. Backfills daily statistics for Steps, Distance, Calories, Sleep, and Resting Heart Rate without triggering transient state change events.

---

## Diagnostic Reporting

If an anomaly occurs or a sensor behaves unexpectedly:

1. Navigate to **Settings -> Devices & Services -> Zepp (Amazfit)**.
2. Click the three vertical dots next to your integration entry and select **Download diagnostics**.
3. Home Assistant generates a structured JSON report containing cloud responses, device hardware descriptors, and coordinator states.
4. All sensitive authorization keys, passwords, email addresses, and network identifiers are automatically redacted (`**REDACTED**`) before export.
5. Attach the file to a [GitHub Issue](https://github.com/yardeff/ha-zepp/issues).

---

## Frequently Asked Questions (FAQ)

#### Compatibility & Ecosystem

* **Q: Does this integration support Mi Fitness (Xiaomi Wear) or Zepp Life (Mi Fit)?**  
  No. Xiaomi / Mi Fitness and legacy Zepp Life operate across separate servers and closed proprietary APIs. Only devices actively registered inside the official **Zepp** mobile app are supported.

* **Q: Which watch models are compatible?**  
  Every smartwatch and smart band that synchronizes through the official Zepp mobile application. This includes the Amazfit Balance, Active, Cheetah, Falcon, T-Rex series, GTR series, GTS series, Bip series, and Amazfit Band series.

#### Data Synchronization & Latency

* **Q: Why do sensors update every 15 minutes instead of instantly?**  
  Wearables transmit data via Bluetooth Low Energy (BLE) to your smartphone; your phone then uploads encrypted batches to Zepp cloud servers. The watch has no direct Wi-Fi communication with Home Assistant. A 15-minute cloud polling cycle strikes an optimal balance between up-to-date figures and preventing cloud rate-limiting or firewall blocking.

* **Q: How can I update metrics immediately?**  
  Open the Zepp app on your phone and pull down on the dashboard to force an immediate BLE-to-cloud upload. Then, click the **Sync Now** button entity on the device card in Home Assistant.

#### Architecture & Security

* **Q: Will using this integration log me out of the Zepp app on my phone?**  
  No. Standard mobile logins displace existing sessions, but this integration connects under the designated web platform application identifier (`com.huami.webapp`), providing an isolated session channel that operates alongside your mobile application.

* **Q: What happens when credentials or tokens expire?**  
  * **Direct Accounts:** Token refreshing is handled automatically in the background using stored credentials.
  * **Social Logins:** When a web cookie session expires, Home Assistant issues a standard **Re-authenticate** alert. Click the alert and paste fresh cookies from your browser.

* **Q: Can this integration send notifications or trigger watch buzzes?**  
  No. This is an official cloud telemetry integration designed for monitoring health and activity. Bidirectional push notifications require local BLE connections or dedicated Zepp OS on-device applications.

---

## License & Disclaimers

This project is licensed under the **MIT License**. Refer to the [LICENSE](LICENSE) file for complete terms and conditions.

* **Trademark Notice:**  
  This software is an independent community project. Amazfit, Zepp, Huami, and their respective logos are registered trademarks of Anhui Huami Information Technology Co., Ltd. and Zepp Health Corporation. This project is not affiliated with, endorsed by, or associated with Zepp Health Corporation.

* **Medical Disclaimer:**  
  All telemetry, biometric data, and statistics provided by this integration are intended solely for personal informational and home automation purposes. They must not be utilized for medical diagnosis, clinical treatment, or critical health monitoring.

---

Copyright (c) 2026 yardev
