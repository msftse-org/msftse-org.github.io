# Repository catalog automation

The landing page reads its repository cards from `data/repositories.json`. A scheduled GitHub Actions workflow rebuilds that file from the MSFTSE GitHub organization every 12 hours and proposes changes through a pull request.

## Flow

1. `.github/workflows/sync-repositories.yml` runs at minute 17 every 12 hours or through manual dispatch.
2. The workflow looks for an open pull request from `automation/repository-catalog` to the default branch and reuses its validated LLM metadata when available.
3. `scripts/sync_repositories.py` performs a fresh, paginated scan of the GitHub organization repositories API with `type=public`. The workflow passes `--visibility public`, which must match `repositoryVisibility` in the configuration.
4. All public repositories are included, including forks, archives, the organization profile, and the catalog repository. Private, internal, and unknown visibility are rejected before overrides or LLM analysis.
5. For a new, non-curated repository, the script gathers a bounded analysis context: GitHub metadata, up to 400 tree paths, the README, common manifests, workflows, and likely application entry points.
6. When LLM secrets are configured, that context is sent to the configured OpenAI-compatible chat-completions endpoint. The response supplies a description, short use case, category, and searchable tags.
7. The validated result is written to `data/repositories.json`. Previously generated LLM metadata is reused from either the default branch or a pending automation branch. When `refreshOnPush` is enabled, repositories whose GitHub `pushed_at` value changed are analyzed again; unchanged repositories do not consume tokens.
8. If the result differs from `main`, the workflow creates the PR or force-updates its automation branch and refreshes its title and body. If a newer scan matches `main`, any stale open catalog PR is closed automatically.
9. A maintainer reviews the proposed metadata and classification before merging. The workflow never merges or writes directly to `main`.

If the LLM secrets have not been added yet, synchronization continues with the existing deterministic metadata rules. Repositories that were not AI-enriched remain eligible for enrichment after the secrets are configured.

## Classification

Classification uses the following precedence:

1. A repository-specific override in `data/catalog-config.json`.
2. Validated LLM analysis of the repository structure and selected text files.
3. A matching repository topic, with high confidence.
4. A matching name or description keyword, with medium confidence.
5. `Product/Application`, the configured low-confidence fallback.

The generated `classification` object explains how each result was selected. For reliable automatic classification, add one of these explicit topics to the source repository:

- `catalog-poc-demo`
- `catalog-sample`
- `catalog-product`
- `catalog-workshop`

If a repository needs curated copy, tags, ordering, or categorization, add an entry under `overrides`. Manual metadata values win and the LLM can fill missing metadata. Visibility always comes from GitHub, never an override. An override containing all of `summary`, `useCase`, `category`, and `tags` is fully curated and skips LLM analysis; set `llmEnrichment` to `false` to skip it explicitly. Setting `include` to `true` can bypass optional archive, fork, and name exclusions, but never visibility filtering or API discovery. Repositories missing from the API response are not synthesized from overrides. Setting `include` to `false` excludes a repository.

## LLM configuration

Add these GitHub Actions repository secrets before enabling production enrichment:

- `CATALOG_LLM_ENDPOINT` (required): the complete OpenAI-compatible chat-completions URL. For Azure OpenAI, include the deployment and `api-version` query string in this URL.
- `CATALOG_LLM_API_KEY` (required): the provider API key.
- `CATALOG_LLM_MODEL` (optional): the model name for endpoints that require `model` in the request body. Azure OpenAI deployments normally identify the model in the URL.
- `CATALOG_LLM_AUTH_STYLE` (optional): `azure` to send the `api-key` header, or `bearer` to send an `Authorization: Bearer` header. When omitted, Azure hostnames are detected automatically and all other endpoints use bearer authentication.

Example endpoint shapes:

```text
https://RESOURCE.openai.azure.com/openai/deployments/DEPLOYMENT/chat/completions?api-version=2024-10-21
https://api.openai.com/v1/chat/completions
```

The script requests JSON and validates category membership, description length, use-case length, and normalized tags before updating the catalog. Repository content is treated as untrusted prompt data, and the configured context limits in `data/catalog-config.json` bound both API calls and token usage. Selected repository text is sent to the configured provider, so use an endpoint approved for the source code being analyzed—especially before enabling private repositories. A configured LLM request or validation failure fails the workflow rather than silently publishing questionable metadata.

## Authentication and repository settings

This repository must be public and use `repositoryVisibility: "public"`. The workflow uses `GITHUB_TOKEN` for public discovery and catalog pull requests; it does not use an organization-wide private-repository token. The old `includePrivate` setting is replaced by the required `repositoryVisibility` field, with only `public` and `private` accepted.

Private discovery belongs exclusively in `msftse-org/msftse-org-private`, configured with `repositoryVisibility: "private"` and an `ORG_REPOSITORY_TOKEN` secret. That token must cover all organization repositories, with metadata read permission for discovery and contents read permission for LLM analysis. Never copy private catalog data into this public repository.

Set **Settings → Pages → Build and deployment → Source** to **GitHub Actions** in both repositories. The deployment validates the catalog's visibility and uploads only `index.html`, `styles.css`, `catalog.js`, and `data/repositories.json`. Legacy branch-based Pages publishing bypasses these workflow checks. The private site must additionally remain privately published (`public: false` in the Pages API); its sync and deployment workflows reject public Pages or legacy publishing.

The public navigation links to the private site's actual Pages URL, https://turbo-adventure-9m6p176.pages.github.io/. GitHub controls access to that destination. If that URL changes, update the link. Removing previously published private metadata from the current catalog does not remove it from Git history or caches; historical cleanup requires a separate owner-approved process.

The repository must allow GitHub Actions to create pull requests. In GitHub, enable **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**. Approval permission is not used, but GitHub exposes creation through this setting.

## Local operation

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

Build from GitHub:

```bash
CATALOG_GITHUB_TOKEN=github_token python3 scripts/sync_repositories.py
```

Build with LLM enrichment:

```bash
CATALOG_GITHUB_TOKEN=github_token \
CATALOG_LLM_ENDPOINT='https://provider.example/v1/chat/completions' \
CATALOG_LLM_API_KEY=api_key \
CATALOG_LLM_MODEL=model_name \
python3 scripts/sync_repositories.py
```

To deliberately regenerate AI metadata for all non-curated repositories, add `--enrich-all`. To troubleshoot the deterministic catalog without making LLM calls, add `--skip-llm`.

For deterministic offline testing, pass a JSON array shaped like the GitHub repositories API:

```bash
python3 scripts/sync_repositories.py --input path/to/repositories.json --dry-run
```
