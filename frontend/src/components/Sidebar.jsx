import { Plus, Trash2, MessageSquare, X, BookOpen, Zap } from "lucide-react";

export default function Sidebar({
  chats = [],
  activeChatId,
  onSelectChat,
  onNewChat,
  onResetChat,
  onDeleteChat,
}) {
  return (
    <div
      className="hidden md:flex flex-col w-64 shrink-0 h-full"
      style={{ background: "var(--sidebar-bg)", borderRight: "1px solid #2e2416" }}
    >
      {/* Logo */}
      <div className="px-5 pt-6 pb-4" style={{ borderBottom: "1px solid #2e2416" }}>
        <div className="flex items-center gap-2.5 mb-1">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-base"
            style={{ background: "var(--amber)", color: "#fff" }}
          >
            📚
          </div>
          <h1 className="font-display text-xl font-semibold text-white tracking-tight">
            BookBot
          </h1>
        </div>
        <p className="text-xs pl-0.5" style={{ color: "#7a6a55" }}>
          AI-powered book discovery
        </p>
      </div>

      {/* New Chat */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150"
          style={{
            background: "var(--amber)",
            color: "#fff",
            boxShadow: "0 2px 8px rgba(212,121,10,0.35)",
          }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--amber-light)"}
          onMouseLeave={e => e.currentTarget.style.background = "var(--amber)"}
        >
          <Plus size={15} />
          New Chat
        </button>
      </div>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {chats.length === 0 ? (
          <p className="text-xs px-3 py-4 text-center" style={{ color: "#4a3e30" }}>
            No conversations yet
          </p>
        ) : (
          chats.map((chat, idx) => (
            <div key={chat.id} className="group relative">
              <button
                onClick={() => onSelectChat(chat.id)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-all duration-100 text-left pr-8"
                style={{
                  background: activeChatId === chat.id ? "var(--sidebar-hover)" : "transparent",
                  color: activeChatId === chat.id ? "#f0ead8" : "#9e8a70",
                  borderLeft: activeChatId === chat.id ? "2px solid var(--amber)" : "2px solid transparent",
                }}
                onMouseEnter={e => {
                  if (activeChatId !== chat.id) e.currentTarget.style.background = "#221b12";
                }}
                onMouseLeave={e => {
                  if (activeChatId !== chat.id) e.currentTarget.style.background = "transparent";
                }}
              >
                <MessageSquare size={13} style={{ flexShrink: 0, opacity: 0.7 }} />
                <span className="truncate">{chat.title || `Chat ${idx + 1}`}</span>
              </button>
              <button
                onClick={() => {
                  if (window.confirm("Delete this chat?")) onDeleteChat(chat.id);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded"
                style={{ color: "#6a5540" }}
                onMouseEnter={e => e.currentTarget.style.color = "#e05555"}
                onMouseLeave={e => e.currentTarget.style.color = "#6a5540"}
              >
                <X size={12} />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="px-3 pb-4 pt-3 space-y-1" style={{ borderTop: "1px solid #2e2416" }}>
        <button
          onClick={onResetChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-150"
          style={{ color: "#a05050" }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(160,80,80,0.12)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
        >
          <Trash2 size={13} />
          Reset Current Chat
        </button>
        <div className="flex items-center justify-center gap-1.5 pt-2">
          <Zap size={11} style={{ color: "#5a4a35" }} />
          <p className="text-xs" style={{ color: "#5a4a35" }}>
            Powered by Groq + LangGraph
          </p>
        </div>
      </div>
    </div>
  );
}
