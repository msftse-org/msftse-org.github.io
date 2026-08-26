# Repository catalog automation

The landing page reads its repository cards from `data/repositories.json`. A scheduled GitHub Actions workflow rebuilds that file from the MSFTSE GitHub organization every 12 hours and proposes changes through a pull request.

## Flow

1. `.github/workflows/sync-repositories.yml` runs at minute 17 every 12 hours or through manual dispatch.
2. `scripts/sync_repositories.py` pages through the GitHub organization repositories API.
3. Forks, archived repositories, the organization profile, and this Pages repository are excluded by default.
4. For a new, non-curated repository, the script gathers a bounded analysis context: GitHub metadata, up to 400 tree paths, the README, common manifests, workflows, and likely application entry points.
5. When LLM secrets are configured, that context is sent to the configured OpenAI-compatible chat-completions endpoint. The response supplies a description, short use case, category, and searchable tags.
6. The validated result is written to `data/repositories.json`. Previously generated LLM metadata is reused from either the default branch or a pending automation branch, so unchanged repositories do not consume tokens on every run.
7. If the generated file differs from `main`, the workflow creates or updates `automation/repository-catalog` and its pull request.
8. A maintainer reviews the proposed metadata and classification before merging. The workflow never merges or writes directly to `main`.

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

If a repository needs curated copy, tags, ordering, visibility, or categorization, add an entry under `overrides`. Manual values always win and the LLM can fill any missing metadata. An override containing all of `summary`, `useCase`, `category`, and `tags` is fully curated and skips LLM analysis; set `llmEnrichment` to `false` to skip it explicitly. Setting `include` to `true` pins a repository even when it is not returned by the API. Setting it to `false` excludes a repository.

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

The default `GITHUB_TOKEN` can discover public organization repositories and update this repository. To discover private repositories, create an `ORG_REPOSITORY_TOKEN` Actions secret with read-only metadata access to the intended organization repositories, then set `includePrivate` to `true` in the catalog configuration.

Private repository names and descriptions become public when included in `data/repositories.json`; enable private discovery only when that disclosure is intentional.

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
