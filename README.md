# Home Assistant Yuno Energy

Sign in with your Yuno Energy email and password to import electricity usage and
costs into Home Assistant. No proxy, phone capture, or copied headers are needed.

This custom integration imports Energy Dashboard statistics and sensors using
Yuno's undocumented mobile API. It supports account login, automatic session
renewal, and manual setup. It is not a Supervisor add-on and is not affiliated
with Yuno Energy.

## Install and sign in

1. Download this repository using **Code → Download ZIP**.
2. Copy `custom_components/yuno_energy` into Home Assistant's
   `/config/custom_components/` directory, replacing that directory if upgrading.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Yuno Energy**.
5. Choose **Sign in with email and password**, enter your Yuno credentials, and
   submit. The default polling interval is six hours; the minimum is 30 minutes.

The integration checks login and electricity usage access before saving the entry.
It saves reusable encrypted app credentials and the session token, without
retaining the plain password. These values still grant account access: protect
Home Assistant's configuration and backups. Sessions are reused across polls and
restarts. An expired session triggers at most one login and one retry of the usage
request. Rejected login credentials prompt reauthentication; network failures and
server errors do not trigger extra login attempts.

### Existing installations

Replace the integration files and restart Home Assistant. Existing entries using
captured tokens or replay-login values continue to work.

To switch an existing entry to email/password login, use its **Reconfigure** menu
and choose **Sign in with email and password**. This updates the same config entry,
so its statistics and entity IDs are retained. Polling options are also retained;
change them using **Configure** if needed. Do not create a second entry or delete
your existing entry to change credentials.

## Helper for manual setup

For manual setup or an older installation, run this helper from a checkout
using Python 3.12 or newer. It uses only the standard library:

```sh
python3 scripts/yuno_setup.py --output yuno-setup.json
```

Enter your email and password at the prompts. Password input is hidden. By
default, the helper computes the six setup fields **offline**; it makes no Yuno
requests. It uses the same encryption and signing code as the integration.

To also obtain a session token with one login request:

```sh
python3 scripts/yuno_setup.py --login --output yuno-setup.json
```

Use a new output filename each time; existing files are never overwritten. Files
are created with owner-only permissions. Omitting `--output` prints the fields to
standard output. The `YUNO_EMAIL` and `YUNO_PASSWORD` environment variables can be
used for noninteractive runs. Do not publish the output or include it in logs.

Copy the resulting JSON values into the original integration's setup fields:

| JSON key | Home Assistant field |
| --- | --- |
| `encrypted_email` | Encrypted email |
| `encrypted_password` | Encrypted password |
| `basic_authorization` | Basic Authorization header |
| `origin_id` | X-Http-originid |
| `login_signature` | Login X-Http-signature |
| `usage_signature` | Electricity usage X-Http-signature |
| `session_token` (with `--login`) | X-Http-sessionToken |

Leave Basic username/password blank when providing the full Basic Authorization
header. These generated values use Android origin `63` regardless of which phone
you use. The account is the same across platforms. The helper's login signature
covers the JSON formatting used by the original integration.

The helper only outputs configuration values. The Home Assistant flow
also checks electricity usage access before it saves an entry.

## Energy Dashboard

The integration imports hourly usage from `hourlyUsageDetails` as Home Assistant external statistics. This is preferred over MQTT-style cumulative sensor updates because the API already returns historical hourly usage.

Yuno returns a 24-value array for each date in the observed API shape. The integration maps index `0..23` to local Europe/Dublin wall-clock hours for that date. On DST transition dates this preserves the app's indexing instead of inventing or dropping an hour, because the API does not expose a per-hour UTC offset. Normal 24-hour days are covered by tests.

The importer tracks timestamps already imported for the config entry to avoid repeated imports during polling. If Yuno revises already-imported historical values, the current version does not attempt recorder statistic adjustment beyond avoiding duplicate unchanged rows.

### Energy Statistics

The Energy Dashboard data is imported as recorder statistics, not as normal sensor entities:

| Statistic | Statistic ID pattern | Unit | Description |
| --- | --- | --- | --- |
| Yuno Energy electricity import | `yuno_energy:<entry_id>_electricity_import` | kWh | Hourly grid-import consumption from `hourlyUsageInKwh`. |
| Yuno Energy electricity import cost | `yuno_energy:<entry_id>_electricity_import_cost` | EUR | Hourly cost from `hourlyUsageInEuro + hourlyStandingChargeInEuro`. |

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

- **Login rejected:** verify the same credentials in the official Yuno app, then
  use Home Assistant's reauthentication form. Do not repeatedly resubmit a failing
  password. The integration treats Yuno error 1004 as rejected credentials.
- **Network or server error:** the integration will retry its normal poll later;
  these failures do not cause an additional login.
- **Unexpected response:** Yuno may have changed its undocumented API. Check for
  an updated version of the integration. Do not attach raw responses or setup values to
  public issues.
- **Existing manual setup has expired:** use Reconfigure to switch to account
  login, or generate fresh values with the helper.
- **Stale usage:** Yuno may not yet have published new smart-meter readings. Check
  the latest usage date and data freshness lag sensors.

## Development

```sh
python -m pip install -e ".[dev]"
ruff check .
mypy custom_components tests scripts
pytest
```

Tests use synthetic encryption vectors and mocked API responses, and must not
call live Yuno endpoints. They cover the Home Assistant forms, session renewal
and persistence, error handling, and the standalone helper. See
[authentication notes](docs/authentication.md) for the protocol and its validation.

Build an installable integration ZIP and a single-file helper:

```sh
python3 scripts/build_artifacts.py
python3 dist/yuno-setup.pyz --help
```

The ZIP expands to `custom_components/yuno_energy/`. The `.pyz` helper can be copied
and run on its own with Python 3.12+, without installing Home Assistant.
