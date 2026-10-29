param(
    [string]$Root = 'D:\AI\MiniMaxH3',
    [string]$Repo = 'Comfy-Org/MiniMax-H3',
    [string]$Revision = 'e5eb578a89295337b8ff433a035929ce0279e0b6',
    [switch]$Direct,
    [switch]$Ref2VA
)
$ErrorActionPreference = 'Stop'
if ($Direct) {
    $env:HTTP_PROXY = ''; $env:HTTPS_PROXY = ''; $env:ALL_PROXY = ''; $env:NO_PROXY = '*'
}

$shared = @(
    @{ Path = 'diffusion_models/minimax_h3_fl2va_pruned_w6a8.safetensors'; Size = 15983746636; Sha256 = 'ac746a2e41628ab25afd44d2b22a7fab8d7e66cd07a01bf89ed9d74b0d3f0c35' },
    @{ Path = 'text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'; Size = 15687142551; Sha256 = '35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6' },
    @{ Path = 'vae/minimax_h3_video_vae_int8_convrot.safetensors'; Size = 2811065184; Sha256 = '52a2c8c73583c86e4f41cdcce3a6ad0ea562987bc0bf3d60a0cef5f5c8e60c0e' },
    @{ Path = 'vae/minimax_h3_audio_vae_fp32.safetensors'; Size = 605254808; Sha256 = '8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48' }
)
$refSet = @(
    @{ Path = 'diffusion_models/minimax_h3_ref2va_pruned_w6a8.safetensors'; Size = 15983746636; Sha256 = 'ece96bbbce76670ec782de84acc888fd9d9b210bd2ab97c1957b39896734f9f1' }
)

$files = if ($Ref2VA) { $refSet } else { $shared }
$Models = Join-Path $Root 'ComfyUI\models'

foreach ($file in $files) {
    $target = Join-Path $Models $file.Path
    $dir = Split-Path $target -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

    if (Test-Path $target) {
        $existing = (Get-Item $target).Length
        if ($existing -eq $file.Size) {
            $hash = (Get-FileHash -Algorithm SHA256 -Path $target).Hash.ToLowerInvariant()
            if ($hash -eq $file.Sha256) {
                Write-Output "SKIP verified $($file.Path)"
                continue
            }
            throw "Existing file has wrong SHA256 and will not be deleted automatically: $target"
        }
        throw "Existing file has unexpected size ($existing vs $($file.Size)) and will not be overwritten: $target"
    }

    $url = "https://huggingface.co/$Repo/resolve/$Revision/$($file.Path)?download=true"
    $partial = "$target.partial"
    if (Test-Path $partial) {
        $have = (Get-Item $partial).Length
        if ($have -gt $file.Size) { throw "Partial exceeds expected size: $partial" }
        Write-Output "RESUME $($file.Path) from $have bytes"
    }
    Write-Output "GET $url"
    # Retry here, not with curl --retry: curl reopens --output on every internal
    # retry, truncating the .partial and discarding downloaded bytes.
    $attempt = 0
    while ($true) {
        $attempt++
        $curlArgs = @('--fail', '--location', '--connect-timeout', '30',
                      '--speed-time', '120', '--speed-limit', '1024',
                      '--continue-at', '-', '--output', $partial, $url)
        & curl.exe @curlArgs
        $code = $LASTEXITCODE
        if ($code -eq 0) { break }
        if ($attempt -ge 10) { throw "Download failed after $attempt attempts: $($file.Path) (exit $code); .partial kept" }
        Write-Output "RETRY $($file.Path) attempt $attempt failed with exit $code"
        Start-Sleep -Seconds 5
    }

    $actualSize = (Get-Item $partial).Length
    if ($actualSize -ne $file.Size) {
        throw "Size mismatch for $($file.Path): $actualSize vs $($file.Size); .partial kept for inspection"
    }
    $hash = (Get-FileHash -Algorithm SHA256 -Path $partial).Hash.ToLowerInvariant()
    if ($hash -ne $file.Sha256) {
        throw "SHA256 mismatch for $($file.Path): $hash; .partial kept for inspection"
    }
    Move-Item -Path $partial -Destination $target
    Write-Output "OK $($file.Path) $actualSize bytes"
}

$total = (Get-ChildItem $Models -Recurse -File -Filter '*.safetensors' | Measure-Object Length -Sum).Sum
Write-Output "Verified model bytes under models/: $total"
