# How it works

An Ableton Instrument Rack (`.adg`) is gzipped XML. Inside a Rack that holds one plug-in,
there is a single plug-in node:

- **VST2** — a `<VstPreset>` with `<Type>` + `<UniqueId>` (identity) and a `<Buffer>` of hex
  (the plug-in's saved chunk).
- **VST3** — a `<Vst3Preset>` with a 16-byte class UID stored as four signed int32
  `<Fields>`, plus `<ProcessorState>` and optional `<ControllerState>` (hex).

The kit makes a Rack that recalls a sound by putting the right **identity** and **state**
into that node and changing nothing else.

## Two ways to get a Rack

**Template conversion** (`bin/convert.py`): you already have a genuine, clean Rack of the
plug-in you saved in Live. The kit swaps its state for a native preset's, proving the rest
of the Rack is byte-identical. Safe but needs one saved Rack per plug-in.

**Synthesis** (`bin/synthesize.py`): the kit builds the Rack from three offline
ingredients, so you need no saved template at all:

1. a **skeleton** — a clean single-instrument Rack shell (the packaged `skeletons/*.adg`
   carry no sound; the whole plug-in node gets overwritten, so any clean Rack works);
2. the plug-in's **identity** — read from Live's plug-in cache
   (`Live-plugins*.db`, `plugins.dev_identifier`): a VST2 `UniqueId` or a VST3 class UID;
3. the **state** — produced from a native preset file by a *state source*.

`rackkit/racks.py` retargets the node's identity and writes the state, then proves every
byte outside the node is unchanged and re-parses the result. `rackkit/engine.py` compresses
it and publishes atomically without overwriting anything.

## State sources

A state source (`rackkit/statesources.py`) knows one vendor's native format and returns the
bytes that belong in the node:

- **Arturia** (`arturia`, VST2): the native `22 serialization::archive` file, duplicated
  into the two-uint64-length two-archive Buffer framing.
- **u-he** (`u-he`, VST3): `#pgm=<name>\n` + the `.h2p`, placed in *both* processor and
  controller state.
- **Vital** (`vital`, VST3): the raw `.vital` JSON as processor state.
- **Surge XT** (`surge`, VST3): the `sub3` chunk lifted out of the `.fxp` wrapper, plus the
  empty JUCE trailer, as processor state.

Each treats the state as opaque. Adding a plug-in is usually just a new source — see
[ADD_A_PLUGIN.md](ADD_A_PLUGIN.md).

## Why it's portable

Everything is gzip + XML + struct + hashlib on bytes. No plug-in is instantiated, no DAW is
scripted, no OS-specific plug-in folders are walked: identities come from Live's cache,
whose schema is the same on macOS and Windows. Paths are inputs, never hardcoded.
