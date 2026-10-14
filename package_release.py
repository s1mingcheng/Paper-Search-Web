"""按允许清单生成 GitHub 上传目录与 ZIP，不读取本机密钥、缓存或日志。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    ".env.example", ".gitattributes", ".gitignore", "README.md",
    "requirements.txt", "start.ps1", "app.py", "deepseek.py", "translator.py",
    "data/zh_en_terms.csv", "data/journal_metrics.example.csv",
)
SOURCE_FOLDERS = {
    "static": {".html", ".css", ".js", ".svg", ".png", ".jpg", ".webp", ".ico", ".woff2"},
    "docs": {".md"}, "tests": {".py"}, "scripts": {".py"},
    ".github": {".yml", ".yaml", ".md"},
}
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def collect_source_files(root: Path = PROJECT_ROOT) -> list[Path]:
    root = root.resolve()
    files = [root / name for name in ROOT_FILES]
    missing = [path.relative_to(root).as_posix() for path in files if not path.is_file()]
    if missing:
        raise ValueError("缺少发布文件：" + ", ".join(missing))
    for folder, suffixes in SOURCE_FOLDERS.items():
        if (root / folder).exists():
            files.extend(path for path in (root / folder).rglob("*")
                         if path.is_file() and path.suffix.lower() in suffixes
                         and "__pycache__" not in path.parts)
    if (root / "LICENSE").is_file():
        files.append(root / "LICENSE")
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("发布清单包含链接或项目目录之外的文件。")
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def validate_source_files(files: list[Path], root: Path = PROJECT_ROOT) -> None:
    """仅检查将上传的文本，不读取私有文件，也不输出匹配值。"""
    for path in files:
        if path.suffix.lower() in {".png", ".jpg", ".webp", ".ico", ".woff2"}:
            continue
        text = path.read_text(encoding="utf-8-sig")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError(f"发现疑似密钥，请先清理发布文件：{path.relative_to(root).as_posix()}")
        if path.name == ".env.example":
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, value = line.split("=", 1)
                if key.strip().endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")) and value.strip():
                    raise ValueError(".env.example 的密钥字段必须留空。")


def build_release(destination: Path, root: Path = PROJECT_ROOT) -> tuple[Path, Path]:
    root = root.resolve()
    destination = destination.resolve()
    archive = destination.with_name(destination.name + ".zip")
    if destination == root or destination in root.parents:
        raise ValueError("发布目录不能是项目根目录或其父目录。")
    if destination.exists() or archive.exists():
        raise ValueError("输出目录或 ZIP 已存在，请使用 --destination 指定新的目录名。")
    files = collect_source_files(root)
    validate_source_files(files, root)
    destination.mkdir(parents=True)
    manifest = {"project": "paper-search-web", "files": []}
    for path in files:
        relative = path.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        manifest["files"].append({"path": relative.as_posix(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    (destination / "release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as bundle:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                bundle.write(path, (Path(destination.name) / path.relative_to(destination)).as_posix())
    return destination, archive


def main() -> None:
    parser = argparse.ArgumentParser(description="生成不含本机配置、缓存与日志的 GitHub 上传目录和 ZIP。")
    parser.add_argument("--destination", type=Path, default=PROJECT_ROOT / "release" / "paper-search-web", help="输出目录；须为尚不存在的目录。")
    args = parser.parse_args()
    try:
        directory, archive = build_release(args.destination)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"打包失败：{exc}\n")
    print(f"上传目录：{directory}\nZIP：{archive}")


if __name__ == "__main__":
    main()
