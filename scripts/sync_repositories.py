#!/usr/bin/env python3
"""Build the landing-page repository catalog from the GitHub organization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ALLOWED_CATEGORIES = {"POC/Demo", "Sample", "Product/Application", "Workshop"}
ACRONYMS = {"ai", "aks", "api", "cli", "mcp", "sre", "sql", "ui"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("data/catalog-config.json"))
    parser.add_argument("--output", type=Path, default=Path("data/repositories.json"))
    parser.add_argument("--input", type=Path, help="Read a GitHub API response from a local JSON fixture")
    parser.add_argument("--token-env", default="CATALOG_GITHUB_TOKEN")
    parser.add_argument("--dry-run", action="store_true", help="Print generated JSON without writing it")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


def fetch_organization_repositories(organization: str, token: str | None) -> list[dict[str, Any]]:
    encoded_org = urllib.parse.quote(organization, safe="")
    url: str | None = (
        f"https://api.github.com/orgs/{encoded_org}/repos"
        "?per_page=100&type=all&sort=full_name&direction=asc"
    )
    repositories: list[dict[str, Any]] = []

    while url:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "msftse-repository-catalog-sync",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                page = json.load(response)
                if not isinstance(page, list):
                    raise RuntimeError("GitHub returned an unexpected repository response")
                repositories.extend(page)
                url = next_link(response.headers.get("Link"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API request failed ({error.code}): {detail}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"GitHub API request failed: {error.reason}") from error

    return repositories


def normalized_words(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def title_from_name(name: str) -> str:
    words = normalized_words(name).split()
    return " ".join(word.upper() if word in ACRONYMS else word.capitalize() for word in words)


def classify_repository(
    repository: dict[str, Any], config: dict[str, Any], override: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    overridden_category = override.get("category")
    if overridden_category:
        validate_category(overridden_category)
        return overridden_category, {"method": "override", "confidence": "high", "matches": []}

    topics = {str(topic).lower() for topic in repository.get("topics") or []}
    for rule in config["categoryRules"]:
        matches = sorted(topics.intersection(str(topic).lower() for topic in rule.get("topics", [])))
        if matches:
            validate_category(rule["category"])
            return rule["category"], {
                "method": "topic",
                "confidence": "high",
                "matches": [f"topic:{match}" for match in matches],
            }

    searchable_text = normalized_words(
        " ".join(
            [
                str(repository.get("name") or ""),
                str(repository.get("description") or ""),
                " ".join(topics),
            ]
        )
    )
    padded_text = f" {searchable_text} "
    for rule in config["categoryRules"]:
        matches = [
            keyword
            for keyword in rule.get("keywords", [])
            if f" {normalized_words(str(keyword))} " in padded_text
        ]
        if matches:
            validate_category(rule["category"])
            return rule["category"], {
                "method": "keyword",
                "confidence": "medium",
                "matches": [f"keyword:{match}" for match in matches],
            }

    category = config["defaultCategory"]
    validate_category(category)
    return category, {"method": "default", "confidence": "low", "matches": []}


def validate_category(category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        choices = ", ".join(sorted(ALLOWED_CATEGORIES))
        raise ValueError(f"Unsupported category {category!r}; expected one of: {choices}")


def should_include(
    repository: dict[str, Any], config: dict[str, Any], override: dict[str, Any]
) -> bool:
    if override.get("include") is False:
        return False
    if override.get("include") is True:
        return True
    if repository["name"] in set(config.get("excludedRepositories", [])):
        return False
    if config.get("excludeArchived", True) and repository.get("archived"):
        return False
    if config.get("excludeForks", True) and repository.get("fork"):
        return False
    if not config.get("includePrivate", False) and repository.get("private"):
        return False
    return True


def synthetic_repository(name: str, override: dict[str, Any]) -> dict[str, Any]:
    if not override.get("url"):
        raise ValueError(f"Pinned repository {name!r} requires an override URL")
    visibility = str(override.get("visibility", "Public"))
    return {
        "name": name,
        "html_url": override["url"],
        "description": override.get("summary"),
        "language": override.get("language"),
        "visibility": visibility.lower(),
        "private": visibility.lower() == "private",
        "topics": override.get("topics", []),
        "archived": False,
        "fork": False,
    }


def stable_accent(name: str) -> str:
    return ("cyan", "violet")[hashlib.sha256(name.encode("utf-8")).digest()[0] % 2]


def catalog_entry(
    repository: dict[str, Any], config: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    name = repository["name"]
    category, classification = classify_repository(repository, config, override)
    organization = config["organization"]
    url = override.get("url") or repository.get("html_url")
    expected_prefix = f"https://github.com/{organization}/"
    if not isinstance(url, str) or not url.startswith(expected_prefix):
        raise ValueError(f"Repository {name!r} has an invalid organization URL: {url!r}")

    raw_visibility = override.get("visibility") or repository.get("visibility")
    if not raw_visibility:
        raw_visibility = "private" if repository.get("private") else "public"
    visibility = str(raw_visibility).capitalize()
    topics = sorted({str(topic).lower() for topic in repository.get("topics") or []})
    summary = override.get("summary") or repository.get("description")

    return {
        "name": name,
        "title": override.get("title") or title_from_name(name),
        "url": url,
        "summary": summary or "A solution engineering repository from the MSFTSE organization.",
        "useCase": override.get("useCase") or config["useCaseByCategory"][category],
        "category": category,
        "language": override.get("language") or repository.get("language") or "Multiple",
        "visibility": visibility,
        "accent": override.get("accent") or stable_accent(name),
        "topics": topics,
        "classification": classification,
    }


def build_catalog(repositories: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    overrides = config.get("overrides", {})
    candidates = {repository["name"]: repository for repository in repositories}

    for name, override in overrides.items():
        if override.get("include") is True and name not in candidates:
            candidates[name] = synthetic_repository(name, override)

    entries: list[tuple[int, dict[str, Any]]] = []
    for name, repository in candidates.items():
        override = overrides.get(name, {})
        if not should_include(repository, config, override):
            continue
        order = int(override.get("order", 10_000))
        entries.append((order, catalog_entry(repository, config, override)))

    entries.sort(key=lambda item: (item[0], item[1]["name"].lower()))
    return {
        "schemaVersion": 1,
        "organization": config["organization"],
        "repositories": [entry for _, entry in entries],
    }


def serialized(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    args = parse_args()
    config = read_json(args.config)
    if args.input:
        repositories = read_json(args.input)
        if not isinstance(repositories, list):
            raise ValueError("The input fixture must contain a JSON array")
    else:
        token = os.environ.get(args.token_env) or os.environ.get("GITHUB_TOKEN")
        repositories = fetch_organization_repositories(config["organization"], token)

    catalog = build_catalog(repositories, config)
    content = serialized(catalog)
    if args.dry_run:
        sys.stdout.write(content)
        return 0

    previous: dict[str, Any] = {"repositories": []}
    if args.output.exists():
        previous = read_json(args.output)
    previous_names = {repository["name"] for repository in previous.get("repositories", [])}
    current_names = {repository["name"] for repository in catalog["repositories"]}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_text(encoding="utf-8") != content:
        args.output.write_text(content, encoding="utf-8")

    print(f"Catalog contains {len(current_names)} repositories.")
    if current_names - previous_names:
        print("Added: " + ", ".join(sorted(current_names - previous_names)))
    if previous_names - current_names:
        print("Removed: " + ", ".join(sorted(previous_names - current_names)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
