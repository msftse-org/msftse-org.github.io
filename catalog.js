(() => {
  const filterButtons = [...document.querySelectorAll("[data-filter]")];
  const repositoryGrid = document.querySelector("#repository-grid");
  const resultCount = document.querySelector("#result-count");
  const emptyState = document.querySelector("#empty-state");
  const catalogStatus = document.querySelector("#catalog-status");
  const searchInput = document.querySelector("#search-input");

  let activeCategory = "All";
  let cards = [];
  let catalogReady = false;

  const createElement = (tagName, className, text) => {
    const element = document.createElement(tagName);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  const createRepositoryCard = (repository, index) => {
    const accent = repository.accent === "violet" ? "violet" : "cyan";
    const card = createElement("article", `repoCard ${accent}`);
    card.dataset.category = repository.category;
    card.dataset.search = [
      repository.name,
      repository.title,
      repository.useCase,
      repository.summary,
      repository.category,
      repository.language,
      ...(repository.topics || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    const cardTop = createElement("div", "cardTop");
    cardTop.append(
      createElement("span", "repoNumber", `/${String(index + 1).padStart(2, "0")}`),
      createElement("span", "visibility", repository.visibility || "Public"),
    );

    const signal = createElement("div", "signal");
    signal.setAttribute("aria-hidden", "true");
    signal.append(document.createElement("span"), document.createElement("span"), document.createElement("span"));

    const footer = createElement("div", "cardFooter");
    const repositoryLink = createElement("a", "", "View repository ");
    repositoryLink.href = repository.url;
    repositoryLink.rel = "noreferrer";
    repositoryLink.setAttribute("aria-label", `View ${repository.title} repository`);
    const externalIcon = createElement("span", "", "↗");
    externalIcon.setAttribute("aria-hidden", "true");
    repositoryLink.append(externalIcon);
    footer.append(createElement("span", "", repository.language || "Multiple"), repositoryLink);

    card.append(
      cardTop,
      signal,
      createElement("p", "useCase", repository.useCase),
      createElement("span", "categoryLabel", repository.category),
      createElement("h2", "", repository.title),
      createElement("p", "summary", repository.summary),
      footer,
    );

    return card;
  };

  const renderCatalog = () => {
    if (!catalogReady) return;

    const query = searchInput.value.trim().toLowerCase();
    let shown = 0;

    cards.forEach((card) => {
      const matchesCategory = activeCategory === "All" || card.dataset.category === activeCategory;
      const matchesSearch = !query || card.dataset.search.includes(query);
      const visible = matchesCategory && matchesSearch;
      card.hidden = !visible;
      if (visible) shown += 1;
    });

    resultCount.textContent = `${String(shown).padStart(2, "0")} / SHOWN`;
    emptyState.hidden = shown !== 0;
  };

  const loadCatalog = async () => {
    try {
      const response = await fetch("data/repositories.json", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Catalog request failed with status ${response.status}`);

      const catalog = await response.json();
      if (!Array.isArray(catalog.repositories)) throw new Error("Catalog response is missing repositories");

      cards = catalog.repositories.map(createRepositoryCard);
      repositoryGrid.prepend(...cards);
      catalogStatus.hidden = true;
      catalogReady = true;
      renderCatalog();
    } catch (error) {
      console.error("Unable to load repository catalog", error);
      catalogStatus.classList.add("error");
      catalogStatus.textContent = "The repository catalog could not be loaded. Visit the MSFTSE GitHub organization to browse repositories.";
      resultCount.textContent = "-- / SHOWN";
    }
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.filter;

      filterButtons.forEach((item) => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", String(active));
      });
      renderCatalog();
    });
  });

  searchInput.addEventListener("input", renderCatalog);
  loadCatalog();
})();
