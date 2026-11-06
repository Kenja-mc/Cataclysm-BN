#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    base = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="bn-mod-validation-") as temporary:
        root = Path(temporary)
        data = root / "data"
        data.mkdir()
        for source in (base / "data").iterdir():
            if source.name != "mods":
                (data / source.name).symlink_to(
                    source, target_is_directory=source.is_dir()
                )
        mods = data / "mods"
        mods.mkdir()
        for source in (base / "data/mods").iterdir():
            (mods / source.name).symlink_to(source, target_is_directory=source.is_dir())
        fixture = mods / "release_validation_fixture"
        fixture.mkdir()
        (fixture / "modinfo.json").write_text(
            json.dumps(
                [
                    {
                        "type": "MOD_INFO",
                        "id": "release_validation_fixture",
                        "name": "Release validation fixture",
                        "description": "Data gate regression",
                        "category": "misc_additions",
                        "dependencies": ["bn"],
                    }
                ]
            )
        )
        command = [
            str(binary),
            "--basepath",
            str(base) + "/",
            "--datadir",
            str(data) + "/",
            "--userdir",
            str(root / "user") + "/",
            "--check-mods",
            "release_validation_fixture",
        ]
        content = fixture / "content.json"
        content.write_text("[]\n")
        valid = subprocess.run(
            command, text=True, capture_output=True, timeout=180, check=False
        )
        if valid.returncode != 0:
            raise RuntimeError("Valid data failed:\n" + valid.stdout + valid.stderr)
        content.write_text(
            '[{"type":"GENERIC","id":"release_invalid_item","name":42}]\n'
        )
        invalid = subprocess.run(
            command, text=True, capture_output=True, timeout=180, check=False
        )
        if invalid.returncode == 0 or "Error loading data:" not in invalid.stderr:
            raise RuntimeError(
                f"Invalid data returned {invalid.returncode}:\n"
                + invalid.stdout
                + invalid.stderr
            )
        print(
            f"PASS: valid mod exits {valid.returncode}; invalid JSON content exits {invalid.returncode}."
        )


if __name__ == "__main__":
    main()
