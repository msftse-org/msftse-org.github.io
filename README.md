# MSFTSE Organization Site

The public GitHub Pages catalog for practical accelerators built by the MSFTSE Solution Engineering Lab.

Visit: https://msftse-org.github.io/

Private catalog (authorized organization members): https://turbo-adventure-9m6p176.pages.github.io/

This repository catalogs **all public repositories** in `msftse-org`, including forks and archives. Its configuration uses `repositoryVisibility: "public"`; private and internal repositories cannot be included through metadata overrides. The private catalog is maintained separately in `msftse-org/msftse-org-private`.

The site is static and requires no build step. `index.html` loads repository cards from `data/repositories.json`, while `catalog.js` provides client-side search and filtering.

Preview it through a local HTTP server so the browser can load the JSON catalog:

```bash
python3 -m http.server 8000
```

The repository catalog is synchronized from the GitHub organization every 12 hours. New repositories can be analyzed by an OpenAI-compatible LLM using their tree, documentation, manifests, workflows, and entry points. The generated description, tags, use case, and category are proposed through a pull request for human review. See [the repository catalog automation design](docs/repository-catalog-automation.md) for setup, credentials, and local commands.

GitHub Pages is deployed by `.github/workflows/deploy-pages.yml`. Configure **Settings → Pages → Build and deployment → Source** as **GitHub Actions** so GitHub uses the named `GitHub Pages Deployment` workflow instead of its built-in `pages-build-deployment` workflow.

The deployment validates public-only catalog entries and uploads only the site assets and generated catalog, not source code or configuration. Public discovery uses `GITHUB_TOKEN`; no organization-wide private-repository token is needed here.
