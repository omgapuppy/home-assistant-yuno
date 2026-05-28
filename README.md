# Home Assistant Yuno Energy

`yuno_energy` is a personal Home Assistant custom integration for importing Yuno Energy Ireland electricity usage into Home Assistant.

It uses Yuno's undocumented private mobile-app API. The API can change without notice, and this project is not affiliated with or endorsed by Yuno Energy. Install it only if you are comfortable maintaining captured mobile-app header values for your own account.

## Features

- Config flow setup under Home Assistant settings.
- Polls `GET /api/bill/electricityUsage`.
- Imports hourly kWh usage into Home Assistant recorder statistics for Energy Dashboard use.
- Exposes regular sensors for latest usage date, latest read type, yesterday usage, yesterday cost, standing charge, returned day count, and data lag.
- Stores credentials and static headers in the Home Assistant config entry. They are not logged by the integration.

## Manual Installation

This repository is not packaged for HACS.

### From a Release Archive

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
