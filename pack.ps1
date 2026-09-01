# Build deploy.zip for Yandex Cloud Functions.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$zipPath = Join-Path $root "deploy.zip"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

$items = @(
    (Join-Path $root "index.py"),
    (Join-Path $root "app"),
    (Join-Path $root "requirements.txt")
)

Compress-Archive -Path $items -DestinationPath $zipPath -Force

Write-Host "Done: $zipPath"
Write-Host "Upload this archive to Yandex Cloud Functions."
Write-Host "Entry point: index.handler"
