# =============================================================================
#  Единая точка входа (Windows PowerShell). Всё выполняется внутри Docker.
#    .\run.ps1 build      — собрать образ (первый раз ~25–40 мин)
#    .\run.ps1 test       — быстрые тесты
#    .\run.ps1 <команда>  — любая команда CLI `liga` (.\run.ps1 help)
#    .\run.ps1 shell      — оболочка в контейнере
#  Если PowerShell запрещает скрипты: используйте run.cmd (обходит ExecutionPolicy).
# =============================================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker не найден. Установите Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker не запущен. Запустите Docker Desktop и повторите."; exit 1 }
if ($args.Count -gt 0 -and $args[0] -eq "build") {
  $rest = @(); if ($args.Count -gt 1) { $rest = $args[1..($args.Count-1)] }
  docker compose build @rest; exit $LASTEXITCODE
}
$commit = (git rev-parse --short HEAD 2>$null)
if (-not $commit) { $commit = "unknown" } elseif (git status --porcelain --untracked-files=no 2>$null) { $commit = "$commit+dirty" }
$env:LIGA_GIT_COMMIT = $commit
docker compose build --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($args.Count -gt 0 -and $args[0] -eq "shell") { docker compose run --rm -it liga bash; exit $LASTEXITCODE }
$cmd = @("help"); if ($args.Count -gt 0) { $cmd = $args }
docker compose run --rm liga @cmd
exit $LASTEXITCODE
