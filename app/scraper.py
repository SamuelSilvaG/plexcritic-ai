import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

def get_filmow_rating(title: str, year: Optional[int] = None) -> Optional[str]:
    """
    Busca o filme no Filmow e extrai a média de notas dos usuários (0 a 5).
    """
    try:
        query = f"{title} {year}" if year else title
        search_url = f"https://filmow.com/buscar/?q={urllib.parse.quote_plus(query)}"
        
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Procura o primeiro item da lista de resultados de busca
        movie_items = soup.select("#movies-list li, .movie-item, li[data-movie-pk]")
        target_link = None
        
        if movie_items:
            for item in movie_items:
                link_el = item.select_one("a.cover, a.title, a")
                if link_el and link_el.get("href"):
                    target_link = link_el["href"]
                    break
        else:
            # Tenta encontrar qualquer link de filme no html
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.match(r"^/[a-zA-Z0-9\-]+-t\d+/?$", href):
                    target_link = href
                    break

        if not target_link:
            return None

        if not target_link.startswith("http"):
            target_link = f"https://filmow.com{target_link}"

        # Acessa a página do filme no Filmow
        movie_resp = requests.get(target_link, headers=HEADERS, timeout=8)
        if movie_resp.status_code != 200:
            return None

        movie_soup = BeautifulSoup(movie_resp.text, "html.parser")
        
        # Busca a nota média (ex: 3.8 / 5)
        # No Filmow, normalmente está em classe 'average' ou itemprop 'ratingValue'
        avg_el = movie_soup.select_one(".average, [itemprop='ratingValue'], .movie-rating-average")
        if avg_el:
            score = avg_el.get_text(strip=True)
            if score:
                return f"{score}/5"
                
    except Exception as e:
        # Falha silenciosa no scraping para não travar o fluxo
        pass

    return None

def get_imdb_rating_from_web(title: str, year: Optional[int] = None, imdb_id: Optional[str] = None) -> Optional[str]:
    """
    Obtém a nota do IMDb diretamente via página ou busca.
    """
    try:
        if imdb_id:
            url = f"https://www.imdb.com/title/{imdb_id}/"
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                rating_el = soup.select_one('[data-testid="hero-rating-bar__aggregate-rating__score"] span')
                if rating_el:
                    return f"{rating_el.get_text(strip=True)}/10"

        # Fallback de busca no IMDb
        query = f"{title} {year}" if year else title
        search_url = f"https://www.imdb.com/find/?q={urllib.parse.quote_plus(query)}&s=tt&ttype=ft"
        resp = requests.get(search_url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            item = soup.select_one(".ipc-metadata-list-summary-item a")
            if item and item.get("href"):
                match = re.search(r"/(tt\d+)/", item["href"])
                if match:
                    return get_imdb_rating_from_web(title, year, imdb_id=match.group(1))
    except Exception:
        pass

    return None

def collect_movie_ratings(title: str, year: Optional[int] = None, plex_audience_rating: Optional[float] = None, imdb_id: Optional[str] = None) -> Dict[str, str]:
    """
    Consolida as notas do IMDb e Filmow.
    """
    # 1. IMDb
    imdb_score = None
    if imdb_id:
        imdb_score = get_imdb_rating_from_web(title, year, imdb_id)
        
    if not imdb_score and plex_audience_rating:
        imdb_score = f"{plex_audience_rating:.1f}/10 (Plex)"
        
    if not imdb_score:
        imdb_score = get_imdb_rating_from_web(title, year)

    # 2. Filmow
    filmow_score = get_filmow_rating(title, year)

    return {
        "imdb": imdb_score or "Não disponível",
        "filmow": filmow_score or "Não disponível"
    }

