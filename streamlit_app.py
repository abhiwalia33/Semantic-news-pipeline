"""Streamlit frontend for AI News Search.

Talks only to the already-deployed live API over HTTP — no backend/app
logic lives here.
"""
import requests
import streamlit as st

API_BASE = "https://ai-news-api-104487450523.us-central1.run.app"
SEARCH_TIMEOUT = 30  # embedding + vector search takes a moment
NEWS_TIMEOUT = 15

st.set_page_config(
    page_title="AI News Search",
    page_icon="🧊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Nord-themed styling
# ---------------------------------------------------------------------------
NORD = {
    "bg": "#2E3440",
    "card": "#3B4252",
    "card_border": "#434C5E",
    "accent": "#5E81AC",
    "accent_bright": "#88C0D0",
    "text": "#ECEFF4",
    "text_soft": "#D8DEE9",
    "muted": "#9EA7B8",
    "muted_dark": "#4C566A",
}

st.markdown(
    f"""
    <style>
    /* App background + base text */
    .stApp {{
        background-color: {NORD["bg"]};
        color: {NORD["text"]};
    }}
    html, body, [class*="css"] {{
        font-family: "Source Sans Pro", "Segoe UI", sans-serif;
    }}

    /* Hide Streamlit chrome so it doesn't look like a default app */
    #MainMenu, footer, header[data-testid="stHeader"] {{
        visibility: hidden;
        height: 0;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {NORD["card"]};
        border-right: 1px solid {NORD["card_border"]};
    }}
    [data-testid="stSidebar"] * {{
        color: {NORD["text_soft"]};
    }}

    /* Header block */
    .app-header {{
        padding: 1.75rem 0 1rem 0;
        border-bottom: 1px solid {NORD["card_border"]};
        margin-bottom: 1.5rem;
    }}
    .app-title {{
        font-size: 2.4rem;
        font-weight: 700;
        color: {NORD["text"]};
        margin: 0;
        letter-spacing: -0.02em;
    }}
    .app-tagline {{
        color: {NORD["muted"]};
        font-size: 1.05rem;
        margin: 0.3rem 0 0.75rem 0;
    }}
    .live-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background-color: rgba(136, 192, 208, 0.12);
        border: 1px solid {NORD["accent_bright"]};
        color: {NORD["accent_bright"]};
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 600;
    }}
    .live-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: {NORD["accent_bright"]};
        box-shadow: 0 0 6px {NORD["accent_bright"]};
    }}

    /* Text input (search bar) */
    .stTextInput > div > div > input {{
        background-color: {NORD["card"]};
        color: {NORD["text"]};
        border: 1.5px solid {NORD["card_border"]};
        border-radius: 10px;
        padding: 0.7rem 1rem;
        font-size: 1.05rem;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: {NORD["accent_bright"]};
        box-shadow: 0 0 0 1px {NORD["accent_bright"]};
    }}
    .stTextInput > div > div > input::placeholder {{
        color: {NORD["muted"]};
    }}
    .stTextInput label {{
        color: {NORD["text_soft"]};
    }}

    /* Buttons */
    .stButton > button {{
        background-color: {NORD["accent"]};
        color: {NORD["text"]};
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        transition: background-color 0.15s ease;
    }}
    .stButton > button:hover {{
        background-color: {NORD["accent_bright"]};
        color: {NORD["bg"]};
    }}

    /* Result cards */
    .result-card {{
        background-color: {NORD["card"]};
        border: 1px solid {NORD["card_border"]};
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }}
    .result-title a {{
        color: {NORD["accent_bright"]};
        font-size: 1.15rem;
        font-weight: 600;
        text-decoration: none;
    }}
    .result-title a:hover {{
        text-decoration: underline;
    }}
    .result-snippet {{
        color: {NORD["text_soft"]};
        font-size: 0.95rem;
        line-height: 1.5;
        margin: 0.6rem 0 0.8rem 0;
    }}
    .score-badge {{
        display: inline-block;
        background-color: rgba(94, 129, 172, 0.25);
        color: {NORD["accent_bright"]};
        border: 1px solid {NORD["accent"]};
        padding: 0.15rem 0.65rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }}

    /* Stat tiles */
    .stat-box {{
        background-color: {NORD["card"]};
        border: 1px solid {NORD["card_border"]};
        border-radius: 10px;
        padding: 0.9rem 1rem;
        text-align: center;
    }}
    .stat-number {{
        font-size: 1.8rem;
        font-weight: 700;
        color: {NORD["accent_bright"]};
    }}
    .stat-label {{
        font-size: 0.8rem;
        color: {NORD["muted"]};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .section-label {{
        color: {NORD["muted"]};
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.4rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------
def fetch_search_results(query: str, limit: int = 5):
    resp = requests.get(
        f"{API_BASE}/search/",
        params={"q": query, "limit": limit},
        timeout=SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_news_count():
    resp = requests.get(f"{API_BASE}/news/", timeout=NEWS_TIMEOUT)
    resp.raise_for_status()
    return len(resp.json())


def check_health():
    resp = requests.get(f"{API_BASE}/health/", timeout=5)
    return resp.status_code == 200


# ---------------------------------------------------------------------------
# Sidebar: stats
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="section-label">Index stats</div>', unsafe_allow_html=True)
    try:
        article_count = fetch_news_count()
        st.markdown(
            f"""
            <div class="stat-box">
                <div class="stat-number">{article_count}</div>
                <div class="stat-label">Articles indexed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except requests.exceptions.RequestException:
        st.markdown(
            '<div class="stat-box"><div class="stat-label">Stats unavailable</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">About</div>', unsafe_allow_html=True)
    st.markdown(
        '<span style="color:#9EA7B8; font-size:0.9rem;">'
        "Semantic search over Hacker News articles, powered by OpenAI "
        "embeddings and pgvector similarity search.</span>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <div class="app-title">AI News Search</div>
        <div class="app-tagline">Semantic search over live-scraped AI news</div>
        <div class="live-badge"><span class="live-dot"></span> Live on Google Cloud Run</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Search bar
# ---------------------------------------------------------------------------
col1, col2 = st.columns([5, 1])
with col1:
    query = st.text_input(
        "Search",
        placeholder="Search AI news… e.g. \"AI safety\", \"microcode\"",
        label_visibility="collapsed",
    )
with col2:
    search_clicked = st.button("Search", use_container_width=True)

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if search_clicked or query:
    if not query.strip():
        st.warning("Type something to search for.")
    else:
        try:
            with st.spinner("Embedding your query and searching…"):
                results = fetch_search_results(query.strip(), limit=5)
        except requests.exceptions.Timeout:
            st.error("The search took too long to respond. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("Couldn't reach the AI News API. Please check your connection and try again.")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            st.error(f"The API returned an error (status {status}). Please try again shortly.")
        except requests.exceptions.RequestException:
            st.error("Something went wrong while searching. Please try again.")
        else:
            if not results:
                st.info("No results found. Try a different query.")
            else:
                st.markdown(
                    f'<div class="section-label">{len(results)} result'
                    f'{"s" if len(results) != 1 else ""}</div>',
                    unsafe_allow_html=True,
                )
                for r in results:
                    score_pct = max(0.0, min(1.0, r["similarity"])) * 100
                    st.markdown(
                        f"""
                        <div class="result-card">
                            <div class="result-title">
                                <a href="{r['url']}" target="_blank">{r['title']}</a>
                            </div>
                            <div class="result-snippet">{r['chunk_content'][:400].strip()}…</div>
                            <span class="score-badge">{score_pct:.1f}% match</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
