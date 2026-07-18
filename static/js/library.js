const libraryGrid = document.querySelector('#libraryGrid');

if (libraryGrid) {
  const pageSize = 16;
  const cards = Array.from(libraryGrid.querySelectorAll('.library-card'));
  const searchInput = document.querySelector('#librarySearch');
  const sortSelect = document.querySelector('#librarySort');
  const resultCount = document.querySelector('#libraryResultCount');
  const emptyState = document.querySelector('#libraryFilterEmpty');
  const pagination = document.querySelector('#libraryPagination');
  const pageNumbers = document.querySelector('#libraryPageNumbers');
  const previousPage = document.querySelector('#previousLibraryPage');
  const nextPage = document.querySelector('#nextLibraryPage');
  const resetFilters = document.querySelector('#resetLibraryFilters');
  const categoryShortcuts = Array.from(document.querySelectorAll('[data-category-shortcut]'));
  const filters = {
    category: document.querySelector('#categoryFilter'),
    width: document.querySelector('#widthFilter'),
    material: document.querySelector('#materialFilter'),
    usage: document.querySelector('#usageFilter'),
    color: document.querySelector('#colorFilter'),
  };
  const modal = document.querySelector('#libraryModal');
  const modalClose = modal.querySelector('.library-modal-close');
  const modalImage = document.querySelector('#libraryModalImage');
  const modalVisual = document.querySelector('#libraryModalVisual');
  let currentPage = 1;
  let visibleCards = [];
  let activeCard = null;

  function sortedCards() {
    const sortMode = sortSelect.value;
    return [...cards].sort((left, right) => {
      if (sortMode === 'id') return Number(left.dataset.id) - Number(right.dataset.id);
      return Number(right.dataset[sortMode]) - Number(left.dataset[sortMode]);
    });
  }

  function matchesFilters(card) {
    const query = searchInput.value.trim().toLocaleLowerCase('zh-CN');
    if (query && !card.dataset.search.toLocaleLowerCase('zh-CN').includes(query)) return false;
    return Object.entries(filters).every(([field, control]) => {
      return !control.value || card.dataset[field] === control.value;
    });
  }

  function renderPage() {
    const totalPages = Math.max(1, Math.ceil(visibleCards.length / pageSize));
    currentPage = Math.min(currentPage, totalPages);
    const pageStart = (currentPage - 1) * pageSize;
    const pageItems = new Set(visibleCards.slice(pageStart, pageStart + pageSize));

    cards.forEach((card) => {
      card.hidden = !pageItems.has(card);
    });
    resultCount.textContent = visibleCards.length;
    emptyState.hidden = visibleCards.length !== 0;
    pagination.hidden = visibleCards.length === 0;
    previousPage.disabled = currentPage === 1;
    nextPage.disabled = currentPage === totalPages;

    pageNumbers.replaceChildren();
    for (let page = 1; page <= totalPages; page += 1) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = page;
      button.className = page === currentPage ? 'is-active' : '';
      button.setAttribute('aria-label', `第 ${page} 页`);
      if (page === currentPage) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', () => changePage(page));
      pageNumbers.append(button);
    }
  }

  function updateCatalog() {
    visibleCards = sortedCards().filter(matchesFilters);
    sortedCards().forEach((card) => libraryGrid.append(card));
    currentPage = 1;
    renderPage();
    categoryShortcuts.forEach((button) => {
      button.classList.toggle('is-active', button.dataset.categoryShortcut === filters.category.value);
    });
  }

  function changePage(page) {
    currentPage = page;
    renderPage();
    document.querySelector('.archive-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function setText(selector, value) {
    document.querySelector(selector).textContent = value;
  }

  function openMaterial(card) {
    activeCard = card;
    const data = card.dataset;
    setText('#libraryModalNumber', String(Number(data.id)).padStart(3, '0'));
    setText('#libraryModalCategory', data.category);
    setText('#libraryModalTitle', data.code);
    setText('#libraryModalStage', data.lifecycle);
    setText('#libraryModalDescription', data.description);
    setText('#libraryModalWidth', data.width);
    setText('#libraryModalMaterial', data.material);
    setText('#libraryModalUsage', data.usage);
    setText('#libraryModalColor', data.color);
    setText('#libraryModalStatus', data.status);
    setText('#libraryModalQuarter', data.quarter);
    setText('#libraryModalSales', `${data.salesLabel} m`);
    setText('#libraryModalPrice', data.priceLabel === '--' ? '--' : `¥${data.priceLabel}/m`);

    if (data.image) {
      modalImage.src = data.image;
      modalImage.alt = `${data.code} ${data.category}蕾丝图案`;
      modalVisual.classList.remove('is-empty');
    } else {
      modalImage.removeAttribute('src');
      modalImage.alt = '';
      modalVisual.classList.add('is-empty');
    }

    modal.hidden = false;
    document.body.classList.add('modal-open');
    modalClose.focus();
  }

  function closeMaterial() {
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    if (activeCard) activeCard.focus();
  }

  searchInput.addEventListener('input', updateCatalog);
  sortSelect.addEventListener('change', updateCatalog);
  Object.values(filters).forEach((control) => control.addEventListener('change', updateCatalog));
  resetFilters.addEventListener('click', () => {
    searchInput.value = '';
    Object.values(filters).forEach((control) => {
      control.value = '';
    });
    updateCatalog();
  });
  categoryShortcuts.forEach((button) => {
    button.addEventListener('click', () => {
      filters.category.value =
        filters.category.value === button.dataset.categoryShortcut ? '' : button.dataset.categoryShortcut;
      updateCatalog();
      document.querySelector('.archive-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  previousPage.addEventListener('click', () => changePage(currentPage - 1));
  nextPage.addEventListener('click', () => changePage(currentPage + 1));
  cards.forEach((card) => card.addEventListener('click', () => openMaterial(card)));
  modal.querySelectorAll('[data-close-library-modal]').forEach((button) => {
    button.addEventListener('click', closeMaterial);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) closeMaterial();
  });

  updateCatalog();
}
