# Script para Build e Push local para o Docker Hub
param(
    [string]$Username = "samuelsilvag",
    [string]$Tag = "latest"
)

$ImageFullName = "${Username}/plexcritic-ai:${Tag}"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Construindo e Publicando: $ImageFullName" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Verifica se o Docker está rodando
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: O Docker Desktop nao esta em execucao. Inicie o Docker e tente novamente." -ForegroundColor Red
    exit 1
}

# 2. Build da imagem
Write-Host "`n[1/3] Iniciando o build da imagem Docker..." -ForegroundColor Yellow
docker build -t $ImageFullName .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Falha ao construir a imagem Docker." -ForegroundColor Red
    exit 1
}

# 3. Confirmação e Push
Write-Host "`n[2/3] Imagem construida com sucesso!" -ForegroundColor Green
Write-Host "[3/3] Enviando imagem para o Docker Hub..." -ForegroundColor Yellow
docker push $ImageFullName

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSucesso! Imagem disponivel em: https://hub.docker.com/r/${Username}/plexcritic-ai" -ForegroundColor Green
} else {
    Write-Host "`nFalha no push. Se nao estiver autenticado, execute primeiro: docker login" -ForegroundColor Red
}

