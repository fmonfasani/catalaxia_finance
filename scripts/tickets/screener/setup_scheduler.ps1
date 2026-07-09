<#
    setup_scheduler.ps1 — Alta de las tareas programadas del screener (Windows Task Scheduler)
    ==========================================================================================
    Crea 4 tareas que corren run_update.py donde está la DB (local/VM):
      - Daily      18:30   --daily      (precios yfinance)
      - Quarterly  1/ene-abr-jul-oct 03:00  --quarterly (fundamentales + rebuild)
      - Monthly    día 5 04:00   --monthly    (IPC INDEC)
      - Annual     2-abr 05:00   --annual     (ratio ADR del 20-F)

    Uso (PowerShell como administrador):
      .\setup_scheduler.ps1              # crea/actualiza las 4 tareas
      .\setup_scheduler.ps1 -Remove      # las borra
      .\setup_scheduler.ps1 -WhatIf      # muestra qué haría, sin ejecutar

    Idempotente: /F sobreescribe si ya existen.
#>
param(
    [switch]$Remove,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# Carpeta de este script (donde viven run_update.py y run_all.py)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$py  = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Error "python no está en el PATH. Instalalo o activá el venv."; exit 1 }

Write-Host "python : $py"
Write-Host "dir    : $dir"
Write-Host ""

# nombre -> (schedule args, comando run_update)
$tasks = @(
    @{ Name = "Screener\Daily-Precios";        Args = @("/SC","DAILY","/ST","18:30");                       Mode = "--daily" },
    @{ Name = "Screener\Quarterly-Fundamentales"; Args = @("/SC","MONTHLY","/MO","3","/D","1","/ST","03:00"); Mode = "--quarterly" },
    @{ Name = "Screener\Monthly-IPC";          Args = @("/SC","MONTHLY","/D","5","/ST","04:00");            Mode = "--monthly" },
    @{ Name = "Screener\Annual-ADR";           Args = @("/SC","YEARLY","/D","2","/M","APR","/ST","05:00");  Mode = "--annual" }
)

foreach ($t in $tasks) {
    if ($Remove) {
        Write-Host "Borrando $($t.Name) ..."
        if (-not $WhatIf) { schtasks /Delete /TN $t.Name /F 2>$null }
        continue
    }
    $cmd = "cmd /c cd /d `"$dir`" && `"$py`" run_update.py $($t.Mode) --quiet"
    $createArgs = @("/Create","/TN",$t.Name) + $t.Args + @("/TR",$cmd,"/F","/RL","LIMITED")
    Write-Host "Creando $($t.Name)  ($($t.Mode)) ..."
    if ($WhatIf) {
        Write-Host "  schtasks $($createArgs -join ' ')"
    } else {
        schtasks @createArgs
    }
}

if (-not $Remove -and -not $WhatIf) {
    Write-Host ""
    Write-Host "Listo. Verificá con:  schtasks /Query /TN `"Screener\Daily-Precios`" /V /FO LIST"
    Write-Host "Probá una corrida:    schtasks /Run   /TN `"Screener\Daily-Precios`""
}
