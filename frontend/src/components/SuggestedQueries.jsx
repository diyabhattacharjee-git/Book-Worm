const SUGGESTIONS = [
  { icon: "🔍", text: "Find books like Atomic Habits" },
  { icon: "💰", text: "Price of Ikigai on Amazon and Flipkart" },
  { icon: "📊", text: "Compare prices for The Alchemist" },
  { icon: "🎁", text: "Recommend self-help books with buy links" },
];

export default function SuggestedQueries({ onSend }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mb-4"
        style={{ background: "var(--amber-pale)", boxShadow: "0 4px 16px rgba(212,121,10,0.15)" }}
      >
        📚
      </div>
      <h2 className="font-display text-2xl font-semibold mb-1" style={{ color: "#1a1208" }}>
        Welcome to BookBot
      </h2>
      <p className="text-sm mb-6" style={{ color: "#8c7b6a" }}>
        Discover books & compare prices across Amazon and Flipkart
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => onSend(s.text)}
            className="flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm text-left transition-all duration-150"
            style={{
              background: "#fff",
              border: "1px solid #e8dfc8",
              color: "#4a3a28",
              boxShadow: "0 1px 3px rgba(80,50,10,0.06)",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = "var(--amber)";
              e.currentTarget.style.boxShadow = "0 2px 8px rgba(212,121,10,0.12)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = "#e8dfc8";
              e.currentTarget.style.boxShadow = "0 1px 3px rgba(80,50,10,0.06)";
            }}
          >
            <span className="text-base">{s.icon}</span>
            <span>{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
