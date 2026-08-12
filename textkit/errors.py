"""Error types for textkit."""


class TextKitError(Exception):
    """Raised for any recoverable failure in a textkit operation.

    All public functions raise this (and only this) on failure so callers --
    including the CLI and the GUI -- have a single exception to catch and can
    show a clean message instead of a traceback.
    """
