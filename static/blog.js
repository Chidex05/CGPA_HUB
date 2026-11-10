const articleSearch = document.getElementById("article-search");
const articleCards = Array.from(document.querySelectorAll(".article-card"));
const filterButtons = Array.from(document.querySelectorAll(".filter-chip"));
const articleCount = document.getElementById("article-count");
const emptyState = document.getElementById("empty-state");

let activeFilter = "all";

function updateArticles() {
  const query = articleSearch.value.trim().toLocaleLowerCase();
  let visibleCount = 0;

  articleCards.forEach((card) => {
    const matchesCategory = activeFilter === "all" || card.dataset.category === activeFilter;
    const searchableText = `${card.dataset.search} ${card.textContent}`.toLocaleLowerCase();
    const matchesQuery = !query || searchableText.includes(query);
    const isVisible = matchesCategory && matchesQuery;

    card.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });

  articleCount.textContent = `${visibleCount} ${visibleCount === 1 ? "article" : "articles"}`;
  emptyState.hidden = visibleCount > 0;
}

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activeFilter = button.dataset.filter;
    filterButtons.forEach((filterButton) => {
      const isActive = filterButton === button;
      filterButton.classList.toggle("is-active", isActive);
      filterButton.setAttribute("aria-pressed", String(isActive));
    });
    updateArticles();
  });
});

articleSearch.addEventListener("input", updateArticles);

document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
  ) {
    event.preventDefault();
    articleSearch.focus();
  }
});
