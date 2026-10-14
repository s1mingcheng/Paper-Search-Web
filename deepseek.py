"""Optional DeepSeek abstract summarization for Paper Search Web."""

from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


class DeepSeekError(RuntimeError):
    """A recoverable DeepSeek API error."""


class DeepSeekService:
    def __init__(
        self,
        cache_path: Path,
        config_path: Path | None = None,
        terms_cache_path: Path | None = None,
    ) -> None:
        self.cache_path = cache_path
        self.terms_cache_path = terms_cache_path or cache_path.with_name("deepseek_terms_cache.json")
        self.config_path = config_path or cache_path.with_name("deepseek_config.json")
        self.max_items = max(1, min(50, int(os.environ.get("DEEPSEEK_MAX_ITEMS", "20") or 20)))
        self.cache = self._load_cache()
        self.terms_cache = self._load_terms_cache()
        self.cache_lock = threading.RLock()
        self.environment_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.environment_base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip()
        self.environment_model = os.environ.get("DEEPSEEK_MODEL", "").strip()
        self.config = self._load_config()
        self.api_key = self.environment_key or str(self.config.get("api_key") or "").strip()
        self.base_url = (
            self.environment_base_url
            or str(self.config.get("base_url") or "").strip()
            or "https://api.deepseek.com"
        ).rstrip("/")
        self.model = self.environment_model or str(self.config.get("model") or "").strip() or "deepseek-chat"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _load_cache(self) -> dict[str, Any]:
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
            print(f"[warn] Could not save DeepSeek summary cache: {exc}")

    def _load_terms_cache(self) -> dict[str, Any]:
        if not self.terms_cache_path.exists():
            return {}
        try:
            data = json.loads(self.terms_cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_terms_cache(self) -> None:
        try:
            self.terms_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.terms_cache_path.write_text(
                json.dumps(self.terms_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[warn] Could not save DeepSeek terms cache: {exc}")

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_config(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            raise DeepSeekError(f"无法保存 DeepSeek 配置: {exc}") from exc

    @staticmethod
    def _mask_key(key: str) -> str:
        key = (key or "").strip()
        if not key:
            return ""
        if len(key) <= 8:
            return "********"
        return f"{key[:4]}…{key[-4:]}"

    def configure(self, api_key: str, model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        key = (api_key or "").strip()
        if not key:
            raise DeepSeekError("请输入 DeepSeek API Key")
        self.api_key = key
        if model and model.strip():
            self.model = model.strip()
        if base_url and base_url.strip():
            self.base_url = base_url.strip().rstrip("/")
        self.config.update(
            {
                "api_key": self.api_key,
                "model": self.model,
                "base_url": self.base_url,
            }
        )
        self._save_config()
        return self.status()

    def clear(self) -> dict[str, Any]:
        self.config.pop("api_key", None)
        self._save_config()
        self.api_key = self.environment_key
        return self.status()

    def key_source(self) -> str:
        if self.environment_key and self.api_key == self.environment_key:
            return "environment"
        if self.config.get("api_key"):
            return "local_file"
        return "none"

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "model": self.model,
            "base_url": self.base_url,
            "max_items": self.max_items,
            "cache_count": len(self.cache),
            "terms_cache_count": len(self.terms_cache),
            "key_hint": self._mask_key(self.api_key),
            "key_source": self.key_source(),
        }

    def _cache_key(self, title: str, abstract: str) -> str:
        raw = f"{self.model}\n{title}\n{abstract}".encode("utf-8", errors="ignore")
        return hashlib.sha256(raw).hexdigest()

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 360,
        temperature: float = 0.2,
    ) -> str:
        if not self.configured:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        endpoint = f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "PaperSearchWeb/1.3 (+http://127.0.0.1)",
            },
            method="POST",
        )
        try:
            context = ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=75, context=context) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(500).decode("utf-8", errors="replace")
            except Exception:
                pass
            raise DeepSeekError(f"DeepSeek HTTP {exc.code}: {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise DeepSeekError(f"DeepSeek 网络连接失败: {exc.reason}") from exc
        except Exception as exc:
            raise DeepSeekError(f"DeepSeek 请求失败: {exc}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise DeepSeekError("DeepSeek 未返回有效结果")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise DeepSeekError("DeepSeek 返回了空内容")
        return content

    def _request_completion(self, title: str, abstract: str) -> str:
        system_prompt = (
            "你是严谨的学术论文摘要编辑。请用中文概括用户提供的论文摘要，"
            "保留研究对象、研究方法、核心发现和结论；不要添加摘要中没有的信息；"
            "不要分点，使用一段话，控制在 180 个汉字以内。"
        )
        user_prompt = f"论文标题：{title or '未提供'}\n\n论文摘要：\n{abstract}"
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=360,
            temperature=0.2,
        )

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        text_value = (content or "").strip()
        text_value = re.sub(r"^```(?:json)?\s*", "", text_value, flags=re.IGNORECASE)
        text_value = re.sub(r"\s*```$", "", text_value)
        start = text_value.find("{")
        end = text_value.rfind("}")
        if start < 0 or end <= start:
            raise DeepSeekError("DeepSeek 未返回有效 JSON")
        try:
            data = json.loads(text_value[start : end + 1])
        except json.JSONDecodeError as exc:
            raise DeepSeekError("DeepSeek 返回的检索词 JSON 无法解析") from exc
        if not isinstance(data, dict):
            raise DeepSeekError("DeepSeek 返回的检索词格式不正确")
        return data

    @staticmethod
    def _normalize_keyword(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    def _sanitize_groups(
        self,
        raw_groups: list[Any],
        clean_keywords: list[str],
    ) -> list[dict[str, Any]]:
        by_normalized = {self._normalize_keyword(value): value for value in clean_keywords}
        result_groups: list[dict[str, Any]] = []
        used_terms: set[str] = set()
        for index, raw_group in enumerate(raw_groups):
            if not isinstance(raw_group, dict):
                continue
            model_keyword = str(raw_group.get("keyword") or "").strip()
            original = by_normalized.get(self._normalize_keyword(model_keyword))
            if not original and index < len(clean_keywords):
                original = clean_keywords[index]
            if not original:
                continue
            terms: list[str] = []
            for raw_term in raw_group.get("terms") or []:
                term = re.sub(r"\s+", " ", str(raw_term or "").strip())
                normalized = self._normalize_keyword(term)
                if not term or len(term) > 90 or normalized == self._normalize_keyword(original):
                    continue
                if normalized in used_terms:
                    continue
                terms.append(term)
                used_terms.add(normalized)
                if len(terms) >= 8:
                    break
            result_groups.append({"keyword": original, "terms": terms})
        return result_groups

    def _validate_search_terms(
        self,
        clean_keywords: list[str],
        candidate_groups: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "你是严格的学术检索语义审计员。逐个检查每个关键词的候选检索词组："
            "只有能够完整承载原始关键词全部含义的词组才能保留；"
            "任何只覆盖部分词义、丢失修饰语、研究对象、作用关系或上下文的词组都必须删除；"
            "如果缺少完整等价表达，可以补充，但不能扩大到无关主题。"
            "每个关键词最多保留 8 个完整词组，多个关键词必须分别处理。只输出 JSON。"
        )
        user_prompt = (
            "原始关键词："
            + "；".join(clean_keywords)
            + "\n候选检索词组："
            + json.dumps(candidate_groups, ensure_ascii=False)
            + "\n请返回："
            + '{"groups":[{"keyword":"原始关键词","terms":["完整等价检索词1","完整等价检索词2"]}]}'
        )
        content = self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1400,
            temperature=0,
        )
        parsed = self._parse_json_object(content)
        return self._sanitize_groups(parsed.get("groups") or [], clean_keywords)

    def select_search_terms(self, keywords: list[str]) -> dict[str, Any]:
        if not self.configured:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，无法使用 DeepSeek 选择检索词")
        clean_keywords = [str(value).strip() for value in keywords if str(value).strip()]
        if not clean_keywords:
            return {"groups": [], "model": self.model, "source": "deepseek"}
        cache_raw = f"{self.model}\n" + "\n".join(clean_keywords)
        cache_key = hashlib.sha256(cache_raw.encode("utf-8", errors="ignore")).hexdigest()
        cached = self.terms_cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("groups") and cached.get("schema_version") == 2:
            return cached

        system_prompt = (
            "你是学术数据库检索词专家。请根据用户输入的关键词，为每个关键词选择适合在 "
            "OpenAlex、Crossref、arXiv、Semantic Scholar、PubMed 和 Europe PMC 中检索的"
            "同义词、英文标准术语、缩写、近义词和相关学术词组。"
            "输入的每个关键词都是一个不可拆分的完整概念。候选词组必须保留该关键词的全部语义，"
            "不能只覆盖其中一个词，不能丢失修饰语、研究对象、作用关系或上下文。"
            "不要扩展到与原始主题无关的方向。必须保留每个原始关键词，并最多返回 8 个补充词。"
            "只输出 JSON，不要输出解释或 Markdown。"
        )
        user_prompt = (
            "用户关键词："
            + "；".join(clean_keywords)
            + "\n请严格返回以下 JSON 结构："
            + '{"groups":[{"keyword":"原始关键词","terms":["完整等价检索词1","related term 2"]}]}'
        )
        content = self._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
            temperature=0.1,
        )
        parsed = self._parse_json_object(content)
        raw_groups = parsed.get("groups")
        if not isinstance(raw_groups, list):
            raise DeepSeekError("DeepSeek 返回的检索词缺少 groups")
        result_groups = self._sanitize_groups(raw_groups, clean_keywords)

        needs_validation = len(clean_keywords) >= 2 or any(len(value) >= 4 for value in clean_keywords)
        validation = "basic"
        validation_warning = ""
        if needs_validation:
            try:
                validated_groups = self._validate_search_terms(clean_keywords, result_groups)
                if any(group.get("terms") for group in validated_groups):
                    result_groups = validated_groups
                    validation = "semantic_complete"
            except Exception as exc:
                validation_warning = str(exc)

        if not any(group.get("terms") for group in result_groups):
            raise DeepSeekError("DeepSeek 未选择出可用的相关检索词")
        result = {
            "groups": result_groups,
            "model": self.model,
            "source": "deepseek",
            "schema_version": 2,
            "validation": validation,
            "validation_warning": validation_warning,
            "updated_at": int(time.time()),
        }
        should_cache = (not needs_validation) or validation == "semantic_complete"
        if should_cache:
            with self.cache_lock:
                self.terms_cache[cache_key] = result
                self._save_terms_cache()
        return result

    def summarize_text(self, title: str, abstract: str) -> str:
        clean_abstract = (abstract or "").strip()
        if not clean_abstract:
            raise DeepSeekError("论文没有摘要，无法概括")
        if len(clean_abstract) > 16000:
            clean_abstract = clean_abstract[:16000]
        key = self._cache_key(title or "", clean_abstract)
        cached = self.cache.get(key)
        if isinstance(cached, dict) and cached.get("summary"):
            return str(cached["summary"])
        summary = self._request_completion(title or "", clean_abstract)
        with self.cache_lock:
            self.cache[key] = {
                "title": title or "",
                "summary": summary,
                "model": self.model,
                "updated_at": int(time.time()),
            }
            self._save_cache()
        return summary

    def summarize_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.configured:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，请先设置环境变量后重启服务")
        selected: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            if not (item.get("abstract") or "").strip():
                continue
            if len(selected) >= self.max_items:
                break
            selected.append(item)
        if not selected:
            return {"summaries": [], "processed": 0, "message": "没有可概括的摘要"}

        summaries: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(3, len(selected))) as executor:
            future_map = {
                executor.submit(
                    self.summarize_text,
                    str(item.get("title") or ""),
                    str(item.get("abstract") or ""),
                ): item
                for item in selected
            }
            for future in as_completed(future_map):
                item = future_map[future]
                uid = str(item.get("_uid") or "")
                try:
                    summary = future.result()
                    summaries.append({"uid": uid, "status": "ok", "summary": summary, "error": ""})
                except Exception as exc:
                    summaries.append({"uid": uid, "status": "error", "summary": "", "error": str(exc)})
        return {
            "summaries": summaries,
            "processed": len(selected),
            "limited": len(results) > len(selected),
            "message": f"已处理 {len(selected)} 条摘要",
        }
