$staging = "d:\Projects\DolFin\frontend\node_modules\.staging"
$target  = "d:\Projects\DolFin\frontend\node_modules"

Get-ChildItem $staging | ForEach-Object {
    $src  = $_.FullName
    $raw  = $_.Name
    # strip trailing 8-hex-char suffix that npm adds during staging
    $name = $raw -replace '-[a-f0-9]{8}$', ''
    $dst  = Join-Path $target $name

    if (Test-Path $dst) {
        Write-Host "Skip $name"
    } else {
        try {
            Copy-Item -Recurse -Force $src $dst
            Write-Host "Copied $name"
        } catch {
            Write-Host "FAIL $name"
        }
    }
}
Write-Host "All done"
