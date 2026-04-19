# BookBot Frontend

Production-ready React + Vite + TailwindCSS frontend for the BookBot AI assistant.

## Stack
- React 18
- Vite 6
- Tailwind CSS v4
- Lucide React icons
- Google Fonts (Fraunces + DM Sans)

## Setup

```bash
npm install
```

### Development

Make sure your backend (`app.py`) is running on `http://localhost:5000`.

```bash
npm run dev
# Opens at http://localhost:3000
# /api requests are proxied to http://localhost:5000
```

### Production Build

```bash
npm run build
# Output in /dist — serve with nginx, Vercel, Netlify, etc.
```

## Environment

Copy `.env.example` to `.env.local`:

```
VITE_API_URL=https://your-backend-url.com/api
```

If `VITE_API_URL` is not set, the app uses Vite's dev proxy (`/api` → `localhost:5000`).

## Features

- **Product Search** — price results from Amazon & Flipkart with buy links
- **Price Comparison** — side-by-side comparison with best deal highlighted
- **Book Recommendations** — AI-curated similar books with reasoning
- **Recommendations + Prices** — recommendations with store links (top 3)
- **Multi-chat** — persistent chat history in localStorage
- **Mobile responsive** — collapsible sidebar drawer on mobile
- **Suggested queries** — quick-start prompts on empty chat
