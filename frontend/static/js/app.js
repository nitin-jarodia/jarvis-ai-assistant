'use strict';

const MOBILE_BREAKPOINT = 960;
const DEFAULT_INPUT_HINT =
  'Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for new line · drop an image or document to attach';

const API = {
  base: '/api',
  async request(method, path, body = null, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const token = state.authToken;
    if (token) headers.Authorization = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    try {
      const url = options.rawPath ? path : `${this.base}${path}`;
      const res = await fetch(url, opts);
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
  get: (path) => API.request('GET', path),
  post: (path, body) => API.request('POST', path, body),
  patch: (path, body) => API.request('PATCH', path, body),
  delete: (path) => API.request('DELETE', path),
  postRaw: (path, body) => API.request('POST', path, body, { rawPath: true }),
  getRaw: (path) => API.request('GET', path, null, { rawPath: true }),
  async upload(path, formData) {
    try {
      const headers = {};
      if (state.authToken) headers.Authorization = `Bearer ${state.authToken}`;
      const res = await fetch(`${this.base}${path}`, { method: 'POST', body: formData, headers });
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

const state = {
  currentUser: null,
  chats: [],
  activeChatId: null,
  messages: [],
  isLoading: false,
  editingNoteId: null,
  activeFile: null,
  pendingImage: null,
  authToken: localStorage.getItem('jarvis_auth_token'),
  currentUserId: localStorage.getItem('jarvis_user_id'),
  sidebarOpen: false,
  sidebarCollapsed: false,
  selectedAgent: 'auto',
  shouldAutoScroll: true,
  streamingMessageId: 0,
  dragDepth: 0,
};

const $ = (id) => document.getElementById(id);

const els = {
  authScreen: $('authScreen'),
  loginTabBtn: $('loginTabBtn'),
  signupTabBtn: $('signupTabBtn'),
  loginForm: $('loginForm'),
  signupForm: $('signupForm'),
  loginEmail: $('loginEmail'),
  loginPassword: $('loginPassword'),
  signupEmail: $('signupEmail'),
  signupPassword: $('signupPassword'),
  loginSubmitBtn: $('loginSubmitBtn'),
  signupSubmitBtn: $('signupSubmitBtn'),
  authMessage: $('authMessage'),
  authUserLabel: $('authUserLabel'),
  logoutBtn: $('logoutBtn'),
  sidebar: $('sidebar'),
  sidebarToggle: $('sidebarToggle'),
  sidebarBackdrop: $('sidebarBackdrop'),
  mobileMenuBtn: $('mobileMenuBtn'),
  openHistoryBtn: $('openHistoryBtn'),
  sidebarHistoryList: $('sidebarHistoryList'),
  chatContainer: $('chatContainer'),
  messagesArea: $('messagesArea'),
  messagesEnd: $('messagesEnd'),
  welcomeSplash: $('welcomeSplash'),
  messageInput: $('messageInput'),
  agentSelect: $('agentSelect'),
  selectedAgentBadge: $('selectedAgentBadge'),
  sendBtn: $('sendBtn'),
  micBtn: $('micBtn'),
  uploadBtn: $('uploadBtn'),
  fileInput: $('fileInput'),
  fileBadgeBar: $('fileBadgeBar'),
  fileBadgeName: $('fileBadgeName'),
  fileBadgeMeta: $('fileBadgeMeta'),
  fileBadgeDismiss: $('fileBadgeDismiss'),
  imageAttachmentBar: $('imageAttachmentBar'),
  imageAttachmentPreview: $('imageAttachmentPreview'),
  imageAttachmentName: $('imageAttachmentName'),
  imageAttachmentMeta: $('imageAttachmentMeta'),
  imageAttachmentHint: $('imageAttachmentHint'),
  imageAttachmentDismiss: $('imageAttachmentDismiss'),
  fileModeChip: $('fileModeChip'),
  fileModeChipName: $('fileModeChipName'),
  chatTitle: $('chatTitle'),
  inputHint: $('inputHint'),
  statusText: $('statusText'),
  statusDot: $('statusDot'),
  newChatBtn: $('newChatBtn'),
  notesGrid: $('notesGrid'),
  noteEditor: $('noteEditor'),
  noteTitleInput: $('noteTitleInput'),
  noteContentInput: $('noteContentInput'),
  saveNoteBtn: $('saveNoteBtn'),
  cancelNoteBtn: $('cancelNoteBtn'),
  addNoteBtn: $('addNoteBtn'),
  historyList: $('historyList'),
  toastContainer: $('toastContainer'),
};

if (typeof marked !== 'undefined') {
  marked.setOptions({ gfm: true, breaks: true });
}

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
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatMessageTime(date = new Date()) {
  return new Date(date).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatBytes(bytes = 0) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function isImageFile(file) {
  if (!file) return false;
  return /^image\/(png|jpeg|jpg)$/i.test(file.type) || /\.(png|jpe?g)$/i.test(file.name || '');
}

function isDocumentFile(file) {
  if (!file) return false;
  return /\.(pdf|txt)$/i.test(file.name || '');
}

function getInputPlaceholder() {
  if (state.activeFile) return `Ask about "${state.activeFile.name}"...`;
  if (state.pendingImage) return 'Ask a question about this image...';
  if (state.selectedAgent === 'generate_image') return 'Describe the image you want Jarvis to create...';
  return 'Message Jarvis...';
}

function getComposerHint() {
  if (state.activeFile) return 'Document mode active. Answers will use the uploaded file.';
  if (state.pendingImage) return 'Image attached. Send with an optional question to analyze it.';
  if (state.selectedAgent === 'generate_image') return 'Describe the image you want. Jarvis will route this to the image generator.';
  if (state.selectedAgent === 'analyze_image') return 'Attach an image or drop one here, then optionally ask a question.';
  if (state.selectedAgent === 'chat') return 'Chat mode active. Text prompts will go straight to Groq.';
  return DEFAULT_INPUT_HINT;
}

function getAgentMeta(agentType) {
  const mapping = {
    auto: { icon: '✨', label: 'Auto' },
    chat: { icon: '💬', label: 'Chat' },
    generate_image: { icon: '🖼️', label: 'Generate Image' },
    analyze_image: { icon: '🔍', label: 'Analyze Image' },
  };
  return mapping[agentType] || null;
}

function renderMarkdown(content) {
  if (typeof marked === 'undefined') return escapeHtml(content).replace(/\n/g, '<br>');
  const raw = marked.parse(content);
  return typeof DOMPurify !== 'undefined'
    ? DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
    : raw;
}

function isMobileViewport() {
  return window.innerWidth <= MOBILE_BREAKPOINT;
}

function isNearBottom(el, threshold = 100) {
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
}

function getSelectedAgentLabel(agentType) {
  return (
    {
      auto: 'Auto',
      chat: 'Chat',
      generate_image: 'Generate Image',
      analyze_image: 'Analyze Image',
    }[agentType] || 'Auto'
  );
}

function updateSelectedAgentUi() {
  if (els.agentSelect) els.agentSelect.value = state.selectedAgent;
  if (!els.selectedAgentBadge) return;

  const allClasses = ['agent-badge--auto', 'agent-badge--chat', 'agent-badge--generate_image', 'agent-badge--analyze_image'];
  els.selectedAgentBadge.classList.remove(...allClasses);
  els.selectedAgentBadge.classList.add(`agent-badge--${state.selectedAgent}`);
  els.selectedAgentBadge.textContent = getSelectedAgentLabel(state.selectedAgent);
}

function updateInputHint(content) {
  if (els.inputHint) els.inputHint.innerHTML = content;
}

function showToast(msg, type = '') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`.trim();
  toast.textContent = msg;
  els.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 220ms ease';
    setTimeout(() => toast.remove(), 260);
  }, 3200);
}

const Sidebar = {
  sync(forceDesktopOpen = false) {
    if (isMobileViewport()) {
      state.sidebarCollapsed = false;
      if (!state.sidebarOpen) {
        document.body.classList.remove('sidebar-open');
        els.sidebarBackdrop.classList.remove('is-visible');
      }
      els.sidebar.classList.remove('is-collapsed');
      return;
    }

    state.sidebarOpen = false;
    document.body.classList.remove('sidebar-open');
    els.sidebarBackdrop.classList.remove('is-visible');
    els.sidebar.classList.toggle('is-collapsed', forceDesktopOpen ? false : state.sidebarCollapsed);
  },
  setMobileOpen(open) {
    state.sidebarOpen = open;
    document.body.classList.toggle('sidebar-open', open);
    els.sidebarBackdrop.classList.toggle('is-visible', open);
  },
  toggle() {
    if (isMobileViewport()) {
      this.setMobileOpen(!state.sidebarOpen);
      return;
    }
    state.sidebarCollapsed = !state.sidebarCollapsed;
    els.sidebar.classList.toggle('is-collapsed', state.sidebarCollapsed);
  },
  closeOnMobile() {
    if (isMobileViewport()) this.setMobileOpen(false);
  },
};

const InputBar = {
  setLoading(loading) {
    state.isLoading = loading;
    els.sendBtn.disabled = loading;
    els.sendBtn.classList.toggle('is-loading', loading);
  },
  focus() {
    els.messageInput.focus();
  },
};

function avatarMarkup(role) {
  if (role === 'user') {
    return `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21a8 8 0 0 0-16 0"></path>
        <circle cx="12" cy="7" r="4"></circle>
      </svg>
    `;
  }

  return `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"></path>
    </svg>
  `;
}

function attachSpeakButton(btn, content) {
  let isSpeaking = false;

  btn.addEventListener('click', () => {
    if (!('speechSynthesis' in window)) {
      showToast('Text-to-speech is not supported in this browser.', 'error');
      return;
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(content);
    utterance.onstart = () => {
      isSpeaking = true;
      btn.textContent = 'Stop';
    };
    utterance.onend = () => {
      isSpeaking = false;
      btn.textContent = 'Speak';
    };
    utterance.onerror = () => {
      isSpeaking = false;
      btn.textContent = 'Speak';
    };
    window.speechSynthesis.speak(utterance);
  });
}

function enhanceRenderedContent(container) {
  container.querySelectorAll('pre > code').forEach((codeEl) => {
    if (codeEl.dataset.enhanced === '1') return;
    codeEl.dataset.enhanced = '1';

    const pre = codeEl.parentElement;
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block';

    const toolbar = document.createElement('div');
    toolbar.className = 'code-block-toolbar';

    const label = document.createElement('span');
    label.className = 'code-block-label';
    const langMatch = (codeEl.className || '').match(/language-([\w-]+)/);
    label.textContent = (langMatch?.[1] || 'code').replace(/^\w/, (s) => s.toUpperCase());

    const copyBtn = document.createElement('button');
    copyBtn.className = 'code-copy-btn';
    copyBtn.type = 'button';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(codeEl.textContent || '');
        copyBtn.classList.add('is-copied');
        copyBtn.textContent = 'Copied';
        setTimeout(() => {
          copyBtn.classList.remove('is-copied');
          copyBtn.textContent = 'Copy';
        }, 1400);
      } catch {
        showToast('Could not copy code block.', 'error');
      }
    });

    toolbar.append(label, copyBtn);
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.append(toolbar, pre);

    if (typeof hljs !== 'undefined') {
      try {
        hljs.highlightElement(codeEl);
      } catch {
        /* noop */
      }
    }
  });
}

function createImageLink(url, className = '') {
  const link = document.createElement('a');
  link.className = className;
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}

function buildAnalysisPreview(url) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message-image-preview';
  const link = createImageLink(url, 'message-image-link');
  const img = document.createElement('img');
  img.className = 'message-image-thumb';
  img.src = url;
  img.alt = 'Uploaded image';
  link.appendChild(img);
  wrapper.appendChild(link);
  return wrapper;
}

function buildGeneratedImageCard(imageUrl, metadata = {}) {
  const card = document.createElement('div');
  card.className = 'generated-image-card';

  const previewLink = createImageLink(imageUrl, 'generated-image-link');
  const img = document.createElement('img');
  img.className = 'generated-image';
  img.src = imageUrl;
  img.alt = metadata.prompt || 'Generated image';
  previewLink.appendChild(img);

  const meta = document.createElement('div');
  meta.className = 'generated-image-meta';
  const prompt = document.createElement('p');
  prompt.className = 'generated-image-prompt';
  prompt.textContent = metadata.prompt || 'Generated image';

  const actions = document.createElement('div');
  actions.className = 'generated-image-actions';
  const expandLink = createImageLink(imageUrl, 'generated-image-action');
  expandLink.textContent = 'Expand';
  const downloadLink = document.createElement('a');
  downloadLink.className = 'generated-image-action';
  downloadLink.href = imageUrl;
  downloadLink.target = '_blank';
  downloadLink.rel = 'noopener noreferrer';
  downloadLink.download = '';
  downloadLink.textContent = 'Download';
  actions.append(expandLink, downloadLink);

  meta.append(prompt, actions);
  card.append(previewLink, meta);
  return card;
}

const MessageBubble = {
  create(role, content, options = {}) {
    const isUser = role === 'user';
    const staggerIndex = options.staggerIndex ?? 0;
    const root = document.createElement('div');
    root.className = `message ${role} message-enter`;
    root.dataset.role = role;
    root.style.setProperty(
      '--msg-delay',
      window.JarvisMotion ? window.JarvisMotion.staggerDelay(staggerIndex) : `${staggerIndex * 45}ms`
    );

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = avatarMarkup(role);

    const stack = document.createElement('div');
    stack.className = 'message-stack';

    const meta = document.createElement('div');
    meta.className = 'message-meta';
    const agentMeta = !isUser ? getAgentMeta(options.agentType) : null;
    meta.innerHTML = `
      <span>${isUser ? 'You' : 'Jarvis'}</span>
      ${agentMeta ? `<span class="agent-badge agent-badge--${options.agentType}">${agentMeta.icon} ${agentMeta.label}</span>` : ''}
      <span>${options.timeLabel || formatMessageTime()}</span>
    `;

    const bubble = document.createElement('div');
    bubble.className = `bubble${isUser ? '' : ' markdown-body'}`;

    const contentEl = document.createElement('div');
    contentEl.className = 'bubble-content';
    bubble.appendChild(contentEl);

    if (options.attachmentUrl && options.messageType === 'image_analysis') {
      bubble.insertBefore(buildAnalysisPreview(options.attachmentUrl), contentEl);
    }

    let cursor = null;
    if (options.streaming) {
      bubble.classList.add('streaming');
      contentEl.textContent = options.initialContent || '';
      cursor = document.createElement('span');
      cursor.className = 'streaming-cursor';
      bubble.appendChild(cursor);
    } else if (isUser) {
      contentEl.textContent = content;
    } else {
      contentEl.innerHTML = renderMarkdown(content);
      enhanceRenderedContent(contentEl);
    }

    if (options.imageUrl && options.messageType === 'image_generation') {
      bubble.appendChild(buildGeneratedImageCard(options.imageUrl, options.messageMetadata || {}));
    }

    stack.append(meta, bubble);

    let speakBtn = null;
    if (!isUser && !options.streaming && !options.suppressActions) {
      const actions = document.createElement('div');
      actions.className = 'message-actions';
      speakBtn = document.createElement('button');
      speakBtn.className = 'speak-btn';
      speakBtn.type = 'button';
      speakBtn.textContent = 'Speak';
      speakBtn.title = 'Play response';
      attachSpeakButton(speakBtn, content);
      actions.appendChild(speakBtn);
      stack.appendChild(actions);
    }

    root.append(avatar, stack);
    root._bubble = bubble;
    root._contentEl = contentEl;
    root._cursor = cursor;
    root._speakBtn = speakBtn;
    root._stack = stack;
    return root;
  },
  finalizeStreaming(root, finalContent) {
    const bubble = root._bubble;
    const contentEl = root._contentEl;
    if (!bubble || !contentEl) return;

    bubble.classList.remove('streaming');
    bubble.classList.add('markdown-body');
    if (root._cursor) root._cursor.remove();
    contentEl.innerHTML = renderMarkdown(finalContent);
    enhanceRenderedContent(contentEl);

    const actions = document.createElement('div');
    actions.className = 'message-actions';
    const speakBtn = document.createElement('button');
    speakBtn.className = 'speak-btn';
    speakBtn.type = 'button';
    speakBtn.textContent = 'Speak';
    attachSpeakButton(speakBtn, finalContent);
    actions.appendChild(speakBtn);
    root._stack.appendChild(actions);
  },
};

const TypingIndicator = {
  show() {
    this.remove();
    const bubble = MessageBubble.create('assistant', '', { streaming: false, suppressActions: true });
    bubble.id = 'typingIndicator';
    bubble.classList.add('typing-bubble');
    bubble._contentEl.innerHTML = `
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    `;
    bubble._bubble.classList.remove('markdown-body');
    const shouldStick = isNearBottom(els.messagesArea, 100);
    els.messagesArea.insertBefore(bubble, els.messagesEnd);
    state.shouldAutoScroll = shouldStick;
    ChatContainer.scrollToBottom(shouldStick);
  },
  remove() {
    const el = $('typingIndicator');
    if (el) el.remove();
  },
};

const ChatContainer = {
  reset({ showSplash = true } = {}) {
    TypingIndicator.remove();
    els.messagesArea.innerHTML = '';
    els.messagesArea.appendChild(els.welcomeSplash);
    els.messagesArea.appendChild(els.messagesEnd);
    els.welcomeSplash.style.display = showSplash ? '' : 'none';
    state.shouldAutoScroll = true;
  },
  hideSplash() {
    if (els.welcomeSplash) els.welcomeSplash.style.display = 'none';
  },
  append(role, content, options = {}) {
    if (!options.keepSplashHidden) this.hideSplash();
    const shouldStick = options.forceScroll === true || isNearBottom(els.messagesArea, 100);
    const messageEl = MessageBubble.create(role, content, options);
    els.messagesArea.insertBefore(messageEl, els.messagesEnd);
    if (options.forceScroll !== false) {
      state.shouldAutoScroll = shouldStick;
      this.scrollToBottom(shouldStick, options.scrollBehavior || 'smooth');
    }
    return messageEl;
  },
  scrollToBottom(force = false, behavior = 'smooth') {
    if (!force && !state.shouldAutoScroll && !isNearBottom(els.messagesArea, 100)) return;
    if (!els.messagesEnd) return;
    els.messagesEnd.scrollIntoView({ behavior, block: 'end' });
  },
  async streamAssistant(content, options = {}) {
    this.hideSplash();
    const shouldStick = isNearBottom(els.messagesArea, 100);
    const messageEl = MessageBubble.create('assistant', '', {
      streaming: true,
      agentType: options.agentType,
    });
    els.messagesArea.insertBefore(messageEl, els.messagesEnd);
    state.shouldAutoScroll = shouldStick;
    this.scrollToBottom(shouldStick);

    const contentEl = messageEl._contentEl;
    const reduced = window.JarvisMotion?.prefersReducedMotion?.() ?? false;
    const parts = content.split(/(\s+)/).filter(Boolean);

    if (reduced || parts.length <= 3) {
      contentEl.textContent = content;
      MessageBubble.finalizeStreaming(messageEl, content);
      this.scrollToBottom(true);
      return messageEl;
    }

    let index = 0;
    let rendered = '';
    const streamId = ++state.streamingMessageId;

    await new Promise((resolve) => {
      const tick = () => {
        if (state.streamingMessageId !== streamId) {
          resolve();
          return;
        }

        const nextChunk = [];
        let chunkCount = 0;
        while (index < parts.length && chunkCount < 3) {
          nextChunk.push(parts[index]);
          if (!/^\s+$/.test(parts[index])) chunkCount += 1;
          index += 1;
        }

        rendered += nextChunk.join('');
        contentEl.textContent = rendered;
        ChatContainer.scrollToBottom(false);

        if (index >= parts.length) {
          resolve();
          return;
        }

        setTimeout(tick, 18 + Math.min(44, nextChunk.join('').length * 2));
      };

      tick();
    });

    contentEl.textContent = content;
    MessageBubble.finalizeStreaming(messageEl, content);
    this.scrollToBottom(false);
    return messageEl;
  },
};

function setAuthMode(mode) {
  const isLogin = mode === 'login';
  els.loginTabBtn.classList.toggle('active', isLogin);
  els.signupTabBtn.classList.toggle('active', !isLogin);
  els.loginForm.classList.toggle('hidden', !isLogin);
  els.signupForm.classList.toggle('hidden', isLogin);
  setAuthMessage(
    isLogin
      ? 'Log in with an existing Jarvis account.'
      : 'Create a new account to start using Jarvis.'
  );
}

function setAuthMessage(message, type = '') {
  if (!els.authMessage) return;
  els.authMessage.className = `auth-message${type ? ` ${type}` : ''}`;
  els.authMessage.textContent = message;
}

function setAuthState(token, userId) {
  state.authToken = token || null;
  state.currentUserId = userId == null ? null : String(userId);
  state.currentUser = state.currentUserId ? { id: state.currentUserId } : null;

  if (state.authToken) localStorage.setItem('jarvis_auth_token', state.authToken);
  else localStorage.removeItem('jarvis_auth_token');

  if (state.currentUserId) localStorage.setItem('jarvis_user_id', state.currentUserId);
  else localStorage.removeItem('jarvis_user_id');

  updateAuthUi();
}

function updateAuthUi() {
  const authenticated = Boolean(state.authToken && state.currentUserId);
  els.authScreen.classList.toggle('hidden', authenticated);
  els.authUserLabel.textContent = authenticated ? `User #${state.currentUserId}` : 'Not authenticated';
  els.logoutBtn.disabled = !authenticated;
}

function resetAppState() {
  state.chats = [];
  state.activeChatId = null;
  state.messages = [];
  state.isLoading = false;
  state.editingNoteId = null;
  state.selectedAgent = 'auto';
  clearActiveFile();
  clearPendingImage({ silent: true });
  updateSelectedAgentUi();
  els.chatTitle.textContent = 'New Conversation';
  delete els.chatTitle.dataset.set;
  ChatContainer.reset({ showSplash: true });
  els.noteEditor.classList.add('hidden');
  els.noteTitleInput.value = '';
  els.noteContentInput.value = '';
  renderSidebarHistory([]);
  renderHistory([]);
}

function getActiveChat() {
  return state.chats.find((chat) => chat.id === state.activeChatId) || null;
}

function updateChatHeader(chat = getActiveChat()) {
  if (!chat) {
    els.chatTitle.textContent = state.activeFile ? 'New Document Chat' : 'New Conversation';
    delete els.chatTitle.dataset.set;
    return;
  }

  els.chatTitle.textContent = chat.title || 'New Chat';
  if (chat.title && chat.title !== 'New Chat') {
    els.chatTitle.dataset.set = '1';
  } else {
    delete els.chatTitle.dataset.set;
  }
}

function renderActiveMessages() {
  ChatContainer.reset({ showSplash: state.messages.length === 0 });
  if (!state.messages.length) {
    updateChatHeader();
    return;
  }

  ChatContainer.hideSplash();
  const fragment = document.createDocumentFragment();
  state.messages.forEach((message, index) => {
    fragment.appendChild(
      MessageBubble.create(message.role, message.content, {
        staggerIndex: index,
        timeLabel: formatMessageTime(message.created_at),
        agentType: message.agent_type,
        messageType: message.message_type,
        imageUrl: message.image_url,
        attachmentUrl: message.attachment_url,
        messageMetadata: message.message_metadata || {},
      })
    );
  });
  els.messagesArea.insertBefore(fragment, els.messagesEnd);
  ChatContainer.scrollToBottom(true, 'auto');
  updateChatHeader();
}

async function verifyStoredSession() {
  if (!state.authToken) {
    updateAuthUi();
    return false;
  }

  try {
    const data = await API.getRaw('/protected');
    setAuthState(state.authToken, data.user_id);
    return true;
  } catch {
    setAuthState(null, null);
    setAuthMessage('Your session expired. Please log in again.', 'error');
    return false;
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const email = els.loginEmail.value.trim();
  const password = els.loginPassword.value;
  if (!email || !password) {
    setAuthMessage('Please enter your email and password.', 'error');
    return;
  }

  els.loginSubmitBtn.disabled = true;
  setAuthMessage('Logging you in...');

  try {
    const loginData = await API.postRaw('/login', { email, password });
    const protectedData = await API.request('GET', '/protected', null, {
      rawPath: true,
      headers: { Authorization: `Bearer ${loginData.access_token}` },
    });

    setAuthState(loginData.access_token, protectedData.user_id);
    setAuthMessage('Login successful.', 'success');
    els.loginForm.reset();
    showToast(`Logged in as user #${protectedData.user_id}.`, 'success');
    await refreshConversationLists().catch(() => {
      showToast('Logged in, but conversation history could not be loaded yet.', 'error');
    });
    InputBar.focus();
  } catch (err) {
    setAuthState(null, null);
    setAuthMessage(err.message || 'Login failed.', 'error');
  } finally {
    els.loginSubmitBtn.disabled = false;
  }
}

async function handleSignup(event) {
  event.preventDefault();
  const email = els.signupEmail.value.trim();
  const password = els.signupPassword.value;
  if (!email || !password) {
    setAuthMessage('Please enter your email and password.', 'error');
    return;
  }

  els.signupSubmitBtn.disabled = true;
  setAuthMessage('Creating your account...');

  try {
    await API.postRaw('/register', { email, password });
    setAuthMessage('Account created. Logging you in now...', 'success');
    const loginData = await API.postRaw('/login', { email, password });
    const protectedData = await API.request('GET', '/protected', null, {
      rawPath: true,
      headers: { Authorization: `Bearer ${loginData.access_token}` },
    });

    setAuthState(loginData.access_token, protectedData.user_id);
    els.signupForm.reset();
    showToast('Account created and logged in.', 'success');
    await refreshConversationLists().catch(() => {
      showToast('Account created, but conversation history could not be loaded yet.', 'error');
    });
    InputBar.focus();
  } catch (err) {
    setAuthState(null, null);
    setAuthMessage(err.message || 'Sign up failed.', 'error');
  } finally {
    els.signupSubmitBtn.disabled = false;
  }
}

function handleLogout() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  setAuthState(null, null);
  resetAppState();
  switchTab('chat');
  setAuthMode('login');
  setAuthMessage('You have been logged out.', 'success');
  showToast('Logged out.', 'success');
}

function switchTab(tabName) {
  ['Chat', 'Notes', 'History'].forEach((name) => {
    const panel = $(`tab${name}`);
    const active = name.toLowerCase() === tabName;
    panel.classList.toggle('tab-panel--active', active);
    panel.setAttribute('aria-hidden', active ? 'false' : 'true');
  });

  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  if (tabName === 'notes') loadNotes();
  if (tabName === 'history') loadHistory();
}

function setActiveFile(file) {
  clearPendingImage({ silent: true });
  state.activeFile = file;
  els.fileBadgeName.textContent = file.name;
  els.fileBadgeMeta.textContent = file.meta || 'Document ready';
  els.fileBadgeBar.classList.remove('hidden');
  els.fileModeChipName.textContent = file.name;
  els.fileModeChip.classList.remove('hidden');
  els.uploadBtn.classList.add('active');
  state.selectedAgent = 'auto';
  updateSelectedAgentUi();
  updateComposerUi();
}

function clearActiveFile() {
  state.activeFile = null;
  els.fileBadgeBar.classList.add('hidden');
  els.fileModeChip.classList.add('hidden');
  if (!state.pendingImage) els.uploadBtn.classList.remove('active');
  updateComposerUi();
}

function setPendingImage(file) {
  clearActiveFile();
  if (state.pendingImage?.previewUrl) URL.revokeObjectURL(state.pendingImage.previewUrl);
  const previewUrl = URL.createObjectURL(file);
  state.pendingImage = {
    file,
    previewUrl,
    name: file.name,
    size: file.size,
    type: file.type,
  };
  els.imageAttachmentPreview.src = previewUrl;
  els.imageAttachmentName.textContent = file.name;
  els.imageAttachmentMeta.textContent = `${formatBytes(file.size)} · Ready to analyze`;
  els.imageAttachmentHint.textContent = 'Image ready for analysis';
  els.imageAttachmentBar.classList.remove('hidden');
  els.uploadBtn.classList.add('active');
  if (!['auto', 'analyze_image'].includes(state.selectedAgent)) {
    state.selectedAgent = 'analyze_image';
    updateSelectedAgentUi();
  }
  switchTab('chat');
  updateComposerUi();
}

function clearPendingImage(options = {}) {
  const { silent = false } = options;
  if (state.pendingImage?.previewUrl) URL.revokeObjectURL(state.pendingImage.previewUrl);
  state.pendingImage = null;
  if (els.imageAttachmentPreview) els.imageAttachmentPreview.removeAttribute('src');
  els.imageAttachmentBar.classList.add('hidden');
  if (!state.activeFile) els.uploadBtn.classList.remove('active');
  updateComposerUi();
  if (!silent) showToast('Image removed.');
}

function updateComposerUi() {
  els.messageInput.placeholder = getInputPlaceholder();
  updateInputHint(getComposerHint());
  if (state.pendingImage) {
    els.imageAttachmentHint.textContent = state.selectedAgent === 'analyze_image'
      ? 'Analyze Image mode active'
      : 'Auto mode will analyze this image';
  }
}

function startDocumentChat(filename) {
  state.activeChatId = null;
  state.messages = [];
  updateChatHeader(null);
  ChatContainer.reset({ showSplash: true });
  switchTab('chat');
}

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
    els.micBtn.classList.add('is-listening');
  };

  recognition.onspeechend = () => recognition.stop();

  recognition.onend = () => {
    updateComposerUi();
    els.micBtn.classList.remove('is-listening');
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) {
      showToast('Empty input. Please speak clearly.', 'error');
      return;
    }
    els.messageInput.value = transcript;
    autoResizeTextarea();
    sendMessage();
  };

  recognition.onerror = (event) => {
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      showToast('Microphone access denied. Please allow permissions.', 'error');
    } else if (event.error === 'no-speech') {
      showToast('No speech detected. Please try again.', 'error');
    } else {
      showToast(`Microphone error: ${event.error}`, 'error');
    }
  };

  try {
    recognition.start();
  } catch {
    showToast('Failed to start microphone.', 'error');
  }
}

function autoResizeTextarea() {
  const ta = els.messageInput;
  ta.style.height = 'auto';
  ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
}

async function sendMessage() {
  if (!state.authToken) {
    updateAuthUi();
    setAuthMessage('Please log in to chat with Jarvis.', 'error');
    return;
  }

  const content = els.messageInput.value.trim();
  if ((!content && !state.pendingImage) || state.isLoading) return;

  ChatContainer.hideSplash();
  InputBar.setLoading(true);
  els.messageInput.value = '';
  autoResizeTextarea();
  let chatId = state.activeChatId;
  const pendingImage = state.pendingImage
    ? { ...state.pendingImage, file: state.pendingImage.file, previewUrl: state.pendingImage.previewUrl }
    : null;
  const hasPendingImage = Boolean(pendingImage);
  const requestMode = hasPendingImage ? state.selectedAgent || 'auto' : state.selectedAgent || 'auto';
  const optimisticMessageType = hasPendingImage ? 'image_analysis' : requestMode === 'generate_image' ? 'image_generation' : 'text';
  const optimisticMessage = {
    id: `temp-user-${Date.now()}`,
    chat_id: chatId,
    role: 'user',
    content: content || 'Analyze this image.',
    message_type: optimisticMessageType,
    attachment_url: hasPendingImage ? pendingImage.previewUrl : null,
    created_at: new Date().toISOString(),
  };

  try {
    if (!chatId) {
      const newChat = await createNewChat({
        clearFile: false,
        focus: false,
        switchToChat: false,
        silent: true,
        throwOnError: true,
      });
      chatId = newChat.id;
    }

    optimisticMessage.chat_id = chatId;
    state.messages.push(optimisticMessage);
    ChatContainer.append('user', optimisticMessage.content, {
      forceScroll: true,
      messageType: optimisticMessage.message_type,
      attachmentUrl: optimisticMessage.attachment_url,
    });
    TypingIndicator.show();
    updateInputHint(
      state.activeFile
        ? 'Searching document...'
        : hasPendingImage
          ? 'Analyzing image...'
          : requestMode === 'generate_image'
            ? 'Generating image...'
            : 'Jarvis is thinking...'
    );

    let data;
    if (hasPendingImage) {
      const formData = new FormData();
      formData.append('content', content);
      formData.append('request_mode', requestMode);
      formData.append('selected_agent', 'auto');
      formData.append('image', pendingImage.file);
      data = await API.upload(`/chat/${chatId}/message/multimodal`, formData);
    } else {
      const payload = { content, selected_agent: 'auto', request_mode: requestMode };
      if (state.activeFile) payload.file_id = state.activeFile.id;
      data = await API.post(`/chat/${chatId}/message`, payload);
    }
    state.activeChatId = data.chat_id;
    state.messages[state.messages.length - 1].id = data.user_message_id;

    TypingIndicator.remove();
    state.messages.push({
      id: data.assistant_message_id,
      chat_id: data.chat_id,
      role: 'assistant',
      agent_type: data.agent_type,
      content: data.reply,
      message_type: data.message_type,
      image_url: data.image_url,
      attachment_url: data.attachment_url,
      provider: data.provider,
      message_metadata: data.metadata || {},
      created_at: new Date().toISOString(),
    });
    if (data.message_type === 'text') {
      await ChatContainer.streamAssistant(data.reply, { agentType: data.agent_type });
    } else {
      ChatContainer.append('assistant', data.reply, {
        forceScroll: true,
        agentType: data.agent_type,
        messageType: data.message_type,
        imageUrl: data.image_url,
        attachmentUrl: data.attachment_url,
        messageMetadata: data.metadata || {},
      });
    }
    if (hasPendingImage) clearPendingImage({ silent: true });
    await refreshConversationLists().catch(() => {});
    updateChatHeader();
  } catch (err) {
    TypingIndicator.remove();
    if (state.messages[state.messages.length - 1]?.id === optimisticMessage.id) {
      state.messages.pop();
      renderActiveMessages();
    }
    els.messageInput.value = content;
    autoResizeTextarea();
    showToast(err.message || 'Failed to send message.', 'error');
  } finally {
    InputBar.setLoading(false);
    updateComposerUi();
    InputBar.focus();
  }
}

async function createNewChat(options = {}) {
  const {
    clearFile = false,
    focus = true,
    switchToChat = true,
    silent = false,
    throwOnError = false,
  } = options;

  try {
    const chat = await API.post('/chat/create', { title: 'New Chat' });
    state.activeChatId = chat.id;
    state.messages = [];
    if (clearFile) {
      clearActiveFile();
      clearPendingImage({ silent: true });
    }
    state.chats = [chat, ...state.chats.filter((entry) => entry.id !== chat.id)];
    renderSidebarHistory(state.chats);
    renderHistory(state.chats);
    renderActiveMessages();
    if (switchToChat) switchTab('chat');
    Sidebar.closeOnMobile();
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (focus) InputBar.focus();
    return chat;
  } catch (err) {
    if (!silent) showToast(err.message || 'Failed to create chat.', 'error');
    if (throwOnError) throw err;
    return null;
  }
}

async function startNewChat() {
  await createNewChat({ clearFile: true });
}

function renderSidebarHistory(convos) {
  const previousScroll = els.sidebarHistoryList.scrollTop;

  if (!convos.length) {
    els.sidebarHistoryList.innerHTML = `
      <div class="sidebar-empty-state">
        <span>Conversations will appear here.</span>
      </div>
    `;
    return;
  }

  els.sidebarHistoryList.innerHTML = convos
    .slice(0, 12)
    .map((c) => `
      <button class="sidebar-history-item${state.activeChatId === c.id ? ' active' : ''}" data-id="${c.id}" type="button">
        <span class="sidebar-history-title">${escapeHtml(c.title || 'Untitled conversation')}</span>
        <span class="sidebar-history-date">${formatDate(c.created_at)}</span>
      </button>
    `)
    .join('');

  els.sidebarHistoryList.querySelectorAll('.sidebar-history-item').forEach((item) => {
    item.addEventListener('click', () => {
      loadConversation(item.dataset.id);
    });
  });

  els.sidebarHistoryList.scrollTop = previousScroll;
}

function renderHistory(convos) {
  const previousScroll = els.historyList.scrollTop;

  if (!convos.length) {
    els.historyList.innerHTML = `<div class="empty-state"><span>🕑</span><p>No conversations yet. Start chatting!</p></div>`;
    return;
  }

  els.historyList.innerHTML = convos
    .map((c) => `
      <div class="history-item" data-id="${c.id}">
        <div class="history-item-info">
          <h4>${escapeHtml(c.title || 'Untitled conversation')}</h4>
          <span>${formatDate(c.created_at)}</span>
        </div>
        <div class="history-item-actions">
          <button class="note-action-btn delete-convo" data-id="${c.id}" type="button">Delete</button>
        </div>
      </div>
    `)
    .join('');

  els.historyList.querySelectorAll('.history-item').forEach((item) => {
    item.addEventListener('click', (event) => {
      if (event.target.closest('.delete-convo')) return;
      loadConversation(item.dataset.id);
    });
  });

  els.historyList.querySelectorAll('.delete-convo').forEach((btn) => {
    btn.addEventListener('click', async (event) => {
      event.stopPropagation();
      await deleteConversation(btn.dataset.id);
    });
  });

  els.historyList.scrollTop = previousScroll;
}

async function refreshConversationLists() {
  if (!state.authToken) {
    state.chats = [];
    renderSidebarHistory([]);
    renderHistory([]);
    return;
  }

  state.chats = await API.get('/chats');
  if (state.activeChatId && !state.chats.some((chat) => chat.id === state.activeChatId)) {
    state.activeChatId = null;
    state.messages = [];
    clearActiveFile();
    renderActiveMessages();
  }
  renderSidebarHistory(state.chats);
  renderHistory(state.chats);
  updateChatHeader();
}

async function loadHistory() {
  if (!state.authToken) return;
  els.historyList.innerHTML = historySkeletonHtml();
  try {
    await refreshConversationLists();
  } catch {
    els.historyList.innerHTML = `<div class="empty-state"><span>🕑</span><p>Could not load history.</p></div>`;
    showToast('Failed to load history.', 'error');
  }
}

async function loadConversation(id) {
  if (!state.authToken) return;

  try {
    clearPendingImage({ silent: true });
    const chatId = parseInt(id, 10);
    state.activeChatId = chatId;
    if (!state.chats.some((chat) => chat.id === chatId)) {
      await refreshConversationLists();
    }

    const chat = state.chats.find((entry) => entry.id === chatId) || null;
    state.messages = await API.get(`/chat/${chatId}`);

    if (chat?.document_file_id) {
      setActiveFile({
        id: chat.document_file_id,
        name: chat.document_filename || 'Document',
        meta: 'Document chat',
      });
    } else {
      clearActiveFile();
    }

    renderActiveMessages();
    switchTab('chat');
    Sidebar.closeOnMobile();
    renderSidebarHistory(state.chats);
    renderHistory(state.chats);
  } catch {
    showToast('Failed to load conversation.', 'error');
  }
}

async function deleteConversation(id) {
  if (!state.authToken) {
    updateAuthUi();
    setAuthMessage('Please log in to access conversations.', 'error');
    return;
  }

  if (!confirm('Delete this chat?')) return;

  try {
    const chatId = parseInt(id, 10);
    await API.delete(`/chat/${chatId}`);
    state.chats = state.chats.filter((chat) => chat.id !== chatId);
    if (state.activeChatId === chatId) {
      state.activeChatId = null;
      state.messages = [];
      clearActiveFile();
      clearPendingImage({ silent: true });
      renderActiveMessages();
    }
    renderSidebarHistory(state.chats);
    renderHistory(state.chats);
    showToast('Chat deleted.', 'success');
  } catch (err) {
    showToast(err.message || 'Failed to delete chat.', 'error');
  }
}

async function loadNotes() {
  if (!state.authToken) return;
  els.notesGrid.innerHTML = notesSkeletonHtml();

  try {
    const notes = await API.get('/notes');
    renderNotes(notes);
  } catch {
    els.notesGrid.innerHTML = `<div class="empty-state"><span>📝</span><p>Could not load notes.</p></div>`;
    showToast('Failed to load notes.', 'error');
  }
}

function renderNotes(notes) {
  if (!notes.length) {
    els.notesGrid.innerHTML = `<div class="empty-state"><span>📝</span><p>No notes yet. Create your first note!</p></div>`;
    return;
  }

  els.notesGrid.innerHTML = notes
    .map((note) => `
      <div class="note-card" data-id="${note.id}">
        <h3>${escapeHtml(note.title)}</h3>
        <p>${escapeHtml(note.content)}</p>
        <div class="note-card-meta">
          <span>${formatDate(note.created_at)}</span>
          <div class="note-actions">
            <button class="note-action-btn edit-note" data-id="${note.id}" type="button">Edit</button>
            <button class="note-action-btn delete-note" data-id="${note.id}" type="button">Delete</button>
          </div>
        </div>
      </div>
    `)
    .join('');

  els.notesGrid.querySelectorAll('.edit-note').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.stopPropagation();
      openEditNote(btn.dataset.id, notes);
    });
  });

  els.notesGrid.querySelectorAll('.delete-note').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.stopPropagation();
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
  const note = notes.find((entry) => entry.id === parseInt(id, 10));
  if (note) openEditor(note.title, note.content, note.id);
}

async function deleteNote(id) {
  if (!state.authToken) {
    updateAuthUi();
    setAuthMessage('Please log in to manage notes.', 'error');
    return;
  }

  if (!confirm('Delete this note?')) return;

  try {
    await API.delete(`/notes/${id}`);
    showToast('Note deleted.', 'success');
    await loadNotes();
  } catch (err) {
    showToast(err.message || 'Failed to delete note.', 'error');
  }
}

async function checkHealth() {
  try {
    const data = await API.get('/health');
    const aiOk = data?.ai_service?.status === 'ok';
    els.statusDot.classList.remove('status-offline');
    els.statusDot.classList.toggle('status-online', aiOk);
    els.statusDot.classList.toggle('status-ai-error', !aiOk);
    els.statusText.textContent = aiOk ? 'Online' : 'AI Error';
  } catch {
    els.statusDot.classList.remove('status-online', 'status-ai-error');
    els.statusDot.classList.add('status-offline');
    els.statusText.textContent = 'Offline';
  }
}

function notesSkeletonHtml() {
  const card = `
    <div class="skeleton-card" aria-hidden="true">
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line" style="width:55%"></div>
    </div>
  `;
  return card.repeat(4);
}

function historySkeletonHtml() {
  const row = `
    <div class="skeleton-row" aria-hidden="true">
      <div class="skeleton skeleton-line" style="width:72%"></div>
      <div class="skeleton skeleton-line" style="width:38%"></div>
    </div>
  `;
  return row.repeat(6);
}

els.loginTabBtn.addEventListener('click', () => setAuthMode('login'));
els.signupTabBtn.addEventListener('click', () => setAuthMode('signup'));
els.loginForm.addEventListener('submit', handleLogin);
els.signupForm.addEventListener('submit', handleSignup);
els.logoutBtn.addEventListener('click', handleLogout);

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    switchTab(btn.dataset.tab);
    Sidebar.closeOnMobile();
  });
});

els.sidebarToggle.addEventListener('click', () => Sidebar.toggle());
els.mobileMenuBtn.addEventListener('click', () => Sidebar.setMobileOpen(true));
els.sidebarBackdrop.addEventListener('click', () => Sidebar.setMobileOpen(false));
els.openHistoryBtn.addEventListener('click', () => {
  switchTab('history');
  Sidebar.closeOnMobile();
});

els.uploadBtn.addEventListener('click', () => els.fileInput.click());
els.fileInput.addEventListener('change', async () => {
  if (!state.authToken) {
    els.fileInput.value = '';
    updateAuthUi();
    setAuthMessage('Please log in to attach a file or image.', 'error');
    return;
  }

  const file = els.fileInput.files[0];
  if (!file) return;
  els.fileInput.value = '';

  if (isImageFile(file)) {
    const maxMb = 8;
    if (file.size > maxMb * 1024 * 1024) {
      showToast(`Image too large (max ${maxMb} MB).`, 'error');
      return;
    }
    setPendingImage(file);
    showToast(`"${file.name}" is ready for image analysis.`, 'success');
    InputBar.focus();
    return;
  }

  if (!isDocumentFile(file)) {
    showToast('Only PDF, TXT, JPG, and PNG files are supported.', 'error');
    return;
  }

  const maxMb = 10;
  if (file.size > maxMb * 1024 * 1024) {
    showToast(`File too large (max ${maxMb} MB).`, 'error');
    return;
  }

  els.uploadBtn.classList.add('uploading');
  els.uploadBtn.title = 'Uploading…';
  updateInputHint('Analyzing document...');
  showToast('Analyzing document...');

  try {
    const formData = new FormData();
    formData.append('file', file);
    const data = await API.upload('/upload', formData);
    setActiveFile({
      id: data.file_id,
      name: data.filename,
      meta: `${data.chunk_count} chunks indexed`,
    });
    startDocumentChat(data.filename);
    showToast(`"${data.filename}" is ready for document chat.`, 'success');
  } catch (err) {
    updateComposerUi();
    showToast(err.message || 'Upload failed.', 'error');
  } finally {
    els.uploadBtn.classList.remove('uploading');
    els.uploadBtn.title = 'Upload a document or image';
  }
});

els.fileBadgeDismiss.addEventListener('click', () => {
  clearActiveFile();
  showToast('Document removed. Back to normal chat.');
});

els.imageAttachmentDismiss.addEventListener('click', () => {
  clearPendingImage();
});

if (els.micBtn) els.micBtn.addEventListener('click', startListening);

els.sendBtn.addEventListener('click', sendMessage);
els.agentSelect.addEventListener('change', (event) => {
  state.selectedAgent = event.target.value || 'auto';
  if (state.activeFile && ['generate_image', 'analyze_image'].includes(state.selectedAgent)) {
    clearActiveFile();
  }
  if (state.pendingImage && !['auto', 'analyze_image'].includes(state.selectedAgent)) {
    clearPendingImage({ silent: true });
  }
  updateSelectedAgentUi();
  updateComposerUi();
});
els.messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});
els.messageInput.addEventListener('input', autoResizeTextarea);
els.messagesArea.addEventListener('scroll', () => {
  state.shouldAutoScroll = isNearBottom(els.messagesArea);
});

els.chatContainer.addEventListener('dragenter', (event) => {
  event.preventDefault();
  event.stopPropagation();
  state.dragDepth += 1;
  els.chatContainer.classList.add('drag-active');
});

els.chatContainer.addEventListener('dragover', (event) => {
  event.preventDefault();
  event.stopPropagation();
  els.chatContainer.classList.add('drag-active');
});

['dragleave', 'dragend'].forEach((eventName) => {
  els.chatContainer.addEventListener(eventName, (event) => {
    event.preventDefault();
    event.stopPropagation();
    state.dragDepth = Math.max(0, state.dragDepth - 1);
    if (state.dragDepth === 0) els.chatContainer.classList.remove('drag-active');
  });
});

els.chatContainer.addEventListener('drop', (event) => {
  event.preventDefault();
  event.stopPropagation();
  state.dragDepth = 0;
  els.chatContainer.classList.remove('drag-active');
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  els.fileInput.files = transfer.files;
  els.fileInput.dispatchEvent(new Event('change'));
});

document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    els.messageInput.value = chip.dataset.msg;
    autoResizeTextarea();
    sendMessage();
  });
});

els.newChatBtn.addEventListener('click', startNewChat);
els.addNoteBtn.addEventListener('click', () => {
  if (!state.authToken) {
    updateAuthUi();
    setAuthMessage('Please log in to manage notes.', 'error');
    return;
  }
  openEditor();
});
els.cancelNoteBtn.addEventListener('click', () => {
  els.noteEditor.classList.add('hidden');
  state.editingNoteId = null;
});
els.saveNoteBtn.addEventListener('click', async () => {
  if (!state.authToken) {
    updateAuthUi();
    setAuthMessage('Please log in to manage notes.', 'error');
    return;
  }

  const title = els.noteTitleInput.value.trim();
  const content = els.noteContentInput.value.trim();
  if (!title) {
    showToast('Please enter a title.', 'error');
    return;
  }
  if (!content) {
    showToast('Please enter content.', 'error');
    return;
  }

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
    await loadNotes();
  } catch (err) {
    showToast(err.message || 'Failed to save note.', 'error');
  }
});

window.addEventListener('resize', () => Sidebar.sync());

window.addEventListener('DOMContentLoaded', () => {
  if (window.JarvisMotion) window.JarvisMotion.markAppReady();
  else requestAnimationFrame(() => document.body.classList.add('app-ready'));

  Sidebar.sync();
  updateSelectedAgentUi();
  updateAuthUi();
  setAuthMode('login');
  updateComposerUi();
  checkHealth();

  verifyStoredSession().then(async (authenticated) => {
    if (authenticated) {
      await refreshConversationLists().catch(() => {});
      InputBar.focus();
    } else {
      els.loginEmail.focus();
    }
  });
});
