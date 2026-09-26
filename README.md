# Android Flasher

A firmware-aware Android flashing platform for Windows, Linux and
macOS. Android Flasher is built around a layered engine: device
detection, firmware analysis, compatibility validation, flash
planning, controlled execution, and post-operation verification.

> **By default the application runs in read-only mode.** Destructive
> operations require explicit configuration, preflight, risk
> classification, and user confirmation.

## Features

- Device detection across ADB, fastboot and fastbootd.
- Normalized device identity: manufacturer, model, codename, product,
  variant, Android version, SDK, build, bootloader state, slot
  architecture, and capabilities.
- Firmware detection from internal structure, not file extension.
- Firmware analysis for raw images, sparse images, factory ZIPs, OTA
  ZIPs, `payload.bin`, and `super.img`.
- Compatibility engine with explicit states:
  `CONFIRMED`, `LIKELY`, `UNKNOWN`, `MISMATCH`, `BLOCKED`.
- Flash planner that produces an immutable plan before any execution.
- Command builder that produces argv lists; the executor always uses
  `shell=False`.
- Risk classification and user confirmation before destructive
  operations.
- Post-operation verification with a structured report.
- Per-session artifacts: `session.json`, `commands.log`,
  `device.json`, `firmware.json`, `result.json`.
- Professional dark and light themes.

## Architecture

See `docs/architecture.md` for the full layered design.

GUI → Flash Controller → Preflight → Device + Firmware
→ Compatibility → Flash Plan → Command Builder
→ Execution → Verification → Session Report

text

## Safety model

Android Flasher refuses to:

- Flash a device whose compatibility state is `MISMATCH` or `BLOCKED`.
- Flash a device with a locked bootloader.
- Erase or format partitions unless explicitly enabled.
- Disable AVB unless explicitly enabled and confirmed.
- Change the active slot unless explicitly enabled.
- Execute a plan whose preflight has failed.
- Execute a plan whose risk assessment is blocked.
- Execute a destructive plan without user confirmation.
- Run any command through a shell.

## Installation

### Requirements

- Python 3.11 or newer.
- Android SDK Platform Tools (`adb`, `fastboot`).

### Setup

```bash
git clone <repo> android-flasher
cd android-flasher

python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# source .venv/Scripts/activate    # Windows Git Bash

python -m pip install --upgrade pip
pip install -r requirements.txt
Run
bash
python app.py
or:

bash
./run.sh          # Linux / macOS / Git Bash
run.bat           # Windows
Configuration
config.yaml controls application behaviour. Safety-relevant defaults:

yaml
safety:
  phase1_read_only: true     # master read-only switch
  allow_flash: false         # enable destructive flashing
  allow_erase: false
  allow_format: false
  allow_set_active: false
  allow_ab_slot_change: false
  block_critical: true

flash:
  allow_fastboot_update: true
  allow_avb_disable: false
  allow_extraction_for_factory_zip: false
Changing these values does not bypass the preflight, risk or
confirmation flows. It only changes which operations the preflight
engine is willing to consider.

Testing
bash
pytest -v
The test suite uses mocks and fixtures. No physical device is
required.

Documentation
docs/architecture.md

docs/supported_devices.md

docs/firmware_formats.md

docs/flashing_modes.md

docs/driver_guide.md

docs/troubleshooting.md

Compatibility disclaimer
Android device support is capability- and profile-driven. No
generic application can safely guarantee compatibility with every
Android device, firmware format, or bootloader revision. Android
Flasher reports what it observes and refuses to overstate certainty.
















# Android Flasher — Complete User Guide (Procedural)

This document explains **exactly what to do, in what order, and what to choose depending on your situation**. It assumes the current Phase 4 application you have installed. Read it top to bottom once, then use the "Quick Reference" table at the bottom for everyday use.

---

## 0. What this tool does — in one paragraph

Android Flasher is a **safety-gated fastboot frontend**. You point it at a firmware file, connect an Android device in fastboot mode, and it will: detect the device, analyze the firmware, compare them, produce a plan, show you the exact commands it will run, ask for confirmation, execute the plan, and verify the result. It refuses to run anything if preflight, compatibility, or risk assessment fails. **By default, it cannot flash anything** — it only detects, analyzes, and plans. You must explicitly arm it in `config.yaml` to permit writes.

---

## 1. Two operating modes

| Mode | When the app is in this mode | What it can do |
|------|------------------------------|----------------|
| **Read Only** (default) | `safety.phase1_read_only: true` in `config.yaml` | Detect devices, analyze firmware, run compatibility, generate plans, preview commands. **Cannot execute** any flash, erase, format, or reboot. |
| **Armed** | `safety.phase1_read_only: false` and `safety.allow_flash: true` | Everything above, plus execution of the plan after preflight, risk assessment, and explicit confirmation. |

The phase pill in the top-right of the window shows which mode you are in — **amber "Read Only"** or **green "Armed"**.

---

## 2. The window at a glance

```
┌─ Menu bar ─────────────────────────────────────────────────────────┐
│ File   View   Help                                                 │
├─ Toolbar card ─────────────────────────────────────────────────────┤
│ [Refresh Devices] [Analyze Firmware] [Run Compatibility]           │
│                          Android Flasher  v2.0.0-phase4 [Read Only]│
├─ Platform Tools banner ────────────────────────────────────────────┤
│ adb: … (1.0.41)  •  fastboot: … (37.0.1)                            │
├─ Splitter ────────────────────────────────────────────────────────┤
│  Left column (Device + Firmware)   │  Right column (tabs)          │
│  ┌─ Device ──────┐                 │  ┌─ Progress card ──┐         │
│  │ State: —      │                 │  │ [Idle] Ready.    │         │
│  │ Serial: —     │                 │  │ ───────────────  │         │
│  │ ...           │                 │  │ 0%               │         │
│  └───────────────┘                 │  └──────────────────┘         │
│  ┌─ Firmware ────┐                 │  ┌─ Tabs ───────────┐         │
│  │ [Select…]     │                 │  │ Compatibility   │         │
│  │ ...           │                 │  │ Partitions      │         │
│  └───────────────┘                 │  │ Flash Plan      │         │
│                                    │  │ Commands        │         │
│                                    │  │ Log             │         │
│                                    │  └─────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
```

**Panels:**

- **Device** — everything the app detected about the connected device.
- **Firmware** — the package you selected and everything the analyzer extracted from it.
- **Progress** — status pill + progress bar + current operation + elapsed time.
- **Compatibility** — side-by-side matrix of device vs firmware attributes.
- **Partitions** — every partition referenced by device or firmware, and whether it matches.
- **Flash Plan** — the ordered list of operations that will be executed, with blockers and warnings.
- **Commands** — the exact argv that will be passed to fastboot, per step. Read-only.
- **Log** — timestamped console output.

---

## 3. The canonical workflow

Do these steps **in this exact order**. Skipping a step will make later steps refuse to run.

### Step 1 — Launch the app

```bash
cd ~/android-flasher
source .venv/Scripts/activate
python app.py
```

You should see the window. The phase pill says **Read Only**. The platform tools banner shows the adb and fastboot versions.

### Step 2 — Prepare your device (choose depending on what you have)

| Your device state | What to do |
|-------------------|-----------|
| Device is off | Turn it on, enable **Developer Options**, enable **USB debugging**, connect by USB, then run `adb reboot bootloader` in a terminal. |
| Device is on with USB debugging already enabled | Connect USB, then run `adb reboot bootloader`. |
| Device is already in bootloader / fastboot | Just connect USB. The screen will say something like "FASTBOOT MODE" or show the bootloader menu. |
| Device is in fastbootd (userspace fastboot) | Some flows require this. See Step 8 for when. |
| Device does not respond to `fastboot devices` in a terminal | Do not proceed. Fix the driver or cable first. See the Troubleshooting section of this guide. |

**Why this step matters:** if the device is not in the right mode, detection returns "no device" and every following step refuses to run.

### Step 3 — Click **Refresh Devices**

- The **Progress** card shows "Detecting devices…" with an animated bar.
- The **Device** panel populates with State, Transport, Serial, Manufacturer, Brand, Model, Codename, Product, Variant, Android, SDK, Build, Bootloader, Slot, Capabilities.
- The **Log** tab records the detection state and any message.
- The **Status bar** at the bottom shows "Detection complete" or a failure message.

**If detection fails:** a dialog appears. Read the Log tab. Common causes: wrong USB mode (device is on but not in fastboot), missing driver, multiple devices connected, USB hub.

**What to verify before moving on:**

- `State` says `FASTBOOT_DEVICE` (or `FASTBOOTD_DEVICE` if you are in fastbootd).
- `Serial` matches the physical device you intend to flash.
- `Bootloader` shows `unlocked` if you intend to flash (the app blocks writes on a locked bootloader).
- `Slot` shows `a` or `b` if the device is A/B.

### Step 4 — Click **Select Firmware…**

A file dialog opens. Choose your firmware file.

**What to choose depending on what you have:**

| Your firmware file | What it probably is | What the app will do |
|--------------------|--------------------|----------------------|
| `boot.img`, `vbmeta.img`, `dtbo.img`, `recovery.img`, `init_boot.img`, `vendor_boot.img` | A single raw image | Detects a raw image, maps it to its partition. |
| `system.img`, `vendor.img`, `product.img`, `odm.img`, `system_ext.img` | A logical partition image | Requires fastbootd to flash on dynamic-partition devices. |
| `super.img` | A super partition image | Flashes the whole dynamic-partition container. |
| A sparse image (any `.img` that starts with bytes `3A FF 26 ED`) | A sparse image | Detected as sparse; the plan handles it as a single partition image. |
| `factory.zip` or any ZIP containing `flash-all.sh`, `flash-all.bat`, `bootloader-*.img`, `radio-*.img`, `image-*.zip` | A factory package | The plan uses `fastboot update` (or a blocker, if extraction is required but disabled). |
| `ota.zip` or any ZIP containing `payload.bin` or `metadata` | An OTA package | The plan uses `fastboot update`. |
| A bare `payload.bin` | A payload container | The plan is blocked. Present the full OTA ZIP instead. |

**Do not guess.** If you are not sure what the file is, let the app tell you — click **Analyze Firmware** and read the **Firmware** panel.

### Step 5 — Click **Analyze Firmware**

- The **Progress** card shows "Analyzing firmware…".
- The **Firmware** panel populates: Name, Type, Target, Android, Build, Images, Size, SHA-256.
- The **Log** records the analysis summary.

**What to verify before moving on:**

| Field | Good value | Bad value |
|-------|-----------|-----------|
| Type | `raw_image`, `sparse_image`, `factory_zip`, `ota_zip` | `unknown` or blank — the file is malformed. |
| Target | A codename (e.g. `panther`, `cheetah`) | blank — the package does not declare a target. You can still proceed, but compatibility will be cautious. |
| SHA-256 | A long hex string | `(not computed)` — hashing was disabled in `config.yaml`. Enable it for production use. |
| Images | One or more image names | Empty — the package has no images the app recognizes. |

**If the analysis fails:** read the Log tab. Common causes: corrupt ZIP, truncated download, unsupported payload-only package.

### Step 6 — Click **Run Compatibility**

- The **Progress** card shows "Running compatibility analysis…".
- The **Compatibility** tab populates with a matrix.
- The **Partitions** tab populates with a partition table.
- The **Log** records the compatibility status.

**Reading the Compatibility matrix:**

Each row has an **Attribute**, a **Device** value, a **Firmware** value, and a **State**.

| State | Meaning |
|-------|---------|
| **PASS** | Device and firmware agree. |
| **WARNING** | Device and firmware differ in a non-critical field (e.g. brand), or the value is only *likely*. Elevated confirmation will be required. |
| **UNKNOWN** | One side does not declare the value. The app will treat this cautiously. |
| **FAIL** | A critical field (codename or product) differs. The planner will **block** the plan. |
| **BLOCKED** | The compatibility engine or the device state is ineligible (e.g. locked bootloader). The planner will **block** the plan. |

**Overall Status:**

| Status | What it means | What to do |
|--------|--------------|-----------|
| `CONFIRMED` | All critical fields matched. | Proceed to Step 7. |
| `LIKELY` | Critical fields matched, but some were silent. | Proceed. Confirmation will be elevated. |
| `UNKNOWN` | Insufficient metadata. | Only proceed if you are certain the firmware is correct for this device. The plan will be blocked unless `allow_unknown_compatibility: true` is set. |
| `MISMATCH` | Critical fields disagree. | **Stop.** You have the wrong firmware. |
| `BLOCKED` | Device or firmware is ineligible. | Read the reasons. Fix the cause (unlock bootloader, correct firmware). |

**Reading the Partitions tab:**

- `Device partitions` — count of partitions the device reports (fastboot getvar all).
- `Firmware partitions` — count of partitions the firmware targets.
- `Matched`, `Extra in firmware`, `Missing from firmware` — comparison counts.
- The table lists each partition with its kind, size, slot-awareness, and source.

**What to verify before moving on:** overall Status must be `CONFIRMED` or `LIKELY` unless you have a specific reason to override.

### Step 7 — Click **Generate Flash Plan**

The app:

1. Builds a `FlashPlan` from device + firmware + compatibility + partition analysis.
2. Runs preflight against the plan.
3. Runs risk assessment against the plan.
4. Populates the **Flash Plan** tab.
5. Populates the **Commands** tab.

**Reading the Flash Plan tab:**

- **Plan Summary**: Plan ID, Status, Target, Firmware, Slot strategy, Risk, Confirmation.
- **Steps table**: each row is `# / Kind / Description / Command`.
- **Blockers & Warnings**: any reason the plan cannot run, plus cautions.

**Plan Status:**

| Status | What it means |
|--------|--------------|
| `READY` | Plan is complete and can be executed without further confirmation. |
| `REQUIRES_CONFIRMATION` | Plan is complete but needs user confirmation before execution (standard or elevated). |
| `BLOCKED` | Plan cannot be executed. Read the blockers. |

**Risk levels:**

| Level | What it means |
|-------|--------------|
| `LOW` | Read-only or fully reversible (reboot, slot read). |
| `MEDIUM` | Writes to a partition that does not affect device usability (`boot`, `init_boot`, `vendor_boot`, `dtbo`, `recovery`). |
| `HIGH` | Writes to `bootloader`, `radio`, `modem`, `vbmeta`, `super`, or any logical partition; changes the active slot. |
| `CRITICAL` | Disables AVB, erases or formats a partition, wipes userdata. Blocked unless `block_critical: false` **and** the user confirms. |

**Reading the Commands tab:**

Every step is listed as `# / Transport / Description / Argv`. The Argv column shows the **exact argv** that will be passed to fastboot. **There is no shell.** No command is ever passed through `cmd.exe`, `bash`, or `sh`.

### Step 8 — (Optional) Review and adjust

Before executing, ask yourself:

1. **Do the blockers make sense?** If the plan is blocked because the bootloader is locked, the correct action is to unlock the bootloader (a manual device-specific process, not part of this tool).
2. **Does the risk level match my intent?** If risk is `CRITICAL` and you did not intend an AVB disable or a wipe, the plan is wrong. Do not force it.
3. **Do the commands look right?** Compare the argv list against the firmware's own instructions or the vendor documentation. If `fastboot flash boot boot.img` is not what you expected, stop.

If you need to adjust **plan-affecting settings** (slot strategy, AVB disable, extraction), those come from `config.yaml` and from the firmware metadata. They are not editable from the GUI — this is deliberate. The GUI cannot invent an unsafe operation.

### Step 9 — Click **Execute Plan…**

**In Read Only mode:** the app refuses immediately and shows a warning dialog. Nothing is executed. If you want to actually flash, proceed to Section 5 to arm the app.

**In Armed mode:**

1. The app runs `ConfirmationBuilder.build()` and shows either:
   - **Standard confirmation** — an OK/Cancel dialog.
   - **Elevated confirmation** — an OK/Cancel dialog that also prints the typed acknowledgement phrase (`FLASH`) and notes that the operation is high-risk.
   - **Blocked** — a warning dialog explaining why the operation is refused.
2. If you confirm:
   - The **Flash Plan** panel disables Execute and enables Cancel.
   - The **Progress** card switches to step mode; the progress bar advances one step at a time.
   - Each step's output is streamed to the **Log** tab and prefixed with `[step N]`.
   - The **Status bar** shows the current step.
3. When execution completes:
   - The **Progress** card shows `Done`.
   - The **Log** shows the final verification status.
   - A `result.json` is written to the session directory.

**If execution fails:** a dialog explains which step failed. Read the Log. Do not immediately retry — the device may be in an intermediate state.

### Step 10 — Review the session

Every run creates a session directory:

```bash
ls -t logs/sessions/ | head -1
```

Inside:

| File | Contents |
|------|----------|
| `session.json` | All recorded events for this run. |
| `session.jsonl` | Append-only event stream. |
| `commands.log` | Every command that was issued. |
| `device.json` | The detected device identity. |
| `firmware.json` | The analyzed firmware metadata. |
| `result.json` | The final verification report. |
| `android_flasher.log` | Application log for this run. |

Keep this directory for auditing or troubleshooting.

---

## 4. What to choose depending on what you have

### 4.1 You want to flash a single boot image

- Firmware: `boot.img`
- Expect: `Type = raw_image`, `Target = your codename`.
- Plan: one `flash boot` step.
- Risk: MEDIUM.
- Confirmation: STANDARD.

### 4.2 You want to flash a full factory image

- Firmware: `factory.zip`
- Expect: `Type = factory_zip`, `Target = your codename`.
- Plan: one `fastboot update factory.zip` step (or a blocked plan if extraction is required but disabled).
- Risk: HIGH.
- Confirmation: ELEVATED (typed phrase).

### 4.3 You want to flash an OTA ZIP

- Firmware: `ota.zip`
- Expect: `Type = ota_zip`, `Target = your codename`.
- Plan: one `fastboot update ota.zip` step.
- Risk: HIGH.
- Confirmation: ELEVATED.

### 4.4 You want to flash a super image

- Firmware: `super.img`
- Expect: `Type = raw_image`, `detected_format = super`.
- Plan: one `flash super` step.
- Risk: HIGH.
- Confirmation: ELEVATED.

### 4.5 You want to flash a dynamic partition (system, vendor, product)

- Firmware: `system.img` or similar.
- Expect: `Type = raw_image`, `detected_format = ext4` or `erofs`.
- Plan: a `reboot fastboot` preparation step, then `flash system`.
- **Requires fastbootd.** The app inserts the reboot step automatically. Your device must support `fastboot reboot fastboot`.
- Risk: HIGH.
- Confirmation: ELEVATED.

### 4.6 You want to disable AVB (verity / verification)

- Firmware: `vbmeta.img`.
- Plan: a `flash vbmeta --disable-verity --disable-verification` step.
- **Blocked by default.** You must set `flash.allow_avb_disable: true` in `config.yaml`.
- Risk: CRITICAL.
- Confirmation: BLOCKED unless `safety.block_critical: false`.

### 4.7 You have a locked bootloader

Stop. The app blocks all write plans. Unlocking the bootloader is a device-specific manual process and is outside the scope of this tool. Once unlocked, refresh detection and re-run.

### 4.8 You have a device in fastbootd already

Detection returns `FASTBOOTD_DEVICE`. Logical-partition plans will work without the extra reboot step. Physical-partition plans still work.

---

## 5. Arming the app for real flashing

Only do this when you are certain you intend to flash.

Edit `config.yaml`:

```yaml
safety:
  phase1_read_only: false     # disable the master read-only switch
  allow_flash: true           # enable the flash operation
  allow_erase: false          # keep destructive extras off
  allow_format: false
  allow_set_active: false
  allow_ab_slot_change: false
  allow_avb_disable: false
  block_critical: true        # still block AVB disable / wipe by default
```

Restart the app. The phase pill turns green and reads **Armed**.

**Even in Armed mode**, every destructive step still passes through:

1. Preflight (device present, serial match, bootloader unlocked, partition exists).
2. Risk assessment (raises to CRITICAL for AVB disable, erase, format, wipe).
3. Confirmation (elevated risk requires the typed phrase `FLASH`).

The GUI cannot bypass any of those checks.

---

## 6. Troubleshooting

### 6.1 "Detection failed"

| Cause | Fix |
|-------|-----|
| Device is not in fastboot mode | `adb reboot bootloader` from a terminal. |
| Multiple devices connected | Disconnect all but the intended device. |
| Missing fastboot driver (Windows) | Install the OEM USB driver and reconnect. |
| USB hub | Use a direct port. |
| Cable | Try a different cable. |

### 6.2 "Compatibility is UNKNOWN"

The firmware does not declare a codename or product. Common for generic raw images. Options:

- Confirm manually that the firmware is for this device, then set `safety.allow_unknown_compatibility: true` in `config.yaml`. The plan will require elevated confirmation.
- Use the full factory image instead of a single image.

### 6.3 "Compatibility mismatch"

The firmware's codename or product differs from the device's. **Stop.** You have the wrong firmware. Verify the file name, the download source, and the device model.

### 6.4 "Bootloader is locked"

The device's bootloader must be unlocked. Unlocking is a device-specific manual process outside the scope of this tool.

### 6.5 "Plan is blocked"

Read the Blockers panel on the Flash Plan tab. Every blocker names the exact cause.

### 6.6 "fastboot disappeared"

The device disconnected mid-execution. Reconnect and run Refresh Devices. Do not retry the flash until the device is visible again.

### 6.7 "Verification failed"

One or more steps failed, timed out, or were cancelled. Read the Log. The device may be in an intermediate state. Do not retry without diagnosis.

---

## 7. Quick reference

| Situation | Firmware | Compatibility expected | Plan status |
|-----------|----------|-----------------------|-------------|
| Flash `boot.img` on matching device | raw `.img` | CONFIRMED | READY/REQUIRES_CONFIRMATION, risk MEDIUM |
| Flash `vbmeta.img` with AVB disable | raw `.img` | CONFIRMED | BLOCKED (unless armed + block_critical false) |
| Flash factory zip | `factory.zip` | CONFIRMED | REQUIRES_CONFIRMATION, risk HIGH |
| Flash OTA zip | `ota.zip` | CONFIRMED | REQUIRES_CONFIRMATION, risk HIGH |
| Flash `super.img` | raw `.img` | CONFIRMED | REQUIRES_CONFIRMATION, risk HIGH |
| Flash logical partition | `system.img` | CONFIRMED | REQUIRES_CONFIRMATION, adds `reboot fastboot` step |
| Flash wrong device's firmware | any | MISMATCH | BLOCKED |
| Flash on locked bootloader | any | BLOCKED | BLOCKED |
| Flash generic raw image | raw `.img` | UNKNOWN | BLOCKED unless `allow_unknown_compatibility: true` |
| Wipe userdata | `userdata.img` | CONFIRMED | BLOCKED unless `safety.allow_wipe: true` + `block_critical: false` |

---

## 8. Safety principles (why the app is designed this way)

1. **Read-only by default.** The app cannot flash anything until you edit `config.yaml`. This is deliberate: a mis-click cannot destroy a device.
2. **No shell execution.** Every fastboot command is passed as an argv list with `shell=False`. There is no string interpolation, no injection risk.
3. **No GUI-constructed commands.** The GUI only calls the engine. The engine constructs commands. This means a bug in a panel cannot produce a rogue command.
4. **Five-level compatibility.** Compatibility is never a boolean. UNKNOWN is never displayed as PASS.
5. **Confirmation cannot be bypassed.** Even in Armed mode, destructive steps require the confirmation dialog. Elevated risk requires typing `FLASH`.
6. **Risk is computed, not configured.** AVB disable, erase, format, and wipe are always CRITICAL regardless of settings.
7. **Session recording.** Every action is timestamped and written to a session directory. If something goes wrong, you have a full audit trail.

---

## 9. The one-minute summary

1. `python app.py`.
2. Boot device into fastboot, connect USB.
3. Click **Refresh Devices** → verify device is detected.
4. Click **Select Firmware…** → pick the file.
5. Click **Analyze Firmware** → verify Type and Target.
6. Click **Run Compatibility** → verify CONFIRMED or LIKELY.
7. Click **Generate Flash Plan** → read the plan and the blockers.
8. If plan is READY or REQUIRES_CONFIRMATION, click **Execute Plan…**.
9. Confirm the dialog (type `FLASH` if required).
10. Read the session artifacts under `logs/sessions/`.

If any step says **BLOCKED**, stop and read the reason. The tool is telling you not to proceed.












































# Prerequisites on the Target Device + How to Boot into Fastboot

This is the complete, procedural guide. Read sections 1–4 **before** launching Android Flasher. Section 5 explains how to enter fastboot on every major device class. Sections 6–9 cover verification, exit, and what to do if it goes wrong.

---

## 1. The five absolute prerequisites

Before you open Android Flasher, the target device must satisfy all five of these. If any one is missing, the app will either fail detection or block the plan.

| # | Prerequisite | Why it matters | How to confirm |
|---|-------------|----------------|----------------|
| 1 | **USB debugging enabled** (if device is booted) | Needed to send `adb reboot bootloader` from the PC. Not needed if you can enter fastboot by holding hardware keys. | Settings → Developer options → USB debugging = ON |
| 2 | **OEM unlocking enabled** | The toggle that permits the bootloader to be unlocked at all. Without it, `fastboot flashing unlock` is refused. | Settings → Developer options → OEM unlocking = ON |
| 3 | **Bootloader unlocked** | The app blocks every write plan on a locked bootloader. Read-only detection works either way. | Device shows "unlocked" in fastboot, or `fastboot getvar unlocked` returns `yes` |
| 4 | **A USB data cable and a working driver** | Charge-only cables and missing drivers cause "no device detected". | `fastboot devices` in a terminal lists the serial |
| 5 | **Sufficient battery** | Some devices refuse flashing below ~30 % battery. | Settings → Battery, or check the bootloader screen |

Additional, non-blocking but recommended:

- A backup of anything important on the device (internal storage, SMS, app data). Flashing some firmware images can wipe userdata.
- Stable power to the PC (a laptop on battery is risky).
- No other Android devices connected to the same PC.
- A known-good USB **data** cable (many cables bundled with chargers are power-only).
- Direct USB port on the PC — **avoid USB hubs**.

---

## 2. Enable Developer Options (if not already enabled)

Developer options is a hidden settings menu. To reveal it:

1. Open **Settings**.
2. Scroll to **About phone** (on Samsung: **About device**; on Xiaomi: **About phone → All specs**).
3. Find **Build number**.
4. Tap **Build number** seven times.
5. A message appears: *"You are now a developer."*
6. Go back to the main Settings screen. A new entry called **Developer options** is now visible.

Some OEMs place it under `Settings → System → Developer options` after revealing it.

---

## 3. Enable USB debugging and OEM unlocking

Inside **Developer options**:

1. Find **USB debugging**. Turn it **ON**. Confirm the prompt.
2. Find **OEM unlocking**. Turn it **ON**. Confirm the prompt.

**If OEM unlocking is greyed out:**

- The device may be SIM-locked or carrier-locked. Contact the carrier.
- The device may have a pending Google account lock (FRP). Sign in to the same account that was previously used and let it sync.
- Some regions (notably certain Chinese-market and carrier-branded models) ship with the toggle permanently disabled. There is no software workaround.

**If OEM unlocking is OFF:**

Do not proceed. The bootloader cannot be unlocked without it, and the app will block every destructive plan.

---

## 4. Unlock the bootloader (once per device)

Unlocking the bootloader is a **device-specific manual process**. Android Flasher does not perform it. This is deliberate: unlocking wipes the device, and doing so silently would be dangerous.

The generic procedure:

1. With USB debugging and OEM unlocking both enabled, connect the device to the PC.
2. Open a terminal on the PC and run:
   ```
   adb reboot bootloader
   ```
   The device reboots into the bootloader. You will see a screen with a large Android robot and text such as `FASTBOOT MODE`.
3. Run:
   ```
   fastboot flashing unlock
   ```
   On very old devices the command is `fastboot oem unlock`.
4. **On the device screen**, a confirmation prompt appears. Press the volume keys to navigate to **Unlock the bootloader** and press the power key to confirm.
5. The device **wipes all data** and reboots. This is expected and unavoidable.
6. After the reboot, complete the initial setup wizard.
7. Re-enable **USB debugging** in Developer options.

Some devices require extra steps or a unique unlock code from the manufacturer. Check the manufacturer's own documentation for your model.

After unlocking:

- The device shows an "unlocked bootloader" warning at every boot. This is normal.
- Some banking apps, Google Wallet, and Play Integrity checks will fail. This is expected on an unlocked bootloader.
- `fastboot getvar unlocked` returns `yes`.

**Samsung devices** use **Download Mode** and **Odin**, not fastboot. See section 5.7. Samsung devices cannot use Android Flasher's fastboot workflow.

---

## 5. How to enter fastboot on each device class

There are **two** ways to enter fastboot:

- **Software** — from a booted device using `adb`. Requires USB debugging.
- **Hardware** — using physical buttons while the device is off. Works even if the OS does not boot.

Use software when possible. Use hardware when the device will not boot into Android, or when `adb` is unavailable.

### 5.1 Generic Android (most Pixel, Motorola, OnePlus, Nothing, Fairphone)

**Software:**

```
adb reboot bootloader
```

**Hardware (device off):**

1. Power the device off completely.
2. Press and hold **Volume Down**.
3. While holding Volume Down, press and hold **Power**.
4. Release both when the bootloader screen appears (a large Android robot, plus text such as `FASTBOOT MODE`).
5. If the device boots into Android instead, power off and try again — you may have released the keys too early.

### 5.2 Google Pixel (all generations)

Same as 5.1. The Pixel bootloader screen reads:

```
FASTBOOT MODE
PRODUCT_NAME - <codename>
...
DEVICE STATE - unlocked
```

Older Pixels may need **Power + Volume Down** for a few seconds, then release Power only.

### 5.3 Xiaomi / Redmi / POCO

**Software:** `adb reboot bootloader`.

**Hardware:** **Volume Down + Power**, release when the Mi Bunny / fastboot screen appears.

Xiaomi bootloaders must be unlocked through Xiaomi's official Mi Unlock tool (requires a Mi account and a 7–30 day waiting period on recent models). The OEM unlocking toggle is separate and not sufficient on its own.

### 5.4 OnePlus

**Software:** `adb reboot bootloader`.

**Hardware:** **Volume Up + Volume Down + Power** together until the bootloader appears.

### 5.5 Motorola

**Software:** `adb reboot bootloader`.

**Hardware:** **Volume Down + Power**.

Motorola bootloaders require an unlock code from Motorola's website, tied to the device's unique ID.

### 5.6 Nothing Phone, Fairphone, Sony, Asus

- **Nothing**: **Volume Down + Power**.
- **Fairphone**: **Volume Down + Power**.
- **Sony**: `adb reboot bootloader` (Sony uses fastboot on most Xperia models).
- **Asus**: **Volume Up + Power** (varies by model).

### 5.7 Samsung — Download Mode (not fastboot)

Samsung does **not** use fastboot. It uses **Download Mode** and Odin/Heimdall. Android Flasher does not support Samsung flashing. If you have a Samsung device, use Odin with the appropriate firmware, and treat this tool as not applicable.

To enter Download Mode anyway (for reference):

1. Power off the device.
2. Hold **Volume Down + Volume Up** (or **Volume Down + Bixby** on older models).
3. Connect the USB cable to the PC.
4. Press **Volume Up** to confirm.

### 5.8 Huawei / Honor

Huawei and Honor stopped issuing bootloader unlock codes in 2018. Modern Huawei devices cannot be unlocked and therefore cannot be flashed by this tool.

### 5.9 Devices that will not boot at all

If the device is stuck on a bootloop, black screen, or a corrupted Android partition, hardware-key entry is the only option. Try:

1. Hold **Volume Down + Power** for 15 seconds (generic).
2. If that fails, try **Volume Up + Power**, then **Volume Up + Volume Down + Power**.
3. Connect USB while holding the keys.

If none of these produce a fastboot screen, the device may be in **EDL mode** (Qualcomm) or **BROM mode** (MediaTek), which require specialised tools outside the scope of Android Flasher.

---

## 6. Confirm the device is in the correct mode

Once you see the fastboot screen, open a terminal on the PC and run:

```
fastboot devices
```

Expected output:

```
SER12345678    fastboot
```

The serial is the unique device identifier. Note it down — the app will show it in the Device panel and you should verify it matches.

If `fastboot devices` prints **nothing**, the device is not visible to fastboot. Do **not** proceed. See section 8.

Additional confirmation commands (optional but useful):

```
fastboot getvar product
```
Returns the device codename (e.g. `panther`, `cheetah`).

```
fastboot getvar current-slot
```
Returns `a` or `b` on A/B devices, or nothing on non-A/B devices.

```
fastboot getvar unlocked
```
Returns `yes` or `no`.

```
fastboot getvar all
```
Dumps every fastboot variable the bootloader exposes. Useful for diagnostics.

---

## 7. Launch Android Flasher

With the device confirmed visible to fastboot and all prerequisites met:

```bash
cd ~/android-flasher
source .venv/Scripts/activate
python app.py
```

Then:

1. Click **Refresh Devices**. The Device panel should populate with the serial, codename, product, bootloader state, and slot.
2. Continue with the workflow (select firmware → analyze → compatibility → plan → execute). The full workflow is documented in the previous user guide.

---

## 8. Troubleshooting detection

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `fastboot devices` prints nothing, device is on and in fastboot | Missing driver (Windows) | Install the OEM USB driver. For Pixel: Google USB Driver. For Xiaomi: Mi USB Driver. Then reconnect. |
| Same as above | Charge-only USB cable | Try a different cable — a known-good data cable. |
| Same as above | USB hub | Plug directly into a port on the PC. |
| Same as above | Device screen says `FASTBOOTD` instead of `FASTBOOT MODE` | You are in userspace fastboot, not bootloader fastboot. Either works, but the app distinguishes them. |
| `adb devices` shows `unauthorized` | USB debugging prompt was not accepted | Unlock the device, accept the prompt, re-run. |
| `adb devices` shows `offline` | Stale adb server | `adb kill-server` then `adb start-server`. |
| Multiple devices listed | More than one Android device connected | Disconnect all but the target device. |
| `fastboot devices` shows the device, but the app says "no device" | Stale tool discovery | Close and restart the app, or click **Refresh Devices** again. |
| `error: cannot open device` | Driver is bound to another service (e.g. Windows still sees it as an MTP camera) | Disconnect, wait 5 seconds, reconnect. |

---

## 9. What NOT to do

- **Do not disconnect USB** during a flash. This is the single biggest cause of bricked devices.
- **Do not let the PC sleep** during a flash. Disable sleep/hibernate for the session.
- **Do not press the power button** on the device during a flash. Some devices will abort mid-write.
- **Do not flash firmware for a different codename.** The app will block this via the compatibility engine, but do not override it.
- **Do not use a hub, a USB 2.0 extension, or a wireless/USB-over-IP connection.**
- **Do not run the app as administrator/root.** There is no reason to, and it obscures permission errors.
- **Do not flash on a device with less than 30 % battery.**
- **Do not attempt to flash a Samsung device via fastboot.** Samsung does not support it.

---

## 10. Quick checklist before clicking Execute

Print this and tick it off:

- [ ] Device is in fastboot mode (`FASTBOOT MODE` on screen).
- [ ] `fastboot devices` in a terminal shows the correct serial.
- [ ] The app's Device panel shows the same serial.
- [ ] `Bootloader` in the Device panel reads `unlocked`.
- [ ] Firmware file was downloaded from a trusted source.
- [ ] Firmware `Target` in the Firmware panel matches the device codename.
- [ ] Compatibility status is `CONFIRMED` or `LIKELY` (not `UNKNOWN`, `MISMATCH`, or `BLOCKED`).
- [ ] Flash plan shows no blockers.
- [ ] Risk level is understood and acceptable.
- [ ] Backup of important data has been taken (if userdata could be touched).
- [ ] USB cable is direct, known-good, and cannot be accidentally unplugged.
- [ ] PC will not sleep during the operation.
- [ ] Battery on the device is above 30 %.
- [ ] You are prepared to type `FLASH` if the confirmation prompt requires it.

Once every box is ticked, click **Execute Plan…** in the Flash Plan tab, read the confirmation dialog, and confirm.

---

## 11. Summary — the shortest possible path

1. On the device: enable Developer Options → USB debugging → OEM unlocking.
2. Unlock the bootloader once (device-specific; wipes data).
3. Connect USB with a good data cable.
4. `adb reboot bootloader` (or use hardware keys).
5. `fastboot devices` — confirm the serial is visible.
6. Launch Android Flasher.
7. Click **Refresh Devices**.
8. Follow the workflow: Select Firmware → Analyze → Compatibility → Generate Plan → Execute.

If any step does not behave as described, stop and consult section 8. The device is in a state where the app will tell you exactly what is wrong — read the Log tab and the Blockers panel.