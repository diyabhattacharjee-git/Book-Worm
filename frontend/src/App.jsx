import { useState, useRef, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatMessage from "./components/ChatMessage";
import TypingIndicator from "./components/TypingIndicator";
import SuggestedQueries from "./components/SuggestedQueries";
import { sendMessage, resetChat } from "./services/api";
import { Send, Menu, X } from "lucide-react";

// ─── Local storage helpers ─────────────────────────────────────────────────────

const STORAGE_KEY = "bookbot_chats_v2";

function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveChats(chats) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
  } catch {
    console.warn("Failed to persist chats");
  }
}

// ─── Chat factory ──────────────────────────────────────────────────────────────

function makeWelcome() {
  return {
    role: "assistant",
    content: "Hi! I'm BookBot 📚 Ask me to find books, compare prices across Amazon & Flipkart, or discover reads similar to your favourites.",
    stores: null,
    recommendations: null,
    recommendations_with_links: null,
    agent_insights: null,
    comparison: null,
  };
}

function newChat() {
  return {
    id: `chat-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    title: "New Chat",
    messages: [makeWelcome()],
  };
}

// ─── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [chats, setChats] = useState(() => {
    const saved = loadChats();
    if (saved.length === 0) return [newChat()];

    // Reuse existing empty first chat or prepend a new one
    const first = saved[0];
    const isUnused = first.title === "New Chat" && first.messages.length === 1;
    return isUnused ? saved : [newChat(), ...saved];
  });

  const [activeChatId, setActiveChatId] = useState(() => {
    const saved = loadChats();
    return saved[0]?.id ?? null;
  });

  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Ensure activeChatId is always valid
  useEffect(() => {
    if (!activeChatId && chats.length > 0) {
      setActiveChatId(chats[0].id);
    }
  }, [activeChatId, chats]);

  // Persist chats
  useEffect(() => {
    saveChats(chats);
  }, [chats]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chats, loading]);

  // Active chat data
  const activeChat = chats.find(c => c.id === activeChatId);
  const messages = activeChat?.messages ?? [];
  const isNewEmptyChat = messages.length <= 1;

  // ── Update messages helper ───────────────────────────────────────────────────

  const pushMessage = useCallback((chatId, msg) => {
    setChats(prev =>
      prev.map(chat => {
        if (chat.id !== chatId) return chat;
        const isFirstUserMsg = chat.messages.length === 1 && msg.role === "user";
        return {
          ...chat,
          title: isFirstUserMsg ? msg.content.slice(0, 32) : chat.title,
          messages: [
            ...chat.messages,
            {
              role: msg.role,
              content: msg.content ?? "",
              stores: msg.stores ?? null,
              recommendations: msg.recommendations ?? null,
              recommendations_with_links: msg.recommendations_with_links ?? null,
              agent_insights: msg.agent_insights ?? null,
              comparison: msg.comparison ?? null,
            },
          ],
        };
      })
    );
  }, []);

  // ── Send ─────────────────────────────────────────────────────────────────────

  const handleSend = useCallback(async (text) => {
    const trimmed = (text ?? input).trim();
    if (!trimmed || loading) return;

    const chatId = activeChatId;
    pushMessage(chatId, { role: "user", content: trimmed });
    setInput("");
    setLoading(true);
    inputRef.current?.focus();

    try {
      const reply = await sendMessage(trimmed, chatId);
      pushMessage(chatId, {
        role: "assistant",
        content: reply.response ?? "",
        stores: reply.stores ?? null,
        recommendations: reply.recommendations ?? null,
        recommendations_with_links: reply.recommendations_with_links ?? null,
        agent_insights: reply.agent_insights ?? null,
        comparison: reply.comparison ?? null,
      });
    } catch (err) {
      console.error("Send error:", err);
      pushMessage(chatId, {
        role: "assistant",
        content: "⚠️ Could not reach the server. Please make sure the backend is running.",
      });
    }

    setLoading(false);
  }, [input, loading, activeChatId, pushMessage]);

  // ── Reset ────────────────────────────────────────────────────────────────────

  const handleReset = useCallback(async () => {
    if (!activeChatId) return;
    await resetChat(activeChatId).catch(() => {});
    setChats(prev =>
      prev.map(c =>
        c.id === activeChatId
          ? { ...c, title: "New Chat", messages: [makeWelcome()] }
          : c
      )
    );
  }, [activeChatId]);

  // ── Delete chat ───────────────────────────────────────────────────────────────

  const handleDeleteChat = useCallback((chatId) => {
    setChats(prev => {
      const updated = prev.filter(c => c.id !== chatId);
      if (updated.length === 0) {
        const fresh = newChat();
        setActiveChatId(fresh.id);
        return [fresh];
      }
      if (chatId === activeChatId) {
        setActiveChatId(updated[0].id);
      }
      return updated;
    });
  }, [activeChatId]);

  // ── New chat ──────────────────────────────────────────────────────────────────

  const handleNewChat = useCallback(() => {
    const first = chats[0];
    const isUnused = first?.title === "New Chat" && first?.messages.length === 1;
    if (isUnused) {
      setActiveChatId(first.id);
      return;
    }
    const fresh = newChat();
    setChats(prev => [fresh, ...prev]);
    setActiveChatId(fresh.id);
  }, [chats]);

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--chat-bg)" }}>
      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar — desktop always visible, mobile drawer */}
      <div
        className={`
          fixed md:static inset-y-0 left-0 z-30
          transform transition-transform duration-200
          ${mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0
        `}
        style={{ width: 256 }}
      >
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={id => { setActiveChatId(id); setMobileSidebarOpen(false); }}
          onNewChat={handleNewChat}
          onResetChat={handleReset}
          onDeleteChat={handleDeleteChat}
        />
      </div>

      {/* Main */}
      <div className="flex flex-col flex-1 min-w-0 h-full">
        {/* Header */}
        <div
          className="flex items-center gap-3 px-4 py-3 shrink-0"
          style={{
            background: "#fff",
            borderBottom: "1px solid #e8dfc8",
            boxShadow: "0 1px 4px rgba(80,50,10,0.05)",
          }}
        >
          <button
            className="md:hidden p-1.5 rounded-lg"
            onClick={() => setMobileSidebarOpen(v => !v)}
            style={{ color: "#8c7b6a" }}
          >
            {mobileSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="text-lg font-semibold font-display" style={{ color: "#1a1208" }}>
            📚 BookBot
          </span>
          <span
            className="ml-auto text-xs px-2.5 py-1 rounded-full"
            style={{ background: "#f0ebe0", color: "#8c7b6a" }}
          >
            {activeChat?.title === "New Chat" ? "New conversation" : activeChat?.title}
          </span>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {isNewEmptyChat ? (
            <SuggestedQueries onSend={handleSend} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
              {messages.map((msg, i) => (
                <ChatMessage key={i} msg={msg} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
          {/* When there are messages, still need scroll ref at bottom */}
          {!isNewEmptyChat && <div ref={bottomRef} />}
        </div>

        {/* Input bar */}
        <div
          className="shrink-0 px-4 py-3"
          style={{
            background: "#fff",
            borderTop: "1px solid #e8dfc8",
            boxShadow: "0 -1px 4px rgba(80,50,10,0.05)",
          }}
        >
          <div className="max-w-3xl mx-auto flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              placeholder="Ask about books, prices, or recommendations…"
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{
                background: "#f7f3ec",
                border: "1.5px solid #e0d5c0",
                color: "#1a1208",
                fontFamily: "'DM Sans', sans-serif",
              }}
              onFocus={e => e.target.style.borderColor = "var(--amber)"}
              onBlur={e => e.target.style.borderColor = "#e0d5c0"}
            />
            <button
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className="flex items-center justify-center w-12 h-12 rounded-xl transition-all duration-150 shrink-0"
              style={{
                background: input.trim() && !loading ? "var(--amber)" : "#e0d5c0",
                color: "#fff",
                boxShadow: input.trim() && !loading ? "0 2px 8px rgba(212,121,10,0.35)" : "none",
                cursor: input.trim() && !loading ? "pointer" : "not-allowed",
              }}
              onMouseEnter={e => {
                if (input.trim() && !loading) e.currentTarget.style.background = "var(--amber-light)";
              }}
              onMouseLeave={e => {
                if (input.trim() && !loading) e.currentTarget.style.background = "var(--amber)";
              }}
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-center text-xs mt-1.5" style={{ color: "#c4b49a" }}>
            BookBot focuses on Amazon.in & Flipkart • Prices may vary
          </p>
        </div>
      </div>
    </div>
  );
}
