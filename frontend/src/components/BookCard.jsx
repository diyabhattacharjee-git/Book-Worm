import { ExternalLink, Star, ShoppingCart, Tag } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function authorString(authors) {
  if (!authors) return "Unknown Author";
  if (Array.isArray(authors)) return authors.join(", ");
  return authors;
}

function StoreLink({ store, data, icon }) {
  if (!data?.link && !data?.price) return null;
  const hasLink = !!data.link;
  const price = data.price && data.price !== "Search manually" ? data.price : null;

  return (
    <div className="flex items-center justify-between gap-2 py-1.5 px-2.5 rounded-lg" style={{ background: "#f7f3ec" }}>
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-medium" style={{ color: "#6b5a3e" }}>{icon} {store}</span>
        {price && (
          <span className="text-xs font-semibold" style={{ color: "#2d5016" }}>{price}</span>
        )}
        {!price && (
          <span className="text-xs" style={{ color: "#a89070" }}>Price unavailable</span>
        )}
      </div>
      {hasLink && (
        <a
          href={data.link}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md transition-colors"
          style={{ background: "#d4790a", color: "#fff" }}
          onMouseEnter={e => e.currentTarget.style.background = "#f5a623"}
          onMouseLeave={e => e.currentTarget.style.background = "#d4790a"}
        >
          Buy <ExternalLink size={10} />
        </a>
      )}
    </div>
  );
}

// ─── Book card without purchase links ─────────────────────────────────────────

export function BookCard({ book, index }) {
  return (
    <div
      className="badge-anim rounded-xl p-4 mb-3"
      style={{
        background: "#fff",
        border: "1px solid #e8dfc8",
        boxShadow: "0 1px 4px rgba(80,50,10,0.07)",
      }}
    >
      <div className="flex gap-3">
        <div
          className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-display font-bold text-sm"
          style={{ background: "var(--amber-pale)", color: "var(--amber)" }}
        >
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm leading-tight mb-0.5" style={{ color: "#1a1208" }}>
            {book.title}
          </h4>
          <p className="text-xs mb-1.5" style={{ color: "#8c7b6a" }}>
            by {authorString(book.authors)}
          </p>
          {book.reason && (
            <p className="text-xs leading-relaxed" style={{ color: "#5a4a35" }}>
              {book.reason}
            </p>
          )}
          {book.why_similar && (
            <p className="text-xs leading-relaxed" style={{ color: "#5a4a35" }}>
              {book.why_similar}
            </p>
          )}
          {book.shared_themes?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {book.shared_themes.slice(0, 3).map((theme, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "#f0ebe0", color: "#7a6240" }}
                >
                  {theme}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Book card WITH purchase links ────────────────────────────────────────────

export function BookCardWithLinks({ book, index }) {
  const flipkart = book.stores?.flipkart;
  const amazon = book.stores?.amazon;
  const hasAnyLink = flipkart?.link || amazon?.link;

  return (
    <div
      className="badge-anim rounded-xl p-4 mb-3"
      style={{
        background: "#fff",
        border: "1px solid #e8dfc8",
        boxShadow: "0 1px 4px rgba(80,50,10,0.07)",
      }}
    >
      <div className="flex gap-3 mb-3">
        <div
          className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center font-display font-bold text-sm"
          style={{ background: "var(--amber-pale)", color: "var(--amber)" }}
        >
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm leading-tight mb-0.5" style={{ color: "#1a1208" }}>
            {book.title}
          </h4>
          <p className="text-xs mb-1.5" style={{ color: "#8c7b6a" }}>
            by {authorString(book.authors)}
          </p>
          {book.reason && (
            <p className="text-xs leading-relaxed mb-2" style={{ color: "#5a4a35" }}>
              {book.reason}
            </p>
          )}
          {book.shared_themes?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {book.shared_themes.slice(0, 3).map((theme, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "#f0ebe0", color: "#7a6240" }}
                >
                  {theme}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Store Links */}
      {hasAnyLink ? (
        <div className="space-y-1.5 pl-0">
          <StoreLink store="Flipkart" data={flipkart} icon="🛒" />
          <StoreLink store="Amazon" data={amazon} icon="📦" />
        </div>
      ) : (
        <div className="flex items-center gap-1.5 pl-0">
          <ShoppingCart size={12} style={{ color: "#c0a870" }} />
          <span className="text-xs" style={{ color: "#c0a870" }}>
            Search this title on Flipkart or Amazon
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Price search result card ─────────────────────────────────────────────────

export function PriceCard({ store, books }) {
  if (!books || books.length === 0) return null;
  const icon = store === "Amazon" ? "📦" : "🛒";
  const accentColor = store === "Amazon" ? "#e07b39" : "#1a73e8";

  return (
    <div
      className="badge-anim rounded-xl overflow-hidden mb-3"
      style={{ border: "1px solid #e8dfc8", background: "#fff" }}
    >
      <div
        className="px-4 py-2.5 flex items-center gap-2"
        style={{ background: accentColor + "15", borderBottom: "1px solid #e8dfc8" }}
      >
        <span>{icon}</span>
        <span className="font-semibold text-sm" style={{ color: accentColor }}>
          {store}
        </span>
        <span className="text-xs ml-auto px-2 py-0.5 rounded-full" style={{ background: accentColor + "20", color: accentColor }}>
          {books.length} result{books.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="p-2 space-y-1.5">
        {books.map((book, i) => (
          <div
            key={i}
            className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg"
            style={{ background: "#f9f6f0" }}
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate" style={{ color: "#1a1208" }}>
                {book.title || "Untitled"}
              </p>
              {book.price && (
                <p className="text-sm font-bold mt-0.5" style={{ color: "#2d5016" }}>
                  {book.price}
                </p>
              )}
            </div>
            {book.link && (
              <a
                href={book.link}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors"
                style={{ background: accentColor, color: "#fff" }}
                onMouseEnter={e => e.currentTarget.style.opacity = "0.85"}
                onMouseLeave={e => e.currentTarget.style.opacity = "1"}
              >
                Buy <ExternalLink size={10} />
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Best deal banner ─────────────────────────────────────────────────────────

export function BestDealBanner({ deal }) {
  if (!deal) return null;
  const best = Array.isArray(deal) ? deal[0] : deal;
  if (!best?.price && !best?.link) return null;

  return (
    <div
      className="badge-anim rounded-xl p-3.5 mb-3 flex items-center justify-between gap-3"
      style={{
        background: "linear-gradient(135deg, #2d5016 0%, #4a7c2f 100%)",
        boxShadow: "0 2px 12px rgba(45,80,22,0.25)",
      }}
    >
      <div>
        <div className="flex items-center gap-1.5 mb-0.5">
          <Star size={13} fill="#ffd700" stroke="#ffd700" />
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "#a8e080" }}>
            Best Deal
          </span>
        </div>
        {best.platform && (
          <p className="text-xs" style={{ color: "#c8e8b0" }}>on {best.platform}</p>
        )}
        {best.price && (
          <p className="text-lg font-bold" style={{ color: "#fff" }}>{best.price}</p>
        )}
      </div>
      {best.link && (
        <a
          href={best.link}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-semibold px-4 py-2 rounded-lg shrink-0"
          style={{ background: "#fff", color: "#2d5016" }}
          onMouseEnter={e => e.currentTarget.style.background = "#e8f5e0"}
          onMouseLeave={e => e.currentTarget.style.background = "#fff"}
        >
          Buy Now <ExternalLink size={13} />
        </a>
      )}
    </div>
  );
}

// ─── Price comparison section ─────────────────────────────────────────────────

export function ComparisonSection({ comparison }) {
  if (!comparison) return null;
  const { amazon, flipkart, best_deals } = comparison;

  return (
    <div className="mt-1 space-y-3">
      {/* Best deals */}
      {best_deals?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#8c7b6a" }}>
            🏆 Best Deals Found
          </p>
          {best_deals.map((deal, i) => (
            <div
              key={i}
              className="badge-anim rounded-xl p-3 mb-2"
              style={{ background: "#f0f7e8", border: "1px solid #b8d898" }}
            >
              <p className="text-sm font-semibold mb-1" style={{ color: "#1a1208" }}>{deal.title}</p>
              <p className="text-xs mb-1.5" style={{ color: "#4a7c2f" }}>{deal.comparison}</p>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs" style={{ color: "#8c7b6a" }}>Best on </span>
                  <span className="text-sm font-bold" style={{ color: "#2d5016" }}>
                    {deal.best_store}: {deal.best_price}
                  </span>
                  {deal.savings && deal.savings !== "Same price" && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded" style={{ background: "#c8e8b0", color: "#2d5016" }}>
                      Save {deal.savings}
                    </span>
                  )}
                </div>
                {deal.link && (
                  <a
                    href={deal.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium px-2.5 py-1.5 rounded-lg flex items-center gap-1"
                    style={{ background: "#2d5016", color: "#fff" }}
                  >
                    Buy <ExternalLink size={10} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Side-by-side */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <p className="text-xs font-medium mb-1.5 flex items-center gap-1" style={{ color: "#e07b39" }}>
            📦 Amazon ({amazon?.length || 0})
          </p>
          {(amazon || []).slice(0, 2).map((b, i) => (
            <div key={i} className="rounded-lg p-2 mb-1.5 text-xs" style={{ background: "#fff7f0", border: "1px solid #f5dcc5" }}>
              <p className="font-medium truncate" style={{ color: "#1a1208" }}>{b.title}</p>
              <p className="font-bold" style={{ color: "#e07b39" }}>{b.price || "N/A"}</p>
              {b.link && (
                <a href={b.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  View →
                </a>
              )}
            </div>
          ))}
        </div>
        <div>
          <p className="text-xs font-medium mb-1.5 flex items-center gap-1" style={{ color: "#1a73e8" }}>
            🛒 Flipkart ({flipkart?.length || 0})
          </p>
          {(flipkart || []).slice(0, 2).map((b, i) => (
            <div key={i} className="rounded-lg p-2 mb-1.5 text-xs" style={{ background: "#f0f4ff", border: "1px solid #c5d5f5" }}>
              <p className="font-medium truncate" style={{ color: "#1a1208" }}>{b.title}</p>
              <p className="font-bold" style={{ color: "#1a73e8" }}>{b.price || "N/A"}</p>
              {b.link && (
                <a href={b.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  View →
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Agent insights badge row ─────────────────────────────────────────────────

export function AgentInsightsBadges({ insights }) {
  if (!insights) return null;
  const items = [
    insights.primary_genre && { label: insights.primary_genre, icon: "📖" },
    insights.writing_style && { label: insights.writing_style, icon: "✍️" },
    insights.reader_goal && { label: insights.reader_goal, icon: "🎯" },
    insights.recommendation_tone && { label: insights.recommendation_tone, icon: "💬" },
  ].filter(Boolean);

  if (items.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mb-3">
      {items.map((item, i) => (
        <span
          key={i}
          className="text-xs px-2 py-0.5 rounded-full"
          style={{ background: "#f0ebe0", color: "#7a6240", border: "1px solid #ddd0b8" }}
        >
          {item.icon} {item.label}
        </span>
      ))}
    </div>
  );
}
