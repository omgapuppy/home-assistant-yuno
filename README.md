# Home Assistant Yuno Energy

`yuno_energy` is a personal Home Assistant custom integration for importing Yuno Energy Ireland electricity usage into Home Assistant.

It uses Yuno's undocumented private mobile-app API. The API can change without notice, and this project is not affiliated with or endorsed by Yuno Energy. Install it only if you are comfortable maintaining captured mobile-app header values for your own account.

## Features

- Config flow setup under Home Assistant settings.
- Polls `GET /api/bill/electricityUsage`.
- Imports hourly kWh usage into Home Assistant recorder statistics for Energy Dashboard use.
- Imports Yuno hourly euro cost as a companion Energy Dashboard cost statistic.
- Exposes regular sensors for latest usage date, latest read type, yesterday usage, yesterday cost, standing charge, returned day count, and data lag.
- Stores credentials and static headers in the Home Assistant config entry. They are not logged by the integration.

## Manual Installation

This repository is not packaged for HACS.

### From a Release Archive

#### Latest Release on Home Assistant OS

For Home Assistant OS or Supervised installs, use the **Terminal & SSH** add-on or a similar Home Assistant web terminal.

1. Open **Settings > Add-ons > Add-on Store**.
2. Install and start **Terminal & SSH** if it is not already installed.
3. Open the add-on web terminal.
4. Paste this command:

   ```bash
   mkdir -p /config && curl -fsSL https://github.com/omgapuppy/home-assistant-yuno/releases/latest/download/yuno_energy.tar.gz | tar -xz -C /config
   ```

5. Confirm the integration files are present:

   ```bash
   test -f /config/custom_components/yuno_energy/manifest.json && echo "Yuno Energy installed"
   ```

6. Restart Home Assistant from **Settings > System > Restart Home Assistant**.
7. Go to **Settings > Devices & services > Add integration** and search for **Yuno Energy**.

The latest-release URL always points at the newest GitHub release artifact named `yuno_energy.tar.gz`.

#### Specific Version

Replace `0.1.0` with the release version you want to install:

```bash
cd /config
curl -L https://github.com/omgapuppy/home-assistant-yuno/releases/download/0.1.0/yuno_energy-0.1.0.tar.gz \
  | tar -xz
```

The archive expands to `custom_components/yuno_energy`.

Zip archives are also attached to each release:

```bash
cd /config
curl -L -o yuno_energy.zip https://github.com/omgapuppy/home-assistant-yuno/releases/download/0.1.0/yuno_energy-0.1.0.zip
unzip -o yuno_energy.zip
rm yuno_energy.zip
```

### From a Local Checkout

1. Copy `custom_components/yuno_energy` into your Home Assistant config directory:

   ```text
   /config/custom_components/yuno_energy
   ```

2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**.
4. Search for **Yuno Energy**.
5. Enter the fields captured from your own Yuno mobile app traffic.

## Required Fields

The Yuno API uses static Basic client auth, static per-endpoint signatures, `X-Http-originid`, and an app-level session token returned by login.

Copy these fields from your own captures:

- From `POST /api/login` request body:
  - `email` value into **Encrypted email**
  - `password` value into **Encrypted password**
- From `POST /api/login` request headers:
  - `Authorization` into **Basic Authorization header**, or copy its Basic username/password into the separate fields
  - `X-Http-originid`, usually `64`
  - `X-Http-signature` into **Login X-Http-signature**
- From `GET /api/bill/electricityUsage` request headers:
  - `X-Http-signature` into **Electricity usage X-Http-signature**

Do not copy `X-Http-sessionToken` into setup. The integration obtains a fresh session token by logging in.

## Capturing Your Own Values

You need to capture traffic from your own iPhone and Yuno app using a TLS debugging proxy such as Proxyman, Charles, or mitmproxy.

Typical flow:

1. Install and trust the proxy certificate on your iPhone.
2. Configure the iPhone Wi-Fi HTTP proxy to point at your computer.
3. Open the Yuno app and sign in.
4. Locate the `POST /api/login` request and the `GET /api/bill/electricityUsage` request.
5. Copy only the fields listed above into Home Assistant.

Do not publish or share captures. They may contain real session tokens, encrypted credentials, account identifiers, contact details, MPRN/PAN/account IDs, and payment details. If interception stops working because the app changes its transport protections, do not patch the app, bypass certificate pinning, defeat attestation, or modify binaries for this integration.

## Energy Dashboard

The integration imports hourly usage from `hourlyUsageDetails` as Home Assistant external statistics. This is preferred over MQTT-style cumulative sensor updates because the API already returns historical hourly usage.

Yuno returns a 24-value array for each date in the observed API shape. The integration maps index `0..23` to local Europe/Dublin wall-clock hours for that date. On DST transition dates this preserves the app's indexing instead of inventing or dropping an hour, because the API does not expose a per-hour UTC offset. Normal 24-hour days are covered by tests.

The importer tracks timestamps already imported for the config entry to avoid repeated imports during polling. If Yuno revises already-imported historical values, the current version does not attempt recorder statistic adjustment beyond avoiding duplicate unchanged rows.

### Energy Statistics

The Energy Dashboard data is imported as recorder statistics, not as normal sensor entities:

| Statistic | Statistic ID pattern | Unit | Description |
| --- | --- | --- | --- |
| Yuno Energy electricity import | `custom_components:yuno_energy_<entry_id>_electricity_import` | kWh | Hourly grid-import consumption from `hourlyUsageInKwh`. |
| Yuno Energy electricity import cost | `custom_components:yuno_energy_<entry_id>_electricity_import_cost` | EUR | Hourly cost from `hourlyUsageInEuro + hourlyStandingChargeInEuro`. |

Use the electricity import statistic as **Grid consumption** in **Settings > Dashboards > Energy**. The cost statistic uses Home Assistant's conventional `_cost` suffix for the imported energy statistic so Energy can associate Yuno's supplied euro values with that grid consumption source.

This means Yuno can act as a whole-home electricity meter with backfilled hourly kWh and cost data. The cost statistic includes the hourly standing charge values returned by Yuno, so Energy Dashboard cost totals should be closer to Yuno's daily totals than a unit-rate-only calculation. Home Assistant does not show the standing charge as a separate Energy Dashboard cost component; use the normal standing charge sensor below for that breakdown.

### Exposed Sensors

These are normal Home Assistant sensor entities created by the integration. Entity IDs are assigned by Home Assistant from the entity names and can be renamed in the UI.

| Sensor name | Unique ID suffix | Unit | Device class | State class | Notes |
| --- | --- | --- | --- | --- | --- |
| Latest usage date | `latest_usage_date` | none | none | none | Latest date present in `hourlyUsageDetails`. |
| Latest read type | `latest_read_type` | none | none | none | Read type for the latest hourly day, for example `Actual`. |
| Yesterday usage | `yesterday_kwh` | kWh | energy | total | Latest daily kWh value from `dailyUsageDetails`. |
| Yesterday usage cost | `yesterday_usage_cost_eur` | EUR | monetary | total | Latest daily usage cost, excluding standing charge. |
| Yesterday standing charge | `yesterday_standing_charge_eur` | EUR | monetary | total | Latest daily standing charge. |
| Days returned | `days_returned` | none | none | measurement | Count of hourly days returned by the API. |
| Data freshness lag | `data_freshness_lag` | d | none | measurement | Difference between today and the latest Yuno usage date. |

### Coverage Compared With MQTT Accumulators

Compared with an MQTT accumulator such as `esbn-to-mqtt`, this integration does not need to synthesize a live monotonically increasing meter from each poll. Yuno returns historical hourly arrays, so the integration backfills Home Assistant recorder statistics directly.

Current coverage:

- Whole-home grid-import kWh: yes, via hourly external statistics.
- Historical backfill: yes, for the rolling date window returned by Yuno.
- Yuno-provided usage cost: yes, via a companion `_cost` external statistic.
- Yuno-provided standing charge: included in the imported Energy cost statistic and also exposed as a normal daily sensor.
- Export/feed-in: no; the captured Yuno electricity usage endpoint does not expose export arrays.
- Live power/current interval telemetry: no; Yuno provides historical hourly usage, not real-time W/kW.
- Revised historical values: not fully handled yet; duplicate timestamps are skipped, but already-imported values are not adjusted if Yuno later revises them.

## Troubleshooting

Login failures usually mean one of the encrypted credential values, Basic auth value, origin id, or login signature has changed. Capture a fresh login from your own app and update the integration entry.

Stale data normally means Yuno has not published newer smart-meter usage yet. Check the latest usage date and data freshness lag sensors.

Signature errors can happen if Yuno updates the mobile app or server-side validation. Capture fresh values from the current app version and update both signature fields.

If the Energy Dashboard does not show data, confirm the integration has completed at least one successful poll and that Home Assistant recorder is enabled.

## Development

Tests use sanitized fixtures and mocks. They must not call live Yuno endpoints.

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy custom_components tests
pytest
```
