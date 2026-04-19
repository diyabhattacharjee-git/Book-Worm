import {
  BookCard,
  BookCardWithLinks,
  PriceCard,
  BestDealBanner,
  ComparisonSection,
  AgentInsightsBadges,
} from "./BookCard";

export default function ChatMessage({ msg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex msg-anim ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center text-sm shrink-0 mr-2 mt-0.5"
          style={{ background: "var(--amber)", boxShadow: "0 2px 6px rgba(212,121,10,0.3)" }}
        >
          📚
        </div>
      )}

      <div
        className="max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
        style={
          isUser
            ? {
                background: "#2d3748",
                color: "#e8dfc8",
                borderBottomRightRadius: "4px",
                boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
              }
            : {
                background: "#fff",
                color: "var(--ink)",
                borderBottomLeftRadius: "4px",
                border: "1px solid #e8dfc8",
                boxShadow: "0 1px 4px rgba(80,50,10,0.07)",
              }
        }
      >
        {/* Main text */}
        {msg.content && (
          <p className="whitespace-pre-wrap break-words mb-1">{msg.content}</p>
        )}

        {/* ── Price Search: stores ── */}
        {msg.stores && (
          <div className="mt-3">
            {/* Best deal if present at top level */}
            {msg.stores.best_deal && (
              <BestDealBanner deal={msg.stores.best_deal} />
            )}
            {Object.entries(msg.stores)
              .filter(([name]) => name !== "best_deal")
              .map(([storeName, books]) =>
                Array.isArray(books) ? (
                  <PriceCard key={storeName} store={storeName} books={books} />
                ) : null
              )}
          </div>
        )}

        {/* ── Price Comparison ── */}
        {msg.comparison && (
          <div className="mt-3">
            <ComparisonSection comparison={msg.comparison} />
          </div>
        )}

        {/* ── Recommendations (no prices) ── */}
        {msg.recommendations?.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wider mb-2.5" style={{ color: "#8c7b6a" }}>
              📚 Similar Books
            </p>
            <AgentInsightsBadges insights={msg.agent_insights} />
            {msg.recommendations.map((book, i) => (
              <BookCard key={i} book={book} index={i} />
            ))}
          </div>
        )}

        {/* ── Recommendations with purchase links ── */}
        {msg.recommendations_with_links?.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wider mb-2.5" style={{ color: "#8c7b6a" }}>
              📚 Similar Books + Where to Buy
            </p>
            <AgentInsightsBadges insights={msg.agent_insights} />
            {msg.recommendations_with_links.map((book, i) => (
              <BookCardWithLinks key={i} book={book} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
