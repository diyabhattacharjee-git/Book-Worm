export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-2 msg-anim">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-sm shrink-0"
        style={{ background: "var(--amber)", boxShadow: "0 2px 6px rgba(212,121,10,0.3)" }}
      >
        📚
      </div>
      <div
        className="flex items-center gap-1.5 px-4 py-3 rounded-2xl rounded-bl-sm"
        style={{
          background: "#fff",
          border: "1px solid #e8dfc8",
          boxShadow: "0 1px 4px rgba(80,50,10,0.07)",
        }}
      >
        <span className="w-1.5 h-1.5 rounded-full dot-1" style={{ background: "#c4a87a" }} />
        <span className="w-1.5 h-1.5 rounded-full dot-2" style={{ background: "#c4a87a" }} />
        <span className="w-1.5 h-1.5 rounded-full dot-3" style={{ background: "#c4a87a" }} />
        <span className="ml-1.5 text-xs" style={{ color: "#a89070" }}>Thinking…</span>
      </div>
    </div>
  );
}
