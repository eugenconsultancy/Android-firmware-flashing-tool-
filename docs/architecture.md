# Architecture

Android Flasher is a layered desktop application. Each layer has a
single responsibility and communicates with adjacent layers only.
┌──────────────────────┐
│ GUI / UI │
└──────────┬───────────┘
│
┌──────────▼───────────┐
│ Flash Controller │
└──────────┬───────────┘
│
┌────────────────▼────────────────┐
│ Preflight Engine │
└───────┬───────────────┬─────────┘
│ │
┌────────▼──────┐ ┌──────▼─────────┐
│ Device Engine │ │ Firmware Engine│
└────────┬──────┘ └──────┬─────────┘
│ │
└───────┬───────┘
│
┌──────────▼──────────┐
│ Compatibility Engine│
└──────────┬──────────┘
│
┌──────────▼──────────┐
│ Flash Plan │
└──────────┬──────────┘
│
┌──────────▼──────────┐
│ Command Executor │
└──────────┬──────────┘
│
┌─────────▼─────────┐
│ Verification │
└───────────────────┘

text

## Layers

### UI layer (`android_flasher/ui`)

PySide6 widgets. The UI never constructs raw fastboot or adb commands
and never spawns processes. It emits signals and renders data produced
by the engine.

### Core layer (`android_flasher/core`)

Flash planning, command construction, execution, and verification.

- `flash_plan.py` – immutable description of intended work.
- `command_builder.py` – converts operations to `CommandSpec` argv lists.
- `command_executor.py` – executes argv lists with `shell=False`, timeouts and cancellation.
- `flash_engine.py` – runs a plan step-by-step.
- `verification.py` – reconciles execution results with the plan.
- `flasher.py` – facade that ties planning, preflight, risk, confirmation and execution together.

### Safety layer (`android_flasher/safety`)

Preflight checks, risk classification, confirmation prompts, backup
classification, and the flash planner.

### Device layer (`android_flasher/devices`)

ADB, fastboot, detection, identification, slots, bootloader state.

### Firmware layer (`android_flasher/firmware`)

Detection, analysis, metadata, package model, compatibility.

### Partition layer (`android_flasher/partitions`)

Physical, logical and dynamic partition modelling.

### Platform tools (`android_flasher/platform_tools`)

Locates and versions adb and fastboot.

### Logging (`android_flasher/logging`)

Application logger, audit trail, and per-session artifact recording.

## Design principles

1. **No shell execution.** Every subprocess uses `shell=False` and an argv list.
2. **No GUI-constructed commands.** The GUI drives the engine; the engine constructs commands.
3. **No destructive bypass.** Every destructive operation passes through the planner, the preflight engine, the risk assessor and the confirmation flow.
4. **No overstated compatibility.** Compatibility states are `CONFIRMED`, `LIKELY`, `UNKNOWN`, `MISMATCH`, `BLOCKED`. UNKNOWN is never rendered as PASS.
5. **No silent claims of success.** Verification reports observed state; it does not claim the device will boot.

## Capability-driven design

Support is driven by device capabilities and firmware metadata, not by
hard-coded Android version checks. New devices are added via profile
data under `profiles/`, not by editing Python code.
