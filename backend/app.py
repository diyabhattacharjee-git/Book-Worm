from flask import Flask, request, jsonify
from flask_cors import CORS

import requests
import json
import re
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time
from functools import wraps
from collections import OrderedDict
from serpapi import GoogleSearch
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage
)

from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional, Any
from langchain_core.messages import BaseMessage

from playwright.sync_api import sync_playwright

load_dotenv()

# ─── LOGGING SETUP (Production-ready) ────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GROQ_KEY = os.getenv("GROQ_API_KEY")
SERP_API_KEY = os.getenv("SERP_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

app = Flask(__name__)
CORS(app)

# ─── LLM ──────────────────────────────────────────────────────────────────────

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=GROQ_KEY
)

# ─── REDIS CACHE (Production) ─────────────────────────────────────────────────

try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    USE_REDIS = True
    logger.info("✅ Redis connected for distributed caching")
except Exception as e:
    USE_REDIS = False
    logger.warning(f"⚠️ Redis not available, using in-memory cache: {e}")


class SimpleCache:
    """Fallback in-memory cache"""
    def __init__(self, max_size=1000, ttl_seconds=86400):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                self.cache.move_to_end(key)
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, datetime.now())


class RedisCache:
    """Production Redis cache"""
    def __init__(self, ttl_seconds=86400):
        self.ttl_seconds = ttl_seconds
        self.client = redis_client

    def get(self, key):
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
        return None

    def set(self, key, value):
        try:
            self.client.setex(key, self.ttl_seconds, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis SET error: {e}")


# Initialize cache based on availability
book_cache = RedisCache(ttl_seconds=86400) if USE_REDIS else SimpleCache(max_size=500, ttl_seconds=86400)


class RateLimiter:
    def __init__(self, max_calls, time_window):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    def can_call(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.time_window]
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False

    def wait_time(self):
        if not self.calls:
            return 0
        return max(0, self.time_window - (time.time() - min(self.calls)))


google_books_limiter = RateLimiter(max_calls=50, time_window=60)

# ─── PLAYWRIGHT BROWSER POOL (Production Fix) ─────────────────────────────────

class BrowserPool:
    """Reusable browser instance to avoid expensive launches"""
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.initialized = False
        
    def initialize(self):
        if not self.initialized:
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu"
                    ]
                )
                self.initialized = True
                logger.info("✅ Browser pool initialized")
            except Exception as e:
                logger.error(f"Browser initialization failed: {e}")
                self.initialized = False
    
    def get_context(self):
        if not self.initialized:
            self.initialize()
        if self.browser:
            return self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            )
        return None
    
    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.initialized = False


browser_pool = BrowserPool()

# Initialize browser pool on startup (production optimization)
try:
    browser_pool.initialize()
except Exception as e:
    logger.warning(f"Browser pool initialization failed on startup: {e}")

# ─── BOOK DATA APIs WITH TIMEOUT ──────────────────────────────────────────────

def google_books_search(query: str, use_cache=True, timeout=5) -> dict:
    cache_key = f"google_books:{query.lower()}"
    if use_cache:
        cached = book_cache.get(cache_key)
        if cached:
            logger.info(f"✅ Cache hit for: {query}")
            return cached

    if not google_books_limiter.can_call():
        logger.info("⏳ Rate limit reached. Trying Open Library fallback...")
        return open_library_search(query)

    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": query, "maxResults": 5}

    try:
        response = requests.get(url, params=params, timeout=timeout)
        if response.status_code == 429:
            return open_library_search(query)
        if response.status_code != 200:
            return open_library_search(query)

        data = response.json()
        if "items" not in data:
            return open_library_search(query)

        book = data["items"][0]["volumeInfo"]
        result = {
            "title": book.get("title", "No title available"),
            "description": book.get("description", "No description available"),
            "authors": book.get("authors", []),
            "categories": book.get("categories", [])
        }
        book_cache.set(cache_key, result)
        return result

    except requests.Timeout:
        logger.warning(f"⏳ Timeout for Google Books: {query}")
        return open_library_search(query)
    except Exception as e:
        logger.error(f"Google Books error: {e}")
        return open_library_search(query)


def open_library_search(query: str, timeout=5) -> dict:
    cache_key = f"open_library:{query.lower()}"
    cached = book_cache.get(cache_key)
    if cached:
        return cached

    url = "https://openlibrary.org/search.json"
    params = {"q": query, "limit": 5}

    try:
        response = requests.get(url, params=params, timeout=timeout)
        if response.status_code != 200:
            return {"error": f"API error {response.status_code}"}

        data = response.json()
        if not data.get("docs"):
            return {"error": "No books found"}

        book = data["docs"][0]
        description = ""
        if "first_sentence" in book:
            description = book["first_sentence"][0] if isinstance(book["first_sentence"], list) else book["first_sentence"]
        elif "subtitle" in book:
            description = book.get("subtitle", "")
        else:
            description = f"A book by {', '.join(book.get('author_name', ['Unknown']))}"

        result = {
            "title": book.get("title", "No title available"),
            "description": description or "No description available",
            "authors": book.get("author_name", []),
            "categories": book.get("subject", [])[:3] if "subject" in book else []
        }
        book_cache.set(cache_key, result)
        return result

    except requests.Timeout:
        logger.warning(f"⏳ Timeout for Open Library: {query}")
        return {"error": "Request timeout"}
    except Exception as e:
        return {"error": str(e)}


def fetch_books_by_keywords(keywords: list, original_title: str, max_per_keyword: int = 2) -> list:
    seen_titles = {original_title.lower()}
    recommended = []
    use_open_library = False

    for keyword in keywords[:3]:
        if not google_books_limiter.can_call():
            use_open_library = True

        if use_open_library:
            remaining = keywords[keywords.index(keyword):]
            open_lib_results = fetch_books_by_keywords_open_library(remaining, original_title, max_per_keyword=2)
            recommended.extend(open_lib_results)
            break

        cache_key = f"keyword_search:{keyword.lower()}"
        cached = book_cache.get(cache_key)

        if cached:
            results = cached
        else:
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {"q": f'subject:"{keyword}"', "maxResults": max_per_keyword, "printType": "books"}
            try:
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 429:
                    remaining = keywords[keywords.index(keyword):]
                    open_lib_results = fetch_books_by_keywords_open_library(remaining, original_title, max_per_keyword=2)
                    recommended.extend(open_lib_results)
                    break
                if response.status_code != 200:
                    continue
                data = response.json()
                results = data.get("items", [])
                book_cache.set(cache_key, results)
            except requests.Timeout:
                logger.warning(f"⏳ Timeout for keyword: {keyword}")
                continue
            except Exception as e:
                logger.error(f"Keyword search error for '{keyword}': {e}")
                continue

        for item in results:
            info = item.get("volumeInfo", {})
            title = info.get("title", "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            recommended.append({
                "title": title,
                "authors": info.get("authors", []),
                "description": info.get("description", "No description available"),
                "categories": info.get("categories", []),
                "matched_keyword": keyword
            })
            
            if len(recommended) >= 10:
                break
                
        if len(recommended) >= 10:
            break
            
        time.sleep(0.2)

    return recommended


def fetch_books_by_keywords_open_library(keywords: list, original_title: str, max_per_keyword: int = 2) -> list:
    seen_titles = {original_title.lower()}
    recommended = []

    for keyword in keywords[:3]:
        cache_key = f"open_library_keyword:{keyword.lower()}"
        cached = book_cache.get(cache_key)

        if cached:
            results = cached
        else:
            url = "https://openlibrary.org/search.json"
            params = {"q": f'subject:{keyword}', "limit": max_per_keyword}
            try:
                response = requests.get(url, params=params, timeout=5)
                if response.status_code != 200:
                    continue
                data = response.json()
                results = data.get("docs", [])
                book_cache.set(cache_key, results)
                time.sleep(0.3)
            except requests.Timeout:
                logger.warning(f"⏳ Timeout for Open Library keyword: {keyword}")
                continue
            except Exception as e:
                logger.error(f"Keyword search error for '{keyword}': {e}")
                continue

        for book in results:
            title = book.get("title", "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            description = ""
            if "first_sentence" in book:
                description = book["first_sentence"][0] if isinstance(book["first_sentence"], list) else book["first_sentence"]
            elif "subtitle" in book:
                description = book.get("subtitle", "")
            else:
                description = f"A book about {keyword}"

            recommended.append({
                "title": title,
                "authors": book.get("author_name", []),
                "description": description or "No description available",
                "categories": book.get("subject", [])[:3] if "subject" in book else [keyword],
                "matched_keyword": keyword
            })
            
            if len(recommended) >= 10:
                break
                
        if len(recommended) >= 10:
            break
            
    return recommended


def fetch_candidates_from_known_titles(known_titles: list, original_title: str) -> list:
    seen = {original_title.lower()}
    candidates = []

    for title in known_titles[:5]:
        if title.lower() in seen:
            continue
        seen.add(title.lower())

        result = google_books_search(title, use_cache=True)
        if "error" not in result:
            candidates.append({
                "title": result["title"],
                "authors": result.get("authors", []),
                "description": result.get("description", "No description available"),
                "categories": result.get("categories", []),
                "matched_keyword": "direct recommendation"
            })
        time.sleep(0.15)

    return candidates


def filter_high_quality_books(candidates):
    filtered = []
    for book in candidates:
        title = book.get("title", "").lower()
        if len(title) < 3:
            continue
        if any(x in title for x in ["summary", "workbook", "analysis", "guide"]):
            continue
        if not book.get("authors"):
            continue
        filtered.append(book)
    return filtered[:10]

# ─── SCRAPING WITH BROWSER POOL ───────────────────────────────────────────────

def fetch_amazon_price_serpapi(query, timeout=10):
    logger.info(f"🔍 Amazon Search: {query}")
    params = {
        "engine": "amazon",
        "amazon_domain": "amazon.in",
        "k": query,
        "api_key": SERP_API_KEY,
        "timeout": timeout
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        books = []
        if "organic_results" in results:
            for item in results["organic_results"][:5]:
                books.append({
                    "title": item.get("title"),
                    "price": item.get("price"),
                    "link": item.get("link")
                })
        logger.info(f"✅ Amazon found {len(books)} books")
        return books
    except Exception as e:
        logger.error(f"Amazon search error: {e}")
        return []


def flipkart_browser_scraper(query, timeout=15):
    """Uses browser pool for better performance"""
    books = []
    context = None
    try:
        context = browser_pool.get_context()
        if not context:
            logger.error("Failed to get browser context")
            return []
            
        page = context.new_page()
        page.set_default_timeout(timeout * 1000)
        
        url = f"https://www.flipkart.com/search?q={query.replace(' ', '%20')}"
        page.goto(url, timeout=timeout * 1000)
        
        try:
            page.wait_for_selector("button._2KpZ6l._2doB4z", timeout=3000)
            page.click("button._2KpZ6l._2doB4z")
        except:
            pass
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(2000)
        page.wait_for_selector("div[data-id]", timeout=timeout * 1000)
        
        cards = page.query_selector_all("div[data-id]")
        seen = set()
        for card in cards[:6]:
            try:
                title_tag = card.query_selector("a[title]")
                if not title_tag:
                    continue
                title = title_tag.get_attribute("title")
                if not title or title in seen:
                    continue
                seen.add(title)
                card_text = card.inner_text()
                price_match = re.search(r"₹\s?[\d,]+", card_text)
                price = price_match.group() if price_match else "Not available"
                href = title_tag.get_attribute("href")
                link = ""
                if href:
                    clean_href = href.split('?')[0]
                    link = clean_href if clean_href.startswith('http') else f"https://www.flipkart.com{clean_href}"
                if link:
                    books.append({"store": "Flipkart", "title": title, "price": price, "link": link})
                if len(books) >= 6:
                    break
            except Exception as e:
                logger.error(f"Card parse error: {e}")
                continue
        
        logger.info(f"✅ Flipkart: {len(books)} books found")
        return books
    except Exception as e:
        logger.error(f"Flipkart error: {e}")
        return []
    finally:
        if context:
            try:
                context.close()
            except:
                pass


def multi_store_price_search(query):
    """Parallel price search with timeout handling"""
    results = {"Amazon": [], "Flipkart": []}
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_flipkart = executor.submit(flipkart_browser_scraper, query, 15)
        future_amazon = executor.submit(fetch_amazon_price_serpapi, query, 10)
        
        try:
            fk = future_flipkart.result(timeout=20)
            results["Flipkart"] = fk
        except Exception as e:
            logger.warning(f"Flipkart timeout: {e}")
            
        try:
            amz = future_amazon.result(timeout=15)
            results["Amazon"] = amz
        except Exception as e:
            logger.warning(f"Amazon timeout: {e}")
    
    logger.info(f"📊 Total results: {len(results['Amazon']) + len(results['Flipkart'])}")
    return results

# ═══════════════════════════════════════════════════════════════════════════════
#  OPTIMIZED MULTI-AGENT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def user_intent_and_context_agent(query: str, book_info: dict) -> dict:
    """Merged UserIntentAgent + ContextAgent into single LLM call"""
    logger.info("🧠 [MergedAgent] Analyzing user intent + building reader profile...")

    prompt = f"""
You are a combined User Intent & Reader Profile Analysis Agent.

User query: "{query}"
Book found: {book_info.get("title", "Unknown")}
Authors: {", ".join(book_info.get("authors", []))}
Description: {book_info.get("description", "")[:500]}

Analyze BOTH the user's intent AND build their reader profile. Return ONLY a JSON object:
{{
  "intent": {{
    "goal": "one of: learn|escape|grow|entertain|gift|research|inspire",
    "mood": "one of: curious|seeking_comfort|motivated|bored|stressed|nostalgic|adventurous",
    "reading_context": "one of: casual|serious|commute|academic|bedtime|social",
    "urgency": "one of: immediate|browsing|planning",
    "inferred_reason": "1 sentence: why this person is likely looking for this book",
    "recommendation_tone": "one of: nurturing|exciting|intellectual|practical|emotional|adventurous"
  }},
  "reader_profile": {{
    "reading_level": "one of: beginner|intermediate|advanced",
    "preferred_length": "one of: short(<200pages)|medium(200-400)|long(400+)|any",
    "cultural_preference": "one of: indian_authors|international|mixed",
    "format_preference": "one of: physical|ebook|audiobook|any",
    "topics_to_emphasize": ["2-3 topics that match their profile"],
    "topics_to_avoid": ["1-2 topics that don't match"],
    "india_relevance": "one of: high|medium|low",
    "profile_summary": "2 sentence reader profile description",
    "ideal_next_book_traits": ["3-4 traits the next book should have"]
  }}
}}

No markdown, no explanation. Only valid JSON.
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)
        logger.info(f"✅ [MergedAgent] Goal={result['intent'].get('goal')}, Level={result['reader_profile'].get('reading_level')}")
        return result
    except Exception as e:
        logger.error(f"[MergedAgent] Error: {e}")
        return {
            "intent": {
                "goal": "learn",
                "mood": "curious",
                "reading_context": "casual",
                "urgency": "browsing",
                "inferred_reason": "User is exploring books on this topic",
                "recommendation_tone": "intellectual"
            },
            "reader_profile": {
                "reading_level": "intermediate",
                "preferred_length": "any",
                "cultural_preference": "mixed",
                "format_preference": "any",
                "topics_to_emphasize": [],
                "topics_to_avoid": [],
                "india_relevance": "medium",
                "profile_summary": "A reader looking for books similar in theme and style.",
                "ideal_next_book_traits": []
            }
        }


def content_similarity_agent(book_info: dict, intent: dict) -> dict:
    """Extracts deep semantic features for finding similar books"""
    logger.info("📚 [ContentSimilarityAgent] Extracting semantic features...")

    prompt = f"""
You are a Content Similarity Agent that creates a precise semantic fingerprint of a book.

Book: {book_info.get("title")}
Authors: {", ".join(book_info.get("authors", []))}
Categories: {", ".join(book_info.get("categories", []))}
Description: {book_info.get("description", "")[:500]}

User's reading goal: {intent.get("goal", "learn")}
User's mood: {intent.get("mood", "curious")}

Extract a semantic fingerprint. Return ONLY a JSON object:
{{
  "primary_genre": "specific genre (e.g. 'narrative nonfiction' not just 'nonfiction')",
  "sub_genres": ["2-3 sub-genres"],
  "core_themes": ["4-6 highly specific themes"],
  "writing_style": "e.g. 'conversational science writing' or 'lyrical memoir'",
  "narrative_structure": "e.g. 'chronological autobiography' or 'case-study driven'",
  "pacing": "one of: slow-burn|steady|fast-paced|episodic",
  "complexity": "one of: accessible|intermediate|advanced|academic",
  "comparable_authors": ["2-3 authors with similar style"],
  "search_keywords": ["6-8 precise search keywords for finding similar books"],
  "avoid_keywords": ["2-3 keywords to avoid (opposite tone/theme)"]
}}

No markdown. Only valid JSON.
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
        result = json.loads(raw)
        logger.info(f"✅ [ContentSimilarityAgent] Genre={result.get('primary_genre')}, Style={result.get('writing_style')}")
        return result
    except Exception as e:
        logger.error(f"[ContentSimilarityAgent] Error: {e}")
        return {
            "primary_genre": "general",
            "sub_genres": [],
            "core_themes": [],
            "writing_style": "general",
            "narrative_structure": "general",
            "pacing": "steady",
            "complexity": "accessible",
            "comparable_authors": [],
            "search_keywords": [book_info.get("title", "")],
            "avoid_keywords": []
        }


def merged_diversity_and_ranking_agent(candidates: list, original_title: str, intent: dict, similarity: dict, context: dict) -> list:
    """
    MERGED: Diversity + Critic into single LLM call
    Reduces from 5 to 4 LLM calls per recommendation request
    """
    logger.info("🌈⚖️ [MergedDiversityRankingAgent] Ensuring diversity + ranking quality...")

    if not candidates:
        return []

    candidates = filter_high_quality_books(candidates)[:10]

    candidate_text = ""
    for i, book in enumerate(candidates, 1):
        desc = book.get("description", "")[:150]
        candidate_text += (
            f"{i}. Title: {book['title']}\n"
            f"   Authors: {', '.join(book.get('authors', ['Unknown']))}\n"
            f"   Categories: {', '.join(book.get('categories', []))}\n"
            f"   Description: {desc}\n\n"
        )

    prompt = f"""
You are a combined Diversity + Quality Ranking Agent for book recommendations.

Original book: "{original_title}"
Reader goal: {intent.get("goal")} | Mood: {intent.get("mood")}
Reader level: {context.get("reading_level")} | Tone wanted: {intent.get("recommendation_tone")}
Primary genre: {similarity.get("primary_genre")}
Core themes: {", ".join(similarity.get("core_themes", []))}
Writing style: {similarity.get("writing_style")}

From this candidate list, select exactly 5 books ensuring:
1. MAXIMUM DIVERSITY (mix of sub-genres, eras, authors, at least 1 hidden gem)
2. HIGHEST QUALITY matches for this reader's profile
3. No more than 2 books from the same author

Return ONLY a JSON array:
[
  {{
    "title": "...",
    "authors": ["..."],
    "score": 8.5,
    "reason": "2-3 sentences explaining why THIS reader would love this book right now",
    "shared_themes": ["2-3 specific shared themes"],
    "emotional_tone": ["1-2 emotions"],
    "reading_level": "beginner|intermediate|advanced",
    "why_different": "1 sentence on what new perspective this adds"
  }}
]

Candidates:
{candidate_text}

No markdown. Only valid JSON array.
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
        ranked = json.loads(raw)

        if isinstance(ranked, list):
            ranked = sorted(ranked, key=lambda x: x.get("score", 0), reverse=True)
            logger.info(f"✅ [MergedDiversityRankingAgent] Final {len(ranked)} diverse & ranked books")
            return ranked[:5]
        return []

    except Exception as e:
        logger.error(f"[MergedDiversityRankingAgent] Error: {e}")
        return [
            {
                "title": b["title"],
                "authors": b.get("authors", []),
                "score": 7.0,
                "reason": f"Similar themes to {original_title}",
                "shared_themes": b.get("categories", [])[:2],
                "emotional_tone": [],
                "reading_level": context.get("reading_level", "intermediate"),
                "why_different": "Offers a fresh perspective on the subject."
            }
            for b in candidates[:5]
        ]


def execution_agent(recommendations: list, context: dict) -> list:
    """Fetches prices for TOP 3 books only"""
    logger.info("🛒 [ExecutionAgent] Planning purchase strategy...")

    enriched = []

    for book in recommendations[:3]:
        title = book["title"]
        logger.info(f"  💳 [ExecutionAgent] Getting prices for: {title}")

        try:
            store_results = multi_store_price_search(title)
        except Exception as e:
            logger.error(f"Price fetch error: {e}")
            store_results = {"Amazon": [], "Flipkart": []}

        flipkart_data = store_results.get("Flipkart", [])
        amazon_data = store_results.get("Amazon", [])

        flipkart_price = None
        flipkart_link = None
        amazon_price = None
        amazon_link = None

        if flipkart_data:
            first = flipkart_data[0]
            flipkart_price = first.get("price")
            flipkart_link = first.get("link")

        if amazon_data:
            first = amazon_data[0]
            amazon_price = first.get("price")
            amazon_link = first.get("link")

        best_platform = None
        best_price = None

        def parse_price(p):
            if not p:
                return None
            nums = re.sub(r"[^\d]", "", str(p))
            return int(nums) if nums else None

        fk_num = parse_price(flipkart_price)
        amz_num = parse_price(amazon_price)

        if fk_num and amz_num:
            if fk_num <= amz_num:
                best_platform = "Flipkart"
                best_price = flipkart_price
            else:
                best_platform = "Amazon"
                best_price = amazon_price
        elif fk_num:
            best_platform = "Flipkart"
            best_price = flipkart_price
        elif amz_num:
            best_platform = "Amazon"
            best_price = amazon_price

        format_advice = "Physical copy recommended for Indian market"
        if context.get("format_preference") == "ebook":
            format_advice = "Kindle edition available on Amazon for lower cost"

        book_enriched = {**book}
        book_enriched["stores"] = {
            "flipkart": {"price": flipkart_price or "Not available", "link": flipkart_link},
            "amazon": {"price": amazon_price or "Not available", "link": amazon_link}
        }
        book_enriched["best_deal"] = {
            "platform": best_platform,
            "price": best_price
        }
        book_enriched["format_advice"] = format_advice
        enriched.append(book_enriched)
        time.sleep(0.5)

    for book in recommendations[3:]:
        book_enriched = {**book}
        book_enriched["stores"] = {
            "flipkart": {"price": "Search manually", "link": None},
            "amazon": {"price": "Search manually", "link": None}
        }
        book_enriched["best_deal"] = {
            "platform": None,
            "price": None
        }
        book_enriched["format_advice"] = "Check Amazon/Flipkart for pricing"
        enriched.append(book_enriched)

    logger.info(f"✅ [ExecutionAgent] Enriched {len(enriched)} books (prices for top 3)")
    return enriched


def run_multi_agent_recommendation(query: str, fetch_prices: bool = False) -> dict:
    """
    OPTIMIZED Orchestrator:
    - Now uses only 4 LLM calls (was 5-6)
    - Merged Intent+Context (saved 1 call)
    - Merged Diversity+Ranking (saved 1 call)
    """
    logger.info(f"\n🚀 OPTIMIZED Multi-Agent Pipeline starting for: '{query}'")

    book_info = google_books_search(query, use_cache=True)
    if "error" in book_info:
        return {"error": f"Could not find book: {query}"}

    logger.info(f"📖 Original book: {book_info['title']}")

    # LLM Call 1: MERGED User Intent + Context Agent
    merged_analysis = user_intent_and_context_agent(query, book_info)
    intent = merged_analysis["intent"]
    context = merged_analysis["reader_profile"]

    # LLM Call 2: Content Similarity Agent (runs in parallel with candidate fetch)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_similarity = executor.submit(content_similarity_agent, book_info, intent)
        similarity = future_similarity.result()

    # Fetch candidate books
    logger.info("📚 Fetching candidate books...")

    # LLM Call 3: Known recommendations
    known_recs_prompt = f"""
You are a world-class book recommendation engine.

Reader profile:
- Original book: {book_info['title']} by {', '.join(book_info.get('authors', []))}
- Reader goal: {intent.get('goal')} | Mood: {intent.get('mood')}
- Preferred writing style: {similarity.get('writing_style')}
- Core themes: {', '.join(similarity.get('core_themes', []))}
- Reading level: {context.get('reading_level')}

Recommend exactly 5 well-known, high-quality books.

Return ONLY a JSON array (no markdown):
[
  {{
    "title": "exact title",
    "authors": ["author names"],
    "description": "2-3 sentences about the book",
    "categories": ["genre/theme tags"],
    "matched_keyword": "which reader trait this matches"
  }}
]
"""
    try:
        resp = llm.invoke([HumanMessage(content=known_recs_prompt)])
        raw = resp.content.strip()
        raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
        llm_candidates = json.loads(raw)
        if not isinstance(llm_candidates, list):
            llm_candidates = []
        logger.info(f"🧠 LLM suggested {len(llm_candidates)} candidates")
    except Exception as e:
        logger.error(f"LLM candidate generation error: {e}")
        llm_candidates = []

    verified_candidates = fetch_candidates_from_known_titles(
        [b["title"] for b in llm_candidates],
        book_info["title"]
    )

    if len(verified_candidates) < 5:
        keywords = similarity.get("search_keywords", [])
        if keywords:
            keyword_candidates = fetch_books_by_keywords(keywords, book_info["title"], max_per_keyword=2)
            existing = {c["title"].lower() for c in verified_candidates}
            for c in keyword_candidates:
                if c["title"].lower() not in existing:
                    verified_candidates.append(c)
                    existing.add(c["title"].lower())
                    if len(verified_candidates) >= 10:
                        break

    verified_titles = {c["title"].lower() for c in verified_candidates}
    for llm_book in llm_candidates:
        if llm_book["title"].lower() not in verified_titles and len(verified_candidates) < 10:
            verified_candidates.append(llm_book)
            verified_titles.add(llm_book["title"].lower())

    logger.info(f"📚 Total candidates pool: {len(verified_candidates)} (capped at 10)")

    # LLM Call 4: MERGED Diversity + Ranking Agent
    final_recommendations = merged_diversity_and_ranking_agent(
        verified_candidates,
        book_info["title"],
        intent,
        similarity,
        context
    )

    if not final_recommendations:
        return {"error": "No suitable recommendations found"}

    if fetch_prices:
        final_recommendations = execution_agent(final_recommendations, context)

    return {
        "original_book": book_info["title"],
        "intent_analysis": intent,
        "reader_profile": context.get("profile_summary", ""),
        "recommendations": final_recommendations,
        "agent_insights": {
            "primary_genre": similarity.get("primary_genre"),
            "writing_style": similarity.get("writing_style"),
            "reader_goal": intent.get("goal"),
            "recommendation_tone": intent.get("recommendation_tone")
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
#  LANGGRAPH TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def format_response(
    text="",
    stores=None,
    recommendations=None,
    recommendations_with_links=None,
    agent_insights=None,
    comparison=None
):
    return json.dumps({
        "response": text,
        "stores": stores,
        "recommendations": recommendations,
        "recommendations_with_links": recommendations_with_links,
        "agent_insights": agent_insights,
        "comparison": comparison
    })


@tool
def compare_price(query: str) -> str:
    """
    Compare prices of a book across Amazon and Flipkart.
    Returns top 2 results from each store with price comparison and best deal recommendation.
    Use ONLY when user explicitly asks to compare prices across stores.
    """
    try:
        logger.info(f"🔍 COMPARE_PRICE: {query}")
        store_results = multi_store_price_search(query)

        amazon_books = store_results.get("Amazon", [])[:2]
        flipkart_books = store_results.get("Flipkart", [])[:2]

        if not amazon_books and not flipkart_books:
            return format_response(
                text="❌ No results found on either store. Try a different search term.",
                comparison=None
            )

        comparison_data = {
            "amazon": amazon_books,
            "flipkart": flipkart_books,
            "best_deals": []
        }

        # Find best deals for each unique book title
        all_titles = set()
        for book in amazon_books:
            all_titles.add(book.get("title", "").lower())
        for book in flipkart_books:
            all_titles.add(book.get("title", "").lower())

        def parse_price(p):
            if not p:
                return None
            nums = re.sub(r"[^\d]", "", str(p))
            return int(nums) if nums else None

        for title_lower in all_titles:
            amz_match = next((b for b in amazon_books if b.get("title", "").lower() == title_lower), None)
            fk_match = next((b for b in flipkart_books if b.get("title", "").lower() == title_lower), None)

            if amz_match and fk_match:
                amz_price = parse_price(amz_match.get("price"))
                fk_price = parse_price(fk_match.get("price"))

                if amz_price and fk_price:
                    if fk_price < amz_price:
                        savings = amz_price - fk_price
                        comparison_data["best_deals"].append({
                            "title": fk_match.get("title"),
                            "best_store": "Flipkart",
                            "best_price": fk_match.get("price"),
                            "link": fk_match.get("link"),
                            "savings": f"₹{savings}",
                            "comparison": f"Amazon: {amz_match.get('price')} | Flipkart: {fk_match.get('price')}"
                        })
                    else:
                        savings = fk_price - amz_price
                        comparison_data["best_deals"].append({
                            "title": amz_match.get("title"),
                            "best_store": "Amazon",
                            "best_price": amz_match.get("price"),
                            "link": amz_match.get("link"),
                            "savings": f"₹{savings}" if savings > 0 else "Same price",
                            "comparison": f"Amazon: {amz_match.get('price')} | Flipkart: {fk_match.get('price')}"
                        })

        return format_response(
            text=f"📊 Price comparison for '{query}' (showing top 2 from each store):",
            comparison=comparison_data
        )

    except Exception as e:
        logger.error(f"compare_price ERROR: {e}")
        return format_response(
            text="⚠️ Something went wrong while comparing prices.",
            comparison=None
        )


@tool
def product_search(query: str) -> str:
    """
    Search for book prices from Amazon & Flipkart.
    Use this for simple price searches when user mentions a book title.
    """
    try:
        logger.info(f"🔍 PRODUCT_SEARCH: {query}")
        store_results = multi_store_price_search(query)

        if not store_results["Amazon"] and not store_results["Flipkart"]:
            return format_response(
                text="❌ No results found. Try rephrasing your search.",
                stores={}
            )

        return format_response(
            text=f"Here are prices for '{query}' 📚",
            stores=store_results
        )
    except Exception as e:
        logger.error(f"product_search ERROR: {e}")
        return format_response(text="⚠️ Something went wrong while searching.", stores={})


@tool
def recommend_similar_books(query: str) -> str:
    """
    Recommend books similar to the query using multi-agent reasoning.
    Use when user wants book recommendations WITHOUT purchase links.
    """
    try:
        logger.info(f"📖 RECOMMEND_SIMILAR_BOOKS: {query}")

        result = run_multi_agent_recommendation(query, fetch_prices=False)

        if "error" in result:
            return format_response(
                text=f"❌ {result['error']}",
                recommendations=[]
            )

        return format_response(
            text=f"📚 Books similar to '{result['original_book']}':",
            recommendations=result["recommendations"],
            agent_insights=result.get("agent_insights")
        )

    except Exception as e:
        logger.error(f"recommend_similar_books ERROR: {e}")
        return format_response(
            text="⚠️ Something went wrong while finding recommendations.",
            recommendations=[]
        )


@tool
def recommend_books_with_prices(query: str) -> str:
    """
    Recommend books similar to the query AND provide purchase links.
    Prices fetched ONLY for top 3 books for better performance.
    Use when user wants book recommendations with prices/links.
    """
    try:
        logger.info(f"🎯 RECOMMEND_BOOKS_WITH_PRICES: {query}")

        result = run_multi_agent_recommendation(query, fetch_prices=True)

        if "error" in result:
            return format_response(
                text=f"❌ {result['error']}",
                recommendations_with_links=[]
            )

        recs_with_links = []
        for book in result["recommendations"]:
            recs_with_links.append({
                "title": book["title"],
                "authors": book.get("authors", []),
                "reason": book.get("reason", ""),
                "shared_themes": book.get("shared_themes", []),
                "emotional_tone": book.get("emotional_tone", []),
                "why_different": book.get("why_different", ""),
                "reading_level": book.get("reading_level", ""),
                "score": book.get("score"),
                "stores": book.get("stores", {}),
                "best_deal": book.get("best_deal", {}),
                "format_advice": book.get("format_advice", "")
            })

        return format_response(
            text=f"📚 Books similar to '{result['original_book']}' (prices for top 3):",
            recommendations_with_links=recs_with_links,
            agent_insights=result.get("agent_insights")
        )

    except Exception as e:
        logger.error(f"recommend_books_with_prices ERROR: {e}")
        return format_response(
            text="⚠️ Something went wrong while finding recommendations with prices.",
            recommendations_with_links=[]
        )

# ─── LANGGRAPH SETUP ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are BookBot — an intelligent book shopping assistant 📚 powered by an OPTIMIZED multi-agent AI system.

**YOUR CORE IDENTITY**
- You ONLY help with book-related queries
- You focus on Indian book shopping platforms (Amazon.in, Flipkart)
- You are friendly, concise, and results-oriented

**TOOL SELECTION** (USE ONLY ONE TOOL PER QUERY)

**compare_price** → Use when:
   - User explicitly asks to "compare prices" across stores
   - "Which store has the best deal for X?"
   - "Compare X on Amazon and Flipkart"
   - Shows top 2 results from EACH store with comparison

**product_search** → Use when:
   - User asks for prices of a specific book
   - User enters just a book name/title
   - "How much does X cost?"
   - "Where can I buy X?"
   - This is FAST and does NOT trigger the full recommendation pipeline

**recommend_similar_books** → Use when:
   - "Books like X"
   - "Similar to Y"
   - User wants recommendations WITHOUT prices
   - This is FASTER (no price fetching)

**recommend_books_with_prices** → Use when:
   - "Recommend books like X with prices"
   - "Similar books I can buy"
   - User wants both recommendations AND purchase info
   - Prices fetched for TOP 3 recommendations only

**RESPONSE GUIDELINES:**
- Be conversational and friendly
- Keep responses concise
- Explain recommendations clearly
- Note that compare_price shows top 2 from EACH store for focused comparison
- Note that recommend_books_with_prices shows prices for top 3 books to keep responses fast
"""

ALL_TOOLS = [compare_price, product_search, recommend_similar_books, recommend_books_with_prices]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}

llm_with_tools = llm.bind_tools(ALL_TOOLS)


class AgentState(TypedDict):
    messages: List[BaseMessage]


def agent_node(state):
    msgs = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(msgs)
    return {"messages": state["messages"] + [response]}


def tool_node(state):
    last = state["messages"][-1]
    out = []

    for tc in last.tool_calls:
        logger.info(f"🔧 TOOL CALL: {tc}")
        result = {"error": "Tool execution failed"}

        try:
            tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            tool_call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})

            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except:
                    args = {}

            if "book_name" in args and "query" not in args:
                args["query"] = args.pop("book_name")

            if not args.get("query"):
                result = json.dumps({"error": "Missing query parameter"})
            elif tool_name in TOOL_MAP:
                tool_result = TOOL_MAP[tool_name].invoke(args)
                result = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                logger.info(f"✅ TOOL RESULT ({tool_name}): {str(result)[:200]}")
            else:
                result = json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"TOOL ERROR: {e}")
            result = json.dumps({"error": str(e)})

        out.append(ToolMessage(content=result, tool_call_id=tool_call_id))

    return {"messages": state["messages"] + out}


def should_continue(state):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
shopbot = graph.compile()

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message", "")
        logger.info(f"\n💬 USER: {user_msg}")

        result = shopbot.invoke({"messages": [HumanMessage(content=user_msg)]})

        response_text = ""
        stores_data = None
        recommendations_data = None
        recommendations_with_links_data = None
        agent_insights_data = None
        comparison_data = None

        for m in reversed(result["messages"]):
            if isinstance(m, ToolMessage):
                try:
                    parsed = json.loads(m.content)
                    response_text = parsed.get("response", "Here are your results 📚")
                    stores_data = parsed.get("stores", None)
                    recommendations_data = parsed.get("recommendations", None)
                    recommendations_with_links_data = parsed.get("recommendations_with_links", None)
                    agent_insights_data = parsed.get("agent_insights", None)
                    comparison_data = parsed.get("comparison", None)
                    break
                except Exception as e:
                    logger.error(f"Tool parse error: {e}")

        if not response_text:
            for m in reversed(result["messages"]):
                if isinstance(m, AIMessage):
                    response_text = m.content
                    break

        return jsonify({
            "response": response_text,
            "stores": stores_data,
            "recommendations": recommendations_data,
            "recommendations_with_links": recommendations_with_links_data,
            "agent_insights": agent_insights_data,
            "comparison": comparison_data
        })

    except Exception as e:
        logger.error(f"CHAT ERROR: {e}")
        return jsonify({
            "response": "⚠️ Backend error occurred",
            "stores": None,
            "recommendations": None,
            "recommendations_with_links": None,
            "agent_insights": None,
            "comparison": None
        }), 500


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "BookBot Multi-Agent PRODUCTION",
        "environment": ENVIRONMENT,
        "cache": "Redis" if USE_REDIS else "In-Memory",
        "browser_pool": browser_pool.initialized,
        "agents": [
            "MergedIntentContextAgent",
            "ContentSimilarityAgent",
            "MergedDiversityRankingAgent",
            "ExecutionAgent"
        ],
        "tools": [
            "compare_price (NEW)",
            "product_search",
            "recommend_similar_books",
            "recommend_books_with_prices"
        ],
        "optimizations": [
            "4 LLM calls (was 5-6)",
            "Redis distributed cache",
            "Browser pool (reusable)",
            "Parallel execution",
            "Gunicorn ready",
            "Production logging"
        ],
        "time": datetime.now().isoformat(),
        "version": "4.0-PRODUCTION"
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    return jsonify({"status": "reset_ok"})


if __name__ == "__main__":
    # Development mode only
    app.run(host="0.0.0.0", port=5000, debug=False)