'use strict';

const API = {
  base: '/api',
  async request(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${this.base}${path}`, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    if (res.status === 204) return null;
    return res.json();
  },
  get: (path) => API.request('GET', path),
  post: (path, body) => API.request('POST', path, body),
  patch: (path, body) => API.request('PATCH', path, body),
  delete: (path) => API.request('DELETE', path),
};

const state = {
  currentConversationId: null,
  isLoading: false,
  editingNoteId: null,
};

const $ = (id) => document.getElementById(id);

const els = {
  messagesArea:     $('messagesArea'),
  welcomeSplash:    $('welcomeSplash'),
  messageInput:     $('messageInput'),
  sendBtn:          $('sendBtn'),
  micBtn:           $('micBtn'),
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

function switchTab(tabName) {
  ['Chat', 'Notes', 'History'].forEach((t) => {
    $(`tab${t}`).classList.toggle('hidden', t.toLowerCase() !== tabName);
  });
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  if (tabName === 'notes') loadNotes();
  if (tabName === 'history') loadHistory();
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ─── Speech-to-Text & Text-to-Speech ────────────────────────────────────────

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
    els.messageInput.placeholder = 'Listening...';
    if (els.micBtn) els.micBtn.style.color = 'var(--error, #ff4757)';
  };
  
  recognition.onspeechend = () => {
    recognition.stop();
    els.messageInput.placeholder = 'Message Jarvis...';
    if (els.micBtn) els.micBtn.style.color = 'var(--text-dim, #999)';
  };
  
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    if (transcript.trim()) {
      els.messageInput.value = transcript;
      sendMessage();
    } else {
      showToast('Empty input. Please speak clearly.', 'error');
    }
  };
  
  recognition.onerror = (event) => {
    els.messageInput.placeholder = 'Message Jarvis...';
    if (els.micBtn) els.micBtn.style.color = 'var(--text-dim, #999)';
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      showToast('Microphone access denied. Please allow permissions.', 'error');
    } else if (event.error === 'no-speech') {
      showToast('No speech detected. Please try again.', 'error');
    } else {
      showToast('Microphone error: ' + event.error, 'error');
    }
  };
  
  try {
    recognition.start();
  } catch (err) {
    showToast('Failed to start microphone.', 'error');
  }
}

if (els.micBtn) {
  els.micBtn.addEventListener('click', startListening);
}

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  window.speechSynthesis.speak(utterance);
}

// ─── Chat ───────────────────────────────────────────────────────────────────

function createMessageEl(role, content) {
  const isUser = role === 'user';
  const div = document.createElement('div');
  div.className = `message ${role}`;
  
  let htmlContent = escapeHtml(content);
  if (!isUser && typeof marked !== 'undefined') {
    htmlContent = marked.parse(content, { breaks: true });
  }

  div.innerHTML = `
    <div class="avatar">${isUser ? '👤' : '⚡'}</div>
    <div style="display:flex; flex-direction:column; gap:4px; max-width:85%;">
      <div class="bubble ${isUser ? '' : 'markdown-body'}">${htmlContent}</div>
      ${!isUser ? `<button class="speak-btn" style="align-self:flex-start; background:none; border:none; cursor:pointer; font-size:14px; opacity:0.8; padding:2px;" title="Play/Stop">🔊 Speak</button>` : ''}
    </div>
  `;

  if (!isUser) {
    const btn = div.querySelector('.speak-btn');
    btn.addEventListener('click', () => {
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        btn.innerHTML = '🔊 Speak';
      } else {
        const utter = new SpeechSynthesisUtterance(content);
        utter.onend = () => { btn.innerHTML = '🔊 Speak'; };
        btn.innerHTML = '⛔ Stop';
        window.speechSynthesis.speak(utter);
      }
    });
  }

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
  return div;
}

function removeTyping() {
  const el = $('typingIndicator');
  if (el) el.remove();
}

function scrollBottom() {
  els.messagesArea.scrollTop = els.messagesArea.scrollHeight;
}

function hideSplash() {
  if (els.welcomeSplash) els.welcomeSplash.style.display = 'none';
}

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
    const data = await API.post('/chat', {
      message: content,
      conversation_id: state.currentConversationId || undefined,
    });

    state.currentConversationId = data.conversation_id;
    removeTyping();
    els.messagesArea.appendChild(createMessageEl('assistant', data.reply));
    scrollBottom();

    if (!els.chatTitle.dataset.set) {
      els.chatTitle.textContent = content.substring(0, 45) + (content.length > 45 ? '…' : '');
      els.chatTitle.dataset.set = '1';
    }
  } catch (err) {
    removeTyping();
    if (userMsgEl && userMsgEl.parentNode) {
      userMsgEl.parentNode.removeChild(userMsgEl);
    }
    showToast(err.message || 'Failed to send message.', 'error');
    els.messageInput.value = content;
  } finally {
    state.isLoading = false;
    els.sendBtn.disabled = false;
    els.messageInput.focus();
  }
}

els.sendBtn.addEventListener('click', sendMessage);

els.messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
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
  els.chatTitle.textContent = 'New Conversation';
  delete els.chatTitle.dataset.set;
  els.messagesArea.innerHTML = '';
  els.messagesArea.appendChild(els.welcomeSplash);
  els.welcomeSplash.style.display = '';
  switchTab('chat');
  els.messageInput.focus();
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
});

// ─── Notes ──────────────────────────────────────────────────────────────────

async function loadNotes() {
  try {
    const notes = await API.get('/notes');
    renderNotes(notes);
  } catch {
    showToast('Failed to load notes.', 'error');
  }
}

function renderNotes(notes) {
  if (!notes.length) {
    els.notesGrid.innerHTML = `
      <div class="empty-state">
        <span>📝</span>
        <p>No notes yet. Create your first note!</p>
      </div>`;
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
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditNote(btn.dataset.id, notes);
    });
  });
  document.querySelectorAll('.delete-note').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteNote(btn.dataset.id);
    });
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
  const title = els.noteTitleInput.value.trim();
  const content = els.noteContentInput.value.trim();
  if (!title) { showToast('Please enter a title.', 'error'); return; }
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
  } catch (err) {
    showToast(err.message || 'Failed to save note.', 'error');
  }
});

async function deleteNote(id) {
  if (!confirm('Delete this note?')) return;
  try {
    await API.delete(`/notes/${id}`);
    showToast('Note deleted.', 'success');
    loadNotes();
  } catch (err) {
    showToast(err.message || 'Failed to delete note.', 'error');
  }
}

// ─── History ─────────────────────────────────────────────────────────────────

async function loadHistory() {
  try {
    const convos = await API.get('/conversations');
    renderHistory(convos);
  } catch {
    showToast('Failed to load history.', 'error');
  }
}

function renderHistory(convos) {
  if (!convos.length) {
    els.historyList.innerHTML = `
      <div class="empty-state">
        <span>🕑</span>
        <p>No conversations yet. Start chatting!</p>
      </div>`;
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
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await deleteConversation(btn.dataset.id);
    });
  });
}

async function loadConversation(id) {
  try {
    const messages = await API.get(`/conversations/${id}/messages`);
    const convo    = await API.get(`/conversations/${id}`);

    state.currentConversationId = parseInt(id);
    els.chatTitle.textContent = convo.title;
    els.chatTitle.dataset.set = '1';
    els.messagesArea.innerHTML = '';

    if (messages.length === 0) {
      els.messagesArea.appendChild(els.welcomeSplash);
      els.welcomeSplash.style.display = '';
    } else {
      hideSplash();
      messages.forEach((m) => {
        els.messagesArea.appendChild(createMessageEl(m.role, m.content));
      });
      scrollBottom();
    }

    switchTab('chat');
  } catch {
    showToast('Failed to load conversation.', 'error');
  }
}

async function deleteConversation(id) {
  if (!confirm('Archive this conversation?')) return;
  try {
    await API.delete(`/conversations/${id}`);
    if (state.currentConversationId === parseInt(id)) {
      state.currentConversationId = null;
    }
    showToast('Conversation archived.', 'success');
    loadHistory();
  } catch (err) {
    showToast(err.message || 'Failed to archive conversation.', 'error');
  }
}

// ─── Utilities ───────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\n/g, '<br>');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
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

// ─── Health Check on Load ─────────────────────────────────────────────────────

async function checkHealth() {
  try {
    await API.get('/health');
    els.statusDot.style.background = 'var(--success)';
    els.statusText.textContent = 'Online';
  } catch {
    els.statusDot.style.background = 'var(--error)';
    els.statusDot.style.boxShadow = '0 0 6px var(--error)';
    els.statusText.textContent = 'Offline';
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  els.messageInput.focus();
});

