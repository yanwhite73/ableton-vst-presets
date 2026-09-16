#!/usr/bin/env python3
"""Adapter registry: all plug-in-format knowledge lives here, none in the engine.

An adapter turns a native preset's opaque state into the exact bytes that belong
inside a genuine Rack template of one *kind* (an Arturia two-archive VST2 Buffer, a
VST3 Processor/Controller state, ...). Each adapter must prove that it changed only
the plug-in-state region of the Rack and left every other byte identical.

To support a new plug-in you usually write a new *state source* for an existing
container kind (e.g. another VST3 vendor's native format), not a whole new adapter.
See docs/ADAPTERS.md and docs/ADD_A_PLUGIN.md.
"""

from __future__ import annotations

from typing import Protocol


class Adapter(Protocol):
    """The contract every adapter satisfies. Duck-typed; no inheritance required."""

    name: str

    def detect(self, template_xml: bytes) -> bool:
        """Cheap, side-effect-free: does this template look like my kind of Rack?"""
        ...

    def inspect(self, template_xml: bytes) -> dict:
        """Validate the template is a clean single-instrument Rack of my kind and
        describe it (plug-in identity, state size, configured parameters). Raise
        ValueError with a specific reason if it is not."""
        ...

    def build(self, template_xml: bytes, native: bytes, *, preset_name: str) -> "tuple[bytes, dict]":
        """Return (candidate_xml, report). Change only the plug-in-state region and
        prove the rest of the Rack XML is byte-identical."""
        ...


_REGISTRY: "dict[str, Adapter]" = {}


def register(adapter) -> None:
    if adapter.name in _REGISTRY:
        raise ValueError(f"Duplicate adapter name: {adapter.name}")
    _REGISTRY[adapter.name] = adapter


def names() -> "list[str]":
    return sorted(_REGISTRY)


def get(name: str):
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown adapter '{name}'. Available: {', '.join(names()) or '(none)'}") from None


def detect(template_xml: bytes):
    """Return the single adapter whose kind this template matches, or raise.

    Ambiguity (0 or >1 matches) is an error, not a guess -- the caller then names
    the adapter explicitly.
    """
    matches = [adapter for adapter in _REGISTRY.values() if adapter.detect(template_xml)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError("No adapter recognised this template; pass --adapter explicitly.")
    raise ValueError(
        "Template matched more than one adapter (" + ", ".join(a.name for a in matches) + "); pass --adapter."
    )


# Registering the built-in adapters. Import side effects populate the registry.
# Each adapter is registered independently so one still-in-progress module cannot
# disable the others.
from . import arturia_buffer as _arturia_buffer  # noqa: E402

register(_arturia_buffer.ADAPTER)

try:
    from . import vst3_state as _vst3_state  # noqa: E402
except ImportError:  # pragma: no cover - present once the VST3 adapter lands
    _vst3_state = None
else:
    for _adapter in _vst3_state.ADAPTERS:
        register(_adapter)
