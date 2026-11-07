[CmdletBinding()]
param(
    [string]$Namespace = "rahbar",
    [string]$RolloutImage = "",
    [switch]$RunRolloutDemo
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$evidenceDir = Join-Path $repoRoot "docs\evidence"

if ((git -C $repoRoot branch --show-current) -ne "dev") {
    throw "Phase 5 evidence must be captured from the dev branch."
}

New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

function Save-KubectlOutput {
    param(
        [string]$FileName,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & kubectl @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $output | Set-Content -Encoding utf8 (Join-Path $evidenceDir $FileName)
    if ($exitCode -ne 0) {
        throw "kubectl $($Arguments -join ' ') failed; see docs/evidence/$FileName"
    }
}

kubectl cluster-info | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No reachable Kubernetes cluster. Start Minikube/Docker before capturing runtime evidence."
}

Save-KubectlOutput "kubectl-top-indexer.txt" @("top", "pod", "-l", "job-name=indexer-job", "-n", $Namespace)
Save-KubectlOutput "kubectl-top-api.txt" @("top", "pods", "-n", $Namespace)
Save-KubectlOutput "get-hpa.txt" @("get", "hpa", "-n", $Namespace)

kubectl scale deployment/api --replicas=4 -n $Namespace | Out-Null
kubectl rollout status deployment/api -n $Namespace --timeout=120s | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "API did not become ready after scaling; endpoint evidence was not captured."
}
Save-KubectlOutput "get-endpoints.txt" @("get", "endpoints", "api", "-n", $Namespace)

if ($RunRolloutDemo) {
    if ([string]::IsNullOrWhiteSpace($RolloutImage)) {
        throw "-RolloutImage is required with -RunRolloutDemo."
    }
    kubectl set image deployment/api "api=$RolloutImage" -n $Namespace
    Save-KubectlOutput "rollout-status.txt" @("rollout", "status", "deployment/api", "-n", $Namespace, "--timeout=120s")
    kubectl rollout undo deployment/api -n $Namespace
    Save-KubectlOutput "rollout-undo.txt" @("rollout", "status", "deployment/api", "-n", $Namespace, "--timeout=120s")
}

Write-Output "Captured Phase 5 Member 1 evidence in $evidenceDir"
