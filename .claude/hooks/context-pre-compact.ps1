# CTX-001 PreCompact hook: archive where the session stands before context is
# compacted. Cheap and deterministic; never edits code, never runs tests, and
# ALWAYS exits 0 so it can never block (auto-)compaction. Failures of optional
# steps are recorded in the archive record instead.
#
# Machine-local pointers (set in .claude/settings.local.json "env", not committed):
#   HOMIES_CONTEXT_ARCHIVE  directory for archives (default ~\.claude\homies-context)
#   HOMIES_CHECKPOINT       the active task CHECKPOINT.md
#   HOMIES_WORKTREE         task worktree for branch/HEAD/status (default: hook cwd)
$ErrorActionPreference = 'Stop'
$errors = New-Object System.Collections.Generic.List[string]
try {
    $raw = [Console]::In.ReadToEnd()
    $in = if ($raw) { $raw | ConvertFrom-Json } else { $null }
    $archive = if ($env:HOMIES_CONTEXT_ARCHIVE) { $env:HOMIES_CONTEXT_ARCHIVE } else { Join-Path $env:USERPROFILE '.claude\homies-context' }
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
    # HOMIES_WORKTREE (machine-local) points git state at the task worktree when
    # the session itself runs from another checkout.
    $cwd = if ($env:HOMIES_WORKTREE) { $env:HOMIES_WORKTREE } elseif ($in -and $in.cwd) { $in.cwd } else { (Get-Location).Path }

    function Invoke-HomiesGit([string[]]$gitArgs) {
        try { (& git -C $cwd @gitArgs 2>$null) -join "`n" } catch { $errors.Add("git $($gitArgs -join ' '): $($_.Exception.Message)"); '' }
    }
    function Sha([string]$path) {
        try { if ($path -and (Test-Path -LiteralPath $path)) { (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() } else { $null } }
        catch { $errors.Add("hash ${path}: $($_.Exception.Message)"); $null }
    }

    $transcript = if ($in) { $in.transcript_path } else { $null }
    $copy = $null
    if ($transcript -and (Test-Path -LiteralPath $transcript)) {
        try {
            $size = (Get-Item -LiteralPath $transcript).Length
            if ($size -le 300MB) {
                $copy = Join-Path $archive "$ts-transcript.jsonl"
                Copy-Item -LiteralPath $transcript -Destination $copy
            } else { $errors.Add("transcript not copied: $size bytes > 300MB") }
        } catch { $errors.Add("transcript copy: $($_.Exception.Message)"); $copy = $null }
    }

    $record = [ordered]@{
        event              = 'PreCompact'
        timestamp_utc      = $ts
        session_id         = if ($in) { $in.session_id } else { $null }
        trigger            = if ($in) { $in.trigger } else { $null }
        cwd                = $cwd
        branch             = Invoke-HomiesGit @('rev-parse', '--abbrev-ref', 'HEAD')
        head               = Invoke-HomiesGit @('rev-parse', 'HEAD')
        git_status_short   = Invoke-HomiesGit @('status', '--short')
        transcript_path    = $transcript
        transcript_sha256  = Sha $transcript
        transcript_copy    = $copy
        checkpoint_path    = $env:HOMIES_CHECKPOINT
        checkpoint_sha256  = Sha $env:HOMIES_CHECKPOINT
        errors             = $errors
    }
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $archive "$ts-precompact.json") -Encoding UTF8
} catch {
    try {
        $fallback = Join-Path $env:USERPROFILE '.claude\homies-context'
        New-Item -ItemType Directory -Force -Path $fallback | Out-Null
        "$(Get-Date -Format o) PreCompact hook failed: $($_.Exception.Message)" | Add-Content -LiteralPath (Join-Path $fallback 'hook-errors.log')
    } catch { }
}
exit 0
