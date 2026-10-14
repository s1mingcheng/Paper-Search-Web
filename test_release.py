"""验证私有文件排除、模板密钥留空与归档校验清单。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.package_release import ROOT_FILES, build_release, validate_source_files


class ReleaseTests(unittest.TestCase):
    def test_private_files_stay_outside_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ROOT_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("DEEPSEEK_API_KEY=\n" if name == ".env.example" else "example\n", encoding="utf-8")
            for name in (".env", "data/deepseek_config.json", "data/translation_cache.json", "data/journal_metrics.csv", "server.log", ".venv/private.txt"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("PRIVATE_SENTINEL", encoding="utf-8")
            directory, archive = build_release(root / "release" / "paper-search-web", root)
            manifest = json.loads((directory / "release-manifest.json").read_text(encoding="utf-8"))
            with ZipFile(archive) as bundle:
                names = set(bundle.namelist())
                self.assertEqual(names, {"paper-search-web/" + name for name in ROOT_FILES} | {"paper-search-web/release-manifest.json"})
                self.assertFalse(any(b"PRIVATE_SENTINEL" in bundle.read(name) for name in names))
                for item in manifest["files"]:
                    self.assertEqual(hashlib.sha256(bundle.read("paper-search-web/" + item["path"])).hexdigest(), item["sha256"])
            with self.assertRaises(ValueError):
                build_release(directory, root)

    def test_example_must_not_contain_a_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            example = root / ".env.example"
            example.write_text("DEEPSEEK_API_KEY=not-an-empty-template\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "密钥字段必须留空"):
                validate_source_files([example], root)


if __name__ == "__main__":
    unittest.main()
