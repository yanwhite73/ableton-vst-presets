# Changelog

An honest log of how this kit evolved — including the mistakes and overclaims we corrected,
because getting to genuinely shareable content meant getting several things wrong first.
Newest first. Dates are development dates; the project is pre-1.0.

## 2026-09-19

### Added
- A deterministic public-package builder with an explicit source allowlist, embedded SHA-256
  manifest, symlink/path/credential checks, and a clean-package regression suite.
- Project-level ignore rules for local configuration, secrets, README-generated Rack trees,
  diagnostics, virtual environments, and release output.
- A read-only, dependency-free GitHub workflow that runs the package gate on pushes and pull
  requests.

### Corrected
- Release packaging no longer depends on recursively zipping a developer checkout, which could
  include machine-local files that are useful locally but unsafe to publish.

## 2026-09-17

### Added
- A proper getting-started in the README: prerequisites, a macOS/Windows paths table, the
  build → review → install flow, the "Live must re-index" step, real gotchas, and a "when to
  hand it to a coding agent" section.
- `docs/COVERAGE.md` — exactly which plug-ins work and which are skipped, with reasons.

### Corrected
- **Overclaim: "every output is labelled `[capture test]`."** Not true — only the single-preset
  tools (`synthesize`, `convert`) label output; the batch tools (`build_all`, `build_library`)
  write final names. Docs fixed so the qualification model reads honestly: load-test a sample of
  a plug-in/format, then batch the rest.
- **Install docs assumed too much.** They now say plainly that macOS already has Python and
  Windows users install it once — no implicit prerequisites left for the reader to guess.

## 2026-09-16

### Added
- One-command orchestrator `build_all`: scan Live's cache → pick a provider per instrument →
  categorise → build → optional install, with per-OS auto-discovery of the Arturia DB and the
  User Library, and graceful per-instrument skips (unknown vendor, unreadable folder).
- Category providers: Arturia from its database, folder-organised vendors from their folders.
- Optional XMP keyword sidecars. **Favourite colour is a user choice** (`--favourite-color`),
  never assumed.
- `--vendor-folders` (on by default in `build_all`): output nests `<vendor>/<instrument>/<category>/`.
- Published as a standalone public repo (kit at the repo root, no monorepo history).

### Fixed
- **Shortcircuit XT was handed Surge's patches** because they share a vendor; the Surge preset
  location now matches only Surge XT.
- Arturia's category database is opened WAL-aware (closed DB → `immutable`, active DB →
  `mode=ro`), fixing an "unable to open database file" error on a closed WAL database.
- Atomic no-overwrite publishing gained an `O_EXCL` fallback for filesystems without hard links
  (Windows/exFAT/network drives).

### Corrected
- **False alarm on preset format.** A hasty one-file-per-folder scan suggested Arturia presets
  were `<rootnode>` XML; sampling properly proved they're the `22 serialization::archive` binary
  the mechanism handles. Caught before it reached the docs — verify before asserting.

## 2026-09-15

### Added
- The engine and its safety contract: stable reads that reject a file changing mid-read, atomic
  publishing that never overwrites, and Rack builders that prove every byte **outside** the
  plug-in node is unchanged.
- State sources for Arturia (VST2 two-archive Buffer), u-he (`.h2p`), Vital (`.vital`) and
  Surge (`.fxp`).
- **Synthesis** — the core result: build a Rack entirely offline from the plug-in's identity
  (read from Live's plug-in cache) + a native preset + a packaged empty-state skeleton, with **no
  hand-saved template per plug-in**. Load-confirmed for Arturia VST2, u-he VST3 and Vital VST3.

### Learned
- **The native preset must match the installed plug-in version.** Vital first loaded a blank
  "init" patch because the preset was an old `synth_version`; a preset from the installed version
  loaded correctly. Now part of the qualification rules and the docs.
- **Appearing in the browser is not success.** Only loading a Rack and hearing the right sound
  qualifies a plug-in/format — structural validity is necessary, not sufficient. This principle
  shaped the `[capture test]` labelling and the "load-test a sample first" workflow.
