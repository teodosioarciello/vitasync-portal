param(
    [switch]$Execute,
    [int]$Limit = 100,
    [string]$LogFile
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Append-LogLine {
    param([string]$Text)

    if (-not $LogFile) {
        return
    }

    if ($null -eq $Text) {
        $Text = ""
    }

    [System.IO.File]::AppendAllText($LogFile, $Text + [Environment]::NewLine, $utf8NoBom)
}

$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo

try {
    $mode = if ($Execute) { "EXECUTE" } else { "DRY-RUN" }

    Write-Host "VitaSync reminder notifications scheduler wrapper" -ForegroundColor Cyan
    Write-Host "Modalita': $mode" -ForegroundColor Cyan
    Write-Host "Limit: $Limit" -ForegroundColor Cyan

    if (-not $Execute) {
        Write-Host "Nessuna notifica inviata/registrata: dry-run." -ForegroundColor Yellow
    } else {
        Write-Host "Attenzione: modalita' execute." -ForegroundColor Yellow
        Write-Host "Con canale console nessuna email reale viene inviata." -ForegroundColor Yellow
        Write-Host "Con canale SMTP configurato possono partire email reali." -ForegroundColor Yellow
    }

    if ($LogFile) {
        Write-Host "LogFile: $LogFile" -ForegroundColor Cyan
    }

    Write-Host ""

    $composeArgs = @(
        "compose",
        "run",
        "--rm",
        "backend",
        "python",
        "scripts/send_due_reminders.py",
        "--limit",
        [string]$Limit
    )

    if (-not $Execute) {
        $composeArgs += "--dry-run"
    }

    if ($LogFile) {
        $logDir = Split-Path -Parent $LogFile

        if ($logDir) {
            New-Item -ItemType Directory -Force -Path $logDir | Out-Null
        }

        if (-not (Test-Path -LiteralPath $LogFile)) {
            [System.IO.File]::WriteAllText($LogFile, "", $utf8NoBom)
        }

        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Append-LogLine "==== VitaSync reminder wrapper | $stamp | mode=$mode | limit=$Limit ===="
    }

    $previousEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        if ($LogFile) {
            $output = & docker @composeArgs 2>&1
            $exitCode = $LASTEXITCODE

            foreach ($line in $output) {
                $text = [string]$line
                Write-Host $text
                Append-LogLine $text
            }
        } else {
            & docker @composeArgs
            $exitCode = $LASTEXITCODE
        }
    }
    finally {
        $ErrorActionPreference = $previousEAP
    }

    if ($LogFile) {
        Append-LogLine "==== wrapper exit code: $exitCode ===="
    }

    Write-Host ""

    if ($exitCode -ne 0) {
        Write-Host "Wrapper terminato con exit code $exitCode." -ForegroundColor Red
    } else {
        Write-Host "Wrapper terminato con successo." -ForegroundColor Green
    }

    exit $exitCode
}
finally {
    Pop-Location
}