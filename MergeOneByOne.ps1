# -------------------------------------------------
# MergeOneByOne.ps1
#   – merges every branch (except main & dev) into dev,
#     handling conflicts automatically by preferring the
#     incoming branch’s version (theirs).
# -------------------------------------------------

Set-Location "C:\Users\Tawassul\Desktop\Rahbar-Starter"

# 0️⃣  Abort any stray merge that might be left over
if (Test-Path .git\MERGE_HEAD) { git merge --abort }

# 1️⃣  Bring remote refs up‑to‑date
git fetch --all

# 2️⃣  Checkout a clean, up‑to‑date dev
if (-not (git rev-parse --verify dev 2>$null)) {
    git checkout -b dev origin/dev
} else {
    git checkout dev
    git pull origin dev
}

# 3️⃣  Build the list of branches to merge (exclude main & dev)
$branches = git for-each-ref --format='%(refname:short)' refs/heads/ refs/remotes/origin/ |
            Where-Object { $_ -ne "main" -and $_ -ne "dev" } |
            Sort-Object -Unique

Write-Host "`n=== Branches that will be merged INTO dev ==="
$branches | ForEach-Object { Write-Host "  $_" }

# 4️⃣  Loop – merge each branch, auto‑resolve conflicts with theirs
foreach ($br in $branches) {
    Write-Host "`n--- Merging $br into dev ---"
    # Attempt a normal merge first
    git merge $br --no-ff -m "Merge branch '$br' into dev"
    if ($LASTEXITCODE -ne 0) {
        # Conflict detected – resolve automatically by taking THEIR version
        Write-Host "⚠️ Conflict detected – auto‑resolving with THEIRS (incoming) version"
        git checkout --theirs .
        git add -u            # stage all resolved files
        git commit -m "Merge branch '$br' into dev (auto‑resolved conflicts with theirs)"
        if ($LASTEXITCODE -ne 0) {
            Write-Error "❗ Unable to auto‑resolve $br – manual resolution required."
            break
        } else {
            Write-Host "✅ $br merged (conflicts auto‑resolved)."
        }
    } else {
        Write-Host "✅ $br merged cleanly."
    }
}

# 5️⃣  If we processed all branches, push the result
if ($br -eq $null) {
    Write-Host "`n🚀 All branches merged – pushing dev ..."
    git push origin dev
    Write-Host "`n✅ dev is now up‑to‑date on the remote."
}
