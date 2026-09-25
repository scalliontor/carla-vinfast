# ============================================================================
#  Dong goi toan bo du an de mang sang may khac (chay tren MAY NGUON Windows)
#
#    powershell -ExecutionPolicy Bypass -File export_bundle.ps1
#    powershell -ExecutionPolicy Bypass -File export_bundle.ps1 -IncludeServerImage
#
#  Ket qua: thu muc $Out gom
#    images\client.tar          image client (Scenario Runner + script)
#    images\server.tar          (chi khi -IncludeServerImage) carlasim/carla:0.9.16, ~20 GB
#    data\out, data\evidence    du lieu da thu / bang chung
#    data\recorder\             file .log cua CARLA recorder
#    docker-compose*.yml, .env.example, import_bundle.sh, README.md
#
#  Mac dinh KHONG kem image server: may dich co mang thi `docker pull` nhanh
#  hon chep 20 GB. May dich khong co mang thi them -IncludeServerImage.
# ============================================================================
param(
    [string]$Out = "D:\Hunganh\carla_migrate_bundle",
    [switch]$IncludeServerImage,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'

$here = $PSScriptRoot
$scen = (Resolve-Path "$here\..").Path
$serverImage = 'carlasim/carla:0.9.16'
$clientImage = 'carla-vinfast-client:0.9.16'

New-Item -ItemType Directory -Force "$Out\images", "$Out\data\recorder" | Out-Null

if (-not $SkipBuild) {
    Write-Host "[1/4] Build image client..."
    docker compose -f "$here\docker-compose.yml" -f "$here\docker-compose.build.yml" build client
    if ($LASTEXITCODE -ne 0) { throw "Build client that bai" }
}

Write-Host "[2/4] Luu image ra file tar..."
docker save -o "$Out\images\client.tar" $clientImage
if ($LASTEXITCODE -ne 0) { throw "docker save client that bai" }
if ($IncludeServerImage) {
    docker pull $serverImage
    if ($LASTEXITCODE -ne 0) { throw "docker pull server that bai" }
    docker save -o "$Out\images\server.tar" $serverImage
    if ($LASTEXITCODE -ne 0) { throw "docker save server that bai" }
}

Write-Host "[3/4] Chep du lieu..."
# robocopy tra ma 0-7 la thanh cong, >=8 moi la loi
foreach ($d in 'out', 'evidence') {
    robocopy "$scen\$d" "$Out\data\$d" /E /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $d that bai ($LASTEXITCODE)" }
}
# File recorder o may nguon nam trong scenario_runner\; tren may dich chung
# nam o data\recorder\ vi server va client phai cung doc duoc.
foreach ($d in 'recorder_osc2', 'recorder_vinfast', 'recordings') {
    if (Test-Path "$scen\scenario_runner\$d") {
        robocopy "$scen\scenario_runner\$d" "$Out\data\recorder\$d" /E /NFL /NDL /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy $d that bai ($LASTEXITCODE)" }
    }
}

Write-Host "[4/4] Chep file cau hinh..."
foreach ($f in 'docker-compose.yml', 'docker-compose.gui.yml', '.env.example', 'import_bundle.sh', 'README.md') {
    Copy-Item "$here\$f" "$Out\$f" -Force
}

$size = (Get-ChildItem -Recurse -File $Out | Measure-Object Length -Sum).Sum / 1GB
Write-Host ("Xong: {0}  ({1:N1} GB)" -f $Out, $size)
Write-Host "Chep ca thu muc nay sang may dich roi chay: bash import_bundle.sh"
