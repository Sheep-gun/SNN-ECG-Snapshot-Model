# Reproduction Notes

## Vivado Project

Open the included project:

```text
vivado_project/SNN_ECG_ModelS_Unified/SNN_ECG_ModelS_Unified.xpr
```

The project uses relative paths to source files:

```text
../../SNN_ECG.srcs/...
```

In this GitHub package, `SNN_ECG.srcs/` is preserved so the `.xpr` can resolve its original relative paths. The same source files are also copied into simplified folders under `rtl/`, `sim/`, and `constraints/` for easier code review. If Vivado reports missing files after moving the repository, recreate the project using the Tcl scripts under `scripts/`.

## Simulation

The strict dataset testbenches are included under `sim/`:

- `tb_snn_ecg_3feat_record_strict_train.v`
- `tb_snn_ecg_3feat_record_strict_val.v`
- `tb_snn_ecg_3feat_record_strict_test.v`

The full `.mem` dataset is not included in this GitHub package. Use the manifests under `datasets/record_wise_strict/` and the original restore workspace to run the full dataset simulation.

## Program Existing Bitstream

The generated bitstream is included:

```text
bitstreams/nexys_a7_model_s_smoke_top.bit
```

It can be programmed through Vivado Hardware Manager or the Tcl script copied under `scripts/`.

## Analog/Mixed-Signal

The analog XModel files are included for documentation and integration reference. They require Questa/XModel tooling and are not synthesized by Vivado.
