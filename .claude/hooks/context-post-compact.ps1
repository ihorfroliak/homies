# CTX-001 PostCompact hook: archive bounded metadata (never raw hook input,
# with compact_summary stored only by explicit opt-in and within its size cap).
# Never rewrites repository or canonical documents. Always exits 0.
$ErrorActionPreference = 'Stop'
try {
    $raw = [Console]::In.ReadToEnd()
    $in = if ($raw) { $raw | ConvertFrom-Json } else { $null }
    $archive = if ($env:HOMIES_CONTEXT_ARCHIVE) { $env:HOMIES_CONTEXT_ARCHIVE } else { Join-Path $env:USERPROFILE '.claude\homies-context' }
    New-Item -ItemType Directory -Force -Path $archive | Out-Null
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
    # HOMIES_WORKTREE (machine-local) points git state at the task worktree when
    # the session itself runs from another checkout.
    $cwd = if ($env:HOMIES_WORKTREE) { $env:HOMIES_WORKTREE } elseif ($in -and $in.cwd) { $in.cwd } else { (Get-Location).Path }
    $head = try { (& git -C $cwd rev-parse HEAD 2>$null) -join '' } catch { '' }
    $summary = if ($in -and ($in.PSObject.Properties.Name -contains 'compact_summary')) { [string]$in.compact_summary } else { $null }

    $record = [ordered]@{
        event           = 'PostCompact'
        timestamp_utc   = $ts
        session_id      = if ($in) { $in.session_id } else { $null }
        trigger         = if ($in) { $in.trigger } else { $null }
        cwd             = $cwd
        head            = $head
        checkpoint_path = $env:HOMIES_CHECKPOINT
        summary_file    = $null
        # Raw hook event intentionally omitted (privacy).
    }
    if ($env:HOMIES_ARCHIVE_COMPACT_SUMMARY -eq '1' -and $summary -and $summary.Length -le 16384) {
        $summaryFile = Join-Path $archive "$ts-summary.md"
        @("# Compact summary $ts", '', "session: $($record.session_id)  trigger: $($record.trigger)  head: $head", '', $summary) |
            Set-Content -LiteralPath $summaryFile -Encoding UTF8
        $record.summary_file = $summaryFile
    }
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $archive "$ts-postcompact.json") -Encoding UTF8
} catch {
    try {
        $fallback = Join-Path $env:USERPROFILE '.claude\homies-context'
        New-Item -ItemType Directory -Force -Path $fallback | Out-Null
        "$(Get-Date -Format o) PostCompact hook failed: $($_.Exception.Message)" | Add-Content -LiteralPath (Join-Path $fallback 'hook-errors.log')
    } catch { }
}
exit 0
