"""离线验证检索准确性；不调用外部接口或 DeepSeek。"""
import unittest
from unittest.mock import patch

import app


def group(keyword, *variants):
    return {"keyword": keyword, "variants": list(variants) or [keyword]}


class SearchQualityTests(unittest.TestCase):
    def test_all_requires_every_concept_without_fallback(self):
        candidates = [{"title": "Machine learning in education"}]
        self.assertEqual(app.relevance_filter(candidates, [group("learning"), group("medicine")], "all"), [])

    def test_any_keeps_matching_concept(self):
        results = app.relevance_filter([{"title": "Machine learning"}], [group("learning"), group("medicine")], "any")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["match_evidence"][0]["keyword"], "learning")

    def test_venue_cannot_satisfy_topic(self):
        self.assertEqual(app.relevance_filter([{"title": "Ocean currents", "venue": "Artificial Intelligence"}], [group("AI", "artificial intelligence")], "all"), [])

    def test_abbreviation_requires_word_boundary(self):
        self.assertEqual(app.relevance_filter([{"title": "Chair design"}], [group("AI")], "all"), [])

    def test_abstract_and_title_scope(self):
        candidates = [{"title": "New methods", "abstract": "A study of machine learning."}]
        terms = [group("机器学习", "machine learning")]
        results = app.relevance_filter(candidates, terms, "all")
        self.assertEqual(results[0]["match_evidence"][0]["field"], "摘要")
        self.assertEqual(app.relevance_filter(candidates, terms, "all", "title"), [])

    def test_exclusions_always_check_title_and_abstract(self):
        candidates = [{"title": "Machine learning", "abstract": "A systematic review"}]
        self.assertEqual(app.relevance_filter(candidates, [group("learning")], "all", "title", ["review"]), [])

    def test_title_hits_rank_before_abstract_hits(self):
        candidates = [{"title": "Methods", "abstract": "Learning", "year": 2026}, {"title": "Learning", "year": 2000}]
        results = app.relevance_filter(candidates, [group("learning")], "all")
        self.assertEqual(results[0]["year"], 2000)
        self.assertGreater(results[0]["relevance_score"], results[1]["relevance_score"])
        self.assertNotIn("relevance_score", candidates[0])

    def test_search_pipeline_filters_merges_and_orders(self):
        terms = [group("learning")]
        request = {"sources": ["openalex", "crossref"], "query_terms": terms, "match_mode": "all", "match_scope": "title_abstract", "exclude_keywords": [], "max_results": 10}
        sources = {
            "openalex": {"id": "openalex", "name": "OpenAlex", "adapter": lambda _: [{"title": "Learning methods", "doi": "10.1/example", "sources": ["OpenAlex"]}]},
            "crossref": {"id": "crossref", "name": "Crossref", "adapter": lambda _: [{"title": "Learning methods", "doi": "10.1/example", "sources": ["Crossref"]}, {"title": "Unrelated"}]},
        }
        with patch.object(app, "normalize_search_request", return_value=request), patch.object(app, "SOURCE_BY_ID", sources), patch.object(app, "enrich_metrics"):
            result = app.search_all_sources({})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["raw_total"], 2)
        self.assertEqual(set(result["results"][0]["sources"]), {"OpenAlex", "Crossref"})
        self.assertEqual(result["results"][0]["relevance_score"], 100)

    def test_openalex_key_is_only_sent_in_header(self):
        request = {"keywords": ["learning"], "query_terms": [group("learning")], "match_mode": "all", "fetch_limit": 50}
        with patch.dict(app.os.environ, {"OPENALEX_API_KEY": "test-key"}), patch.object(app, "request_json", return_value={"results": []}) as call:
            app.search_openalex(request)
        self.assertNotIn("test-key", call.call_args.args[0])
        self.assertEqual(call.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
