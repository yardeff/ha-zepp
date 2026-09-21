# Zepp for Home Assistant

Custom integration for Home Assistant connecting Zepp (Amazfit) devices.

Compatible with any device connected through the official **Zepp** app (not Zepp Life / Mi Fitness).

---

## Installation

### HACS
1. Add custom repository: `https://github.com/yarchefis/ha-zepp` (Category: **Integration**).
2. Download **Zepp** and restart Home Assistant.

### Manual
Copy `custom_components/zepp` into your `<config>/custom_components/` directory and restart Home Assistant.

---

## Configuration

Add integration via **Settings -> Devices & Services -> Add Integration -> Zepp**.
Follow the step-by-step instructions shown directly in the setup dialog.

---

## Historical Data Sync (LTS)

Upon setup, the integration backfills recent history into Home Assistant Long-Term Statistics.

To sync a custom period (e.g. 30 days, 1 year, or 5 years), run the service / action:

- **Service**: `zepp.sync_history`
- **Parameter**: `days` (number of days in the past to fetch, e.g. `30`, `365`, `1825`)

---

## Internal Architecture

- **Polling interval:** 15 minutes.
- **Session handling:** Uses web API tokens so the mobile Zepp app remains active and does not log out.
- **Authentication refresh:**
  - Password logins auto-refresh when tokens expire.
  - Social logins (Google / Apple / Mi) support native re-authentication flow when expired.
- **Sensors provided:** Steps, Distance, Calories, Heart Rate, Resting HR, Sleep (score, stages, duration), SpO2, Stress, PAI, Training Load, Weight, Battery.

---

## License

MIT License (c) 2026 yardev

