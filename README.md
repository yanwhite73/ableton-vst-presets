# rack-preset-kit

Turn a plug-in's saved presets into browsable **Ableton Instrument Racks** (`.adg`) — so
they show up in Live's browser as named presets — without loading the plug-in, driving
Live, or using any third-party software. Pure Python standard library; the same code runs
on macOS and Windows.

It grew out of a one-off Pigments exporter and was generalised into a device-agnostic
kit. The core discovery: for many plug-ins you don't need to hand-save a template per
instrument — the kit can **synthesize** a Rack offline from the plug-in's identity (read
from Live's own plug-in cache) plus a native preset file.

## What it can and can't do — read this first

- It works by treating the plug-in's serialized state as **opaque bytes** and placing them
  into a genuine Rack structure. It does not parse, migrate, or rebuild plug-in state.
- **Synthesis works when a plug-in's native preset file *is* its own state chunk**, and the
  preset **version-matches the installed plug-in**. Proven for Arturia VST2, u-he VST3, and
  Vital VST3 (see [docs/SYNTHESIS.md](docs/SYNTHESIS.md)).
- Where the native file is *not* the state (e.g. it needs a wrapper), you extract one real
  saved Rack to learn the transform — the per-vendor "state source" work in
  [docs/ADD_A_PLUGIN.md](docs/ADD_A_PLUGIN.md).
- It cannot help plug-ins that keep presets **inside the plug-in** or in a **database**
  rather than as files (e.g. KORG opsix/wavestate, Valhalla's built-in presets, Kick 2,
  Microtonic).
- It builds **Instrument Racks only** — effects aren't supported yet (they'd need an Audio
  Effect Rack path). Full coverage — what works and what's skipped, with reasons — is in
  [docs/COVERAGE.md](docs/COVERAGE.md).
- **Appearing in the browser is not success.** Only loading the produced Rack in Live and
  hearing the right sound qualifies a given plug-in/format. Every output is labelled
  `[capture test]` until you confirm it.

Nothing is ever overwritten; no plug-in is loaded; no DAW state or database is written.

## Requirements

Python 3.9+. **No third-party packages.** Ableton Live (for its plug-in cache and to load
the results). macOS is verified; Windows is written to be portable but not yet tested there
— see the bring-up checklist in [AGENTS.md](AGENTS.md).

## Quickstart — one command

```sh
# Build categorised Racks for every instrument the kit can handle, into a staging folder.
python3 bin/build_all.py --staging ./out/racks
# Review ./out/racks (layout: vendor/instrument/category/preset.adg), then install:
python3 bin/build_all.py --staging ./out/racks2 --install
```

`build_all` scans Live's plug-in cache and picks a provider per instrument automatically —
Arturia from its database (real categories), u-he / Vital / Surge and other folder-organised
vendors from their preset folders. Output is nested by vendor
(`<vendor>/<instrument>/<category>/`) by default; pass `--no-vendor-folders` for a flat
`<instrument>/<category>/` layout. It auto-detects the Arturia DB and your User Library, and
anything it can't place (unknown vendor, unreadable folder) is reported and skipped, never
fatal. Limit it with `--only "CS-80 V3,Vital"`; override paths with `--arturia-db`,
`--destination`, `--live-db`. See [docs/COVERAGE.md](docs/COVERAGE.md) for what works.

## Finer control (the same steps, à la carte)

```sh
python3 bin/scan_instruments.py --out ./out                      # what's installed + identities
python3 bin/synthesize.py --native <preset> --name "CS-80 V3" \  # one Rack to load-test
    --output "CS-80 test [capture test].adg"
python3 bin/catalog_arturia.py --instrument "CS-80 V3" --out ./out/cs80.json   # Arturia: DB categories
python3 bin/find_presets.py --root <folder> --name "Vital" --out ./out/vital.json  # folders = categories
python3 bin/build_library.py --catalog ./out/cs80.json --staging ./out/cs80_stage
python3 bin/install.py --staging ./out/cs80_stage --manifest-sha256 <hash from manifest.json>
```

The state source (Arturia archive / u-he `.h2p` / Vital `.vital` / Surge `.fxp`) is
auto-detected; force it with `--source`. Skeletons default to the packaged empty-state shells
in `skeletons/`; override with your own clean Rack via `--skeleton` (see `bin/make_skeleton.py`).

**Folder permissions:** the kit reads your preset folders and Live's cache, and writes only
into new folders in your User Library. On macOS, reading `~/Music` or `~/Documents` (Vital,
Surge) may prompt for access, or need the terminal granted Full Disk Access; installing needs
write access to the User Library. Permission errors are reported per-instrument and skipped.

## Proven plug-ins

| Family | Container | Native | Status |
|---|---|---|---|
| Arturia (Pigments, CS-80, Mini, DX7, CMI, Mellotron, Modular, Wurli, …) | VST2 | `22 serialization::archive` | ✅ load-confirmed |
| u-he (Tyrell, Zebra CM, Bazille CM) | VST3 | `.h2p` | ✅ load-confirmed |
| Vital | VST3 | `.vital` (version-matched) | ✅ load-confirmed |
| Surge XT | VST3 | `.fxp` | state source included; confirm by load |

## Layout

```
rackkit/    engine, racks (VST2/VST3 builders), statesources, cache, synth, skeletons,
            providers (folder + Arturia-DB catalogues), builder, installer, locations, adapters
bin/        build_all (one-command orchestrator), scan_instruments, find_presets,
            catalog_arturia, build_library, install, synthesize, inspect_template,
            convert, make_skeleton
skeletons/  packaged empty-state Rack shells (vst2.adg, vst3.adg)
docs/       HOW_IT_WORKS, COVERAGE, SYNTHESIS, LIMITS, ADD_A_PLUGIN
tests/      offline test suite (python3 tests/test_rackkit.py)
AGENTS.md   how to extend the kit (hand this to a coding agent) + Windows bring-up
```

See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) for the mechanism and
[docs/LIMITS.md](docs/LIMITS.md) for the boundaries. MIT licensed.
