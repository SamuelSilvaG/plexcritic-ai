import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Servidor Plex
    PLEX_URL = os.getenv("PLEX_URL", "http://localhost:32400").rstrip("/")
    PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
    # Se vazio, analisa todas as bibliotecas de filmes, séries e animes automaticamente
    PLEX_LIBRARY_NAMES = [name.strip() for name in os.getenv("PLEX_LIBRARY_NAMES", "Filmes,Movies,Séries,Series,Animes,Anime").split(",") if name.strip()]
    
    # Modelo OpenAI (OpenAI, Groq, OpenRouter, etc.)
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.groq.com/openai/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    
    # Comportamento de Avaliação no Plex
    # 1. Dá nota em estrelas de 0 a 10 no campo "Sua Avaliação" (User Rating) do Plex
    AUTO_RATE_PLEX = os.getenv("AUTO_RATE_PLEX", "true").lower() in ("true", "1", "yes")
    
    # 2. Atualiza a Frase de Efeito (Tagline) com o veredito curto (ex: 🎯 Vale a pena • IMDb: 8.2)
    UPDATE_PLEX_TAGLINE = os.getenv("UPDATE_PLEX_TAGLINE", "true").lower() in ("true", "1", "yes")

    # 3. Adiciona a análise no campo Sinopse (Summary)
    UPDATE_PLEX_SUMMARY = os.getenv("UPDATE_PLEX_SUMMARY", "true").lower() in ("true", "1", "yes")
    SUMMARY_POSITION = os.getenv("SUMMARY_POSITION", "top").lower()

    # Outras configurações
    CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))
    DELAY_BETWEEN_ITEMS = float(os.getenv("DELAY_BETWEEN_ITEMS", "5.0"))
    PORT = int(os.getenv("PORT", "8080"))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/plex_critic.db" if os.path.exists("/data") else "plex_critic.db")
