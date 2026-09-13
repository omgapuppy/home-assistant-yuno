from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from custom_components.yuno_energy.yuno_api.auth import AuthConfig
from scripts import yuno_setup


def test_helper_generates_upstream_fields_with_only_standard_library(tmp_path: Path) -> None:
    output = tmp_path / "setup.json"
    result = subprocess.run(
        [sys.executable, "-S", "scripts/yuno_setup.py", "--output", str(output)],
        env={**os.environ, "YUNO_EMAIL": "offline@example.invalid", "YUNO_PASSWORD": " synthetic "},
        capture_output=True,
        text=True,
        check=True,
    )
    values = json.loads(output.read_text())
    assert (
        values
        == AuthConfig.from_account_credentials(
            "offline@example.invalid", " synthetic "
        ).setup_values()
    )
    assert " synthetic " not in output.read_text()
    assert "password" not in values
    assert "session_token" not in values
    assert result.stdout == ""
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_helper_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "setup.json"
    output.write_text("keep this")
    result = subprocess.run(
        [sys.executable, "-S", "scripts/yuno_setup.py", "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert output.read_text() == "keep this"


def test_optional_login_adds_token_once(tmp_path: Path) -> None:
    output = tmp_path / "setup.json"
    with (
        patch("sys.argv", ["yuno_setup.py", "--login", "--output", str(output)]),
        patch.dict(
            os.environ, {"YUNO_EMAIL": "offline@example.invalid", "YUNO_PASSWORD": "synthetic"}
        ),
        patch.object(yuno_setup, "fetch_session_token", return_value="fixture-token") as login,
    ):
        assert yuno_setup.main() == 0
    login.assert_called_once()
    assert json.loads(output.read_text())["session_token"] == "fixture-token"


def test_packaged_helper_runs_on_its_own(tmp_path: Path) -> None:
    from zipfile import ZipFile

    from scripts.build_artifacts import build

    archive, helper = build(tmp_path)
    with ZipFile(archive) as package:
        names = package.namelist()
    assert "custom_components/yuno_energy/yuno_api/auth.py" in names
    assert "custom_components/yuno_energy/translations/en.json" in names
    assert all(name.startswith("custom_components/yuno_energy/") for name in names)
    result = subprocess.run(
        [sys.executable, "-S", str(helper)],
        cwd=tmp_path,
        env={**os.environ, "YUNO_EMAIL": "offline@example.invalid", "YUNO_PASSWORD": "synthetic"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert (
        json.loads(result.stdout)
        == AuthConfig.from_account_credentials(
            "offline@example.invalid",
            "synthetic",
        ).setup_values()
    )
