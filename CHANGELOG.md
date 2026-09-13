# Changelog

## Unreleased

- Add email/password setup using the verified Android login format, with no proxy capture.
- Save encrypted app credentials and session tokens without retaining the plain password.
- Renew expired sessions once and persist replacements across polls and restarts.
- Add reauthentication and migration from manual setup while preserving config entry IDs.
- Keep existing captured-token and replay-login configurations supported.
- Add a standard-library setup helper for the original integration, with optional single login.
- Add offline encryption, HTTP serialization, config-flow and session lifecycle tests.

## 0.1.6

- Group Yuno sensor entities under a Home Assistant device for the config entry.

## 0.1.5

- Use Home Assistant-valid external statistic IDs for recorder imports.
- Align recorder statistic metadata source with the `yuno_energy` statistic ID domain.

## 0.1.4

- Accept Yuno date fields returned as ISO datetimes such as `2026-05-27T00:00:00`.

## 0.1.3

- Surface sanitized config-flow failure details in the Home Assistant UI and logs.
- Include safe Yuno API error metadata such as HTTP status, title, and error code.
- Improve config-flow error classification for usage response parse failures.

## 0.1.2

- Add session-token setup and polling support for long-lived Yuno app sessions.
- Improve config-flow login validation errors without logging secrets.
- Clarify capture header-to-field mapping in setup docs.

## 0.1.1

- Import Yuno hourly euro costs as a companion Energy Dashboard cost statistic.
- Document exposed sensors, external statistics, and Energy Dashboard coverage.

## 0.1.0

- Initial manual Home Assistant custom integration for Yuno Energy Ireland.
- Added config flow, polling coordinator, sensors, API client boundary, sanitized tests, recorder statistics import helper, CI, and release workflow.
