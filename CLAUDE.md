# Project

We are building an AI News API.

The application:
- collects AI news from multiple sources
- normalizes all sources into one NewsItem format
- enriches news using an LLM
- stores results in PostgreSQL
- exposes stored news through FastAPI

# Workflow

External Sources
→ Scrapers
→ Normalization
→ LLM Enrichment
→ PostgreSQL
→ FastAPI

The batch pipeline writes news to PostgreSQL.
The FastAPI service reads news from PostgreSQL.

# Technology

- Python
- Pydantic
- OpenAI API
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker
- uv
- Render

# Project Structure

ai-news-api/
│
├── app/                         # Our application code
│
│   ├── main.py                  # Start the API and listen for requests
│   ├── pipeline.py              # Run the daily news collection pipeline
│   ├── config.py                # Load API keys and app settings
│   │
│   ├── api/                     # Let other apps access our news
│   │   └── routes/
│   │       ├── news.py          # Endpoints like GET /news
│   │       └── health.py        # Check that the API is running
│   │
│   ├── scrapers/                # Collect news from external sources
│   │   ├── base.py              # Common rules for all scrapers
│   │   ├── hackernews.py        # Collect Hacker News stories (source: hackernews)
│   │   ├── rss.py               # Collect AI lab blog feeds (sources: openai_news, deepmind_blog)
│   │   └── arxiv.py             # Collect recent AI papers (source: arxiv)
│   │
│   ├── agents/                  # Use AI to understand/enrich news
│   │   └── news_agent.py        # Generate summaries and topics
│   │
│   ├── services/                # Coordinate the application's workflows
│   │   ├── ingestion.py         # Scrape, normalize and save new news
│   │   └── enrichment.py        # Enrich saved news using the LLM
│   │
│   ├── database/                # Store and retrieve news
│   │   ├── connection.py        # Connect Python to PostgreSQL
│   │   ├── models.py            # Define database tables
│   │   └── repository.py        # Read/write news in the database
│   │
│   └── schemas/                 # Define our common data format
│       └── news.py              # Define what a NewsItem looks like
│
├── tests/                       # Check that the application works
│
├── Dockerfile                   # Package our Python app for deployment
├── docker-compose.yml           # Run app + PostgreSQL locally
├── render.yaml                  # Tell Render what cloud services to create
├── .env.example                 # Show which secrets/settings are required
├── pyproject.toml               # Python dependencies and project config
└── README.md                    # Explain how to run/use the project

# Responsibilities

- main.py: FastAPI application entry point
- pipeline.py: batch ingestion/enrichment entry point
- api/: HTTP endpoints
- scrapers/: retrieve external data
- agents/: LLM logic
- services/: application workflows
- database/: database connection, models and queries
- schemas/: shared Pydantic schemas

# Principles

- Keep the project simple.
- Use one canonical NewsItem schema.
- Keep scraping, LLM, database and API logic separate.
- The API should not scrape news during a request.
- Build incrementally.

# Working rules

- Branch `portfolio-upgrade` holds the multi-source work (hackernews, openai_news,
  deepmind_blog, arxiv). Don't merge or push to main until the new version is deployed
  and the pipeline has run on the cloud database: README.md describes the new sources
  and the live demo doesn't have them yet.
- Never commit or push without being asked. Don't commit if tests fail.
- Never print, create or commit secrets or .env contents.
- Run tests with `uv run pytest`. INGEST_LIMIT is only for small local pipeline runs
  and must not affect tests.
- The local database is the Docker container `pgvector-db`. Check that DATABASE_URL
  points to localhost before any run that writes to the database.
