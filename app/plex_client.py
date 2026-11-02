import logging
import re
import time
from typing import List, Optional, Dict, Any
from plexapi.server import PlexServer
from app.config import Config
from app.db import is_movie_analyzed, save_analysis
from app.scraper import collect_movie_ratings
from app.ai_analyzer import generate_movie_analysis

logger = logging.getLogger("plex-critic.plex")

MARKERS = ["💡 [ANÁLISE CRÍTICA]", "🎯 Veredito:", "🎯 Recomendação:"]
ERROR_MARKER = "Não foi possível sintetizar a opinião com a IA no momento"

class PlexManager:
    def __init__(self):
        self.server: Optional[PlexServer] = None
        self._connect()

    def _connect(self):
        if not Config.PLEX_TOKEN or not Config.PLEX_URL:
            logger.warning("PLEX_URL ou PLEX_TOKEN não foram configurados.")
            return

        try:
            self.server = PlexServer(Config.PLEX_URL, Config.PLEX_TOKEN)
            logger.info(f"Conectado ao Plex com sucesso: {self.server.friendlyName} (v{self.server.version})")
        except Exception as e:
            logger.error(f"Falha ao conectar ao servidor Plex ({Config.PLEX_URL}): {e}")
            self.server = None

    def get_libraries(self):
        if not self.server:
            self._connect()
        if not self.server:
            return []

        libs = []
        for section in self.server.library.sections():
            if section.type in ("movie", "show") and (not Config.PLEX_LIBRARY_NAMES or section.title in Config.PLEX_LIBRARY_NAMES):
                libs.append(section)
        return libs

    def extract_imdb_id(self, item) -> Optional[str]:
        """
        Extrai o id do IMDb a partir dos GUIDs do item no Plex.
        """
        try:
            if hasattr(item, "guids"):
                for guid in item.guids:
                    match = re.search(r"imdb://(tt\d+)", guid.id)
                    if match:
                        return match.group(1)
        except Exception:
            pass
        return None

    @staticmethod
    def strip_existing_analysis(summary: str) -> str:
        """
        Remove qualquer bloco de análise anterior do resumo para preservar a sinopse original limpa.
        """
        if not summary:
            return ""

        for marker in MARKERS:
            if marker in summary:
                if summary.startswith(marker):
                    sep = "\n\n---\n"
                    if sep in summary:
                        return summary.split(sep, 1)[1].strip()
                    return ""
                bottom_sep = f"\n\n---\n{marker}"
                if bottom_sep in summary:
                    return summary.split(bottom_sep, 1)[0].strip()

        return summary.strip()

    def calculate_numeric_rating(self, ratings: Dict[str, str], verdict: str) -> Optional[float]:
        """
        Calcula nota numérica de 0 a 10 para aplicar no campo de estrelas do Plex.
        """
        try:
            imdb_str = ratings.get("imdb", "")
            match = re.search(r"(\d+(\.\d+)?)", imdb_str)
            if match:
                score = float(match.group(1))
                if score <= 10.0:
                    return round(score, 1)

            filmow_str = ratings.get("filmow", "")
            match_filmow = re.search(r"(\d+(\.\d+)?)", filmow_str)
            if match_filmow:
                # Converte escala 0 a 5 do Filmow para 0 a 10 do Plex
                score = float(match_filmow.group(1)) * 2.0
                return round(min(score, 10.0), 1)
        except Exception:
            pass

        if verdict == "Vale a pena":
            return 8.5
        elif verdict == "Depende do gosto":
            return 6.5
        elif verdict == "Não recomendo":
            return 4.0
        return None

    def update_item_in_plex(self, item, analysis_text: str, force: bool = False):
        """
        Anexa a análise resumida no resumo do filme dentro do Plex sem títulos redundantes.
        """
        if not Config.UPDATE_PLEX_SUMMARY:
            return

        try:
            current_summary = item.summary or ""
            has_old_error = ERROR_MARKER in current_summary
            already_has_analysis = any(m in current_summary for m in MARKERS)

            if already_has_analysis and not force and not has_old_error:
                logger.info(f"O resumo de '{item.title}' já contém análise. Pulando edição.")
                return

            clean_summary = self.strip_existing_analysis(current_summary)
            content = analysis_text.strip()

            if Config.SUMMARY_POSITION == "bottom":
                new_summary = f"{clean_summary}\n\n---\n{content}" if clean_summary else content
            else:
                new_summary = f"{content}\n\n---\n{clean_summary}" if clean_summary else content

            item.editSummary(new_summary)
            logger.info(f"Resumo atualizado no Plex para '{item.title}'.")
        except Exception as e:
            logger.error(f"Erro ao atualizar resumo de '{item.title}' no Plex: {e}")

    def apply_plex_evaluations(self, item, verdict: str, ratings: Dict[str, str], analysis_text: str):
        """
        Aplica a avaliação completa no Plex: Resumo, Estrelas e Frase de Efeito (Tagline).
        """
        # 1. Atualiza Sinopse (Summary)
        self.update_item_in_plex(item, analysis_text, force=True)

        # 2. Posta nota em estrelas no campo 'Sua Avaliação' (User Rating de 0 a 10)
        if Config.AUTO_RATE_PLEX:
            score = self.calculate_numeric_rating(ratings, verdict)
            if score is not None:
                try:
                    item.rate(score)
                    logger.info(f"⭐ Avaliação de {score}/10 estrelas postada no Plex para '{item.title}'.")
                except Exception as e:
                    logger.warning(f"Não foi possível aplicar estrelas para '{item.title}': {e}")

        # 3. Atualiza Frase de Efeito (Tagline) com a recomendação e apenas notas válidas
        if Config.UPDATE_PLEX_TAGLINE and hasattr(item, "editTagline"):
            try:
                tagline_parts = [f"🎯 {verdict}"]
                imdb_n = ratings.get('imdb', '').strip()
                if imdb_n and imdb_n.upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
                    tagline_parts.append(f"IMDb {imdb_n}")
                filmow_n = ratings.get('filmow', '').strip()
                if filmow_n and filmow_n.upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
                    tagline_parts.append(f"Filmow {filmow_n}")
                tagline = " • ".join(tagline_parts)
                item.editTagline(tagline, locked=True)
                logger.info(f"Tagline atualizada no Plex para '{item.title}': {tagline}")
            except Exception as e:
                pass

    def process_movie(self, movie, force: bool = False) -> Dict[str, Any]:
        """
        Processa um único item: coleta notas, gera análise e posta no Plex.
        """
        key = str(movie.ratingKey)
        title = movie.title
        year = getattr(movie, "year", None)

        if not force and is_movie_analyzed(key):
            logger.info(f"Item '{title}' ({year}) já foi analisado anteriormente. Pulando.")
            return {"status": "already_analyzed", "title": title, "year": year}

        logger.info(f"Iniciando análise para '{title}' ({year})...")
        imdb_id = self.extract_imdb_id(movie)
        audience_rating = getattr(movie, "audienceRating", None) or getattr(movie, "rating", None)
        clean_overview = self.strip_existing_analysis(movie.summary or "")

        # Identifica se é Filme, Série ou Anime
        media_type = "Filme"
        try:
            sec_title = movie.section().title.lower() if hasattr(movie, "section") and callable(movie.section) else ""
            genres = [g.tag.lower() for g in getattr(movie, "genres", []) if hasattr(g, "tag")]
            if "anime" in sec_title or "anime" in genres or "animation" in genres and "japan" in [c.tag.lower() for c in getattr(movie, "countries", []) if hasattr(c, "tag")]:
                media_type = "Anime"
            elif getattr(movie, "type", "") == "show" or "série" in sec_title or "series" in sec_title:
                media_type = "Série"
        except Exception:
            pass

        # 1. Coleta notas
        ratings = collect_movie_ratings(
            title=title,
            year=year,
            plex_audience_rating=audience_rating,
            imdb_id=imdb_id
        )

        # 2. Gera análise resumida com OpenAI
        analysis_text = generate_movie_analysis(
            title=title,
            year=year,
            ratings=ratings,
            overview=clean_overview,
            media_type=media_type
        )

        # Extrai veredito simples para registro no banco
        verdict = "Indefinido"
        if "Vale a pena" in analysis_text:
            verdict = "Vale a pena"
        elif "Não recomendo" in analysis_text:
            verdict = "Não recomendo"
        elif "Depende do gosto" in analysis_text:
            verdict = "Depende do gosto"

        # 3. Posta as avaliações no Plex (estrelas, tagline e resumo)
        self.apply_plex_evaluations(movie, verdict, ratings, analysis_text)

        # 4. Salva no banco de dados local
        save_analysis(
            rating_key=key,
            title=title,
            year=year,
            imdb_rating=ratings["imdb"],
            filmow_rating=ratings["filmow"],
            verdict=verdict,
            analysis_text=analysis_text
        )

        logger.info(f"Análise concluída com sucesso para '{title}': Recomendação: {verdict}")

        return {
            "status": "success",
            "rating_key": key,
            "title": title,
            "year": year,
            "verdict": verdict,
            "ratings": ratings,
            "analysis": analysis_text
        }

    def scan_and_analyze_library(self) -> List[Dict[str, Any]]:
        """
        Varre as bibliotecas configuradas e processa os itens pendentes.
        """
        libs = self.get_libraries()
        results = []

        if not libs:
            logger.warning("Nenhuma biblioteca correspondente encontrada no Plex.")
            return results

        for lib in libs:
            logger.info(f"Varrendo biblioteca '{lib.title}'...")
            try:
                items = lib.search(sort="addedAt:desc")
                for item in items:
                    key = str(item.ratingKey)
                    if not is_movie_analyzed(key):
                        try:
                            res = self.process_movie(item)
                            results.append(res)
                            time.sleep(Config.DELAY_BETWEEN_ITEMS)  # Pausa segura de 5s entre itens
                        except Exception as item_err:
                            logger.error(f"Pulando '{item.title}' devido a erro na análise: {item_err}")
            except Exception as e:
                logger.error(f"Erro ao varrer biblioteca '{lib.title}': {e}")

        return results

    def find_and_analyze_by_name(self, title_query: str) -> Optional[Dict[str, Any]]:
        """
        Pesquisa um filme, série ou anime pelo nome na biblioteca do Plex e executa a análise.
        """
        if not self.server:
            self._connect()
        if not self.server:
            raise Exception("Não conectado ao servidor Plex.")

        for lib in self.get_libraries():
            results = lib.search(title=title_query)
            if results:
                movie = results[0]
                return self.process_movie(movie, force=True)

        return None
