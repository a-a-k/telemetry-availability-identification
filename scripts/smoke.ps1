$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    python -m unittest discover -s tests -v
    python -m telemetry_availability validate-config --config configs/rq1_synthetic.yaml
    python -m telemetry_availability validate-stress-config --config configs/m5_stress.yaml
    python -m telemetry_availability run `
        --config configs/rq1_synthetic.yaml `
        --out .smoke `
        --family same_domain_replicas `
        --mode full `
        --mode no_joint_health `
        --repetitions 3 `
        --sample-sizes 100
    python -m telemetry_availability run-stress-experiment `
        --config configs/m5_stress.yaml `
        --out .smoke/stress `
        --series exporter_loss `
        --series temporal_bursts `
        --series wrong_domain_map `
        --series rare_branch `
        --series readiness_lag `
        --repetitions 1 `
        --sample-sizes 100 `
        --bootstrap-replicates 9
}
finally {
    Pop-Location
}
