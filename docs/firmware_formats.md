# Firmware Formats

Android firmware arrives in several distinct container formats. Android
Flasher detects the format from the file's internal structure, not its
extension.

## Recognized formats

| Format        | Detection signal                          | Handling                       |
| ------------- | ----------------------------------------- | ------------------------------ |
| Raw `.img`    | Header magic (e.g. `ANDROID!`, `AVB0`)    | `fastboot flash`               |
| Sparse image  | `3A FF 26 ED` magic                        | `fastboot flash` (sparse)      |
| ZIP archive   | `PK\x03\x04` or `PK\x05\x06`              | Package analysis               |
| Factory ZIP   | Contains `flash-all.sh` / bootloader imgs | `fastboot update` or extraction |
| OTA ZIP       | Contains `payload.bin` or OTA metadata    | `fastboot update`              |
| `payload.bin` | Payload container                          | Not directly flashable         |
| `super.img`   | Super partition image                      | `fastboot flash super`         |

## Why extension is not trusted

A file named `boot.img` may be:
- a valid Android boot image
- an AVB vbmeta image
- a sparse image
- a corrupt or truncated file

The detector reads the first bytes and inspects archive members before
classifying a file.

## Integrity

When hashing is enabled, the analyzer computes SHA-256 (and optionally
SHA-512) of the selected firmware. The hash is displayed in the
Firmware panel and recorded in `firmware.json` for the session.

A firmware image can be the correct model but still be corrupted or
incomplete. Integrity hashing is the mechanism for detecting that.

## Payload-only firmware

A bare `payload.bin` is not directly flashable over fastboot. The
application refuses to invent a workflow for it. Present the full OTA
ZIP instead.

## Factory ZIP extraction

Factory ZIP extraction-based flashing is a Phase 3.5 capability and is
**not** implemented. When `allow_extraction_for_factory_zip` is
`false` (the default), factory ZIPs are applied via `fastboot update`
when `allow_fastboot_update` is enabled.

When extraction is requested, the planner produces a plan that
includes an explicit blocker, so the application never silently
half-applies a package.
