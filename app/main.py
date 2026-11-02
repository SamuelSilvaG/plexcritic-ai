import logging
import json
import html
import socket
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import Config
from app.db import init_db, get_connection
from app.plex_client import PlexManager

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("plex-critic.server")

plex_manager = PlexManager()
scheduler = BackgroundScheduler()

def scheduled_job():
    logger.info("Iniciando verificação periódica de novos filmes no Plex...")
    try:
        results = plex_manager.scan_and_analyze_library()
        logger.info(f"Verificação concluída. {len(results)} novos títulos analisados.")
    except Exception as e:
        logger.error(f"Erro durante a verificação automática: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização
    init_db()
    if Config.CHECK_INTERVAL_MINUTES > 0:
        scheduler.add_job(scheduled_job, "interval", minutes=Config.CHECK_INTERVAL_MINUTES, id="plex_library_scan")
        scheduler.start()
        logger.info(f"Agendador iniciado: varreduras a cada {Config.CHECK_INTERVAL_MINUTES} minutos.")
    yield
    # Finalização
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Agendador encerrado.")

app = FastAPI(title="PlexCritic AI", lifespan=lifespan)

_dns_cache = {}

def get_allowed_ips():
    now = time.time()
    allowed_ips = set()
    for host in Config.ALLOWED_HOSTS_OR_IPS:
        clean_host = host.split("/")[0].strip()
        if not clean_host:
            continue
        if clean_host.replace(".", "").isdigit():
            allowed_ips.add(clean_host)
            continue
        cached = _dns_cache.get(clean_host)
        if cached and (now - cached["time"] < 60):
            allowed_ips.add(cached["ip"])
        else:
            try:
                ip = socket.gethostbyname(clean_host)
                _dns_cache[clean_host] = {"ip": ip, "time": now}
                allowed_ips.add(ip)
            except Exception as e:
                logger.warning(f"Erro ao resolver DNS de {clean_host}: {e}")
                if cached:
                    allowed_ips.add(cached["ip"])
    return allowed_ips

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""

@app.middleware("http")
async def ip_whitelist_middleware(request: Request, call_next):
    if not Config.ALLOWED_HOSTS_OR_IPS:
        return await call_next(request)
    
    path = request.url.path
    if path in ("/", "/analyze-ui", "/scan"):
        client_ip = get_client_ip(request)
        if client_ip not in ("127.0.0.1", "::1"):
            allowed_ips = get_allowed_ips()
            if client_ip not in allowed_ips:
                logger.warning(f"Acesso bloqueado ao dashboard vindo do IP: {client_ip}. Permitidos: {allowed_ips}")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html lang="pt-BR">
                <head>
                    <meta charset="UTF-8">
                    <title>Acesso Restrito</title>
                    <script src="https://cdn.tailwindcss.com"></script>
                </head>
                <body class="bg-gray-950 text-gray-100 flex items-center justify-center min-h-screen p-4 font-sans">
                    <div class="max-w-md w-full bg-gray-900 border border-red-800 rounded-2xl p-8 shadow-2xl text-center">
                        <div class="text-5xl mb-4">⛔</div>
                        <h1 class="text-2xl font-bold text-red-500 mb-2">Acesso Restrito</h1>
                        <p class="text-gray-400 text-sm mb-4">Este dashboard está configurado para aceitar apenas requisições do IP autorizado.</p>
                        <div class="bg-gray-800 p-3 rounded-lg text-xs font-mono text-gray-300 border border-gray-700">
                            Seu IP detectado: <span class="text-amber-400 font-bold">{html.escape(client_ip)}</span>
                        </div>
                    </div>
                </body>
                </html>
                """, status_code=403)
                
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
def index(scanning: int = 0):
    """
    Página web com status, busca rápida de filme/série e lista dos últimos analisados.
    """
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM analyzed_movies").fetchone()[0]
        recent = conn.execute("SELECT * FROM analyzed_movies ORDER BY analyzed_at DESC LIMIT 20").fetchall()

    plex_status = "🟢 Conectado" if plex_manager.server else "🔴 Desconectado (Verifique PLEX_URL e PLEX_TOKEN)"
    scan_banner = (
        '<div class="bg-amber-500/15 border border-amber-500/40 text-amber-300 px-4 py-3 rounded-xl text-sm">'
        '🔄 Varredura iniciada em segundo plano! Acompanhe pelos logs ou atualize esta página em instantes.'
        '</div>'
        if scanning else ""
    )

    recent_rows = ""
    for r in recent:
        badge_color = "#10b981" if "Vale a pena" in r["verdict"] else ("#f59e0b" if "gosto" in r["verdict"] else "#ef4444")
        
        # Oculta fontes sem notas e protege contra XSS
        safe_title = html.escape(f"{r['title']} ({r['year'] or 'N/A'})")
        safe_verdict = html.escape(str(r["verdict"]))
        safe_date = html.escape(str(r["analyzed_at"])[:19])

        notas_list = []
        if r['imdb_rating'] and r['imdb_rating'].strip().upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
            notas_list.append(f"IMDb: {html.escape(r['imdb_rating'])}")
        if r['filmow_rating'] and r['filmow_rating'].strip().upper() not in ('N/A', 'N/D', 'NÃO DISPONÍVEL', 'NONE'):
            notas_list.append(f"Filmow: {html.escape(r['filmow_rating'])}")
        notas_html = "<br>".join(notas_list) if notas_list else '<span class="text-gray-500 text-xs">Sem notas</span>'

        recent_rows += f"""
        <tr class="border-b border-gray-800 hover:bg-gray-800/50 transition">
            <td class="py-3 px-4 font-medium">{safe_title}</td>
            <td class="py-3 px-4 text-sm text-yellow-400">{notas_html}</td>
            <td class="py-3 px-4">
                <span style="background-color: {badge_color};" class="text-xs px-2.5 py-1 rounded-full font-bold text-black">{safe_verdict}</span>
            </td>
            <td class="py-3 px-4 text-xs text-gray-400">{safe_date}</td>
        </tr>
        """

    if not recent_rows:
        recent_rows = '<tr><td colspan="4" class="text-center py-6 text-gray-500">Nenhum título analisado ainda.</td></tr>'

    output_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PlexCritic AI</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-950 text-gray-100 min-h-screen p-6 font-sans">
        <div class="max-w-4xl mx-auto space-y-6">
            <header class="flex justify-between items-center border-b border-gray-800 pb-4">
                <div>
                    <h1 class="text-3xl font-extrabold text-amber-500 flex items-center gap-2">🎬 PlexCritic AI</h1>
                    <p class="text-sm text-gray-400">Análise automática, notas e recomendações sem spoilers para o seu Plex</p>
                </div>
                <div class="text-right text-xs">
                    <span class="font-semibold block">{plex_status}</span>
                    <span class="text-gray-500">Total analisados: {count}</span>
                </div>
            </header>

            {scan_banner}

            <!-- Card de Busca Manual -->
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-lg font-semibold text-gray-200 mb-2">🔍 Analisar Filme, Série ou Anime</h2>
                <form action="/analyze-ui" method="post" class="flex gap-3">
                    <input type="text" name="title" required maxlength="200" placeholder="Digite o nome do filme, série ou anime na biblioteca..." 
                           class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-500">
                    <button type="submit" class="bg-amber-500 hover:bg-amber-600 font-bold text-gray-950 px-5 py-2.5 rounded-lg text-sm transition">
                        Pesquisar & Analisar
                    </button>
                </form>
            </div>

            <!-- Tabela de Últimos Analisados -->
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-lg">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-semibold text-gray-200">📋 Últimos Títulos Analisados</h2>
                    <form action="/scan" method="post">
                        <button type="submit" class="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 px-3 py-1.5 rounded-lg text-gray-300">
                            🔄 Forçar Varredura Agora
                        </button>
                    </form>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="text-xs text-gray-400 uppercase border-b border-gray-800">
                                <th class="py-3 px-4">Título</th>
                                <th class="py-3 px-4">Notas</th>
                                <th class="py-3 px-4">Recomendação</th>
                                <th class="py-3 px-4">Data</th>
                            </tr>
                        </thead>
                        <tbody>
                            {recent_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return output_html

@app.post("/analyze-ui", response_class=HTMLResponse)
def analyze_ui(title: str = Form(...)):
    """
    Pesquisa e analisa um título via interface web com proteção XSS completa.
    """
    clean_title = title.strip()[:200]
    safe_title = html.escape(clean_title)
    try:
        result = plex_manager.find_and_analyze_by_name(clean_title)
        if not result:
            return HTMLResponse(f"""
                <body class="bg-gray-950 text-gray-100 p-8 font-sans">
                    <div class="max-w-xl mx-auto bg-gray-900 border border-red-800 rounded-xl p-6">
                        <h2 class="text-red-400 font-bold text-xl mb-2">Título não encontrado</h2>
                        <p class="text-gray-300 mb-4">Nenhum título correspondente a "{safe_title}" foi localizado nas bibliotecas configuradas do seu Plex.</p>
                        <a href="/" class="text-amber-400 underline">&larr; Voltar</a>
                    </div>
                </body>
            """, status_code=404)

        # Sanitiza a saída da IA antes de converter quebras de linha
        analysis_safe = html.escape(result["analysis"]).replace("\n", "<br>")
        return HTMLResponse(f"""
            <body class="bg-gray-950 text-gray-100 p-8 font-sans">
                <div class="max-w-2xl mx-auto bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-xl space-y-4">
                    <h2 class="text-2xl font-bold text-amber-500">Resultado da Análise</h2>
                    <div class="bg-gray-800 p-4 rounded-lg font-mono text-sm leading-relaxed border border-gray-700 text-gray-200">
                        {analysis_safe}
                    </div>
                    <p class="text-xs text-green-400">✓ Resumo, estrelas e comentários sincronizados com o Plex!</p>
                    <a href="/" class="inline-block mt-4 text-amber-400 underline">&larr; Voltar ao Início</a>
                </div>
            </body>
        """)
    except Exception as e:
        safe_err = html.escape(str(e))
        return HTMLResponse(f"""
            <body class="bg-gray-950 text-gray-100 p-8 font-sans">
                <div class="max-w-xl mx-auto bg-gray-900 border border-red-800 rounded-xl p-6">
                    <h2 class="text-red-400 font-bold text-xl mb-2">Erro</h2>
                    <p class="text-gray-300 mb-4">{safe_err}</p>
                    <a href="/" class="text-amber-400 underline">&larr; Voltar</a>
                </div>
            </body>
        """, status_code=500)

@app.post("/analyze")
def analyze_movie_api(payload: dict):
    """
    API JSON para solicitar análise de um título por nome.
    Exemplo: {"title": "O Poderoso Chefão"}
    """
    title = payload.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=400, detail="Campo 'title' é obrigatório e deve ser um texto válido.")

    clean_title = title.strip()[:200]
    result = plex_manager.find_and_analyze_by_name(clean_title)
    if not result:
        raise HTTPException(status_code=404, detail=f"Título '{clean_title}' não encontrado na biblioteca do Plex.")

    return result

@app.post("/scan")
def trigger_scan(request: Request, background_tasks: BackgroundTasks):
    """
    Dispara varredura imediata de novos títulos em segundo plano.
    """
    background_tasks.add_task(scheduled_job)
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/?scanning=1", status_code=303)
    return {"message": "Varredura iniciada em segundo plano."}

@app.get("/webhook")
def plex_webhook_info():
    """
    Confirmação amigável ao abrir a URL do webhook pelo navegador (GET).
    """
    return {
        "status": "ready",
        "message": "Webhook ativo! Cadastre esta URL no Plex (que enviará requisições POST automaticamente)."
    }

@app.post("/webhook")
async def plex_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para Webhooks nativos do Plex Media Server.
    Dispara análise imediata quando um novo filme, série ou episódio é adicionado à biblioteca.
    """
    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str or not isinstance(payload_str, str):
        return {"status": "ignored", "reason": "Sem payload"}

    try:
        data = json.loads(payload_str)
        event = data.get("event")
        metadata = data.get("Metadata", {})

        # Evento quando um novo item é adicionado à biblioteca (Filme, Série ou Episódio de Anime/Série)
        if event == "library.new":
            item_type = metadata.get("type")
            target_key = None
            if item_type in ("movie", "show"):
                target_key = metadata.get("ratingKey")
            elif item_type == "episode":
                target_key = metadata.get("grandparentRatingKey") or metadata.get("ratingKey")
            elif item_type == "season":
                target_key = metadata.get("parentRatingKey") or metadata.get("ratingKey")

            if target_key:
                logger.info(f"Recebido webhook de novo item no Plex: {metadata.get('title')} ({item_type}, target_key: {target_key})")
                
                def process_webhook_item():
                    if plex_manager.server and target_key:
                        try:
                            item = plex_manager.server.fetchItem(int(target_key))
                            plex_manager.process_movie(item)
                        except Exception as err:
                            logger.error(f"Erro ao processar item do webhook: {err}")

                background_tasks.add_task(process_webhook_item)
                return {"status": "processing", "title": metadata.get("title")}

    except Exception as e:
        logger.error(f"Erro ao processar webhook do Plex: {e}")

    return {"status": "ignored"}
