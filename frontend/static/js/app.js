'use strict';

// ─── API Client ────────────────────────────────────────────────────────────────

const API = {
  base: '/api',
  async request(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(`${this.base}${path}`, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed (${res.status})`);
      }
      if (res.status === 204) return null;
      return res.json();
    } catch (err) {
      if (err.name === 'TypeError') {
        throw new Error('Cannot reach the server. Is the backend running?');
      }
      throw err;
    }
  },
  get:    (path)        => API.request('GET', path),
  post:   (path, body)  => API.request('POST', path, body),
  patch:  (path, body)  => API.request('PATCH', path, body),
  delete: (path)        => API.request('DELETE', path),

  /** Upload a file using multipart/form-data (no Content-Type override). */
  async upload(path, formData) {
    try {
      const res = await fetch(`${this.base}${path}`, { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Upload failed (${res.status})`);
      }
      return res.json();
    } catch (err) {
      if (err.name === 'TypeError') {
        throw new Error('Cannot reach the server. Is the backend running?');
      }
      throw err;
    }
  },
};

// ─── State ─────────────────────────────────────────────────────────────────────

const state = {
  currentConversationId: null,
  isLoading:             false,
  editingNoteId:         null,
  /** Active file: { id: string, name: string, chunks: number } | null */
  activeFile:            null,
};

// ─── DOM Helpers ───────────────────────────────────────────────────────────────

const $ = (id) => document.getElementById(id);

const els = {
  messagesArea:     $('messagesArea'),
  welcomeSplash:    $('welcomeSplash'),
  messageInput:     $('messageInput'),
  sendBtn:          $('sendBtn'),
  micBtn:           $('micBtn'),
  uploadBtn:        $('uploadBtn'),
  fileInput:        $('fileInput'),
  fileBadgeBar:     $('fileBadgeBar'),
  fileBadge:        $('fileBadge'),
  fileBadgeName:    $('fileBadgeName'),
  fileBadgeMeta:    $('fileBadgeMeta'),
  fileBadgeDismiss: $('fileBadgeDismiss'),
  fileModeChip:     $('fileModeChip'),
  fileModeChipName: $('fileModeChipName'),
  chatTitle:        $('chatTitle'),
  statusText:       $('statusText'),
  statusDot:        $('statusDot'),
  newChatBtn:       $('newChatBtn'),
  notesGrid:        $('notesGrid'),
  noteEditor:       $('noteEditor'),
  noteTitleInput:   $('noteTitleInput'),
  noteContentInput: $('noteContentInput'),
  saveNoteBtn:      $('saveNoteBtn'),
  cancelNoteBtn:    $('cancelNoteBtn'),
  addNoteBtn:       $('addNoteBtn'),
  historyList:      $('historyList'),
  toastContainer:   $('toastContainer'),
};

// ─── Markdown Renderer (marked + DOMPurify) ────────────────────────────────────

if (typeof marked !== 'undefined') {
  marked.setOptions({ gfm: true, breaks: true });
}

function renderMarkdown(content) {
  if (typeof marked === 'undefined') return escapeHtml(content);
  const raw = marked.parse(content);
  return typeof DOMPurify !== 'undefined'
    ? DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
    : raw;
}

// ─── Tab Navigation ────────────────────────────────────────────────────────────

function switchTab(tabName) {
  ['Chat', 'Notes', 'History'].forEach((t) => {
    $(`tab${t}`).classList.toggle('hidden', t.toLowerCase() !== tabName);
  });
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  if (tabName === 'notes')   loadNotes();
  if (tabName === 'history') loadHistory();
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ─── File Upload ───────────────────────────────────────────────────────────────

els.uploadBtn.addEventListener('click', () => els.fileInput.click());

els.fileInput.addEventListener('change', async () => {
  const file = els.fileInput.files[0];
  if (!file) return;

  // Reset input so re-selecting same file fires the event
  els.fileInput.value = '';

  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'txt'].includes(ext)) {
    showToast('Only PDF and TXT files are supported.', 'error');
    return;
  }

  const MAX_MB = 10;
  if (file.size > MAX_MB * 1024 * 1024) {
    showToast(`File too large (max ${MAX_MB} MB).`, 'error');
    return;
  }

  // Show uploading state
  els.uploadBtn.classList.add('uploading');
  els.uploadBtn.title = 'Uploading…';
  showToast(`Uploading "${file.name}"…`, '');

  try {
    const fd = new FormData();
    fd.append('file', file);
    const data = await API.upload('/upload', fd);
    setActiveFile({ id: data.file_id, name: data.filename, chunks: data.chunk_count });
    showToast(`✅ "${data.filename}" ready — ${data.chunk_count} chunks indexed.`, 'success');
  } catch (err) {
    showToast(err.message || 'Upload failed.', 'error');
  } finally {
    els.uploadBtn.classList.remove('uploading');
    els.uploadBtn.title = 'Upload PDF or TXT';
  }
});

function setActiveFile(file) {
  state.activeFile = file;

  // Update file badge bar
  els.fileBadgeName.textContent = file.name;
  els.fileBadgeMeta.textContent = `${file.chunks} chunks`;
  els.fileBadgeBar.classList.remove('hidden');

  // Update header chip
  els.fileModeChipName.textContent = file.name;
  els.fileModeChip.classList.remove('hidden');

  // Update input placeholder
  els.messageInput.placeholder = `Ask about "${file.name}"…`;

  // Update send button title
  els.uploadBtn.classList.add('active');
}

function clearActiveFile() {
  state.activeFile = null;

  els.fileBadgeBar.classList.add('hidden');
  els.fileModeChip.classList.add('hidden');
  els.messageInput.placeholder = 'Message Jarvis...';
  els.uploadBtn.classList.remove('active');
}

els.fileBadgeDismiss.addEventListener('click', () => {
  clearActiveFile();
  showToast('Document removed. Back to normal chat.', '');
});

// ─── Speech Recognition ────────────────────────────────────────────────────────

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = SpeechRecognition ? new SpeechRecognition() : null;

function startListening() {
  if (!recognition) {
    showToast('Speech recognition is not supported in this browser.', 'error');
    return;
  }
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    els.messageInput.placeholder = 'Listening…';
    if (els.micBtn) els.micBtn.style.color = 'var(--error)';
  };
  recognition.onspeechend = () => recognition.stop();
  recognition.onend = () => {
    els.messageInput.placeholder = state.activeFile
      ? `Ask about "${state.activeFile.name}"…`
      : 'Message Jarvis...';
    if (els.micBtn) els.micBtn.style.color = 'var(--text-dim)';
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (transcript) {
      els.messageInput.value = transcript;
      autoResizeTextarea();
      sendMessage();
    } else {
      showToast('Empty input. Please speak clearly.', 'error');
    }
  };
  recognition.onerror = (event) => {
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      showToast('Microphone access denied. Please allow permissions.', 'error');
    } else if (event.error === 'no-speech') {
      showToast('No speech detected. Please try again.', 'error');
    } else {
      showToast('Microphone error: ' + event.error, 'error');
    }
  };
  try { recognition.start(); } catch { showToast('Failed to start microphone.', 'error'); }
}

if (els.micBtn) els.micBtn.addEventListener('click', startListening);

// ─── Text-to-Speech (per-message) ─────────────────────────────────────────────

function attachSpeakButton(btn, content) {
  let isSpeaking = false;
  btn.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) {
      showToast('Text-to-speech is not supported in this browser.', 'error');
      return;
    }
    if (isSpeaking) { window.speechSynthesis.cancel(); return; }
    const utter = new SpeechSynthesisUtterance(content);
    utter.onstart = () => { isSpeaking = true;  btn.innerHTML = '⛔ Stop'; };
    utter.onend   = () => { isSpeaking = false; btn.innerHTML = '🔊 Speak'; };
    utter.onerror = () => { isSpeaking = false; btn.innerHTML = '🔊 Speak'; };
    window.speechSynthesis.speak(utter);
  });
}

// ─── Chat Messages ─────────────────────────────────────────────────────────────

function createMessageEl(role, content) {
  const isUser = role === 'user';
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = `bubble${isUser ? '' : ' markdown-body'}`;
  if (isUser) {
    bubbleDiv.textContent = content;
  } else {
    bubbleDiv.innerHTML = renderMarkdown(content);
  }

  const avatarDiv = document.createElement('div');
  avatarDiv.className = 'avatar';
  avatarDiv.textContent = isUser ? '👤' : '⚡';

  const wrapperDiv = document.createElement('div');
  wrapperDiv.style.cssText = 'display:flex; flex-direction:column; gap:4px; max-width:85%;';
  wrapperDiv.appendChild(bubbleDiv);

  if (!isUser) {
    const speakBtn = document.createElement('button');
    speakBtn.className = 'speak-btn';
    speakBtn.title = 'Play / Stop';
    speakBtn.innerHTML = '🔊 Speak';
    wrapperDiv.appendChild(speakBtn);
    attachSpeakButton(speakBtn, content);
  }

  div.appendChild(avatarDiv);
  div.appendChild(wrapperDiv);
  return div;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'message assistant typing-bubble';
  div.id = 'typingIndicator';
  div.innerHTML = `
    <div class="avatar">⚡</div>
    <div class="bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  els.messagesArea.appendChild(div);
  scrollBottom();
}

function removeTyping() {
  const el = $('typingIndicator');
  if (el) el.remove();
}

function scrollBottom() { els.messagesArea.scrollTop = els.messagesArea.scrollHeight; }
function hideSplash()   { if (els.welcomeSplash) els.welcomeSplash.style.display = 'none'; }

// ─── Send Message ─────────────────────────────────────────────────────────────

async function sendMessage() {
  const content = els.messageInput.value.trim();
  if (!content || state.isLoading) return;

  hideSplash();
  state.isLoading = true;
  els.sendBtn.disabled = true;
  els.messageInput.value = '';
  autoResizeTextarea();

  const userMsgEl = createMessageEl('user', content);
  els.messagesArea.appendChild(userMsgEl);
  scrollBottom();
  showTyping();

  try {
    let data;

    if (state.activeFile) {
      // ── File Chat Mode ─────────────────────────────────────────────────────
      data = await API.post('/file-chat', {
        query:           content,
        file_id:         state.activeFile.id,
        conversation_id: state.currentConversationId || undefined,
      });
    } else {
      // ── Normal Chat Mode ───────────────────────────────────────────────────
      data = await API.post('/chat', {
        message:         content,
        conversation_id: state.currentConversationId || undefined,
      });
    }

    state.currentConversationId = data.conversation_id;
    removeTyping();
    els.messagesArea.appendChild(createMessageEl('assistant', data.reply));
    scrollBottom();

    if (!els.chatTitle.dataset.set) {
      const prefix = state.activeFile ? `📄 ` : '';
      els.chatTitle.textContent = prefix + content.substring(0, 42) + (content.length > 42 ? '…' : '');
      els.chatTitle.dataset.set = '1';
    }
  } catch (err) {
    removeTyping();
    if (userMsgEl && userMsgEl.parentNode) userMsgEl.parentNode.removeChild(userMsgEl);
    els.messageInput.value = content;
    showToast(err.message || 'Failed to send message.', 'error');
  } finally {
    state.isLoading = false;
    els.sendBtn.disabled = false;
    els.messageInput.focus();
  }
}

els.sendBtn.addEventListener('click', sendMessage);
els.messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

function autoResizeTextarea() {
  const ta = els.messageInput;
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
}
els.messageInput.addEventListener('input', autoResizeTextarea);

document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    els.messageInput.value = chip.dataset.msg;
    sendMessage();
  });
});

els.newChatBtn.addEventListener('click', () => {
  state.currentConversationId = null;
  clearActiveFile();
  els.chatTitle.textContent = 'New Conversation';
  delete els.chatTitle.dataset.set;
  els.messagesArea.innerHTML = '';
  els.messagesArea.appendChild(els.welcomeSplash);
  els.welcomeSplash.style.display = '';
  switchTab('chat');
  els.messageInput.focus();
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
});

// ─── Notes ─────────────────────────────────────────────────────────────────────

async function loadNotes() {
  try {
    const notes = await API.get('/notes');
    renderNotes(notes);
  } catch { showToast('Failed to load notes.', 'error'); }
}

function renderNotes(notes) {
  if (!notes.length) {
    els.notesGrid.innerHTML = `<div class="empty-state"><span>📝</span><p>No notes yet. Create your first note!</p></div>`;
    return;
  }
  els.notesGrid.innerHTML = notes.map((n) => `
    <div class="note-card" data-id="${n.id}">
      <h3>${escapeHtml(n.title)}</h3>
      <p>${escapeHtml(n.content)}</p>
      <div class="note-card-meta">
        <span>${formatDate(n.created_at)}</span>
        <div class="note-actions">
          <button class="note-action-btn edit-note" data-id="${n.id}">✏️ Edit</button>
          <button class="note-action-btn delete delete-note" data-id="${n.id}">🗑️ Delete</button>
        </div>
      </div>
    </div>
  `).join('');
  document.querySelectorAll('.edit-note').forEach((btn) => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); openEditNote(btn.dataset.id, notes); });
  });
  document.querySelectorAll('.delete-note').forEach((btn) => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); deleteNote(btn.dataset.id); });
  });
}

function openEditor(title = '', content = '', noteId = null) {
  state.editingNoteId = noteId;
  els.noteTitleInput.value = title;
  els.noteContentInput.value = content;
  els.noteEditor.classList.remove('hidden');
  els.noteTitleInput.focus();
}
function openEditNote(id, notes) {
  const note = notes.find((n) => n.id === parseInt(id));
  if (note) openEditor(note.title, note.content, note.id);
}

els.addNoteBtn.addEventListener('click', () => openEditor());
els.cancelNoteBtn.addEventListener('click', () => {
  els.noteEditor.classList.add('hidden');
  state.editingNoteId = null;
});
els.saveNoteBtn.addEventListener('click', async () => {
  const title   = els.noteTitleInput.value.trim();
  const content = els.noteContentInput.value.trim();
  if (!title)   { showToast('Please enter a title.', 'error'); return; }
  if (!content) { showToast('Please enter content.', 'error'); return; }
  try {
    if (state.editingNoteId) {
      await API.patch(`/notes/${state.editingNoteId}`, { title, content });
      showToast('Note updated!', 'success');
    } else {
      await API.post('/notes', { title, content });
      showToast('Note saved!', 'success');
    }
    els.noteEditor.classList.add('hidden');
    state.editingNoteId = null;
    loadNotes();
  } catch (err) { showToast(err.message || 'Failed to save note.', 'error'); }
});

async function deleteNote(id) {
  if (!confirm('Delete this note?')) return;
  try {
    await API.delete(`/notes/${id}`);
    showToast('Note deleted.', 'success');
    loadNotes();
  } catch (err) { showToast(err.message || 'Failed to delete note.', 'error'); }
}

// ─── History ───────────────────────────────────────────────────────────────────

async function loadHistory() {
  try {
    const convos = await API.get('/conversations');
    renderHistory(convos);
  } catch { showToast('Failed to load history.', 'error'); }
}

function renderHistory(convos) {
  if (!convos.length) {
    els.historyList.innerHTML = `<div class="empty-state"><span>🕑</span><p>No conversations yet. Start chatting!</p></div>`;
    return;
  }
  els.historyList.innerHTML = convos.map((c) => `
    <div class="history-item" data-id="${c.id}">
      <div class="history-item-info">
        <h4>${escapeHtml(c.title)}</h4>
        <span>${formatDate(c.created_at)}</span>
      </div>
      <div class="history-item-actions">
        <button class="note-action-btn delete delete-convo" data-id="${c.id}">🗑️</button>
      </div>
    </div>
  `).join('');
  document.querySelectorAll('.history-item').forEach((item) => {
    item.addEventListener('click', (e) => {
      if (e.target.closest('.delete-convo')) return;
      loadConversation(item.dataset.id);
    });
  });
  document.querySelectorAll('.delete-convo').forEach((btn) => {
    btn.addEventListener('click', async (e) => { e.stopPropagation(); await deleteConversation(btn.dataset.id); });
  });
}

async function loadConversation(id) {
  try {
    const [messages, convo] = await Promise.all([
      API.get(`/conversations/${id}/messages`),
      API.get(`/conversations/${id}`),
    ]);
    state.currentConversationId = parseInt(id);
    els.chatTitle.textContent = convo.title;
    els.chatTitle.dataset.set = '1';
    els.messagesArea.innerHTML = '';
    if (messages.length === 0) {
      els.messagesArea.appendChild(els.welcomeSplash);
      els.welcomeSplash.style.display = '';
    } else {
      hideSplash();
      messages.forEach((m) => els.messagesArea.appendChild(createMessageEl(m.role, m.content)));
      scrollBottom();
    }
    switchTab('chat');
  } catch { showToast('Failed to load conversation.', 'error'); }
}

async function deleteConversation(id) {
  if (!confirm('Archive this conversation?')) return;
  try {
    await API.delete(`/conversations/${id}`);
    if (state.currentConversationId === parseInt(id)) state.currentConversationId = null;
    showToast('Conversation archived.', 'success');
    loadHistory();
  } catch (err) { showToast(err.message || 'Failed to archive conversation.', 'error'); }
}

// ─── Utilities ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function showToast(msg, type = '') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  els.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}

// ─── Health Check ──────────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const data = await API.get('/health');
    const aiOk = data?.ai_service?.status === 'ok';
    els.statusDot.style.background = aiOk ? 'var(--success)' : 'var(--error)';
    els.statusDot.style.boxShadow  = `0 0 6px ${aiOk ? 'var(--success)' : 'var(--error)'}`;
    els.statusText.textContent = aiOk ? 'Online' : 'AI Error';
  } catch {
    els.statusDot.style.background = 'var(--error)';
    els.statusDot.style.boxShadow  = '0 0 6px var(--error)';
    els.statusText.textContent = 'Offline';
  }
}

// ─── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  els.messageInput.focus();
});
