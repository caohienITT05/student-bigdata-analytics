param(
    [ValidateSet('prepare','smoke','a','oulad','sql','verify','all')][string]$Stage = 'all',
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$pipelineRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pipelineConfig = Get-Content -LiteralPath (Join-Path $pipelineRoot 'config/data_sources.json') -Raw | ConvertFrom-Json
Push-Location -LiteralPath $pipelineRoot
try {
    & (Join-Path $pipelineRoot '.venv/Scripts/python.exe') -X utf8 -m pipeline.prepare
    if ($LASTEXITCODE -ne 0) { throw 'Source preparation failed' }
    if ($Stage -eq 'prepare') { return }
    $pipelineArguments = @('run','--rm','--cpus','2','--memory','2g','--memory-swap','4g','--network','none',
        '--hostname','student-bigdata-spark','--add-host','student-bigdata-spark:127.0.0.1','--env','SPARK_LOCAL_IP=127.0.0.1',
        '--mount',"type=bind,source=$pipelineRoot,target=/workspace,readonly")
    foreach ($pipelineFolder in @('data/clean','data/curated','reports/data_pipeline')) {
        $pipelinePath = (Resolve-Path -LiteralPath (Join-Path $pipelineRoot $pipelineFolder)).Path
        if (-not $pipelinePath.StartsWith($pipelineRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Output outside project' }
        $pipelineArguments += @('--mount',"type=bind,source=$pipelinePath,target=/workspace/$pipelineFolder")
    }
    $pipelineArguments += @('--workdir','/workspace','--env','PYTHONPATH=/workspace','--entrypoint','/opt/spark/bin/spark-submit',
        $pipelineConfig.spark.image,'--master',$pipelineConfig.spark.master,'--driver-memory',$pipelineConfig.spark.driver_memory,
        '--conf','spark.ui.enabled=false','--conf','spark.driver.host=127.0.0.1','--conf','spark.driver.bindAddress=127.0.0.1',
        '/workspace/pipeline/batch.py','--root','/workspace','--stage',$Stage)
    if ($Force) { $pipelineArguments += '--force' }
    & docker @pipelineArguments
    if ($LASTEXITCODE -ne 0) { throw "Spark stage $Stage failed (exit $LASTEXITCODE)" }
} finally { Pop-Location }
