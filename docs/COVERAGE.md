# What this kit can convert — coverage

A plug-in can be converted only when three things line up:

1. **Its presets exist as files on disk** (not stored inside the plug-in or in a database).
2. **There is a state source for that file format** (the "is this file the plug-in's actual
   state?" transform — see [ADD_A_PLUGIN.md](ADD_A_PLUGIN.md)).
3. **Live has scanned the plug-in** (so its identity is in the plug-in cache).

If any of those is missing, the instrument is reported and **skipped, never fails the run**.

## Works today (load-confirmed)

| Vendor / family | Container | Native format | Categories from |
|---|---|---|---|
| Arturia (Pigments, CS-80, Mini, DX7, CMI, Mellotron, Modular, Wurli, …) | VST2 | `22 serialization::archive` | Arturia's `db.db3` |
| u-he (Tyrell, Zebra CM, Bazille CM) | VST3 | `.h2p` | preset folders |
| Vital | VST3 | `.vital` (version-matched) | preset folders |
| Surge XT | VST3 | `.fxp` | preset folders | *(state source included; confirm by loading one)* |

Any other vendor that keeps presets in **named folders as files** in a supported format will
also work — point `find_presets`/`build_all` at it.

## Not covered (and why)

- **Effects.** The kit builds **Instrument** Racks only. An effect (reverb, delay, …) needs an
  **Audio Effect Rack** — a different skeleton and install location. That path isn't built yet.
- **Plug-ins whose presets aren't files.** If factory presets live **inside** the plug-in
  (e.g. KORG opsix/wavestate, Valhalla's built-in presets) or in a single **database/blob**
  (some drum machines), there is nothing on disk to wrap. Capturing those would require loading
  the plug-in and reading its state, which this kit deliberately never does.
- **A known format in an unknown place.** If a plug-in stores preset files but in a folder the
  kit doesn't know, pass `--root` (or add a default in `locations.py`). See
  [the cross-OS notes in LIMITS.md](LIMITS.md).
- **A new file format.** Even with the files found, a vendor whose native file is *not* the
  plug-in's own state needs a new **state source** (a few lines — see
  [ADD_A_PLUGIN.md](ADD_A_PLUGIN.md)) plus one load test to confirm.
- **VST3-only Arturia installs.** The Arturia path uses the VST2 identity; an Arturia plug-in
  installed as VST3 only (no VST2 in the cache) is skipped until a VST3 Arturia state source
  exists.

## Extending coverage

Point the tools at your presets with `--root`; if the format is new, add a state source. The
step-by-step is in [ADD_A_PLUGIN.md](ADD_A_PLUGIN.md), and [../AGENTS.md](../AGENTS.md) is
written to hand to a coding agent to do it on your machine.
