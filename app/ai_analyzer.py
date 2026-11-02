import logging
import re
from typing import Optional, Dict
from openai import OpenAI
from app.config import Config

logger = logging.getLogger("plex-critic.ai")

SYSTEM_INSTRUCTION = """
Você é um avaliador de filmes, séries e animes ultra objetivo e conciso.
Seu objetivo é fornecer um resumo direto para quem está decidindo o que assistir no Plex.

REGRAS:
1. Seja MUITO RESUMIDO e direto ao ponto.
2. NÃO adicione títulos como "Análise Crítica" ou o nome da obra (já aparecem na interface do Plex).
3. SEM SPOILERS e sem recomendar trailers.
4. NOTAS: Inclua na linha '⭐ Notas:' APENAS as fontes que têm nota real disponível (ex: '⭐ Notas: IMDb: 7.0/10'). Se uma fonte for N/A, N/D ou não disponível, NUNCA exiba essa fonte nem escreva N/A. Se nenhuma fonte tiver nota, OMITA completamente a linha de notas.
5. Responda ESTRITAMENTE neste formato compacto:

🎯 Recomendação: [ESCOLHA UMA: **Vale a pena** | **Depende do gosto** | **Não recomendo**] — [Explicação sincera em 1 ou 2 frases curtas].
⭐ Notas: [Apenas as fontes válidas separadas por ' | ', ou omita esta linha se nenhuma tiver nota]
👥 Recepção: [Resumo em 1 frase rápida da opinião da crítica e do público].
📖 Sinopse: [Resumo em 1 ou 2 frases sem spoilers].
"""

def clean_analysis_text(text: str) -> str:
    """
    Limpa o texto gerado removendo menções a N/A, N/D ou fontes sem nota.
    """
    cleaned_lines = []
    for line in text.strip().split("\n"):
        line_clean = line
        if "Notas:" in line_clean:
            # Remove ocorrências de 'Filmow: N/A', 'IMDb: N/A', etc.
            line_clean = re.sub(r"\|\s*(Filmow|IMDb):\s*(N/A|N/D|Não disponível|None)\b", "", line_clean, flags=re.IGNORECASE)
            line_clean = re.sub(r"(Filmow|IMDb):\s*(N/A|N/D|Não disponível|None)\b\s*\|?", "", line_clean, flags=re.IGNORECASE)
            line_clean = re.sub(r"\s*\|\s*$", "", line_clean).strip()
            line_clean = re.sub(r":\s*\|\s*", ": ", line_clean).strip()
            # Se não restou nenhuma nota após 'Notas:', omite a linha inteira
            if re.match(r"^⭐?\s*Notas:\s*$", line_clean, flags=re.IGNORECASE):
                continue
        cleaned_lines.append(line_clean)
    return "\n".join(cleaned_lines).strip()

def generate_movie_analysis(title: str, year: Optional[int], ratings: Dict[str, str], overview: Optional[str] = None, media_type: str = "Filme") -> str:
    """
    Gera a análise resumida de filme, série ou anime usando a API OpenAI / Groq.
    """
    if not Config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não configurada no arquivo .env.")

    # Filtra apenas notas que realmente existem
    valid_ratings = []
    imdb = ratings.get('imdb', '').strip()
    if imdb and imdb.upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
        valid_ratings.append(f"IMDb: {imdb}")

    filmow = ratings.get('filmow', '').strip()
    if filmow and filmow.upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
        valid_ratings.append(f"Filmow: {filmow}")

    ratings_info = " | ".join(valid_ratings) if valid_ratings else "Nenhuma nota prévia disponível (omita a linha de notas)"

    prompt = f"""
Avalie:
- Título: {title} ({year or 'N/A'})
- Tipo: {media_type}
- Notas válidas disponíveis: {ratings_info}
- Contexto original: {overview or 'Não informado'}
"""

    client = OpenAI(
        base_url=Config.OPENAI_API_BASE,
        api_key=Config.OPENAI_API_KEY
    )

    models_to_try = [Config.OPENAI_MODEL]
    if "groq.com" in Config.OPENAI_API_BASE:
        for m in ["openai/gpt-oss-120b", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]:
            if m not in models_to_try:
                models_to_try.append(m)

    last_err = None
    for candidate_model in models_to_try:
        try:
            response = client.chat.completions.create(
                model=candidate_model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            if response and response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if content:
                    if candidate_model != Config.OPENAI_MODEL:
                        Config.OPENAI_MODEL = candidate_model
                    return clean_analysis_text(content)
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "404" in err_str or "does not exist" in err_str:
                continue
            raise e

    raise RuntimeError(f"Erro na API OpenAI: {last_err}")
