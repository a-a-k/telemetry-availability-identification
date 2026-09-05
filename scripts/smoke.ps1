$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    python -m unittest discover -s tests -v
    python -m telemetry_availability validate-config --config configs/rq1_synthetic.yaml
    python -m telemetry_availability run `
        --config configs/rq1_synthetic.yaml `
        --out .smoke `
        --family same_domain_replicas `
        --mode full `
        --mode no_joint_health `
        --repetitions 3 `
        --sample-sizes 100
}
finally {
    Pop-Location
}
