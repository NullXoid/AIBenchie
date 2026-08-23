"""Public-safe AIBenchie runtime helpers."""

from . import echolabs_store

# Temporary source-compatibility alias for the unfinished display-brand rename.
# New code should import the stable, lowercase ``echolabs_store`` module.
Elabs_store = echolabs_store

__all__ = ["Elabs_store", "echolabs_store"]
