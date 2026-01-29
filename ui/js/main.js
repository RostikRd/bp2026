marked.setOptions({
  breaks: true,
  gfm: true,
});

const btn = document.getElementById('btn');
const qInput = document.getElementById('q');
const out = document.getElementById('out');

function formatSources(md) {
  const zdrojeMatch = md.match(/## 📚 Zdroje\n(.*?)(?=\n## |\n⚖️ |$)/s);
  if (!zdrojeMatch) {
    return md;
  }
  return md;
}

/**
 * Show loading state
 */
function showLoading() {
  btn.disabled = true;
  btn.textContent = 'Spracovávam...';
  out.innerHTML = '<div class="loading"></div> <span>AI spracováva vašu otázku...</span>';
}

function hideLoading() {
  btn.disabled = false;
  btn.textContent = 'Odoslať otázku';
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
  out.innerHTML = `<div class="error"><strong>Chyba:</strong> ${message}</div>`;
}

async function submitQuestion() {
  const q = qInput.value.trim();
  
  if (!q) {
    showError('Prosím, zadajte otázku.');
    return;
  }

  showLoading();

  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    let md = data.answer ?? '';
    md = formatSources(md);
    out.innerHTML = marked.parse(md);
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  } catch (error) {
    const errorMessage = error.message || 'Nepodarilo sa spracovať požiadavku. Skúste to znova.';
    showError(errorMessage);
  } finally {
    hideLoading();
  }
}

qInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    submitQuestion();
  }
});

/**
 * Initialize event listeners
 */
btn.addEventListener('click', submitQuestion);

// Handle logo fallback
const logo = document.querySelector('.logo');
if (logo) {
  logo.addEventListener('error', function() {
    if (this.src.includes('logo_named.png')) {
      this.src = '/logo.png';
    }
  });
}

const navButtons = document.querySelectorAll('.nav-button');
const pages = document.querySelectorAll('.page');

function switchPage(pageId) {
  pages.forEach(page => {
    page.classList.remove('active');
  });
  const targetPage = document.getElementById(`page-${pageId}`);
  if (targetPage) {
    targetPage.classList.add('active');
  }
  navButtons.forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.page === pageId) {
      btn.classList.add('active');
    }
  });
}

navButtons.forEach(button => {
  button.addEventListener('click', () => {
    const pageId = button.dataset.page;
    switchPage(pageId);
  });
});
