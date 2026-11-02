<div align="center">

# 🎬 PlexCritic AI

**Análises inteligentes, notas consolidadas e recomendações sinceras sem spoilers diretamente no seu Plex Media Server.**

[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Groq / OpenAI](https://img.shields.io/badge/Groq%20%2F%20OpenAI-FF6F00?style=for-the-badge&logo=openai&logoColor=white)](https://console.groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

<p align="center">
  <a href="#-principais-recursos">Recursos</a> •
  <a href="#-como-fica-no-seu-plex">Como Fica no Plex</a> •
  <a href="#-instalação-rápida">Instalação</a> •
  <a href="#-configurações-env">Variáveis de Ambiente</a> •
  <a href="#-webhook-em-tempo-real">Webhook</a> •
  <a href="#-licença">Licença</a>
</p>

</div>

---

## 🌟 Visão Geral

O **PlexCritic AI** é uma aplicação em container Docker que monitora automaticamente suas bibliotecas de **Filmes, Séries e Animes** no **Plex Media Server**.

Quando um título novo é detectado (ou pesquisado sob demanda), ele:
1. Consulta as notas do **IMDb** e **Filmow** (ocultando qualquer fonte sem avaliação).
2. Gera uma **recomendação direta, sincera e sem spoilers** via IA (**Groq**, **OpenAI**, ou qualquer endpoint compatível).
3. **Avalia automaticamente no Plex**:
   - ⭐ Preenche as estrelas amarelas no campo oficial **"Sua Avaliação"** (`User Rating`).
   - 🏷️ Insere o veredito na **Frase de Efeito** (`Tagline`).
   - 📖 Anexa a resenha no início da **Sinopse** (`Summary`).

---

## 📺 Como Fica no seu Plex

Ao abrir o filme ou série na sua TV, celular ou computador:

```text
🎯 Recomendação: Vale a pena — Uma trama eletrizante com ritmo ágil e reviravoltas bem amarradas.
⭐ Notas: IMDb: 8.2/10 | Filmow: 4.1/5
👥 Recepção: Aclamado pela crítica por sua direção impecável e fotografia marcante.
📖 Sinopse: Acompanha a jornada de sobrevivência de uma tripulação isolada após uma falha crítica.

---
[Sinopse original cadastrada no seu servidor Plex]
```

> 💡 **Nota:** Se o Filmow ou IMDb não tiverem nota registrada para a obra, a fonte é **automaticamente ocultada** para manter o layout limpo.

---

## ✨ Principais Recursos

- ⚡ **Detecção Automática em Tempo Real**: Suporte nativo a Webhooks do Plex (`library.new`) e varredura periódica em segundo plano.
- 🍿 **Filmes, Séries & Animes**: Detecta novos episódios e vincula a recomendação diretamente na página principal da série/anime.
- 🔒 **Sem Spoilers**: Prompts calibrados estritamente para manter surpresas intactas e nunca recomendar trailers.
- 🛡️ **Segurança Blindada**: Proteção nativa contra injeções de script (XSS) e higienização rigorosa de entradas de formulário.
- 🚀 **100% Gratuito com Groq (itsfree.ai)**: Respostas em menos de 1 segundo utilizando modelos de ponta sem custos de API.
- 🌐 **Dashboard Web Embutido**: Painel moderno em Tailwind CSS na porta `8080` com busca manual e histórico das últimas avaliações.

---

## 🚀 Instalação Rápida

### Pré-requisitos
- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/) instalados.
- Um servidor **Plex Media Server** em execução na sua rede local.
- Uma chave de API gratuita da **Groq** ([console.groq.com](https://console.groq.com/keys)) ou OpenAI.

---

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU_USUARIO/plexcritic-ai.git
cd plexcritic-ai
```

### 2. Configurar o `.env`
Copie o modelo de ambiente:
```bash
cp .env.example .env
```

Edite o arquivo `.env`:
```env
# Endereço do seu Plex e Token de Acesso
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=seu_token_aqui

# Bibliotecas a monitorar (deixe em branco para analisar todas)
PLEX_LIBRARY_NAMES=Filmes,Series,Animes

# Provedor de IA (Recomendado: Groq - Ultra rápido e gratuito)
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_sua_chave_groq_aqui
OPENAI_MODEL=openai/gpt-oss-120b
```

> ❓ **Como pegar o Plex Token?**  
> No Plex Web, clique nos três pontinhos `...` de qualquer filme > **Obter Informações** > **Ver XML**. O token estará no final da barra de endereço: `X-Plex-Token=SEU_TOKEN`.

---

### 3. Iniciar o Container
```bash
docker compose up -d --build
```

Acompanhe os logs em tempo real:
```bash
docker compose logs -f
```

Acesse o painel web em seu navegador:  
👉 **`http://localhost:8080`** (ou `http://IP_DO_SERVIDOR:8080`)

---

## ⚙️ Variáveis de Ambiente (`.env`)

| Variável | Padrão | Descrição |
| :--- | :---: | :--- |
| `PLEX_URL` | `http://localhost:32400` | URL do seu servidor Plex. |
| `PLEX_TOKEN` | - | Seu `X-Plex-Token` para autenticação. |
| `PLEX_LIBRARY_NAMES` | `Filmes,Series,Animes` | Bibliotecas monitoradas (vazio = todas). |
| `OPENAI_API_BASE` | `https://api.groq.com/openai/v1` | Endpoint da API OpenAI ou compatível. |
| `OPENAI_API_KEY` | - | Chave de API da Groq/OpenAI. |
| `OPENAI_MODEL` | `openai/gpt-oss-120b` | Modelo LLM utilizado para as resenhas. |
| `AUTO_RATE_PLEX` | `true` | Posta nota numérica nas estrelas do Plex (0 a 10). |
| `UPDATE_PLEX_TAGLINE` | `true` | Escreve o veredito na Frase de Efeito (`Tagline`). |
| `UPDATE_PLEX_SUMMARY` | `true` | Anexa a análise resumida no texto da sinopse. |
| `CHECK_INTERVAL_MINUTES`| `10` | Intervalo da varredura periódica (em minutos). |
| `DELAY_BETWEEN_ITEMS` | `5` | Pausa de segurança entre requisições (em segundos). |
| `PORT` | `8080` | Porta onde a aplicação responderá. |

---

## ⚡ Webhook em Tempo Real (Opcional - Plex Pass)

Se você possui assinatura Plex Pass e deseja análises instantâneas no exato segundo em que um novo filme ou episódio é adicionado:

1. Acesse o **Plex Web** > **Configurações** (ícone de chave inglesa).
2. Na barra lateral esquerda, vá em **Webhooks**.
3. Clique em **Adicionar Webhook**.
4. Insira a URL da sua aplicação:
   ```text
   http://IP_DO_DOCKER:8080/webhook
   ```
5. Clique em **Salvar Alterações**.

---

## 🛡️ Segurança

- As chaves de API e tokens locais nunca devem ser adicionados ao controle de versão (`.env` está incluído no `.gitignore` e `.dockerignore`).
- Toda a saída HTML exibida no painel web passa por sanitização rigorosa contra Cross-Site Scripting (XSS).
- O SQLite local armazena hashes e chaves de títulos já processados para impedir chamadas duplicadas à API de IA.

---

## 🤝 Contribuições

Contribuições são muito bem-vindas! Se você tiver ideias de melhorias, novos scrapers de notas (ex: Letterboxd, MyAnimeList) ou correções:

1. Faça um Fork do projeto.
2. Crie uma Branch para a sua feature (`git checkout -b feature/NovaFuncionalidade`).
3. Commit suas alterações (`git commit -m 'Adiciona suporte a Letterboxd'`).
4. Push para a Branch (`git push origin feature/NovaFuncionalidade`).
5. Abra um **Pull Request**.

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja [`LICENSE`](LICENSE) para mais detalhes.
