import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.database.models import Base, NewsChunkModel, NewsItemModel  # noqa: F401

load_dotenv()

url = os.getenv("SUPABASE_DATABASE_URL")
engine = create_engine(url)

with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

print("Tables to be created:")
for table in Base.metadata.tables:
    print(f"- {table}")

Base.metadata.create_all(bind=engine)
print("Tables created successfully on Supabase.")