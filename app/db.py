import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any
from app.config import Config

def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(Config.DATABASE_PATH)), exist_ok=True)
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyzed_movies (
                rating_key TEXT PRIMARY KEY,
                title TEXT,
                year INTEGER,
                imdb_rating TEXT,
                filmow_rating TEXT,
                verdict TEXT,
                analysis_text TEXT,
                analyzed_at TIMESTAMP
            )
        """)
        # Limpa registros anteriores que falharam com erro de API para que sejam reanalisados
        conn.execute("""
            DELETE FROM analyzed_movies
            WHERE analysis_text LIKE '%Não foi possível sintetizar a opinião com a IA no momento%'
        """)
        conn.commit()

def is_movie_analyzed(rating_key: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM analyzed_movies WHERE rating_key = ?", (str(rating_key),)).fetchone()
        return row is not None

def save_analysis(rating_key: str, title: str, year: Optional[int], imdb_rating: str, filmow_rating: str, verdict: str, analysis_text: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO analyzed_movies 
            (rating_key, title, year, imdb_rating, filmow_rating, verdict, analysis_text, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(rating_key), title, year, imdb_rating, filmow_rating, verdict, analysis_text, datetime.utcnow()))
        conn.commit()

def get_analysis_by_key(rating_key: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM analyzed_movies WHERE rating_key = ?", (str(rating_key),)).fetchone()
        if row:
            return dict(row)
    return None

