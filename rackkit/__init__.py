"""rack-preset-kit: put a plug-in's saved state into a genuine Ableton Rack template.

Pure standard library, no plug-in loading, no DAW control, no network. See docs/.
"""

from . import engine  # noqa: F401

__all__ = ["engine", "adapters"]
