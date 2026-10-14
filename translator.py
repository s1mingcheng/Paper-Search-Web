"""Bilingual keyword expansion for academic search.

Chinese keywords are expanded to English with:
1. a local academic term/synonym dictionary, and
2. an optional public MyMemory translation request.

The original Chinese term is always retained. Every English translation and
dictionary synonym is added to the same concept group, so adapters can search
for any variant of a concept while preserving AND/OR between concepts.
"""

from __future__ import annotations

import csv
import json
import os
import re
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

CJK_RE = re.compile(r"[\u3400-\u9fff]")
TRANSLATION_CACHE_LOCK = threading.RLock()


def clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", unescape(str(value or "")))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_term(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).casefold()


def has_chinese(value: Any) -> bool:
    return bool(CJK_RE.search(clean_text(value)))


def split_bilingual_values(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [clean_text(part) for part in re.split(r"[|;；]+", text) if clean_text(part)]


def add_variants(target: list[str], values: Any) -> None:
    if isinstance(values, str):
        values = [values]
    seen = {normalize_term(item) for item in target}
    for value in values or []:
        text = clean_text(value)
        key = normalize_term(text)
        if text and key and key not in seen and len(text) <= 180:
            target.append(text)
            seen.add(key)


class TranslationService:
    def __init__(self, dictionary_path: Path, cache_path: Path) -> None:
        self.dictionary_path = dictionary_path
        self.cache_path = cache_path
        self.provider = os.environ.get("TRANSLATION_PROVIDER", "auto").strip().lower() or "auto"
        self.email = os.environ.get("MYMEMORY_EMAIL", "")
        self.dictionary = self._load_dictionary()
        self.cache = self._load_cache()

    def _load_dictionary(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        if not self.dictionary_path.exists():
            return result
        try:
            with self.dictionary_path.open("r", encoding="utf-8-sig", newline="") as handle:
                lines = [line for line in handle if not line.lstrip().startswith("#")]
            reader = csv.DictReader(lines)
            for row in reader:
                zh = clean_text(row.get("zh") or row.get("chinese") or "")
                if not zh:
                    continue
                values: list[str] = []
                add_variants(values, split_bilingual_values(row.get("en") or row.get("english") or ""))
                add_variants(values, split_bilingual_values(row.get("synonyms") or ""))
                if values:
                    result[normalize_term(zh)] = values
        except Exception as exc:
            print(f"[warn] Could not read translation dictionary: {exc}")
        return result

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if not self.cache_path.exists():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[warn] Could not save translation cache: {exc}")

    def _local_variants(self, keyword: str) -> list[str]:
        key = normalize_term(keyword)
        exact = self.dictionary.get(key)
        if exact:
            return list(exact)
        remaining = keyword
        translated_parts: list[str] = []
        matched: list[str] = []
        for zh, values in sorted(self.dictionary.items(), key=lambda item: len(item[0]), reverse=True):
            if zh and zh in remaining and values:
                translated_parts.append(values[0])
                matched.append(zh)
                remaining = remaining.replace(zh, " ", 1)
        phrase = clean_text(" ".join(translated_parts))
        if phrase and matched:
            return [phrase]
        return []

    def _mymemory_translate(self, keyword: str) -> str:
        params = {
            "q": keyword,
            "langpair": "zh-CN|en",
        }
        if self.email:
            params["de"] = self.email
        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PaperSearchWeb/1.1 (+http://127.0.0.1)",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        try:
            context = ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=8, context=context) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise RuntimeError(f"MyMemory: {exc}") from exc
        status = str(data.get("responseStatus") or "")
        translated = clean_text((data.get("responseData") or {}).get("translatedText"))
        if status not in {"200", "200.0"} and not translated:
            raise RuntimeError("MyMemory 返回状态异常")
        if not translated or "MYMEMORY WARNING" in translated.upper():
            raise RuntimeError("MyMemory 未返回有效翻译")
        return translated

    def expand_keyword(self, keyword: str) -> dict[str, Any]:
        variants: list[str] = []
        sources: list[str] = []
        warnings: list[str] = []
        add_variants(variants, [keyword])
        local_values = self._local_variants(keyword)
        if local_values:
            add_variants(variants, local_values)
            sources.append("本地学术词库")
        if has_chinese(keyword) and self.provider in {"auto", "mymemory"}:
            cache_key = normalize_term(keyword)
            cached = self.cache.get(cache_key)
            if isinstance(cached, dict) and cached.get("variants"):
                add_variants(variants, [keyword])
                add_variants(variants, cached.get("variants") or [])
                sources.append("翻译缓存")
            else:
                try:
                    translated = self._mymemory_translate(keyword)
                    add_variants(variants, translated)
                    sources.append("MyMemory")
                    self.cache[cache_key] = {
                        "keyword": keyword,
                        "variants": [translated],
                        "updated_at": int(time.time()),
                    }
                    with TRANSLATION_CACHE_LOCK:
                        self._save_cache()
                except Exception as exc:
                    warnings.append(str(exc))
        return {
            "keyword": keyword,
            "variants": variants,
            "translation_sources": list(dict.fromkeys(sources)),
            "translation_warnings": warnings,
        }

    def expand(self, keywords: list[str]) -> list[dict[str, Any]]:
        return [self.expand_keyword(keyword) for keyword in keywords]

    def dictionary_count(self) -> int:
        return len(self.dictionary)

    def component_variants(self, keyword: str) -> set[str]:
        key = normalize_term(keyword)
        components: set[str] = set()
        for zh, values in self.dictionary.items():
            zh_key = normalize_term(zh)
            if not zh_key or zh_key == key or zh_key not in key:
                continue
            for value in values:
                normalized = normalize_term(value)
                if normalized:
                    components.add(normalized)
        return components

    def is_component_only(self, keyword: str, term: str) -> bool:
        term_key = normalize_term(term)
        return bool(term_key and term_key in self.component_variants(keyword))

def escape_query_term(value: Any) -> str:
    return clean_text(value).replace("\\", "\\\\").replace('"', '\\"')


def group_variants(group: Any) -> list[str]:
    if not isinstance(group, dict):
        return []
    values = group.get("variants")
    return [clean_text(value) for value in values or [] if clean_text(value)]


def build_grouped_query(query_terms: list[dict[str, Any]], match_mode: str, *, quote: bool = True) -> str:
    joiner = " AND " if match_mode == "all" else " OR "
    groups: list[str] = []
    for group in query_terms or []:
        parts: list[str] = []
        for variant in group_variants(group):
            escaped = escape_query_term(variant)
            parts.append(f'"{escaped}"' if quote else escaped)
        if parts:
            groups.append("(" + " OR ".join(parts) + ")")
    return joiner.join(groups)


def build_flat_query(query_terms: list[dict[str, Any]], match_mode: str) -> str:
    flatten: list[str] = []
    for group in query_terms or []:
        add_variants(flatten, group_variants(group))
    if match_mode == "all":
        return " ".join(flatten)
    return " OR ".join(flatten)


def all_variant_terms(query_terms: list[dict[str, Any]]) -> list[str]:
    flatten: list[str] = []
    for group in query_terms or []:
        add_variants(flatten, group_variants(group))
    return flatten

def build_primary_query(query_terms: list[dict[str, Any]], match_mode: str) -> str:
    primary: list[str] = []
    for group in query_terms or []:
        variants = group_variants(group)
        if not variants:
            continue
        add_variants(primary, [variants[0]])
        english = [value for value in variants if not CJK_RE.search(value)]
        if english:
            add_variants(primary, [english[0]])
    if match_mode == "all":
        return " ".join(primary)
    return " OR ".join(primary)
