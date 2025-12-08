/**
 * Main application JavaScript
 * Handles form submission, API communication, and markdown rendering
 */

// Initialize marked.js for markdown rendering
marked.setOptions({
  breaks: true,
  gfm: true,
});

// DOM elements
const btn = document.getElementById('btn');
const qInput = document.getElementById('q');
const out = document.getElementById('out');

/**
 * Format sources section in markdown
 * @param {string} md - Markdown text
 * @returns {string} - Formatted markdown
 */
function formatSources(md) {
  const zdrojeMatch = md.match(/## 📚 Zdroje\n\n(.*?)(?=\n\n|$)/s);
  if (!zdrojeMatch) {
    return md;
  }

  const zdrojeText = zdrojeMatch[1];
  const sources = zdrojeText.split('\n').filter(line => line.trim());
  
  const formattedSources = sources.map(line => {
    line = line.trim();
    
    // Already formatted as list item
    if (line.startsWith('-')) {
      return line;
    }
    
    // Format: "1. Text" -> "- Text"
    const numMatch = line.match(/^(\d+)\.\s*(.+)$/);
    if (numMatch) {
      return `- ${numMatch[2]}`;
    }
    
    // Format: "[1] Text" -> "- [1] Text"
    const bracketMatch = line.match(/^\[(\d+)\]\s*(.+)$/);
    if (bracketMatch) {
      return `- [${bracketMatch[1]}] ${bracketMatch[2]}`;
    }
    
    // Default: add list marker
    return `- ${line}`;
  }).join('\n');

  return md.replace(/## 📚 Zdroje\n\n.*/s, `## 📚 Zdroje\n\n${formattedSources}\n`);
}

/**
 * Show loading state
 */
function showLoading() {
  btn.disabled = true;
  btn.textContent = 'Spracovávam...';
  out.innerHTML = '<div class="loading"></div> <span>AI spracováva vašu otázku...</span>';
}

/**
 * Hide loading state
 */
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

/**
 * Send question to API and display response
 */
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

    // Format sources section
    md = formatSources(md);

    // Render markdown
    out.innerHTML = marked.parse(md);

    // Smooth scroll to answer
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  } catch (error) {
    const errorMessage = error.message || 'Nepodarilo sa spracovať požiadavku. Skúste to znova.';
    showError(errorMessage);
    console.error('Error:', error);
  } finally {
    hideLoading();
  }
}

/**
 * Handle keyboard shortcuts
 */
qInput.addEventListener('keydown', (e) => {
  // Ctrl/Cmd + Enter to submit
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

/**
 * Page navigation functionality
 */
const navButtons = document.querySelectorAll('.nav-button');
const pages = document.querySelectorAll('.page');

function switchPage(pageId) {
  // Hide all pages
  pages.forEach(page => {
    page.classList.remove('active');
  });

  // Show selected page
  const targetPage = document.getElementById(`page-${pageId}`);
  if (targetPage) {
    targetPage.classList.add('active');
  }

  // Update active button
  navButtons.forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.page === pageId) {
      btn.classList.add('active');
    }
  });
}

// Add click handlers to navigation buttons
navButtons.forEach(button => {
  button.addEventListener('click', () => {
    const pageId = button.dataset.page;
    switchPage(pageId);
  });
});
