# Limits and qualification boundaries

This kit is deliberately narrow and honest about what it does not do.

## It cannot

- **Synthesize a sound from nothing.** It re-wraps presets that already exist on disk and
  that you already own. It does not model or generate plug-in state.
- **Serve plug-ins that don't store presets as files.** If presets live inside the plug-in
  (e.g. KORG opsix/wavestate, Valhalla's built-in factory presets) or in a database (Kick 2,
  Microtonic, Synplant's blobs), there is no file to wrap.
- **Build effect Racks.** It makes Instrument Racks only; effects would need a separate Audio
  Effect Rack path (different skeleton, effect-typed node, `Audio Effects/` destination).
  See [COVERAGE.md](COVERAGE.md).
- **Guarantee cross-machine or cross-version recall.** A Rack made here references the same
  plug-in and, for sample-based instruments, the same sample content. Absolute sample paths,
  VST2-vs-VST3 identity, and plug-in version differences can all break recall on another
  machine. The native preset must match the **installed plug-in version** (an old preset can
  load as init).
- **Prove a sound by building a file.** Structural validity ≠ audible recall.

## Qualification

- The single-preset tools (`synthesize`, `convert`) label their output `[capture test]` until
  you pass `--qualified`. The batch tools (`build_all`, `build_library`) write final names — so
  qualify a plug-in/format by load-testing a sample first, then batch-build the rest. A
  plug-in that opens with the correct sound is qualified; structural validity alone is not.
- Synthesis is proven for Arturia VST2, u-he VST3 and Vital VST3 (see
  [SYNTHESIS.md](SYNTHESIS.md)). Other plug-ins are unqualified until load-tested, even if a
  state source is provided.

## Platform and discovery across users

- macOS is verified. Windows is written to be portable (Live's plug-in DB has the same schema
  there; the only OS-specific primitive, atomic no-overwrite publishing, has an `O_EXCL`
  fallback) but is **not yet tested**. See the bring-up checklist in [../AGENTS.md](../AGENTS.md).
- Preset-folder locations differ by OS **and by user** (many plug-ins let you relocate presets).
  `locations.py` holds per-OS defaults for the supported vendors and uses whichever exists, so a
  standard install works with no config. A **moved or custom** preset folder is not auto-found —
  pass `--root` (or add a default). No default table can know where every user put their presets.

## Legal

Wrapping presets you own for your own use is a local convenience. Redistributing factory
content is a separate licensing question this kit takes no position on — it ships no presets
and no plug-in content.

## Safety properties (enforced in code)

- Inputs are read with a stability check that rejects a file changing mid-read.
- Publishing is atomic and never overwrites an existing file (hard-link, or `O_EXCL`).
- Rack builders prove every byte outside the plug-in node is unchanged and re-parse output.
- The installer refuses to merge or replace an existing folder and verifies against a
  manifest hash before and after copying.
