#!/usr/bin/env python3
"""Build an integration ZIP and a standalone setup helper from shared sources."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipapp
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = Path("custom_components/yuno_energy")


def build(output_dir: Path) -> tuple[Path, Path]:
    """Package only integration source files; never include local setup outputs."""
    version = json.loads((ROOT / COMPONENT / "manifest.json").read_text())["version"]
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"yuno_energy-{version}.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as handle:
        handle.write(ROOT / "LICENSE", COMPONENT / "LICENSE")
        for source in sorted((ROOT / COMPONENT).rglob("*")):
            if source.is_file() and source.suffix in {".py", ".json"}:
                handle.write(source, source.relative_to(ROOT))
    helper = output_dir / "yuno-setup.pyz"
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        (staging / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
        # Use the same auth implementation, not a separately maintained copy.
        (staging / "__main__.py").write_bytes((ROOT / "scripts/yuno_setup.py").read_bytes())
        for relative in [
            Path("custom_components/__init__.py"),
            COMPONENT / "__init__.py",
            COMPONENT / "const.py",
            COMPONENT / "yuno_api/__init__.py",
            COMPONENT / "yuno_api/auth.py",
            COMPONENT / "yuno_api/client.py",
            COMPONENT / "yuno_api/models.py",
        ]:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        zipapp.create_archive(staging, helper, interpreter="/usr/bin/env python3", compressed=True)
    return archive, helper


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    for artifact in build(parser.parse_args().output_dir):
        print(artifact)
