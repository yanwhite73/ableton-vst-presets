#!/usr/bin/env python3
"""Build and audit a deterministic, machine-neutral public source package.

The package is assembled from an explicit source allowlist rather than by recursively zipping the
checkout. Local configuration, generated Racks, diagnostics, virtual environments, and unrelated
monorepo files therefore cannot enter it. The resulting ZIP contains its own SHA-256 manifest.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PREFIX = PurePosixPath("rack-preset-kit")
ROOT_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "requirements.txt",
)
SOURCE_DIRS = (".github/workflows", "bin", "docs", "rackkit", "skeletons", "tests", "tools")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "venv",
    "out",
    "test",
    "racks",
    "build",
    "dist",
    "output",
    "diagnostics",
}
FORBIDDEN_NAMES = {".DS_Store", ".env", ".rackkit.local.json"}
FORBIDDEN_ARCHIVE_SUFFIXES = {".7z", ".rar", ".tar", ".tgz", ".zip"}
PRIVATE_MARKERS = (
    b"/" + b"Users/",
    b"/" + b"home/",
    b"/private/" + b"var/folders/",
    b"Documents/" + b"Music docs/Code",
    b"C:" + b"\\Users\\",
    b"C:/" + b"Users/",
    b"BEGIN " + b"OPENSSH PRIVATE KEY",
    b"BEGIN " + b"PRIVATE KEY",
    b"BEGIN " + b"RSA PRIVATE KEY",
    b"BEGIN " + b"EC PRIVATE KEY",
    b"BEGIN " + b"PGP PRIVATE KEY",
)
SECRET_PATTERNS = (
    re.compile(rb"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bsk_live_[A-Za-z0-9]{16,}\b"),
    re.compile(rb"\bsk-(?:proj|svcacct)-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
)
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
MANIFEST_NAME = "PACKAGE-MANIFEST.sha256"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files(root: Path = PROJECT_ROOT) -> list[tuple[PurePosixPath, bytes]]:
    """Return the explicit, audited public source payload."""
    paths: list[Path] = []
    for name in ROOT_FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"Required public source file is missing: {path}")
        paths.append(path)
    for dirname in SOURCE_DIRS:
        directory = root / dirname
        if not directory.is_dir():
            raise ValueError(f"Required public source directory is missing: {directory}")
        for path in directory.rglob("*"):
            rel = path.relative_to(root)
            if any(part in SKIP_PARTS for part in rel.parts) or path.suffix in SKIP_SUFFIXES:
                continue
            if path.is_symlink():
                raise ValueError(f"Symlinks are not allowed in the public package: {rel}")
            if path.is_file():
                paths.append(path)

    payload = []
    for path in sorted(set(paths), key=lambda item: item.relative_to(root).as_posix()):
        rel = PurePosixPath(path.relative_to(root).as_posix())
        _audit_path(rel)
        data = path.read_bytes()
        _audit_content(rel, data)
        payload.append((rel, data))
    return payload


def _audit_path(rel: PurePosixPath) -> None:
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError(f"Unsafe package path: {rel}")
    if any(part in FORBIDDEN_PARTS for part in rel.parts):
        raise ValueError(f"Generated or local directory is forbidden in the package: {rel}")
    name = rel.name
    if (
        name in FORBIDDEN_NAMES
        or (name.startswith(".env.") and name != ".env.example")
        or name.startswith(".rackkit.local.")
        or name.endswith(".local.json")
    ):
        raise ValueError(f"Machine-local file is forbidden in the package: {rel}")
    if rel.suffix.lower() in FORBIDDEN_ARCHIVE_SUFFIXES:
        raise ValueError(f"Nested archive is forbidden in the package: {rel}")


def _audit_content(rel: PurePosixPath, data: bytes) -> None:
    for marker in PRIVATE_MARKERS:
        if marker in data:
            raise ValueError(f"Machine-specific/private path marker in {rel}: {marker!r}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(data):
            raise ValueError(f"Credential-like content in {rel}: {pattern.pattern!r}")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def write_package(output: Path, payload: list[tuple[PurePosixPath, bytes]]) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = "".join(f"{digest(data)}  {rel.as_posix()}\n" for rel, data in payload).encode()
    members = list(payload) + [(PurePosixPath(MANIFEST_NAME), manifest)]
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel, data in sorted(members, key=lambda item: item[0].as_posix()):
            archive.writestr(_zip_info((ARCHIVE_PREFIX / rel).as_posix()), data)
    audit_package(output)
    return digest(output.read_bytes())


def audit_package(package: Path) -> None:
    """Reject unsafe names/content and verify the embedded file manifest."""
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if names != sorted(names):
            raise ValueError("Package members are not sorted deterministically")
        if len(names) != len(set(names)):
            raise ValueError("Package contains duplicate member names")

        actual: dict[str, str] = {}
        manifest_member = (ARCHIVE_PREFIX / MANIFEST_NAME).as_posix()
        for info in infos:
            path = PurePosixPath(info.filename)
            if not path.parts or path.parts[0] != ARCHIVE_PREFIX.name:
                raise ValueError(f"Package member is outside {ARCHIVE_PREFIX}/: {path}")
            rel = PurePosixPath(*path.parts[1:])
            if rel.as_posix() == MANIFEST_NAME:
                continue
            _audit_path(rel)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"Symlink is forbidden in package: {rel}")
            data = archive.read(info)
            _audit_content(rel, data)
            actual[rel.as_posix()] = digest(data)

        if manifest_member not in names:
            raise ValueError("Package SHA-256 manifest is missing")
        expected = {}
        for line in archive.read(manifest_member).decode("utf-8").splitlines():
            checksum, rel = line.split("  ", 1)
            expected[rel] = checksum
        if expected != actual:
            raise ValueError("Package SHA-256 manifest does not match its members")


def run_tests() -> None:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "dist/rack-preset-kit.zip")
    parser.add_argument("--check-only", action="store_true", help="Audit a temporary ZIP; keep no artifact")
    parser.add_argument("--skip-tests", action="store_true", help="Package only (not for release qualification)")
    args = parser.parse_args()

    if not args.skip_tests:
        run_tests()
    payload = source_files()
    if args.check_only:
        with tempfile.TemporaryDirectory(prefix="rackkit-package-") as temp:
            output = Path(temp) / "rack-preset-kit.zip"
            checksum = write_package(output, payload)
            print(f"Public package audit passed: {len(payload)} source files; SHA-256 {checksum}")
        return

    output = args.output.resolve()
    checksum = write_package(output, payload)
    print(f"Built {output} ({len(payload)} source files + manifest)")
    print(f"SHA-256 {checksum}")


if __name__ == "__main__":
    main()
