$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Edite o arquivo .env e informe OPENAI_API_KEY. Depois execute este script novamente." -ForegroundColor Yellow
  exit 1
}
& .\.venv\Scripts\python.exe -m app.ingest

