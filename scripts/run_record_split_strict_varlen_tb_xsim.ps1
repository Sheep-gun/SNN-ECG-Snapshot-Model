param(
    [ValidateSet("train", "val", "test")]
    [string]$Split = "val"
)

$ErrorActionPreference = "Stop"

$Root = "C:\Users\YangGeon\SNN_ECG_RESTORE_MODEL_S"
$VivadoBin = "C:\Xilinx\Vivado\2020.2\bin"
$SrcDir = Join-Path $Root "SNN_ECG.srcs\sources_1\new"
$SimDir = Join-Path $Root "SNN_ECG.srcs\sim_1\new"
$WorkDir = Join-Path $Root ("xsim_record_strict_" + $Split)
$ResultDir = Join-Path $Root ("results\" + $Split)

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
New-Item -ItemType Directory -Force -Path $ResultDir | Out-Null

$TopTb = "tb_snn_ecg_3feat_record_strict_$Split"
$Prj = Join-Path $WorkDir "sources.prj"
$RunTcl = Join-Path $WorkDir "run_all.tcl"

$Files = @(
    "$SrcDir\ecg_event_encoder.v",
    "$SrcDir\snn_ecg_input_normalizer.v",
    "$SrcDir\qrs_lif_detector.v",
    "$SrcDir\pnn_rhythm_predictor.v",
    "$SrcDir\dscr_spike_counter.v",
    "$SrcDir\ram_peak_accumulator.v",
    "$SrcDir\rdm_variability_neuron.v",
    "$SrcDir\ectopic_pair_neuron.v",
    "$SrcDir\qrs_maf_neuron.v",
    "$SrcDir\rbbb_qrs_delay_bank.v",
    "$SrcDir\abandoned_feature_stubs.v",
    "$SrcDir\class_score_neurons.v",
    "$SrcDir\snn_ecg_3feat_top.v",
    "$SrcDir\snn_ecg_model_a_plus_core.v",
    "$SimDir\tb_snn_ecg_3feat_dataset.v",
    "$SimDir\$TopTb.v"
)

$missing = $Files | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    Write-Host "Missing source files:"
    $missing | ForEach-Object { Write-Host $_ }
    exit 1
}

$prjLines = $Files | ForEach-Object { "verilog work `"$_`"" }
Set-Content -Path $Prj -Value $prjLines -Encoding ASCII
Set-Content -Path $RunTcl -Value @("run all", "quit") -Encoding ASCII

Push-Location $WorkDir
try {
    & "$VivadoBin\xvlog.bat" --nolog -prj $Prj 2>&1 | Tee-Object -FilePath (Join-Path $WorkDir "xvlog.log")
    if ($LASTEXITCODE -ne 0) { throw "xvlog failed with exit code $LASTEXITCODE" }

    & "$VivadoBin\xelab.bat" --nolog -debug typical $TopTb -s "${TopTb}_behav" 2>&1 | Tee-Object -FilePath (Join-Path $WorkDir "xelab.log")
    if ($LASTEXITCODE -ne 0) { throw "xelab failed with exit code $LASTEXITCODE" }

    & "$VivadoBin\xsim.bat" "${TopTb}_behav" --nolog -tclbatch "run_all.tcl" 2>&1 | Tee-Object -FilePath (Join-Path $WorkDir "xsim.log")
    if ($LASTEXITCODE -ne 0) { throw "xsim failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
