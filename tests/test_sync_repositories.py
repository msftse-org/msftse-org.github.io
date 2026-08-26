import os
import unittest
from unittest.mock import patch

from scripts.sync_repositories import (
    build_catalog,
    classify_repository,
    extract_json_object,
    enrich_catalog_repositories,
    llm_auth_style,
    next_link,
    previous_llm_enrichments,
    select_context_entries,
    title_from_name,
    validate_llm_endpoint,
    validate_llm_enrichment,
)


def base_config():
    return {
        "organization": "msftse-org",
        "includePrivate": False,
        "excludeArchived": True,
        "excludeForks": True,
        "excludedRepositories": ["msftse-org.github.io"],
        "defaultCategory": "Product/Application",
        "useCaseByCategory": {
            "POC/Demo": "Proof of concept",
            "Sample": "Sample",
            "Product/Application": "Application",
            "Workshop": "Workshop",
        },
        "categoryRules": [
            {"category": "Workshop", "topics": ["catalog-workshop"], "keywords": ["workshop"]},
            {"category": "Sample", "topics": ["catalog-sample"], "keywords": ["sample"]},
            {"category": "POC/Demo", "topics": ["catalog-poc-demo"], "keywords": ["demo"]},
            {"category": "Product/Application", "topics": ["catalog-product"], "keywords": ["platform"]},
        ],
        "overrides": {},
    }


def repository(name, **values):
    result = {
        "name": name,
        "html_url": f"https://github.com/msftse-org/{name}",
        "description": "A useful repository",
        "language": "Python",
        "visibility": "public",
        "private": False,
        "topics": [],
        "archived": False,
        "fork": False,
    }
    result.update(values)
    return result


class ClassificationTests(unittest.TestCase):
    def test_override_wins_over_topics(self):
        category, detail = classify_repository(
            repository("training", topics=["catalog-workshop"]),
            base_config(),
            {"category": "Sample"},
        )
        self.assertEqual(category, "Sample")
        self.assertEqual(detail["method"], "override")

    def test_topic_wins_over_keyword(self):
        category, detail = classify_repository(
            repository("demo-platform", topics=["catalog-workshop"]), base_config(), {}
        )
        self.assertEqual(category, "Workshop")
        self.assertEqual(detail["confidence"], "high")

    def test_keyword_and_default_classification(self):
        category, detail = classify_repository(repository("customer-demo"), base_config(), {})
        self.assertEqual((category, detail["method"]), ("POC/Demo", "keyword"))

        category, detail = classify_repository(repository("utilities"), base_config(), {})
        self.assertEqual((category, detail["confidence"]), ("Product/Application", "low"))


class CatalogTests(unittest.TestCase):
    def test_filters_and_pinned_repository(self):
        config = base_config()
        config["overrides"] = {
            "private-reference": {
                "include": True,
                "order": 1,
                "url": "https://github.com/msftse-org/private-reference",
                "summary": "Pinned private repository",
                "category": "Sample",
                "visibility": "Private",
            }
        }
        repositories = [
            repository("active-demo", description="Customer demo"),
            repository("private-repo", private=True, visibility="private"),
            repository("old-repo", archived=True),
            repository("forked-repo", fork=True),
            repository("msftse-org.github.io"),
        ]

        catalog = build_catalog(repositories, config)
        names = [entry["name"] for entry in catalog["repositories"]]
        self.assertEqual(names, ["private-reference", "active-demo"])
        self.assertEqual(catalog["repositories"][0]["visibility"], "Private")
        self.assertEqual(catalog["repositories"][1]["category"], "POC/Demo")

    def test_output_order_is_stable(self):
        catalog = build_catalog([repository("zeta"), repository("alpha")], base_config())
        self.assertEqual([entry["name"] for entry in catalog["repositories"]], ["alpha", "zeta"])

    def test_llm_enrichment_populates_catalog_and_override_still_wins(self):
        enrichment = {
            "summary": "An AI-generated repository summary.",
            "useCase": "Automated operations",
            "category": "Sample",
            "tags": ["Azure", "AI Agents"],
            "_metadata": {"method": "llm"},
        }
        catalog = build_catalog(
            [repository("agent-platform")],
            base_config(),
            {"agent-platform": enrichment},
        )
        entry = catalog["repositories"][0]
        self.assertEqual(entry["summary"], enrichment["summary"])
        self.assertEqual(entry["category"], "Sample")
        self.assertEqual(entry["classification"]["method"], "llm")
        self.assertEqual(entry["tags"], ["azure", "ai-agents"])
        self.assertEqual(entry["enrichment"], {"method": "llm"})

        config = base_config()
        config["overrides"] = {
            "agent-platform": {"summary": "Curated summary", "category": "Workshop"}
        }
        entry = build_catalog(
            [repository("agent-platform")], config, {"agent-platform": enrichment}
        )["repositories"][0]
        self.assertEqual(entry["summary"], "Curated summary")
        self.assertEqual(entry["category"], "Workshop")
        self.assertEqual(entry["classification"]["method"], "override")

        config["overrides"]["agent-platform"].update(
            {"useCase": "Curated use case", "tags": ["curated", "manual", "metadata"]}
        )
        entry = build_catalog(
            [repository("agent-platform")], config, {"agent-platform": enrichment}
        )["repositories"][0]
        self.assertNotIn("enrichment", entry)
        self.assertEqual(entry["tags"], ["curated", "manual", "metadata"])

    def test_previous_llm_enrichment_can_be_reused(self):
        previous = {
            "repositories": [
                {
                    "name": "agent-platform",
                    "summary": "Generated summary",
                    "useCase": "Agent operations",
                    "category": "Product/Application",
                    "tags": ["agents", "azure", "operations"],
                    "enrichment": {"method": "llm"},
                }
            ]
        }
        enrichment = previous_llm_enrichments(previous)["agent-platform"]
        self.assertEqual(enrichment["summary"], "Generated summary")
        self.assertEqual(enrichment["_metadata"]["method"], "llm")

    def test_helpers(self):
        self.assertEqual(title_from_name("azure-sql-mcp"), "Azure SQL MCP")
        self.assertEqual(
            next_link('<https://api.github.com/page/2>; rel="next", <https://api.github.com/page/4>; rel="last"'),
            "https://api.github.com/page/2",
        )


class LlmAnalysisTests(unittest.TestCase):
    def test_context_selection_prioritizes_readme_manifests_and_entrypoints(self):
        tree = [
            {"path": "src/helper.py", "sha": "1", "type": "blob"},
            {"path": "node_modules/package/index.js", "sha": "2", "type": "blob"},
            {"path": "src/main.py", "sha": "3", "type": "blob"},
            {"path": "package.json", "sha": "4", "type": "blob"},
            {"path": "README.md", "sha": "5", "type": "blob"},
            {"path": "image.png", "sha": "6", "type": "blob"},
        ]
        selected = select_context_entries(tree, 4)
        self.assertEqual(
            [entry["path"] for entry in selected],
            ["README.md", "package.json", "src/main.py", "src/helper.py"],
        )

    def test_response_validation_normalizes_tags_and_code_fences(self):
        parsed = extract_json_object(
            '```json\n{"summary":"Useful tool", "useCase":"Cloud automation", '
            '"category":"Sample", "tags":["Azure AI", "Python", "Automation"]}\n```'
        )
        enrichment = validate_llm_enrichment(parsed, 6)
        self.assertEqual(enrichment["tags"], ["azure-ai", "python", "automation"])

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_llm_enrichment(
                {
                    "summary": "Useful tool",
                    "useCase": "Cloud automation",
                    "category": "Library",
                    "tags": ["python", "azure", "automation"],
                },
                6,
            )

    def test_auth_style_auto_detect_and_override(self):
        self.assertEqual(
            llm_auth_style("https://catalog.openai.azure.com/openai/deployments/model/chat/completions"),
            "azure",
        )
        self.assertEqual(llm_auth_style("https://api.openai.com/v1/chat/completions"), "bearer")
        with patch.dict(os.environ, {"CATALOG_LLM_AUTH_STYLE": "azure"}):
            self.assertEqual(llm_auth_style("https://example.test/chat"), "azure")
        validate_llm_endpoint("https://example.test/chat")
        with self.assertRaises(ValueError):
            validate_llm_endpoint("http://example.test/chat")

    @patch("scripts.sync_repositories.request_llm_enrichment")
    @patch("scripts.sync_repositories.repository_analysis_context")
    def test_enrichment_reuses_existing_and_skips_fully_curated(
        self, analysis_context, request_enrichment
    ):
        config = base_config()
        config["overrides"] = {
            "curated": {
                "summary": "Curated",
                "useCase": "Curated use case",
                "category": "Sample",
                "tags": ["one", "two", "three"],
            }
        }
        existing = {
            "existing": {
                "summary": "Existing",
                "useCase": "Existing use case",
                "category": "Sample",
                "tags": ["one", "two", "three"],
                "_metadata": {"method": "llm"},
            }
        }
        analysis_context.return_value = {"repository": {"name": "new"}}
        request_enrichment.return_value = {
            "summary": "Generated",
            "useCase": "Generated use case",
            "category": "Sample",
            "tags": ["one", "two", "three"],
            "_metadata": {"method": "llm"},
        }

        result = enrich_catalog_repositories(
            [repository("existing"), repository("curated"), repository("new")],
            config,
            existing,
            "github-token",
            "https://example.test/chat",
            "api-key",
            "model",
            False,
        )

        self.assertEqual(set(result), {"existing", "new"})
        analysis_context.assert_called_once()
        request_enrichment.assert_called_once()


if __name__ == "__main__":
    unittest.main()
