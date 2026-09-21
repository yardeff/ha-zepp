# Zepp (Amazfit) for Home Assistant

<p align="center">
  <img src="https://raw.githubusercontent.com/yarchefis/ha-zepp/main/custom_components/zepp/brand/logo.png" alt="Zepp Logo" width="180">
</p>

<p align="center">
  <b>Home Assistant custom integration for Zepp / Amazfit smartwatches & fitness trackers</b><br>
  Real-time sensors, seamless dual authentication, and full <b>365-day historical statistics (LTS) sync</b> directly into Home Assistant.
</p>

---

## ✨ Features

- 🔄 **No Mobile App Logouts:** Authenticates using an isolated web session (`com.huami.webapp`). Your official Zepp phone app stays active and connected.
- 🔑 **Two Sign-In Options:**
  1. **Direct Login (Email & Password):** Fast 1-step login for standalone Zepp accounts.
  2. **Browser Cookies (Google, Apple ID, Xiaomi, Social):** Full support for federated sign-in with 1-click console helper.
- 📈 **365-Day Historical LTS Sync:** Automatically backfills up to 1 year of hourly heart rate, daily steps, calories, sleep stages, all-day stress, and PAI directly into Home Assistant's Long-Term Statistics database.
- 💓 **Rich Biometric & Health Sensors:**
  - 🚶 **Activity:** Steps, distance, active calories, total calories.
  - ❤️ **Heart Rate:** Live HR, minimum/maximum/average HR attributes, resting heart rate (RHR).
  - 😴 **Sleep Analysis:** Sleep duration, sleep score, deep sleep, light sleep, REM, wake time.
  - 🩸 **Vital Signs:** Blood Oxygen ($SpO_2$), All-day Stress score, PAI (Personal Activity Intelligence).
  - 🔋 **Device State:** Watch battery percentage, charging state, last sync timestamp.
- 🛠️ **Device Attributes:** Watch model, firmware version, serial number, Bluetooth MAC address.

---

## ⌚ Supported Devices

Compatible with all watches and bands synced via the official **Zepp** app:
- **Amazfit Balance, Active, Active Edge**
- **Amazfit Cheetah (Round / Square / Pro)**
- **Amazfit T-Rex 3, T-Rex Ultra, T-Rex 2, T-Rex Pro**
- **Amazfit GTR 4, GTR 3 Pro, GTR 3, GTR 2**
- **Amazfit GTS 4, GTS 4 Mini, GTS 3, GTS 2**
- **Amazfit Bip 5, Bip 3 Pro, Bip 3**
- **Amazfit Helio Ring, Band 7**
- *And all other Zepp OS compatible wearables.*

---

## 📦 Installation

### Option 1: Via HACS (Recommended)
1. Open **HACS** in your Home Assistant.
2. Click the three dots in the top right corner ➔ **Custom repositories**.
3. Add repository URL: `https://github.com/yarchefis/ha-zepp` with category **Integration**.
4. Search for **Zepp (Amazfit)**, click **Download**, and restart Home Assistant.

### Option 2: Manual Installation
1. Download the latest release zip from GitHub.
2. Copy the `custom_components/zepp` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings ➔ Devices & Services ➔ Add Integration**.
2. Search for **Zepp (Amazfit)**.
3. Choose your preferred authentication method:

### Method A: Direct (Email & Password)
- Choose this if you registered in the Zepp app using your email address and password.

### Method B: Social Login (Google / Apple / Xiaomi)
1. Open the [Zepp Login Page](https://user.zepp.com/universalLogin/index.html#/login?project_name=watchface&project_redirect_uri=https%3A%2F%2Fwatchface.zepp.com%2Fcreate&platform_app=com.huami.webapp&specify_lang=en).
2. Sign in with your **Google**, **Apple**, or **Xiaomi** account.
3. Once logged in, you will land on the Watchface Maker page.
4. Press `F12` (Developer Tools) ➔ open the **Console** tab. *(If prompted, type `allow pasting` and press Enter)*.
5. Paste this command and hit Enter:
   ```javascript
   copy(document.cookie); console.log("%c COPIED TO CLIPBOARD! Press Ctrl+V in Home Assistant: ", "background: #22c55e; color: #fff; font-size: 14px; font-weight: bold; padding: 4px;"); console.log(document.cookie);
   ```
6. Return to Home Assistant and press `Ctrl + V` into the authorization field.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
