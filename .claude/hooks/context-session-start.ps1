# CTX-001 SessionStart hook (matchers: compact, resume): inject a SMALL recovery
# pointer — branch, HEAD, the active CHECKPOINT path and the latest compact
# summary path — never the transcript or the checkpoint itself. Always exits 0.
$ErrorActionPreference = 'Stop'
try {
    $raw = [Console]::In.ReadToEnd()
    $in = if ($raw) { $raw | ConvertFrom-Json } else { $null }
    # HOMIES_WORKTREE (machine-local) points git state at the task worktree when
    # the session itself runs from another checkout.
    $cwd = if ($env:HOMIES_WORKTREE) { $env:HOMIES_WORKTREE } elseif ($in -and $in.cwd) { $in.cwd } else { (Get-Location).Path }
    $source = if ($in -and $in.source) { $in.source } else { 'unknown' }
    $branch = try { (& git -C $cwd rev-parse --abbrev-ref HEAD 2>$null) -join '' } catch { '?' }
    $head = try { (& git -C $cwd rev-parse HEAD 2>$null) -join '' } catch { '?' }
    $archive = if ($env:HOMIES_CONTEXT_ARCHIVE) { $env:HOMIES_CONTEXT_ARCHIVE } else { Join-Path $env:USERPROFILE '.claude\homies-context' }
    $latest = $null
    if (Test-Path -LiteralPath $archive) {
        $latest = Get-ChildItem -LiteralPath $archive -File |
            Where-Object { $_.Name -like '*-summary.md' -or $_.Name -like '*-postcompact.json' -or $_.Name -like '*-precompact.json' } |
            Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    $checkpoint = if ($env:HOMIES_CHECKPOINT) { $env:HOMIES_CHECKPOINT } else { '(none configured: HOMIES_CHECKPOINT unset)' }
    $text = @(
        "Homies context recovery (session start: $source).",
        "Branch: $branch  HEAD: $head",
        "Active CHECKPOINT: $checkpoint",
        "Latest compact archive: $(if ($latest) { $latest } else { '(none)' })",
        'Before continuing material work: read the CHECKPOINT, check git status/HEAD, compare with its NEXT ACTION, then continue.',
        'Repository/canon and Git outrank the CHECKPOINT; the CHECKPOINT outranks compact summaries and chat memory (.claude/rules/context-survival.md).'
    ) -join "`n"
    $out = @{ hookSpecificOutput = @{ hookEventName = 'SessionStart'; additionalContext = $text } }
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::Out.Write(($out | ConvertTo-Json -Depth 4 -Compress))
} catch { }
exit 0
