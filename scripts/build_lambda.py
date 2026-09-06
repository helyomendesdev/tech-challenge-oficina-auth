from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build" / "lambda"
STAGING_DIR = BUILD_ROOT / "staging"
LOCK_PATH = ROOT / "requirements.lock"
DEFAULT_ZIP_PATH = BUILD_ROOT / "oficina_auth_lambda.zip"
FIXED_ZIP_TIMESTAMP = (2024, 1, 1, 0, 0, 0)
EXCLUDED_NAMES = {
    ".git",
    ".venv",
    ".env",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "bin",
    "tests",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = (".dist-info", ".data")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reproducible Lambda ZIP artifact.")
    parser.add_argument("--output", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--platform", default="manylinux2014_x86_64")
    parser.add_argument("--python-version", default="3.11")
    parser.add_argument("--abi", default="cp311")
    args = parser.parse_args()

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    _validate_runtime_lock()
    _prepare_build_dir()
    _install_runtime_dependencies(
        platform=args.platform,
        python_version=args.python_version,
        abi=args.abi,
    )
    _copy_application_code()
    _remove_forbidden_paths(STAGING_DIR)
    _create_reproducible_zip(output_path)
    checksum = _sha256(output_path)
    checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {output_path.name}\n", encoding="utf-8")

    print(f"artifact={output_path.relative_to(ROOT).as_posix()}")
    print(f"sha256={checksum}")
    return 0


def _prepare_build_dir() -> None:
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)


def _install_runtime_dependencies(platform: str, python_version: str, abi: str) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--no-cache-dir",
            "--no-deps",
            "--only-binary=:all:",
            "--require-hashes",
            "--platform",
            platform,
            "--implementation",
            "cp",
            "--python-version",
            python_version,
            "--abi",
            abi,
            "--target",
            str(STAGING_DIR),
            "--requirement",
            str(LOCK_PATH),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


def _validate_runtime_lock() -> None:
    if not LOCK_PATH.is_file():
        raise RuntimeError(f"Runtime dependency lock not found: {LOCK_PATH.name}")

    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    declared = {
        _normalize_package_name(_requirement_name(requirement))
        for requirement in pyproject["project"].get("dependencies", [])
    }
    direct = set()
    locked = set()
    for line in LOCK_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("# direct:"):
            direct.add(_normalize_package_name(stripped.removeprefix("# direct:").strip()))
            continue
        if not stripped or stripped.startswith("#") or stripped.startswith("--"):
            continue
        requirement = stripped.split("#", 1)[0].rstrip("\\ ")
        if "==" not in requirement:
            raise RuntimeError("Runtime dependency lock contains an unpinned requirement")
        locked.add(_normalize_package_name(_requirement_name(requirement)))

    if direct != declared:
        missing = ", ".join(sorted(declared - direct)) or "none"
        stale = ", ".join(sorted(direct - declared)) or "none"
        raise RuntimeError(
            f"Runtime dependency lock is stale (missing direct: {missing}; stale direct: {stale})"
        )
    if not direct <= locked:
        missing = ", ".join(sorted(direct - locked))
        raise RuntimeError(f"Runtime dependency lock marks missing packages: {missing}")


def _requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", requirement)
    if not match:
        raise RuntimeError("Could not parse a runtime dependency name")
    return match.group(1)


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _copy_application_code() -> None:
    shutil.copytree(ROOT / "src" / "oficina_auth", STAGING_DIR / "oficina_auth")


def _remove_forbidden_paths(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.name in EXCLUDED_NAMES or path.name.endswith(EXCLUDED_SUFFIXES):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def _create_reproducible_zip(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    files = sorted(path for path in STAGING_DIR.rglob("*") if path.is_file())
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in files:
            relative_path = path.relative_to(STAGING_DIR).as_posix()
            info = zipfile.ZipInfo(relative_path, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
