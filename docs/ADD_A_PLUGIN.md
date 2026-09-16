# Adding a plug-in: a worked example

Goal: make the kit convert a new plug-in's presets. In most cases this is one small **state
source** in `rackkit/statesources.py`. Follow the decision tree in
[../AGENTS.md](../AGENTS.md); this is a concrete walk-through.

## Example: u-he (Tyrell / Zebra / Bazille)

**1. Where are the presets, and what format?**
u-he stores presets as `.h2p` text files (e.g. `/Library/Audio/Presets/u-he/ZebraCM/...`).
Files on disk — good.

**2. Which container?**
Live's cache lists a VST3 class UID for these (`device:vst3:instr:d39d5b69-...`). So this is
the VST3 ProcessorState path.

**3. Is the native file the state, or does it need a wrapper?**
Placing a raw `.h2p` as the state loads the plug-in but not the patch. Diffing a real saved
Rack against the `.h2p` shows the Rack's state is the `.h2p` prefixed with `#pgm=<name>\n`,
and u-he puts the same bytes in *both* processor and controller state. That's the transform.

**4. Write the source** (already in `statesources.py`):

```python
class UheH2P:
    name = "u-he"
    container = "vst3"

    def detect(self, native, filename):
        return filename.lower().endswith(".h2p") and b"#AM=" in native[:512]

    def build(self, native, filename):
        state = b"#pgm=" + PurePath(filename).stem.encode("utf-8") + b"\n" + native
        return state, state   # processor, controller
```

Register it in `SOURCES`.

**5. Add a unit test** in `tests/test_rackkit.py` with a synthetic `.h2p` fixture (detect
true, `build` prefixes `#pgm=`, processor == controller).

**6. Try it and load-test:**

```sh
python3 bin/synthesize.py \
    --native "/Library/Audio/Presets/u-he/ZebraCM/Hurrying Home.h2p" \
    --name "ZebraCM" \
    --output "Zebra Hurrying Home [capture test].adg"
```

Drag it into Live. If Zebra opens with the right sound, record it in `docs/SYNTHESIS.md` and
you're done. Then batch a folder with `find_presets.py` + `build_library.py`.

## When native ≠ state and there's no simple wrapper

Some plug-ins transform their presets on save in a way you can't reproduce from the file
alone. Then the honest path is **extraction**: the human saves a real Rack per preset (or you
extract the plug-in node from Racks/Sets they already have) and you swap only the state you
read from a genuine node. That is the `bin/convert.py` template path — reliable, but it needs
a real saved Rack as the source of truth.
