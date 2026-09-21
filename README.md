# Zepp (Amazfit) for Home Assistant

[English](README.md) | [Русский](README.ru.md)

[![Telegram](https://img.shields.io/badge/Telegram-Channel-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://t.me/yardev_code)

Home Assistant integration for connecting **Amazfit and Zepp smartwatches and fitness bands** using the official Zepp cloud APIs.

Syncs daily activity, heart rate, sleep stages, stress, SpO2, workout load, and stores historical metrics directly in Home Assistant Long-Term Statistics (LTS).

> [!IMPORTANT]
> **Only devices managed via the Zepp app are supported**  
> This integration exclusively supports smartwatches and fitness bands connected to the official **Zepp** mobile application (Android / iOS). Devices running on Xiaomi / Mi Fitness or Zepp Life (Mi Fit) are not supported because they use different cloud servers and protocols.

---

## Highlights

* **▸ Keeps mobile app session active**  
  Authenticates using a dedicated web platform client (`com.huami.webapp`), so your official Zepp mobile app stays signed in without being disconnected.

* **▸ Automatic regional server detection**  
  Probes Zepp global cloud endpoints (Russia, Europe, US, Asia) during setup and automatically connects to the server where your watch is registered.

* **▸ Multi-device support**  
  If you have multiple watches on your account, the integration detects which one is currently worn (`activeStatus == 1`) and creates separate devices in Home Assistant.

* **▸ Sensor fault tolerance**  
  Each sensor category is polled independently. If an older or budget watch lacks a specific feature (such as continuous stress or HRV), all other sensors continue updating without issues.

* **▸ Long-Term Statistics (LTS)**  
  Historical activity, steps, distance, calories, and sleep data are stored directly into Home Assistant Long-Term Statistics without cluttering the state history database.

---

## Sensors & Entities

### 1. Device Information

| Sensor | Entity ID Suffix | Device Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Watch Model** | `_model` | — | String | Device model and technical parameters |
| **MAC Address** | `_mac` | — | String | Bluetooth MAC address |
| **Firmware Version**| `_firmware` | — | String | Installed firmware version |
| **Serial Number** | `_serial` | — | String | Hardware serial number |

> **Note on Battery Level:**  
> On modern Amazfit watches running Zepp OS (Active, Balance, Cheetah, T-Rex 3, etc.), battery percentage is communicated strictly over local Bluetooth Low Energy (BLE) to the official smartphone app. The Zepp cloud REST API does not receive or store battery percentage for these watches. An empty `Unknown` battery entity is deliberately omitted to keep the dashboard clean. For local real-time battery tracking in Home Assistant, use the provided `auth_key` attribute with the native Bluetooth or ESPHome BLE integration.

<details>
<summary><b>Advanced Attributes & BLE Authentication Key</b></summary>

> The `_model` sensor attributes expose low-level technical parameters:
>
> * `auth_key` — 32-character AES Bluetooth authentication key
> * `hardware_version` — Board revision
> * `product_id` — Numeric model ID
> * `bt_mac` — Bluetooth adapter address
> * `region_host` — Cloud server endpoint
> * `user_id` — Zepp cloud user ID
>
> **Local presence tracking with ESPHome:**  
> The `auth_key` can be used in ESPHome for passive BLE tracking at home without disconnecting the watch from your phone:
>
> ```yaml
> ble_client:
>   - mac_address: FF:5C:1D:4D:7A:40
>     id: amazfit_watch
> # Use the auth_key attribute from your _model sensor
> ```
</details>

### 2. Daily Activity

| Sensor | Entity ID Suffix | State Class | Device Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Steps** | `_steps` | `total_increasing` | — | steps | Total steps today |
| **Distance** | `_distance` | `total_increasing` | `distance` | m | Distance covered today |
| **Calories** | `_calories` | `total_increasing` | — | kcal | Active calories burned today |
| **Step Goal** | `_step_goal` | — | — | steps | Configured daily step goal |

### 3. Sleep

| Sensor | Entity ID Suffix | State Class | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Sleep Score** | `_sleep_score` | `measurement` | score | Overall sleep quality score (0–100) |
| **Sleep Duration** | `_sleep_duration` | `measurement` | min | Total night sleep duration |
| **Deep Sleep** | `_deep_sleep` | `measurement` | min | Slow-wave deep sleep duration |
| **Light Sleep** | `_light_sleep` | `measurement` | min | Light sleep duration |
| **REM Sleep** | `_rem_sleep` | `measurement` | min | Rapid Eye Movement sleep duration |
| **Awake Time** | `_awake_time` | `measurement` | min | Wakefulness duration during the night |
| **Wake Count** | `_wake_count` | `measurement` | — | Number of awakenings |
| **Sleep Resting HR**| `_sleep_rhr` | `measurement` | bpm | Resting heart rate during sleep |

### 4. Heart Rate & Health

| Sensor | Entity ID Suffix | State Class | Unit | Description / Attributes |
| :--- | :--- | :--- | :--- | :--- |
| **Heart Rate** | `_heart_rate` | `measurement` | bpm | Latest reading. Attributes: `min_heart_rate`, `max_heart_rate`, `avg_heart_rate` |
| **Resting Heart Rate**| `_resting_hr`| `measurement` | bpm | Daily resting heart rate baseline |
| **Stress Level** | `_stress` | `measurement` | score | Stress level (0–100). Attributes: `min_stress`, `max_stress` |
| **Blood Oxygen (SpO2)**| `_spo2` | `measurement` | `%` | Blood oxygen saturation |
| **Breathing Quality** | `_breathing_score` | `measurement` | score | Sleep breathing quality score |
| **PAI** | `_pai` | `measurement` | PAI | 7-day rolling Personal Activity Intelligence score |
| **Heart Rate Variability (HRV)** | `_hrv` | `measurement` | ms | Heart rate variability (rMSSD) |
| **Readiness Score** | `_readiness_score` | `measurement` | score | Morning physical and mental recovery score |

### 5. Workout Training Load

| Sensor | Entity ID Suffix | State Class | Description / Attributes |
| :--- | :--- | :--- | :--- |
| **7-Day Training Load** | `_training_load` | `measurement` | Rolling 7-day workout load. Attributes: `optimal_min`, `optimal_max` |
| **Daily Training Load** | `_training_load_today` | `measurement` | Training load accumulated today |

<details>
<summary><b>Body Composition Scale Sensors (if linked to account)</b></summary>

> If you have a smart scale paired with your Zepp account, these sensors are added automatically:
>
> * **Weight** (`_weight`) — kg
> * **BMI** (`_bmi`) — Body Mass Index
> * **Body Fat** (`_body_fat`) — %
> * **Muscle Mass** (`_muscle_mass`) — kg
> * **Body Water** (`_body_water`) — %
> * **Bone Mass** (`_bone_mass`) — kg
</details>

### 6. Controls

| Button | Entity ID Suffix | Description |
| :--- | :--- | :--- |
| **Sync Now** | `_sync_now` | Requests an immediate cloud refresh without waiting for the 15-minute polling interval |

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS -> Integrations** in Home Assistant.
2. In the top right corner, click the menu (three dots) -> **Custom repositories**.
3. Fill in:
   * **Repository:** `https://github.com/yardeff/ha-zepp`
   * **Type:** `Integration`
4. Click **Add**, find **Zepp (Amazfit)** in the list, and click **Download**.
5. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the repository source archive.
2. Copy the `custom_components/zepp` folder into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.

---

## Configuration

In Home Assistant, go to **Settings -> Devices & Services -> Add Integration** and search for **Zepp (Amazfit)**.

### Option A: Zepp Account (Email & Password)

> Use this option if you registered your Zepp account directly with an email address and password.

1. Choose **Direct Zepp Account (Email & Password)**.
2. Enter your email address and password.
3. Leave the region as **Auto-detect / Worldwide (Recommended)**.
4. Click **Submit**. The integration connects to your server and sets up your watch.

---

### Option B: Social Login (Google, Apple ID, Mi Account)

> If you sign in to Zepp using Google, Apple, or Mi, your account doesn't have a direct Zepp password. In this case, use cookies from the web version.

<details open>
<summary><b>How to get cookies (takes 1 minute)</b></summary>

1. Open the sign-in page in a desktop browser:  
   [Official Zepp Sign-In Portal](https://user.zepp.com/universalLogin/index.html#/login?project_name=watchface&project_redirect_uri=https%3A%2F%2Fwatchface.zepp.com%2Fcreate&platform_app=com.huami.webapp&specify_lang=en)

2. Sign in with your **Google**, **Apple ID**, or **Mi Account**.

3. After signing in, you will be redirected to the Zepp Watchface Maker — this confirms that an active session was created.

4. Press `F12` (or right-click -> **Inspect**) and open the **Console** tab.  
   *(If the browser shows a security warning about pasting, type `allow pasting` and press Enter).*

5. Paste this command and press `Enter`:

```javascript
copy(document.cookie); console.log('%c[SUCCESS] Cookies copied to clipboard!', 'background: #22c55e; color: #000; font-size: 14px; font-weight: bold; padding: 4px;');
```

6. In Home Assistant, choose **Browser Cookies**, paste the clipboard contents (`Ctrl+V`), and click **Submit**.
</details>

---

## Services

### `zepp.sync_history`

Downloads historical data from Zepp cloud servers directly into Home Assistant Long-Term Statistics.

```yaml
action: zepp.sync_history
data:
  days: 365
```

> [!NOTE]
> When you first add the integration, it automatically imports historical data for the past year in the background. You do not need to run this service periodically: recent metrics are saved to statistics automatically on every poll.

---

## Polling Interval & Custom Timer

By default, the integration fetches fresh metrics from the Zepp cloud every **15 minutes**. This provides an optimal balance between up-to-date health statistics and preventing cloud rate-limiting.

If your automations require more frequent updates (e.g. during an active day) or less frequent requests:

1. Navigate to **Settings -> Devices & Services -> Zepp (Amazfit)**.
2. Click the **Configure** button (gear icon) on the integration card.
3. Select your preferred polling frequency from the dropdown:
   * `5 minutes` — for high-frequency activity and heart rate tracking.
   * `10 minutes` — accelerated polling.
   * `15 minutes (Default)` — recommended baseline balance.
   * `30 minutes` — conservative polling.
   * `60 minutes` — hourly updates.
4. Click **Submit**. The new polling schedule takes effect immediately on the fly without needing to restart Home Assistant.

---

## Diagnostics & Log Capture

The integration includes a built-in diagnostic subsystem fully integrated with Home Assistant standards:

* **In-Memory Ring Buffer:** A dedicated handler (`ZeppLogCaptureHandler`) continuously retains the last 100 internal log events of `custom_components.zepp` directly in memory.
* **Diagnostics Report Contents (JSON):**
  * `recent_logs` — chronological trace of API requests, cluster discovery responses, and background tasks.
  * `system_status` — integration version, active cloud cluster (`region_host`), polling interval, timestamp, and health status of the latest sync.
  * `metrics_health` — table of sensor availability (indicates which sensors provide valid values and which are not supported by the current watch model).
  * `devices` — list of discovered watch models, firmware revisions, and hardware IDs.
* **Privacy & Secret Redaction:** All authentication tokens (`apptoken`), passwords, email addresses, Bluetooth MAC addresses, and encryption keys (`auth_key`) are automatically sanitized with `[REDACTED]` placeholders.

### How to Download Diagnostics:

1. Go to **Settings -> Devices & Services -> Zepp (Amazfit)**.
2. Click the three dots menu on the integration card and select **Download diagnostics**.
3. Attach the downloaded JSON file to your report on [GitHub Issues](https://github.com/yardeff/ha-zepp/issues) — it provides the exact context needed to diagnose issues without exposing your private credentials.

---

## Frequently Asked Questions

<details>
<summary><b>Which devices are supported?</b></summary>

> Any smartwatch or fitness band that syncs through the official Zepp mobile app on Android or iOS.
>
> Devices using Mi Fitness (Xiaomi Wear) or Zepp Life (Mi Fit) are not supported because they run on completely different servers and closed protocols.
</details>

<details>
<summary><b>Why don't sensors update immediately?</b></summary>

> The watch communicates with your smartphone over Bluetooth, and the official Zepp mobile app periodically syncs that data to the cloud. Most wearables do not possess a direct Wi-Fi radio connection to Home Assistant.
>
> Cloud data is updated as soon as the watch syncs with your phone. If you need quicker updates in Home Assistant, you can reduce the polling interval down to 5 minutes via the **Configure** menu, or press the **Sync Now** button (`_sync_now`) after swiping down on the Zepp mobile app home screen.
</details>

<details>
<summary><b>Will this log me out of the mobile app on my phone?</b></summary>

> No. The integration connects under a dedicated web client ID (`com.huami.webapp`), so your phone session stays active.
</details>

<details>
<summary><b>What happens when a session expires?</b></summary>

> * **With email and password:** The integration automatically refreshes tokens in the background.
> * **With Google / Apple:** When cookies expire, Home Assistant will show a **Re-authenticate** prompt. Simply copy fresh cookies from your browser and submit.
</details>

<details>
<summary><b>Can this integration send notifications to the watch?</b></summary>

> No. This integration reads health and activity metrics from the cloud. Sending notifications requires a direct local Bluetooth connection or a companion app running on the watch (Zepp OS).
</details>

---

## Community & Author

* Author: [yardev](https://github.com/yardeff)
* Telegram: [@yardev_code](https://t.me/yardev_code)

---

## License

Released under the **MIT License** — see [LICENSE](LICENSE) for details.

> **Disclaimer:**  
> Amazfit, Zepp, and Huami are trademarks of Anhui Huami Information Technology Co., Ltd. and Zepp Health Corporation. This integration is an independent community project.  
> All health metrics are for informational purposes only and are not intended for medical use.

---

Copyright (c) 2026 yardev
