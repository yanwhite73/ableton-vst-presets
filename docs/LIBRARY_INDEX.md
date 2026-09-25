# Library index — describing an installed Rack library for other tools

`bin/index_library.py` reads an installed library of single-plug-in Racks and writes one JSON
file (`rack-preset-kit.library-index.v1`). It needs no build manifest, so it also works for
libraries installed long ago, moved or reorganised. It only reads Racks and sidecars.
(This is different from the *build catalog*, `rack-preset-kit.catalog.v1`, which lists native
presets to convert.)

```sh
python3 bin/index_library.py --out ./out/library-index.json            # Live's User Library
python3 bin/index_library.py --root <folder> --out ./out/index.json    # any folder
```

## Entry fields

| field | meaning |
| --- | --- |
| `id` | Location ID: hash of format, identity and relative path. Stable while the Rack stays put. |
| `path` | Path relative to the indexed root, with `/` separators. |
| `sha256`, `size` | Hash and size of the `.adg` file itself. |
| `format` | `vst2` or `vst3`. |
| `unique_id` / `class_uid` | Exact plug-in identity: VST2 UniqueId (int), or VST3 class UID (32 lowercase hex). |
| `name` | File name without `.adg`. |
| `instrument`, `category`, `bank` | Sidecar `Instrument`/`Type`/`Bank` keywords. Instrument and category fall back to folder names. |
| `colors` | Ableton Collection colour indices from the sidecar (for example `"2"` is orange). |

Racks that are not exactly one VST2/VST3 plug-in node, such as native Live racks, are listed
under `errors` with a reason. They are never guessed at.

## Rules for consumers

- Identify a plug-in by `format` plus exact identity. A name alone never distinguishes VST2
  from VST3, and it never authorizes a match.
- Relink a moved Rack only to an **unambiguous** content match. Libraries do contain
  byte-identical Racks: one real library of 11,141 had 6 duplicated hashes.
- An index is a snapshot. Before loading, recheck the file still exists and has the recorded
  hash.
- A correct identity does not prove the sound loads correctly. A preset saved by another
  plug-in version can open as the init patch (see [SYNTHESIS](SYNTHESIS.md)). Load-test each
  plug-in family.
