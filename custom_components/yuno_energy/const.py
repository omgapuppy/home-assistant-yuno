"""Constants for the Yuno Energy integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "yuno_energy"
PLATFORMS = ["sensor"]

DEFAULT_BASE_URL = "https://appbillpay.yunoenergy.ie:2015"
DEFAULT_ORIGIN_ID = "64"
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)
MIN_SCAN_INTERVAL_MINUTES = 30

CONF_ENCRYPTED_EMAIL = "encrypted_email"
CONF_ENCRYPTED_PASSWORD = "encrypted_password"
CONF_BASIC_AUTHORIZATION = "basic_authorization"
CONF_BASIC_USERNAME = "basic_username"
CONF_BASIC_PASSWORD = "basic_password"
CONF_ORIGIN_ID = "origin_id"
CONF_LOGIN_SIGNATURE = "login_signature"
CONF_USAGE_SIGNATURE = "usage_signature"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
