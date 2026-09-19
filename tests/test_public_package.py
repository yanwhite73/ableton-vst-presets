from __future__ import annotations

from pathlib import Path, PurePosixPath
import tempfile
import unittest
import zipfile

from tools import build_public_package as package


class PublicPackage(unittest.TestCase):
    def test_source_payload_is_machine_neutral(self):
        payload = package.source_files()
        names = {rel.as_posix() for rel, _ in payload}
        self.assertIn("README.md", names)
        self.assertIn(".github/workflows/public-package.yml", names)
        self.assertIn("tools/build_public_package.py", names)
        self.assertFalse(any("local" in PurePosixPath(name).name for name in names))
        self.assertFalse(any(set(PurePosixPath(name).parts) & package.FORBIDDEN_PARTS for name in names))

    def test_two_packages_are_byte_identical_and_manifested(self):
        payload = package.source_files()
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.zip"
            second = Path(temp) / "second.zip"
            self.assertEqual(package.write_package(first, payload), package.write_package(second, payload))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIn("rack-preset-kit/PACKAGE-MANIFEST.sha256", archive.namelist())

    def test_private_absolute_path_is_rejected(self):
        marker = b"/" + b"Users/example/private"
        with self.assertRaisesRegex(ValueError, "private path marker"):
            package._audit_content(PurePosixPath("bad.txt"), marker)

    def test_generated_and_local_paths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Generated or local directory"):
            package._audit_path(PurePosixPath("output/private.json"))
        with self.assertRaisesRegex(ValueError, "Machine-local file"):
            package._audit_path(PurePosixPath("preferences.local.json"))
        with self.assertRaisesRegex(ValueError, "Machine-local file"):
            package._audit_path(PurePosixPath("docs/.env.production"))
        with self.assertRaisesRegex(ValueError, "Machine-local file"):
            package._audit_path(PurePosixPath("docs/.DS_Store"))
        with self.assertRaisesRegex(ValueError, "Nested archive"):
            package._audit_path(PurePosixPath("tools/old-release.zip"))

    def test_credential_like_content_is_rejected(self):
        fake = b"ghp_" + (b"A" * 24)
        with self.assertRaisesRegex(ValueError, "Credential-like content"):
            package._audit_content(PurePosixPath("bad.txt"), fake)
        fake_aws = b"AKIA" + (b"A" * 16)
        with self.assertRaisesRegex(ValueError, "Credential-like content"):
            package._audit_content(PurePosixPath("bad.txt"), fake_aws)

    def test_linux_and_windows_home_paths_are_rejected(self):
        values = (b"/" + b"home/example/private", b"C:/" + b"Users/example/private")
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "private path marker"):
                package._audit_content(PurePosixPath("bad.txt"), value)


if __name__ == "__main__":
    unittest.main()
