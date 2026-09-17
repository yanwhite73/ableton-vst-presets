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
- **Appearing in the browser is not success.** Only loading a produced Rack in Live and
  hearing the right sound qualifies a given plug-in/format. The single-preset tools
  (`synthesize`, `convert`) label their output `[capture test]` until you pass `--qualified`;
  the batch tools (`build_all`, `build_library`) write final names — so **load-test a sample
  of a plug-in/format before trusting a whole library built from it.**

Nothing is ever overwritten; no plug-in is loaded; no DAW state or database is written.

## Getting started

**Before you start.** You need Ableton Live with the plug-ins you want to convert, plus
Python 3.9+ and `git`. There are no other dependencies — the kit is pure standard library, so
there is no `pip install` step.

- **macOS already has Python 3.** If your first `python3` command offers to install Apple's
  Command Line Tools, accept it — that's the only one-time setup. Use `python3` in the commands
  below.
- **Windows doesn't ship Python** — install it once from
  [python.org](https://www.python.org/downloads/) and tick *"Add Python to PATH"*. Then use
  `python` wherever the commands below say `python3`.

**Get the kit:**

```sh
git clone https://github.com/yanwhite73/ableton-vst-presets.git
cd ableton-vst-presets
```

**Where the kit looks.** It auto-detects all of these, so you rarely type a path — the table
is for understanding, and for overriding when your setup is non-standard.

| What it needs | macOS | Windows |
|---|---|---|
| Live's plug-in list (identities) | `~/Library/Application Support/Ableton/Live Database/Live-plugins*.db` | `%APPDATA%\Ableton\Live Database\Live-plugins*.db` |
| Install target (User Library) | `~/Music/Ableton/User Library/Presets/Instruments` | `~\Documents\Ableton\User Library\Presets\Instruments` |
| Arturia categories DB | `/Library/Arturia/Presets/db.db3` | `C:\ProgramData\Arturia\Presets\db.db3` |
| u-he presets | `/Library/Audio/Presets/u-he/<product>/` | `~\Documents\u-he\<product>\` |
| Vital presets | `~/Music/Vital/` | `~\Documents\Vital\` |
| Surge presets | `~/Documents/Surge XT/Patches/` | `~\Documents\Surge XT\Patches\` |

Moved your presets, or a vendor isn't listed? Override with `--root <folder>`,
`--arturia-db <path>`, `--live-db <path>`, `--destination <path>`. Anything not found is
skipped with a message — it never crashes.

**Run it — one command:**

```sh
# 1. Build into a folder you choose. Nothing is installed yet; review it first.
python3 bin/build_all.py --staging ./racks

# 2. Happy with ./racks? Build + install into Live's User Library (non-destructive):
python3 bin/build_all.py --staging ./racks-install --install
```

Output is laid out `vendor/instrument/category/preset.adg` (add `--no-vendor-folders` for a
flat `instrument/category/`). Narrow it with `--only "CS-80 V3,Vital"`. See
[docs/COVERAGE.md](docs/COVERAGE.md) for which plug-ins work.

**See it in Live.** The Racks land in your User Library, but **Live won't show them until it
re-indexes** — restart Live (or wait for its next scan). Then browse
`User Library → Presets → Instruments → <vendor> → <instrument>`.

### Gotchas

- **Version match.** The native preset must be from the *installed* version of the plug-in. An
  old preset can load as a blank "init" patch — export presets from your current version.
- **macOS privacy prompts.** Reading `~/Music` or `~/Documents` (Vital, Surge) may pop a
  permission prompt, or need your terminal added to System Settings → Privacy & Security →
  Full Disk Access.
- **Load-test before trusting a whole library.** Build one preset, load it in Live, confirm the
  sound — *then* batch the rest. A file that builds cleanly isn't proof the sound is right.
- **Non-destructive.** It never overwrites, and `install` refuses to merge into a folder that
  already exists — so to rebuild an instrument, install to a fresh spot or move the old one aside.

### When to bring in an AI coding agent

Some things depend on *your* machine and can't be baked into defaults. Hand
[AGENTS.md](AGENTS.md) to a coding agent (Claude Code, Cursor, …) and ask it to:

- **Find your presets** — *"Find where my &lt;vendor&gt; presets live on this machine and build them."*
- **Add a plug-in** — *"Add support for &lt;plug-in&gt;: check whether its preset file is its state, write a state source, and load-test one."*
- **Bring it up on Windows** — *"Run the Windows bring-up checklist in AGENTS.md and report back."*

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
