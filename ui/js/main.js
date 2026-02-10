marked.setOptions({
  breaks: true,
  gfm: true,
});

// Auth: redirect to welcome (/) if not logged in; show greeting with username
(async function checkAuth() {
  try {
    const res = await fetch('/api/me', { credentials: 'include' });
    if (res.status === 401) {
      window.location.href = '/';
      return;
    }
    const data = await res.json().catch(function() { return {}; });
    const greetingEl = document.getElementById('user-greeting');
    if (greetingEl && data.username) {
      greetingEl.textContent = 'Vitajte, ' + data.username;
    }
  } catch (_) {
    window.location.href = '/';
    return;
  }
})();

// Logout: link <a href="/logout">, server clears session and redirects to /

// Variant B: server-side draft. After agent response we get draft_id; "Uložiť odpoveď" sends only draft_id.
const btn = document.getElementById('btn');
const qInput = document.getElementById('q');
const out = document.getElementById('out');
let currentDraftId = null;
const PREVIEW_LEN = 80;

// User documents: selected document id for context (null = no document)
let selectedDocumentId = null;
let documentsList = [];

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
  currentDraftId = null;
  setSaveButtonState(false, false);
}

function setSaveButtonState(hasDraft, saved) {
  var saveBtn = document.getElementById('btn-save-answer');
  if (!saveBtn) return;
  if (saved) {
    saveBtn.textContent = 'Uložené';
    saveBtn.classList.add('btn-save-disabled');
    saveBtn.setAttribute('aria-disabled', 'true');
    return;
  }
  if (hasDraft) {
    saveBtn.textContent = 'Uložiť odpoveď';
    saveBtn.classList.remove('btn-save-disabled');
    saveBtn.removeAttribute('aria-disabled');
  } else {
    saveBtn.textContent = 'Uložiť odpoveď';
    saveBtn.classList.add('btn-save-disabled');
    saveBtn.setAttribute('aria-disabled', 'true');
  }
}

async function submitQuestion() {
  const q = qInput.value.trim();
  if (!q) {
    showError('Prosím, zadajte otázku.');
    return;
  }
  var docIdToSend = null;
  if (selectedDocumentId !== null && selectedDocumentId !== undefined) {
    var doc = documentsList.find(function(d) { return d.id === selectedDocumentId; });
    if (doc && doc.status === 'ready') {
      docIdToSend = selectedDocumentId;
    } else {
      if (doc && doc.status === 'processing') {
        showError('Vybraný dokument sa ešte spracováva. Počkajte na stav „ready“ alebo odošlite otázku bez dokumentu.');
        return;
      }
      if (doc && doc.status === 'error') {
        showError('Vybraný dokument má chybu. Vyberte iný alebo odošlite otázku bez dokumentu.');
        return;
      }
    }
  }
  showLoading();
  currentDraftId = null;
  setSaveButtonState(false, false);

  try {
    const body = { question: q };
    if (docIdToSend !== null) body.document_id = docIdToSend;
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      credentials: 'include'
    });

    if (response.status === 401) {
      window.location.href = '/';
      return;
    }
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    const answerText = typeof data.answer === 'string' ? data.answer.trim() : (data.answer ? String(data.answer) : '');
    var did = data.draft_id;
    currentDraftId = (did !== undefined && did !== null && Number.isFinite(Number(did))) ? Number(did) : null;
    var md = formatSources(answerText);
    out.innerHTML = marked.parse(md);
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    setSaveButtonState(!!currentDraftId, false);
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

// ---------- Documents (upload, list, select) ----------
async function loadDocuments() {
  var loadingEl = document.getElementById('documents-loading');
  var emptyEl = document.getElementById('documents-empty');
  var itemsEl = document.getElementById('documents-items');
  if (!itemsEl) return;
  if (loadingEl) loadingEl.style.display = 'block';
  if (emptyEl) emptyEl.style.display = 'none';
  itemsEl.innerHTML = '';
  try {
    var res = await fetch('/api/documents', { credentials: 'include' });
    if (res.status === 401) { window.location.href = '/'; return; }
    var data = await res.json().catch(function() { return { items: [] }; });
    documentsList = data.items || [];
    renderDocumentsList();
    if (documentsList.length === 0 && emptyEl) emptyEl.style.display = 'block';
  } catch (e) {
    if (emptyEl) { emptyEl.textContent = 'Chyba pri načítaní zoznamu.'; emptyEl.style.display = 'block'; }
  } finally {
    if (loadingEl) loadingEl.style.display = 'none';
  }
}

function renderDocumentsList() {
  var itemsEl = document.getElementById('documents-items');
  var emptyEl = document.getElementById('documents-empty');
  if (!itemsEl) return;
  itemsEl.innerHTML = '';
  documentsList.forEach(function(doc) {
    var div = document.createElement('div');
    div.className = 'doc-item';
    var statusClass = (doc.status || '').toLowerCase();
    var statusLabel = doc.status === 'ready' ? 'Pripravený' : doc.status === 'processing' ? 'Spracováva sa' : doc.status === 'error' ? 'Chyba' : doc.status || '';
    var preview = (doc.extracted_preview || doc.extracted_text || '').trim();
    if (preview.length > 300) preview = preview.slice(0, 300) + '…';
    var radioId = 'doc-radio-' + doc.id;
    var canSelect = doc.status === 'ready';
    div.innerHTML =
      (canSelect
        ? '<input type="radio" name="document-for-question" id="' + radioId + '" value="' + doc.id + '">'
        : '') +
      '<span class="doc-filename">' + escapeHtml(doc.original_filename || '') + '</span>' +
      '<span class="doc-status-badge ' + statusClass + '">' + escapeHtml(statusLabel) + '</span>' +
      (doc.error_message ? '<span class="doc-error-msg" title="' + escapeHtml(doc.error_message) + '">' + escapeHtml(doc.error_message.slice(0, 60)) + (doc.error_message.length > 60 ? '…' : '') + '</span>' : '') +
      (preview ? '<div class="doc-preview">' + escapeHtml(preview) + '</div>' : '') +
      '<button type="button" class="doc-remove" data-doc-id="' + doc.id + '">Odstrániť</button>';
    itemsEl.appendChild(div);
    if (canSelect) {
      var radio = div.querySelector('input[type="radio"]');
      radio.checked = selectedDocumentId === doc.id;
      radio.addEventListener('change', function() {
        selectedDocumentId = this.value ? parseInt(this.value, 10) : null;
        updateSelectedDocIndicator();
      });
    }
    var removeBtn = div.querySelector('.doc-remove');
    if (removeBtn) {
      removeBtn.addEventListener('click', function() {
        var id = parseInt(this.getAttribute('data-doc-id'), 10);
        deleteDocument(id);
      });
    }
  });
  if (documentsList.length === 0 && emptyEl) emptyEl.style.display = 'block';
  else if (emptyEl) emptyEl.style.display = 'none';
  updateSelectedDocIndicator();
}

function updateSelectedDocIndicator() {
  var el = document.getElementById('selected-doc-indicator');
  if (!el) return;
  if (selectedDocumentId == null) {
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  var doc = documentsList.find(function(d) { return d.id === selectedDocumentId; });
  if (!doc) {
    selectedDocumentId = null;
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  el.textContent = 'Použitý dokument pre odpoveď: ' + (doc.original_filename || 'dokument');
  el.style.display = 'block';
}

async function uploadDocument() {
  var fileInput = document.getElementById('doc-file');
  var statusEl = document.getElementById('doc-upload-status');
  var uploadBtn = document.getElementById('btn-upload-doc');
  if (!fileInput || !fileInput.files || !fileInput.files.length) {
    if (statusEl) { statusEl.textContent = 'Vyberte súbor.'; statusEl.className = 'doc-status error'; }
    return;
  }
  var file = fileInput.files[0];
  statusEl.textContent = 'Nahrávam a spracovávam...';
  statusEl.className = 'doc-status processing';
  if (uploadBtn) uploadBtn.disabled = true;
  try {
    var form = new FormData();
    form.append('file', file);
    var res = await fetch('/api/documents/upload', {
      method: 'POST',
      body: form,
      credentials: 'include'
    });
    if (res.status === 401) { window.location.href = '/'; return; }
    var data = await res.json().catch(function() { return {}; });
    if (res.ok) {
      statusEl.textContent = 'Súbor nahratý. Stav: ' + (data.status || '');
      statusEl.className = 'doc-status ' + (data.status === 'ready' ? 'ready' : data.status === 'error' ? 'error' : 'processing');
      fileInput.value = '';
      // Auto-select uploaded document so the next question uses it as context
      if (data.document_id != null) {
        selectedDocumentId = parseInt(data.document_id, 10);
      }
      loadDocuments();
    } else {
      statusEl.textContent = data.detail || 'Chyba pri nahrávaní.';
      statusEl.className = 'doc-status error';
    }
  } catch (e) {
    statusEl.textContent = 'Chyba siete pri nahrávaní.';
    statusEl.className = 'doc-status error';
  } finally {
    if (uploadBtn) uploadBtn.disabled = false;
  }
}

async function deleteDocument(docId) {
  try {
    var res = await fetch('/api/documents/' + docId, { method: 'DELETE', credentials: 'include' });
    if (res.status === 401) { window.location.href = '/'; return; }
    if (res.ok) {
      if (selectedDocumentId === docId) selectedDocumentId = null;
      loadDocuments();
    }
  } catch (e) {}
}

document.getElementById('btn-upload-doc').addEventListener('click', uploadDocument);
// Load documents when page is ready and when switching to AI assistant
if (document.getElementById('documents-list')) loadDocuments();

function showSaveToast(message) {
  var toast = document.getElementById('save-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'save-toast';
    toast.style.cssText = 'position:fixed;bottom:20px;right:20px;padding:12px 20px;background:var(--success);color:#fff;border-radius:8px;z-index:9999;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = 'block';
  setTimeout(function() { toast.style.display = 'none'; }, 3000);
}

var saveInProgress = false;

/**
 * Save current draft to history (POST /api/saved/from-draft). Uses only currentDraftId.
 * Exposed on window for onclick in HTML.
 */
window.saveAnswer = async function saveAnswer(ev) {
  if (ev) {
    ev.preventDefault();
    ev.stopPropagation();
  }
  var saveBtn = document.getElementById('btn-save-answer');
  if (saveInProgress) return;
  if (!currentDraftId) {
    if (saveBtn) saveBtn.textContent = 'Najprv získajte odpoveď';
    setTimeout(function() { if (saveBtn) saveBtn.textContent = 'Uložiť odpoveď'; }, 2000);
    return;
  }
  if (saveBtn && saveBtn.textContent === 'Uložené') return;
  saveInProgress = true;
  if (saveBtn) saveBtn.textContent = 'Ukladám...';
  try {
    var res = await fetch('/api/saved/from-draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_id: Number(currentDraftId) }),
      credentials: 'include'
    });
    if (res.status === 401) {
      window.location.href = '/';
      return;
    }
    if (res.status === 410 || res.status === 404) {
      var errData = await res.json().catch(function() { return {}; });
      var msg = (errData.detail || 'Čiernopis vypršal alebo neexistuje. Získajte odpoveď znova a uložte.');
      if (saveBtn) setSaveButtonState(false, false);
      alert(msg);
      currentDraftId = null;
      return;
    }
    if (!res.ok) {
      var errBody = await res.text();
      try { var j = JSON.parse(errBody); errBody = j.detail || errBody; } catch (e) {}
      if (saveBtn) setSaveButtonState(!!currentDraftId, false);
      alert('Chyba pri ukladaní: ' + errBody);
      return;
    }
    var json = await res.json().catch(function() { return {}; });
    currentDraftId = null;
    setSaveButtonState(false, true);
    showSaveToast('Záznam bol uložený do histórie.');
    if (json.item) prependHistoryItem(json.item);
  } catch (err) {
    if (saveBtn) setSaveButtonState(!!currentDraftId, false);
    alert('Chyba siete pri ukladaní. Skúste to znova.');
  } finally {
    saveInProgress = false;
  }
}

// Save button: ensure click is always handled (onclick in HTML + delegation fallback).
// Do not intercept clicks on links (e.g. logout <a href="/logout">).
document.body.addEventListener('click', function(e) {
  var t = e.target;
  while (t && t !== document.body) {
    if (t.tagName === 'A' && t.getAttribute('href')) return; // allow navigation
    if (t.id === 'btn-save-answer') {
      e.preventDefault();
      e.stopPropagation();
      saveAnswer(e);
      return;
    }
    t = t.parentNode;
  }
});

/** Add one saved item to the top of history list (used right after save so user sees it in História). */
function prependHistoryItem(item) {
  const listEl = document.getElementById('history-list');
  const emptyEl = document.getElementById('history-empty');
  if (!listEl) return;
  const preview = (item.question_text || '').trim();
  const short = preview.length > PREVIEW_LEN ? preview.slice(0, PREVIEW_LEN) + '…' : preview;
  const dateStr = item.created_at ? new Date(item.created_at).toLocaleString('sk-SK') : '';
  const div = document.createElement('div');
  div.className = 'history-item';
  div.dataset.id = item.id;
  div.innerHTML =
    '<div class="history-item-header">' +
      '<span class="history-item-preview">' + escapeHtml(short || '(prázdna otázka)') + '</span>' +
      '<span class="history-item-date">' + escapeHtml(dateStr) + '</span>' +
    '</div>' +
    '<div class="history-item-body">' +
      '<div class="history-item-q"><strong>Otázka</strong><div class="history-item-body-content">' + escapeHtml(item.question_text || '') + '</div></div>' +
      '<div class="history-item-a"><strong>Odpoveď</strong><div class="history-item-body-content history-answer-md">' + (item.answer_text ? marked.parse(item.answer_text) : '') + '</div></div>' +
      '<button type="button" class="history-item-remove">Odstrániť zo zoznamu</button>' +
    '</div>';
  listEl.insertBefore(div, listEl.firstChild);
  const header = div.querySelector('.history-item-header');
  const removeBtn = div.querySelector('.history-item-remove');
  header.addEventListener('click', function() { div.classList.toggle('expanded'); });
  removeBtn.addEventListener('click', function(e) { e.stopPropagation(); removeHistoryItem(item.id, div); });
  if (emptyEl) emptyEl.style.display = 'none';
}

/**
 * Load history list (GET /api/saved) and render accordion
 */
async function loadHistory() {
  const listEl = document.getElementById('history-list');
  const emptyEl = document.getElementById('history-empty');
  const loadingEl = document.getElementById('history-loading');
  if (!listEl || !emptyEl || !loadingEl) return;
  listEl.innerHTML = '';
  emptyEl.style.display = 'none';
  loadingEl.style.display = 'block';
  try {
    const res = await fetch('/api/saved', { credentials: 'include', cache: 'no-store' });
    if (res.status === 401) {
      window.location.href = '/';
      return;
    }
    const data = await res.json().catch(function() { return { items: [] }; });
    const items = data.items || [];
    loadingEl.style.display = 'none';
    if (items.length === 0) {
      emptyEl.style.display = 'block';
      return;
    }
    items.forEach(function(item) {
      const preview = (item.question_text || '').trim();
      const short = preview.length > PREVIEW_LEN ? preview.slice(0, PREVIEW_LEN) + '…' : preview;
      const dateStr = item.created_at ? new Date(item.created_at).toLocaleString('sk-SK') : '';
      const div = document.createElement('div');
      div.className = 'history-item';
      div.dataset.id = item.id;
      div.innerHTML =
        '<div class="history-item-header">' +
          '<span class="history-item-preview">' + escapeHtml(short || '(prázdna otázka)') + '</span>' +
          '<span class="history-item-date">' + escapeHtml(dateStr) + '</span>' +
        '</div>' +
        '<div class="history-item-body">' +
          '<div class="history-item-q"><strong>Otázka</strong><div class="history-item-body-content">' + escapeHtml(item.question_text || '') + '</div></div>' +
          '<div class="history-item-a"><strong>Odpoveď</strong><div class="history-item-body-content history-answer-md">' + (item.answer_text ? marked.parse(item.answer_text) : '') + '</div></div>' +
          '<button type="button" class="history-item-remove">Odstrániť zo zoznamu</button>' +
        '</div>';
      listEl.appendChild(div);
      const header = div.querySelector('.history-item-header');
      const removeBtn = div.querySelector('.history-item-remove');
      header.addEventListener('click', function() {
        div.classList.toggle('expanded');
      });
      removeBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        removeHistoryItem(item.id, div);
      });
    });
  } catch (_) {
    loadingEl.style.display = 'none';
    emptyEl.style.display = 'block';
  }
}

function escapeHtml(s) {
  const p = document.createElement('p');
  p.textContent = s;
  return p.innerHTML;
}

async function removeHistoryItem(id, rowEl) {
  try {
    const res = await fetch('/api/saved/' + id, { method: 'DELETE', credentials: 'include' });
    if (res.status === 401) { window.location.href = '/'; return; }
    if (res.ok) {
      rowEl.remove();
      const listEl = document.getElementById('history-list');
      const emptyEl = document.getElementById('history-empty');
      if (listEl && listEl.children.length === 0 && emptyEl) emptyEl.style.display = 'block';
    }
  } catch (_) {}
}

/**
 * Initialize event listeners
 */
btn.addEventListener('click', submitQuestion);

// Handle logo fallback
const logo = document.querySelector('.logo');
if (logo) {
  logo.addEventListener('error', function() {
    if (this.src.includes('logo_named.png')) {
      this.src = '/assets/logo_named.svg';
    } else if (this.src.includes('logo_named.svg')) {
      this.src = '/assets/logo.svg';
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
  if (pageId === 'page2') loadHistory();
  if (pageId === 'ai-assistant') loadDocuments();
}

navButtons.forEach(button => {
  if (button.id === 'btn-logout' || button.tagName === 'A') return; // Logout link; do not switch page
  button.addEventListener('click', () => {
    const pageId = button.dataset.page;
    switchPage(pageId);
  });
});

