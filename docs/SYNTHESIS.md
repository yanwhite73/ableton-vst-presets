# Offline rack synthesis — no template needed (Arturia VST2)

**Confirmed 2026-09-15.** A Rack **synthesized entirely offline** — no hand-saved
template, no extraction from an existing Rack, no Live automation — loaded a real
Arturia instrument and recalled the native sound.

- Test: `CS-80 V3 [SYNTH capture test].adg`, built from a Pigments skeleton + CS-80's
  cache identity + the native `Factory/16 SQC` preset. User dragged it into Live:
  **"loaded 16sqc cs80 AND SOUNDS NORMAL".**

This overturns the earlier working assumption that each plug-in needs its own
hand-saved (or extracted-from-a-real-Rack) template. For Arturia VST2 it does not.

## Why it works

Ableton resolves a VST2 inside a Rack purely by `<Type>` + `<UniqueId>` — there is no
plug-in name or path string in the node (`<Name>` is empty). The *sound* lives in the
plug-in's opaque chunk, stored as the `<Buffer>`. Live re-queries the plug-in for its
parameters on load, so a blank/foreign configured-parameter list is tolerated.

So a loadable Rack for instrument X is assembled from three offline ingredients:

1. **Skeleton** — any Arturia VST2 two-archive Buffer Rack (we use an installed
   Pigments Rack). Everything outside the plug-in node is reused byte-for-byte.
2. **Identity** — retarget the node's `UniqueId` to X's VST2 unique id, read from
   Live's plugin cache (`Live-plugins-*.db`, `plugins.dev_identifier` =
   `device:vst:instr:<UniqueId>?n=<Name>`). `Type` stays `1178747752` (`FBCh`).
3. **State** — set the `<Buffer>` to the observed framing: two little-endian uint64
   lengths + two byte-identical copies of X's native `22 serialization::archive`
   preset file. Blank `<ParameterSettings>` so Pigments' configured params can't
   mis-map onto X.

No plug-in is instantiated, no DAW is driven, no network/DB is written. Pure stdlib
byte work, so it is cross-platform by construction (identities just come from the
Windows copy of the same cache DB).

## Boundaries / still to confirm

- **`FBCh` Type and the duplicate-two-archive framing** are observed on Pigments and
  CS-80 V3. Spot-check across structurally different instruments (a sampler-based one
  like CMI/Mellotron, a big modular) before treating all 26 as done.
- **Sample-based instruments** (CMI, Mellotron, …) may reference external content;
  recall of the *engine* state is not proof the samples resolve on another machine.
- **VST2 only.** VST3 synthesis (class UID from the cache + a VST3 preset skeleton)
  is a separate, unproven experiment; the VST3 path is currently extraction-based
  (Surge/Tyrell).
- **One load test per instrument still qualifies it.** Appearing in the browser is not
  success; only the plug-in opening with the right sound is.
- **Redistribution of factory content** is a separate licensing question. This is a
  local convenience that re-wraps presets the user already owns and has installed.

## Results log (user load-tests in Live)

Synthesis only works when the native preset file **is** the plug-in's own state chunk.

| Plug-in | API | Native form | Result |
|---|---|---|---|
| CS-80 V3 | VST2 | Arturia archive | ✅ loads + correct sound |
| Mini V3, DX7 V, CMI V, Mellotron V, Modular V3, Wurli V2 | VST2 | Arturia archive | ✅ all load (incl. sample-based CMI/Mellotron) |
| Zebra CM, Bazille CM (u-he) | VST3 | `.h2p` | ✅ load + correct sound (`#pgm=`header + h2p in processor & controller state; Tyrell mechanism generalises across u-he) |
| Vital | VST3 | `.vital` JSON | ✅ loads + correct sound with a **version-matched** preset. First failed to init on a `synth_version` 0.9.1 factory preset; a 1.5.5 user preset (matching the installed plug-in) works. |

Takeaways:

- A correct class UID reliably instantiates the right VST3 plug-in; the `ProcessorState`
  (VST3) or `Buffer` (VST2) must be the plug-in's actual serialized state.
- **The native preset must match the installed plug-in version.** Vital rejected a very
  old preset as state and reset to init; the version-matched preset loaded.
- Three proven synthesis families, no saved templates: **Arturia VST2** (archive
  duplicated in the two-archive Buffer), **u-he VST3** (`#pgm=`+`.h2p` in processor and
  controller state), **Vital VST3** (raw `.vital` JSON as processor state).
- Where the native file is *not* the plug-in's state (a wrapper/transform is needed),
  extract one real save to learn the mapping — that is the per-vendor "state source" work.
