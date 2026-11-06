"""Exception hierarchy for bire."""


class BiReError(Exception):
    """Base exception for all bire errors."""


bireError = BiReError


class ValidationError(BiReError):
    """Raised when an AST fails semantic validation."""


class ParseError(BiReError):
    """Raised when regex or DSL parsing fails."""


class RenderError(BiReError):
    """Raised when code rendering fails."""
