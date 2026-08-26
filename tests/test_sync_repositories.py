import unittest

from scripts.sync_repositories import build_catalog, classify_repository, next_link, title_from_name


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

    def test_helpers(self):
        self.assertEqual(title_from_name("azure-sql-mcp"), "Azure SQL MCP")
        self.assertEqual(
            next_link('<https://api.github.com/page/2>; rel="next", <https://api.github.com/page/4>; rel="last"'),
            "https://api.github.com/page/2",
        )


if __name__ == "__main__":
    unittest.main()
