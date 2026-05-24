// Shared per-page table search box. Mirrors cols-filters.js: binds the page's
// #search input, debounces, broadcasts 'ft-search-changed', and exposes
// window.FTSearch.term(). Search is transient — never persisted, cleared on
// reload. Each page applies FT.matchesSearch over its own in-memory rows.
(() => {
  const input = document.querySelector('#search');
  if (!input) return;

  let term = '';
  let timer = 0;

  // Wrap the input so a custom clear button can sit inside with a comfortable
  // hit area — the native type=search × is tiny and unstyleable.
  const box = document.createElement('span');
  box.className = 'search-box';
  input.parentNode.insertBefore(box, input);
  box.appendChild(input);
  const clearBtn = document.createElement('button');
  clearBtn.type = 'button';
  clearBtn.className = 'search-clear';
  clearBtn.setAttribute('aria-label', 'Clear search');
  clearBtn.textContent = '×';
  box.appendChild(clearBtn);

  function syncClear() {
    clearBtn.classList.toggle('visible', input.value.length > 0);
  }

  function commit() {
    const next = input.value.trim();
    if (next === term) return;
    term = next;
    window.dispatchEvent(new CustomEvent('ft-search-changed', { detail: term }));
  }

  function clearSearch(refocus) {
    input.value = '';
    syncClear();
    clearTimeout(timer);
    commit();
    if (refocus) input.focus();
    else input.blur();
  }

  // Debounced so fast typing never thrashes a re-render.
  input.addEventListener('input', () => {
    syncClear();
    clearTimeout(timer);
    timer = setTimeout(commit, 80);
  });

  clearBtn.addEventListener('click', () => clearSearch(true));

  // Esc clears + blurs.
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') clearSearch(false);
  });

  // "/" focuses search from anywhere — unless already typing in a field.
  document.addEventListener('keydown', (e) => {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA'
      || t.tagName === 'SELECT' || t.isContentEditable)) return;
    e.preventDefault();
    input.focus();
    input.select();
  });

  window.FTSearch = { term: () => term };
})();
