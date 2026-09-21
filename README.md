# Zepp (Amazfit) for Home Assistant

[English](README.md) | [Русский](README.ru.md)

Production-grade Home Assistant custom integration connecting **Zepp and Amazfit smartwatches and fitness bands** through official cloud APIs.

Provides real-time biometric telemetry, cardiovascular analytics, sleep architecture stages, athletic load metrics, and historical Long-Term Statistics (LTS) backfilling.

> [!IMPORTANT]
> **Ecosystem Compatibility Scope**  
> This integration exclusively supports wearable hardware (smartwatches and fitness bands) synchronized through the official **Zepp** mobile application on Android and iOS. Devices managed via Xiaomi / Mi Fitness or legacy Zepp Life (Mi Fit) operate on separate cloud infrastructure and are not supported.

---

## Technical Highlights

* **▸ Session Coexistence & Web Isolation**  
  Authenticates via an isolated web platform identifier (`com.huami.webapp`). The official Zepp mobile app on Android/iOS remains active without session invalidation or forced logouts.

* **▸ Dynamic Cluster Binding**  
  Probes regional cloud endpoints (`api-mifit-ru`, `api-mifit-de2`, `api-mifit-us2`, `api-mifit-sg2`, `api-mifit-cn3`) during discovery and binds communication strictly to the cluster hosting the user's active wearable hardware.

* **▸ Multi-Device Wrist Prioritization**  
  Automatically identifies the currently worn device (`activeStatus == 1`) when multiple wearables exist on an account. Each watch is provisioned as an independent Home Assistant device registry entry with isolated entity IDs.

* **▸ Fault-Tolerant Metric Boundaries**  
  Every biometric category (heart rate, sleep, stress, SpO2, PAI, HRV, athletic load, battery, scale) executes inside an isolated exception boundary. Older or budget models lacking specific sensors (e.g., HRV or continuous stress) continue updating all remaining metrics without coordinator failure.

* **▸ Long-Term Statistics (LTS) Recorder Engine**  
  Native integration with Home Assistant's statistical database engine. Automatically backfills historical data directly into `statistics` and `statistics_short_term` tables without generating transient state history events.

---

## Entity Catalog

### 1. Device Hardware & Diagnostics

| Sensor | Entity ID Suffix | Device Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Watch Model** | `_model` | None | String | Hardware model descriptor and platform parameters |
| **Battery Level** | `_battery` | `battery` | `%` | Real-time wearable battery percentage |
| **MAC Address** | `_mac` | None | String | Hardware Bluetooth MAC address |
| **Firmware Version**| `_firmware` | None | String | Installed device firmware version |
| **Serial Number** | `_serial` | None | String | Factory serial number |

<details>
<summary><b>View Advanced Hardware Attributes & BLE Key Extraction</b></summary>

> The `_model` entity exposes low-level hardware attributes within its state attributes:
>
> * `hardware_version` — Component board revision
> * `product_id` — Numeric model identifier
> * `auth_key` — 32-character AES Bluetooth authentication key
> * `bt_mac` — Bluetooth adapter hardware address
> * `region_host` — Target cloud cluster endpoint
> * `user_id` — Numeric Zepp cloud account identifier
>
> **Local BLE Presence Tracking (ESPHome / BTHome):**  
> The 32-character `auth_key` can be used directly with ESPHome or passive BLE monitor components to track the watch locally without pairing conflicts:
>
> ```yaml
> # Example: ESPHome BLE Client
> ble_client:
>   - mac_address: FF:5C:1D:4D:7A:40
>     id: amazfit_watch
> # Use the auth_key attribute from your _model sensor
> ```
</details>

### 2. Daily Activity & Cumulative Movement

| Sensor | Entity ID Suffix | State Class | Device Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Steps** | `_steps` | `total_increasing` | None | steps | Total steps accumulated today |
| **Distance** | `_distance` | `total_increasing` | `distance` | m | Cumulative distance traversed today |
| **Calories** | `_calories` | `total_increasing` | None | kcal | Active metabolic energy expended today |
| **Step Goal** | `_step_goal` | None | None | steps | Configured daily step objective |

### 3. Sleep Architecture & Respiration

| Sensor | Entity ID Suffix | State Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sleep Score** | `_sleep_score` | `measurement` | score | Algorithmic sleep quality index (0-100) |
| **Sleep Duration** | `_sleep_duration` | `measurement` | min | Total recorded nocturnal sleep duration |
| **Deep Sleep** | `_deep_sleep` | `measurement` | min | Stage 3 slow-wave sleep duration |
| **Light Sleep** | `_light_sleep` | `measurement` | min | Stage 1 and Stage 2 light sleep duration |
| **REM Sleep** | `_rem_sleep` | `measurement` | min | Rapid Eye Movement phase duration |
| **Awake Time** | `_awake_time` | `measurement` | min | Cumulative nighttime wakefulness duration |
| **Wake Count** | `_wake_count` | `measurement` | None | Number of discrete awakening events |
| **Sleep Resting HR**| `_sleep_rhr` | `measurement` | bpm | Basal resting heart rate recorded during sleep |

### 4. Cardiovascular & Autonomic Biometrics

| Sensor | Entity ID Suffix | State Class | Unit | Description / Attributes |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate** | `_heart_rate` | `measurement` | bpm | Latest reading. Attributes: `min_heart_rate`, `max_heart_rate`, `avg_heart_rate` |
| **Resting Heart Rate**| `_resting_hr`| `measurement` | bpm | Daily basal resting heart rate baseline |
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

<details>
<summary><b>View Optional Body Composition Scale Sensors</b></summary>

> When smart scales are associated with the user profile, the following additional sensors populate automatically:
>
> * **Weight** (`_weight`) — Unit: `kg`, Device Class: `weight`
> * **BMI** (`_bmi`) — Body Mass Index
> * **Body Fat** (`_body_fat`) — Unit: `%`
> * **Muscle Mass** (`_muscle_mass`) — Unit: `kg`
> * **Body Water** (`_body_water`) — Unit: `%`
> * **Bone Mass** (`_bone_mass`) — Unit: `kg`
</details>

### 6. Interactive Controls (Button Platform)

| Button Entity | Entity ID Suffix | Device Class | Description |
| :--- | :--- | :--- | :--- |
| **Sync Now** | `_sync_now` | `update` | Requests an immediate cloud refresh without waiting for the 15-minute polling timer |

---

## Installation

### Method 1: HACS (Recommended)

1. Navigate to **HACS -> Integrations** in the Home Assistant interface.
2. Click the overflow menu (three vertical dots) in the upper-right corner and select **Custom repositories**.
3. Enter the repository details:
   * **Repository:** `https://github.com/yardeff/ha-zepp`
   * **Type:** `Integration`
4. Click **Add**, locate **Zepp (Amazfit)** in the integration catalog, and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Deployment

1. Download the latest source archive from the GitHub repository.
2. Extract the `custom_components/zepp` folder into your Home Assistant configuration directory:
   ```text
   <config>/custom_components/zepp/
   ```
3. Restart Home Assistant.

---

## Configuration

In Home Assistant, navigate to **Settings -> Devices & Services -> Add Integration** and search for **Zepp (Amazfit)**.

### Method A: Direct Zepp Account (Email & Password)

> Select this method if you registered in Zepp using your email address and a direct password.

1. Choose **Direct Zepp Account (Email & Password)** in the setup dialog.
2. Enter your account email address and password.
3. Keep the region setting as **Auto-detect / Worldwide (Recommended)**.
4. Click **Submit**. The integration authenticates, discovers the regional server, and provisions all device entities.

---

### Method B: Social Login (Google, Apple ID, Mi Account)

> Select this method if you sign in to Zepp using Google, Apple, or Mi. Since federated accounts do not have a dedicated Zepp password, authentication uses browser session cookies.

<details open>
<summary><b>Step-by-Step Browser Cookie Extraction Guide</b></summary>

1. Open the official sign-in portal in your desktop browser:  
   [Zepp Web Sign-In Portal](https://user.zepp.com/universalLogin/index.html#/login?project_name=watchface&project_redirect_uri=https%3A%2F%2Fwatchface.zepp.com%2Fcreate&platform_app=com.huami.webapp&specify_lang=en)

2. Complete authentication using your **Google**, **Apple**, or **Mi** account credentials.

3. After successful authentication, the portal redirects to the Zepp Developer / Watchface interface. This redirection confirms an active web session.

4. Press `F12` (or right-click anywhere and select **Inspect**) to open Browser Developer Tools, then switch to the **Console** tab.  
   *(If your browser displays a security notice blocking pastes, type `allow pasting` into the console and press Enter).*

5. Copy and execute the following snippet in the Console:

```javascript
copy(document.cookie); console.log('%c[SUCCESS] Cookies copied to clipboard!', 'background: #22c55e; color: #000; font-size: 14px; font-weight: bold; padding: 4px;');
```

6. Return to the Home Assistant setup dialog, select **Browser Cookies**, press `Ctrl+V` in the text field, and click **Submit**.
</details>

---

## Services

### `zepp.sync_history`

Performs bulk historical backfilling of wearable records directly into Home Assistant's Long-Term Statistics database (`statistics` and `statistics_short_term` tables).

```yaml
action: zepp.sync_history
data:
  days: 365
```

> [!NOTE]
> **Automatic Initial Sync:**  
> Upon initial integration configuration, a 365-day historical backfill runs automatically in the background. You do not need to schedule periodic executions of this service; ongoing daily metrics are captured continuously during normal polling.

---

## Diagnostics & Troubleshooting

<details>
<summary><b>How to Download Sanitized Diagnostic Reports for GitHub Issues</b></summary>

If an anomaly occurs or an API endpoint returns unexpected values:

1. Navigate to **Settings -> Devices & Services -> Zepp (Amazfit)**.
2. Click the three vertical dots on the integration card and select **Download diagnostics**.
3. Home Assistant generates a structured JSON report containing coordinator states, device registers, and API responses.
4. All authorization tokens, passwords, email addresses, and MAC addresses are automatically scrubbed (`**REDACTED**`) prior to export.
5. Attach the downloaded JSON file to your report on [GitHub Issues](https://github.com/yardeff/ha-zepp/issues).
</details>

---

## Frequently Asked Questions

<details>
<summary><b>Ecosystem & Device Compatibility</b></summary>

> **Q: Does this integration support Mi Fitness (Xiaomi Wear) or Zepp Life (Mi Fit)?**  
> No. Xiaomi / Mi Fitness and legacy Zepp Life operate across separate servers and closed proprietary APIs. Only devices actively registered inside the official **Zepp** mobile app are supported.
>
> **Q: Which wearable models are compatible?**  
> Any smartwatch or smart band actively synchronizing through the official Zepp mobile application.
</details>

<details>
<summary><b>Data Sync Frequency & Bluetooth Latency</b></summary>

> **Q: Why do sensors update every 15 minutes instead of in real time?**  
> Wearables communicate with your mobile phone via Bluetooth Low Energy (BLE); your phone periodically pushes encrypted batches to the cloud. The watch has no direct Wi-Fi communication with Home Assistant. Polling the cloud faster than every 15 minutes would not yield newer data (until the phone syncs with the watch) and risks IP rate-limiting by cloud firewalls.
>
> **Q: How can I force an immediate data refresh?**  
> 1. Open the Zepp app on your phone and pull down on the dashboard to force an immediate BLE-to-cloud upload.  
> 2. Click the **Sync Now** button entity on your device card in Home Assistant.
</details>

<details>
<summary><b>Session Security & Token Expiry</b></summary>

> **Q: Will using this integration log me out of the Zepp app on my phone?**  
> No. Standard mobile logins displace existing sessions, but this integration connects under the designated web platform application identifier (`com.huami.webapp`), providing an isolated session channel that operates alongside your mobile application.
>
> **Q: What happens when session tokens expire?**  
> * **Direct Accounts:** Token refreshing is handled automatically in the background using stored credentials.  
> * **Social Logins:** When a web cookie session expires, Home Assistant issues a standard **Re-authenticate** prompt. Click the alert and paste fresh cookies from your browser.
</details>

<details>
<summary><b>Notifications & Two-Way Hardware Control</b></summary>

> **Q: Can this integration send notifications to the watch or trigger vibrations?**  
> No. This is an official cloud telemetry integration designed for health monitoring and automation triggers. Bidirectional push notifications require local BLE connections or dedicated Zepp OS on-device applications.
>
> **Q: Does it export raw GPS activity routes and maps?**  
> No. The integration collects aggregated athletic telemetry (steps, distance, active calories, and training load), but does not ingest large binary/GPX map coordinate streams.
</details>

---

## License & Disclaimers

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for complete terms.

> **Trademark Notice:**  
> Amazfit, Zepp, Huami, and their respective logos are registered trademarks of Anhui Huami Information Technology Co., Ltd. and Zepp Health Corporation. This software is an independent community project and is not affiliated with, sponsored by, or endorsed by Zepp Health Corporation.

> **Medical Disclaimer:**  
> All biometric metrics, health assessments, and physical activity values provided by this integration are intended solely for personal informational and home automation purposes. They must not be utilized for medical diagnosis, clinical evaluation, or critical health monitoring.

---

Copyright (c) 2026 yardev
