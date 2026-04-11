import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "../lib/api";
import { streamAssistantText } from "../lib/streamAssistant";
import { getArchivedChatIds, getPinnedChatIds, toggleArchivedChatId, togglePinnedChatId } from "../lib/storage";
import type {
  ActiveFile,
  AgentMode,
  Chat,
  HealthResponse,
  Message,
  Note,
  PendingImage,
  SendMessageResponse,
} from "../types";

const TOKEN_KEY = "jarvis_auth_token";
const USER_KEY = "jarvis_user_id";
const MOBILE_BP = 960;

export type TabId = "chat" | "notes" | "history";

export type ToastItem = { id: number; message: string; type: "success" | "error" | "" };

export type UiMessage = Message & {
  isStreaming?: boolean;
  streamPlain?: string;
};

type UploadDocResult = { file_id: string; filename: string; chunk_count: number };

function isImageFile(file: File): boolean {
  return /^image\/(png|jpeg|jpg)$/i.test(file.type) || /\.(png|jpe?g)$/i.test(file.name || "");
}

function isDocumentFile(file: File): boolean {
  return /\.(pdf|txt)$/i.test(file.name || "");
}

type JarvisContextValue = {
  /* auth */
  authToken: string | null;
  userId: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
  authMode: "login" | "signup";
  setAuthMode: (m: "login" | "signup") => void;
  authBanner: { text: string; variant: "neutral" | "success" | "error" } | null;
  setAuthBanner: (b: JarvisContextValue["authBanner"]) => void;

  /* shell */
  tab: TabId;
  setTab: (t: TabId) => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean | ((p: boolean) => boolean)) => void;
  sidebarMobileOpen: boolean;
  setSidebarMobileOpen: (v: boolean) => void;
  isMobile: boolean;

  /* health */
  healthOnline: boolean;
  healthLabel: string;

  /* chats */
  chats: Chat[];
  chatSearch: string;
  setChatSearch: (s: string) => void;
  pinnedIds: Set<number>;
  archivedIds: Set<number>;
  togglePin: (id: number) => void;
  toggleArchive: (id: number) => void;
  activeChatId: number | null;
  messages: UiMessage[];
  isSending: boolean;
  selectedAgent: AgentMode;
  setSelectedAgent: (a: AgentMode) => void;
  activeFile: ActiveFile | null;
  pendingImage: PendingImage | null;
  createNewChat: (opts?: { clearFile?: boolean }) => Promise<Chat | undefined>;
  loadConversation: (id: number) => Promise<void>;
  deleteConversation: (id: number) => Promise<void>;
  renameConversation: (id: number, title: string) => Promise<void>;
  sendMessage: (text: string, chatIdOverride?: number | null) => Promise<void>;
  clearActiveFile: () => void;
  clearPendingImage: (opts?: { silent?: boolean }) => void;
  setPendingImageFromFile: (file: File) => void;
  uploadDocument: (file: File) => Promise<void>;
  chatTitle: string;
  refreshChats: () => Promise<void>;

  /* notes */
  notes: Note[];
  notesLoading: boolean;
  loadNotes: () => Promise<void>;
  saveNote: (title: string, content: string, id?: number | null) => Promise<void>;
  deleteNote: (id: number) => Promise<void>;

  /* history tab */
  historyLoading: boolean;
  loadHistoryTab: () => Promise<void>;

  /* composer ref handlers */
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  triggerFilePicker: () => void;
  onFileSelected: (fileList: FileList | null) => Promise<void>;

  /* toasts */
  toasts: ToastItem[];
  showToast: (message: string, type?: ToastItem["type"]) => void;
  dismissToast: (id: number) => void;

  /* regenerate / copy helpers */
  lastUserContent: () => string | null;
  composerText: string;
  setComposerText: (text: string) => void;
};

const JarvisContext = createContext<JarvisContextValue | null>(null);

export function JarvisProvider({ children }: { children: ReactNode }) {
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [userId, setUserId] = useState<string | null>(() => localStorage.getItem(USER_KEY));
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authBanner, setAuthBanner] = useState<JarvisContextValue["authBanner"]>(null);

  const [tab, setTab] = useState<TabId>("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarMobileOpen, setSidebarMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" && window.innerWidth <= MOBILE_BP
  );

  const [healthOnline, setHealthOnline] = useState(true);
  const [healthLabel, setHealthLabel] = useState("Online");

  const [chats, setChats] = useState<Chat[]>([]);
  const [chatSearch, setChatSearch] = useState("");
  const [pinnedIds, setPinnedIds] = useState(() => getPinnedChatIds());
  const [archivedIds, setArchivedIds] = useState(() => getArchivedChatIds());

  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [selectedAgent, setSelectedAgentState] = useState<AgentMode>("auto");
  const [activeFile, setActiveFile] = useState<ActiveFile | null>(null);
  const [pendingImage, setPendingImage] = useState<PendingImage | null>(null);

  const [notes, setNotes] = useState<Note[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastId = useRef(0);

  const streamingGen = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [composerText, setComposerText] = useState("");

  const isAuthenticated = Boolean(authToken && userId);

  const showToast = useCallback((message: string, type: ToastItem["type"] = "") => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 3200);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const persistAuth = useCallback((token: string | null, uid: string | null) => {
    setAuthToken(token);
    setUserId(uid);
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
    if (uid) localStorage.setItem(USER_KEY, uid);
    else localStorage.removeItem(USER_KEY);
  }, []);

  const resetAppState = useCallback(() => {
    setChats([]);
    setActiveChatId(null);
    setMessages([]);
    setSelectedAgentState("auto");
    setActiveFile(null);
    setPendingImage((prev) => {
      if (prev?.previewUrl) URL.revokeObjectURL(prev.previewUrl);
      return null;
    });
    setComposerText("");
  }, []);

  const logout = useCallback(() => {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    persistAuth(null, null);
    resetAppState();
    setTab("chat");
    setAuthMode("login");
    setAuthBanner({ text: "You have been logged out.", variant: "success" });
    showToast("Logged out.", "success");
  }, [persistAuth, resetAppState, showToast]);

  const checkHealth = useCallback(async () => {
    try {
      const data = await api.get<HealthResponse>("/health", null);
      const aiOk = data?.ai_service?.status === "ok";
      setHealthOnline(aiOk);
      setHealthLabel(aiOk ? "Online" : "AI Error");
    } catch {
      setHealthOnline(false);
      setHealthLabel("Offline");
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = window.setInterval(checkHealth, 30_000);
    return () => clearInterval(id);
  }, [checkHealth]);

  useEffect(() => {
    const onResize = () => {
      const m = window.innerWidth <= MOBILE_BP;
      setIsMobile(m);
      if (m) setSidebarCollapsed(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const refreshChats = useCallback(async () => {
    if (!authToken) {
      setChats([]);
      return;
    }
    try {
      const list = await api.get<Chat[]>("/chats", authToken);
      setChats(list);
      setActiveChatId((cur) => {
        if (cur != null && !list.some((c) => c.id === cur)) {
          setMessages([]);
          setActiveFile(null);
          return null;
        }
        return cur;
      });
    } catch {
      setChats([]);
    }
  }, [authToken]);

  const verifySession = useCallback(async () => {
    if (!authToken) return false;
    try {
      const data = await api.getRaw<{ user_id: number }>("/protected", authToken);
      persistAuth(authToken, String(data.user_id));
      setAuthBanner(null);
      return true;
    } catch {
      persistAuth(null, null);
      setAuthBanner({ text: "Your session expired. Please log in again.", variant: "error" });
      return false;
    }
  }, [authToken, persistAuth]);

  useEffect(() => {
    void verifySession().then((ok) => {
      if (ok) void refreshChats();
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const loginData = await api.postRaw<{ access_token: string }>("/login", { email, password });
      const protectedData = await api.getRaw<{ user_id: number }>("/protected", loginData.access_token);
      persistAuth(loginData.access_token, String(protectedData.user_id));
      setAuthBanner({ text: "Welcome back.", variant: "success" });
      showToast(`Logged in as user #${protectedData.user_id}.`, "success");
      await refreshChats();
    },
    [persistAuth, refreshChats, showToast]
  );

  const signup = useCallback(
    async (email: string, password: string) => {
      await api.postRaw("/register", { email, password });
      await login(email, password);
      showToast("Account created and logged in.", "success");
    },
    [login, showToast]
  );

  const clearActiveFile = useCallback(() => {
    setActiveFile(null);
  }, []);

  const clearPendingImage = useCallback(
    (opts?: { silent?: boolean }) => {
      setPendingImage((prev) => {
        if (prev?.previewUrl) URL.revokeObjectURL(prev.previewUrl);
        return null;
      });
      if (!opts?.silent) showToast("Image removed.");
    },
    [showToast]
  );

  const setSelectedAgent = useCallback(
    (a: AgentMode) => {
      setSelectedAgentState(a);
      if (activeFile && ["generate_image", "analyze_image"].includes(a)) {
        setActiveFile(null);
      }
      if (pendingImage && !["auto", "analyze_image"].includes(a)) {
        clearPendingImage({ silent: true });
      }
    },
    [activeFile, pendingImage, clearPendingImage]
  );

  const setPendingImageFromFile = useCallback((file: File) => {
    setActiveFile(null);
    setPendingImage((prev) => {
      if (prev?.previewUrl) URL.revokeObjectURL(prev.previewUrl);
      const previewUrl = URL.createObjectURL(file);
      return { file, previewUrl, name: file.name, size: file.size, type: file.type };
    });
    setSelectedAgentState((a) => (["auto", "analyze_image"].includes(a) ? a : "analyze_image"));
    setTab("chat");
  }, []);

  const chatTitle = useMemo(() => {
    if (activeFile && !activeChatId) return "New Document Chat";
    const c = chats.find((x) => x.id === activeChatId);
    return c?.title || "New Conversation";
  }, [activeChatId, activeFile, chats]);

  const loadConversation = useCallback(
    async (id: number) => {
      if (!authToken) return;
      clearPendingImage({ silent: true });
      setActiveChatId(id);
      const allChats = await api.get<Chat[]>("/chats", authToken);
      setChats(allChats);
      const chat = allChats.find((c) => c.id === id);
      const list = await api.get<Message[]>(`/chat/${id}`, authToken);
      if (chat?.document_file_id) {
        setActiveFile({
          id: chat.document_file_id,
          name: chat.document_filename || "Document",
          meta: "Document chat",
        });
      } else {
        setActiveFile(null);
      }
      setMessages(
        list.map((m) => ({
          ...m,
          message_type: (m.message_type || "text") as Message["message_type"],
        }))
      );
      setTab("chat");
      setSidebarMobileOpen(false);
    },
    [authToken, clearPendingImage]
  );

  const createNewChat = useCallback(
    async (opts?: { clearFile?: boolean }) => {
      if (!authToken) return;
      try {
        const chat = await api.post<Chat>("/chat/create", { title: "New Chat" }, authToken);
        setActiveChatId(chat.id);
        setMessages([]);
        if (opts?.clearFile !== false) {
          setActiveFile(null);
          clearPendingImage({ silent: true });
        }
        setChats((prev) => [chat, ...prev.filter((c) => c.id !== chat.id)]);
        setTab("chat");
        setSidebarMobileOpen(false);
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        await refreshChats();
        return chat;
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Failed to create chat.", "error");
        return undefined;
      }
    },
    [authToken, clearPendingImage, refreshChats, showToast]
  );

  const deleteConversation = useCallback(
    async (id: number) => {
      if (!authToken) return;
      if (!confirm("Delete this chat?")) return;
      try {
        await api.delete(`/chat/${id}`, authToken);
        setChats((prev) => prev.filter((c) => c.id !== id));
        if (activeChatId === id) {
          setActiveChatId(null);
          setMessages([]);
          setActiveFile(null);
          clearPendingImage({ silent: true });
        }
        showToast("Chat deleted.", "success");
        await refreshChats();
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Failed to delete chat.", "error");
      }
    },
    [activeChatId, authToken, clearPendingImage, refreshChats, showToast]
  );

  const renameConversation = useCallback(
    async (id: number, title: string) => {
      if (!authToken) return;
      try {
        const updated = await api.patch<Chat>(`/conversations/${id}`, { title }, authToken);
        setChats((prev) => prev.map((c) => (c.id === id ? updated : c)));
        showToast("Chat renamed.", "success");
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Failed to rename chat.", "error");
      }
    },
    [authToken, showToast]
  );

  const togglePin = useCallback((id: number) => {
    setPinnedIds(togglePinnedChatId(id));
  }, []);

  const toggleArchive = useCallback((id: number) => {
    setArchivedIds(toggleArchivedChatId(id));
  }, []);

  const loadNotes = useCallback(async () => {
    if (!authToken) return;
    setNotesLoading(true);
    try {
      const list = await api.get<Note[]>("/notes", authToken);
      setNotes(list);
    } catch {
      showToast("Failed to load notes.", "error");
    } finally {
      setNotesLoading(false);
    }
  }, [authToken, showToast]);

  const saveNote = useCallback(
    async (title: string, content: string, id?: number | null) => {
      if (!authToken) return;
      if (id) {
        await api.patch(`/notes/${id}`, { title, content }, authToken);
        showToast("Note updated.", "success");
      } else {
        await api.post("/notes", { title, content }, authToken);
        showToast("Note saved.", "success");
      }
      await loadNotes();
    },
    [authToken, loadNotes, showToast]
  );

  const deleteNote = useCallback(
    async (id: number) => {
      if (!authToken) return;
      if (!confirm("Delete this note?")) return;
      try {
        await api.delete(`/notes/${id}`, authToken);
        showToast("Note deleted.", "success");
        await loadNotes();
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Failed to delete note.", "error");
      }
    },
    [authToken, loadNotes, showToast]
  );

  const loadHistoryTab = useCallback(async () => {
    if (!authToken) return;
    setHistoryLoading(true);
    try {
      await refreshChats();
    } finally {
      setHistoryLoading(false);
    }
  }, [authToken, refreshChats]);

  const setTabWrapped = useCallback(
    (t: TabId) => {
      setTab(t);
      if (t === "notes") void loadNotes();
      if (t === "history") void loadHistoryTab();
    },
    [loadHistoryTab, loadNotes]
  );

  const triggerFilePicker = useCallback(() => fileInputRef.current?.click(), []);

  const uploadDocument = useCallback(
    async (file: File) => {
      if (!authToken) return;
      const maxMb = 10;
      if (file.size > maxMb * 1024 * 1024) {
        showToast(`File too large (max ${maxMb} MB).`, "error");
        return;
      }
      const fd = new FormData();
      fd.append("file", file);
      try {
        const data = await api.upload<UploadDocResult>("/upload", fd, authToken);
        setActiveFile({
          id: data.file_id,
          name: data.filename,
          meta: `${data.chunk_count} chunks indexed`,
        });
        setPendingImage((prev) => {
          if (prev?.previewUrl) URL.revokeObjectURL(prev.previewUrl);
          return null;
        });
        setSelectedAgentState("auto");
        setActiveChatId(null);
        setMessages([]);
        setTab("chat");
        showToast(`"${data.filename}" is ready for document chat.`, "success");
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Upload failed.", "error");
      }
    },
    [authToken, showToast]
  );

  const onFileSelected = useCallback(
    async (fileList: FileList | null) => {
      if (!authToken) {
        showToast("Please log in to attach a file.", "error");
        return;
      }
      const file = fileList?.[0];
      if (!file) return;

      if (isImageFile(file)) {
        const maxMb = 8;
        if (file.size > maxMb * 1024 * 1024) {
          showToast(`Image too large (max ${maxMb} MB).`, "error");
          return;
        }
        setPendingImageFromFile(file);
        showToast(`"${file.name}" is ready for image analysis.`, "success");
        return;
      }

      if (!isDocumentFile(file)) {
        showToast("Only PDF, TXT, JPG, and PNG files are supported.", "error");
        return;
      }

      await uploadDocument(file);
    },
    [authToken, setPendingImageFromFile, showToast, uploadDocument]
  );

  const sendMessage = useCallback(
    async (contentRaw: string, chatIdOverride?: number | null) => {
      const content = contentRaw.trim();
      if (!authToken) {
        setAuthBanner({ text: "Please log in to chat.", variant: "error" });
        return;
      }
      if ((!content && !pendingImage) || isSending) return;

      setIsSending(true);
      setComposerText("");

      const pending = pendingImage
        ? {
            ...pendingImage,
            file: pendingImage.file,
            previewUrl: pendingImage.previewUrl,
          }
        : null;
      const hasPendingImage = Boolean(pending);
      const requestMode = hasPendingImage ? selectedAgent || "auto" : selectedAgent || "auto";

      const optimisticType = hasPendingImage
        ? "image_analysis"
        : requestMode === "generate_image"
          ? "image_generation"
          : "text";

      const optimistic: UiMessage = {
        id: `temp-user-${Date.now()}`,
        chat_id: activeChatId ?? 0,
        role: "user",
        content: content || "Analyze this image.",
        message_type: optimisticType,
        attachment_url: hasPendingImage ? pending!.previewUrl : null,
        created_at: new Date().toISOString(),
      };

      try {
        let chatId = chatIdOverride ?? activeChatId;
        if (!chatId) {
          const newChat = await api.post<Chat>("/chat/create", { title: "New Chat" }, authToken);
          chatId = newChat.id;
          setActiveChatId(chatId);
          setChats((prev) => [newChat, ...prev.filter((c) => c.id !== newChat.id)]);
        }

        optimistic.chat_id = chatId!;
        setMessages((m) => [...m, optimistic]);

        let data: SendMessageResponse;
        if (hasPendingImage && pending) {
          const formData = new FormData();
          formData.append("content", content);
          formData.append("request_mode", requestMode);
          formData.append("selected_agent", "auto");
          formData.append("image", pending.file);
          data = await api.upload<SendMessageResponse>(
            `/chat/${chatId}/message/multimodal`,
            formData,
            authToken
          );
        } else {
          const payload: Record<string, unknown> = {
            content,
            selected_agent: "auto",
            request_mode: requestMode,
          };
          if (activeFile) payload.file_id = activeFile.id;
          data = await api.post<SendMessageResponse>(`/chat/${chatId}/message`, payload, authToken);
        }

        setActiveChatId(data.chat_id);
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last && last.id === optimistic.id) {
            next[next.length - 1] = { ...last, id: data.user_message_id, chat_id: data.chat_id };
          }
          return next;
        });

        const assistantMsg: UiMessage = {
          id: data.assistant_message_id,
          chat_id: data.chat_id,
          role: "assistant",
          agent_type: data.agent_type,
          content: data.reply,
          message_type: data.message_type,
          image_url: data.image_url,
          attachment_url: data.attachment_url,
          message_metadata: data.metadata || {},
          created_at: new Date().toISOString(),
        };

        if (hasPendingImage) clearPendingImage({ silent: true });

        if (data.message_type === "text") {
          const streamId = ++streamingGen.current;
          setMessages((m) => [...m, { ...assistantMsg, isStreaming: true, streamPlain: "", content: "" }]);

          await streamAssistantText(
            data.reply,
            (partial) => {
              if (streamingGen.current !== streamId) return;
              setMessages((m) => {
                const next = [...m];
                const i = next.length - 1;
                const last = next[i];
                if (last && last.role === "assistant" && last.id === assistantMsg.id) {
                  next[i] = { ...last, streamPlain: partial };
                }
                return next;
              });
            },
            () => streamingGen.current !== streamId
          );

          setMessages((m) => {
            const next = [...m];
            const i = next.length - 1;
            const last = next[i];
            if (last && last.id === assistantMsg.id) {
              const { streamPlain: _s, isStreaming: _i, ...rest } = last;
              next[i] = { ...rest, content: data.reply, isStreaming: false };
            }
            return next;
          });
        } else {
          setMessages((m) => [...m, assistantMsg]);
        }

        await refreshChats();
      } catch (e) {
        streamingGen.current += 1;
        setMessages((m) => (m[m.length - 1]?.id === optimistic.id ? m.slice(0, -1) : m));
        setComposerText(contentRaw);
        showToast(e instanceof ApiError ? e.message : "Failed to send message.", "error");
      } finally {
        setIsSending(false);
      }
    },
    [
      activeChatId,
      activeFile,
      authToken,
      clearPendingImage,
      isSending,
      pendingImage,
      refreshChats,
      selectedAgent,
      showToast,
    ]
  );

  const lastUserContent = useCallback(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") return messages[i].content;
    }
    return null;
  }, [messages]);

  const value = useMemo<JarvisContextValue>(
    () => ({
      authToken,
      userId,
      isAuthenticated,
      login,
      signup,
      logout,
      authMode,
      setAuthMode,
      authBanner,
      setAuthBanner,
      tab: tab,
      setTab: setTabWrapped,
      sidebarCollapsed,
      setSidebarCollapsed,
      sidebarMobileOpen,
      setSidebarMobileOpen,
      isMobile,
      healthOnline,
      healthLabel,
      chats,
      chatSearch,
      setChatSearch,
      pinnedIds,
      archivedIds,
      togglePin,
      toggleArchive,
      activeChatId,
      messages,
      isSending,
      selectedAgent,
      setSelectedAgent,
      activeFile,
      pendingImage,
      createNewChat,
      loadConversation,
      deleteConversation,
      renameConversation,
      sendMessage,
      clearActiveFile,
      clearPendingImage,
      setPendingImageFromFile,
      uploadDocument,
      chatTitle,
      refreshChats,
      notes,
      notesLoading,
      loadNotes,
      saveNote,
      deleteNote,
      historyLoading,
      loadHistoryTab,
      fileInputRef,
      triggerFilePicker,
      onFileSelected,
      toasts,
      showToast,
      dismissToast,
      lastUserContent,
      composerText,
      setComposerText,
    }),
    [
      authToken,
      userId,
      isAuthenticated,
      login,
      signup,
      logout,
      authMode,
      authBanner,
      tab,
      setTabWrapped,
      sidebarCollapsed,
      sidebarMobileOpen,
      isMobile,
      healthOnline,
      healthLabel,
      chats,
      chatSearch,
      pinnedIds,
      archivedIds,
      togglePin,
      toggleArchive,
      activeChatId,
      messages,
      isSending,
      selectedAgent,
      setSelectedAgent,
      activeFile,
      pendingImage,
      createNewChat,
      loadConversation,
      deleteConversation,
      renameConversation,
      sendMessage,
      clearActiveFile,
      clearPendingImage,
      setPendingImageFromFile,
      uploadDocument,
      chatTitle,
      refreshChats,
      notes,
      notesLoading,
      loadNotes,
      saveNote,
      deleteNote,
      historyLoading,
      loadHistoryTab,
      toasts,
      showToast,
      dismissToast,
      lastUserContent,
      composerText,
      setComposerText,
      onFileSelected,
    ]
  );

  return <JarvisContext.Provider value={value}>{children}</JarvisContext.Provider>;
}

export function useJarvis() {
  const ctx = useContext(JarvisContext);
  if (!ctx) throw new Error("useJarvis must be used within JarvisProvider");
  return ctx;
}
