# MSFTSE Organization Site

The public GitHub Pages catalog for practical accelerators built by the MSFTSE Solution Engineering Lab.

Visit: https://msftse-org.github.io/

The site is static and requires no build step. `index.html` loads repository cards from `data/repositories.json`, while `catalog.js` provides client-side search and filtering.

Preview it through a local HTTP server so the browser can load the JSON catalog:

```bash
python3 -m http.server 8000
```

The repository catalog is synchronized from the GitHub organization every 12 hours. Changes are proposed through a pull request for human review. See [the repository catalog automation design](docs/repository-catalog-automation.md) for classification rules, credentials, and local commands.
