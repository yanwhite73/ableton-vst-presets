# Working on rack-preset-kit (for coding agents)

Hand this file to a coding agent to extend the kit to your plug-ins or bring it up on
Windows. It assumes the agent can read files and run Python, but **cannot load plug-ins or
drive Ableton** — a human does the load tests.

## Ground rules

- Standard library only. No third-party packages, no network, no plug-in hosting, no GUI
  automation. Keep it cross-platform (all paths are inputs; identities come from Live's
  plug-in cache DB, whose schema is the same on macOS and Windows).
- Treat plug-in state as opaque bytes. Never parse/migrate/rebuild it.
- Change only the plug-in node of a Rack; prove every other byte is identical (the
  builders in `rackkit/racks.py` already enforce this).
- Never overwrite; publish atomically (`rackkit/engine.publish_new`).
- "Appears in the browser" is not success. A human must load the result in Live and confirm
  the sound. Keep outputs named `[capture test]` until then.

## Add support for a new plug-in

Most new plug-ins need only a new **state source** in `rackkit/statesources.py`. The one
question that decides everything: **is the plug-in's native preset file the same bytes as
its own serialized state?**

1. Find where the plug-in stores presets on disk and the file format. If presets live only
   inside the plug-in or in a database (not as files), stop — this kit can't help.
2. Determine the container from Live's cache (`rackkit/cache.py`): a VST2 `UniqueId` means
   the VST2 two-archive Buffer path; a VST3 class UID means the ProcessorState path.
3. Decide whether native == state:
   - **Cheapest test:** synthesize one Rack with the native file placed directly as the
     state (as this kit does for Arturia/Vital), give it to the human to load. If the plug-in
     opens with the right sound, native == state and your source just passes the bytes
     through (VST2: return the native for the Buffer; VST3: return `(native, b"")`).
   - If it loads but resets to **init**, the native needs a wrapper. Learn it: have the human
     save ONE real Rack of the plug-in with a known preset, then diff the Rack's
     `ProcessorState`/`Buffer` against the native file. The difference is the transform your
     source must apply (e.g. u-he prepends `#pgm=<name>\n`; Surge lifts the `sub3` chunk out
     of the `.fxp` wrapper and appends the JUCE trailer).
   - Always **version-match**: use a preset saved by the *installed* plug-in version. Old
     presets are a common cause of an init load (see Vital in `docs/SYNTHESIS.md`).
4. Write the source as a small class in `statesources.py` with `name`, `container`,
   `detect(native, filename)`, and `build(...)`. Add it to `SOURCES`. Add a unit test in
   `tests/test_rackkit.py` with a synthetic fixture.
5. Have the human load a couple of results, then record the outcome in `docs/SYNTHESIS.md`.

## Windows bring-up (one-shot)

The kit is written to be portable but has only been verified on macOS. Run this once on a
Windows machine with Ableton Live installed and report the results back — no iteration
expected:

1. Locate the plug-in cache: `%APPDATA%\Ableton\Live Database\Live-plugins*.db`.
   Run `python bin\scan_instruments.py --out out` — confirm it lists instruments with
   identities. If the DB isn't auto-found, pass `--live-db` explicitly. If the schema differs
   (the `plugins` table lacks `dev_identifier`/`subcategories`), capture the actual columns.
2. Confirm atomic no-overwrite publishing works on the target drive: run
   `python tests\test_rackkit.py` (the `publish_no_overwrite` test exercises the `os.link`
   path and the `O_EXCL` fallback). On exFAT/network drives the fallback should engage.
3. Synthesize one Rack for an installed instrument and have someone load it in Live.
4. Report: did the scan list instruments? did the tests pass? did the Rack load with the
   right sound? Note any path/format differences so `cache.default_db_paths` can be adjusted.

## Where things are

`docs/HOW_IT_WORKS.md` (mechanism), `docs/SYNTHESIS.md` (what's proven + rules),
`docs/LIMITS.md` (boundaries), `docs/ADD_A_PLUGIN.md` (worked example). Run the suite with
`python3 tests/test_rackkit.py`.
