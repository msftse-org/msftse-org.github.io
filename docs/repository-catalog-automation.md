# Repository catalog automation

The landing page reads its repository cards from `data/repositories.json`. A scheduled GitHub Actions workflow rebuilds that file from the MSFTSE GitHub organization every 12 hours and proposes changes through a pull request.

## Flow

1. `.github/workflows/sync-repositories.yml` runs at minute 17 every 12 hours or through manual dispatch.
2. `scripts/sync_repositories.py` pages through the GitHub organization repositories API.
3. Forks, archived repositories, the organization profile, and this Pages repository are excluded by default.
4. Each included repository is mapped to one of the four landing-page categories.
5. The deterministic result is written to `data/repositories.json`.
6. If the generated file differs from `main`, the workflow creates or updates `automation/repository-catalog` and its pull request.
7. A maintainer reviews the proposed metadata and classification before merging. The workflow never merges or writes directly to `main`.

## Classification

Classification uses the following precedence:

1. A repository-specific override in `data/catalog-config.json`.
2. A matching repository topic, with high confidence.
3. A matching name or description keyword, with medium confidence.
4. `Product/Application`, the configured low-confidence fallback.

The generated `classification` object explains how each result was selected. For reliable automatic classification, add one of these explicit topics to the source repository:

- `catalog-poc-demo`
- `catalog-sample`
- `catalog-product`
- `catalog-workshop`

If a repository needs curated copy, ordering, visibility, or categorization, add an entry under `overrides`. Setting `include` to `true` pins a repository even when it is not returned by the API. Setting it to `false` excludes a repository.

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

For deterministic offline testing, pass a JSON array shaped like the GitHub repositories API:

```bash
python3 scripts/sync_repositories.py --input path/to/repositories.json --dry-run
```
