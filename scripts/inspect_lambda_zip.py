from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP_PATH = ROOT / "build" / "lambda" / "oficina_auth_lambda.zip"
FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "dist",
    "tests",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".crt", ".env", ".pyc", ".pyo", ".pyd"}
FORBIDDEN_NAME_SUFFIXES = (".dist-info", ".data")
REQUIRED_ENTRIES = {
    "oficina_auth/handlers/auth.py",
    "oficina_auth/application/authenticate_client.py",
    "oficina_auth/infrastructure/jwt_tokens.py",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Lambda ZIP for forbidden local files.")
    parser.add_argument("artifact", nargs="?", type=Path, default=DEFAULT_ZIP_PATH)
    args = parser.parse_args()
    artifact = args.artifact if args.artifact.is_absolute() else ROOT / args.artifact

    failures = inspect_zip(artifact)
    if failures:
        for failure in failures:
            print(f"zip_inspection_error={failure}")
        return 1

    print(f"zip_inspection=ok entries={len(_zip_entries(artifact))}")
    return 0


def inspect_zip(artifact: Path) -> list[str]:
    if not artifact.is_file():
        return [f"artifact not found: {artifact}"]

    entries = _zip_entries(artifact)
    failures: list[str] = []
    missing = sorted(REQUIRED_ENTRIES.difference(entries))
    if missing:
        failures.append(f"missing required entries: {', '.join(missing)}")

    for entry in entries:
        parts = set(Path(entry).parts)
        suffix = Path(entry).suffix.lower()
        if parts.intersection(FORBIDDEN_PARTS):
            failures.append(f"forbidden path in artifact: {entry}")
        if suffix in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden file suffix in artifact: {entry}")
        if any(part.endswith(FORBIDDEN_NAME_SUFFIXES) for part in parts):
            failures.append(f"forbidden metadata directory in artifact: {entry}")

    return failures


def _zip_entries(artifact: Path) -> set[str]:
    try:
        with zipfile.ZipFile(artifact) as archive:
            return {info.filename for info in archive.infolist() if not info.is_dir()}
    except zipfile.BadZipFile:
        print("zip_inspection_error=invalid zip file", file=sys.stderr)
        return set()


if __name__ == "__main__":
    raise SystemExit(main())
