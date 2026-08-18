"""Exceptions KageKit raises.

No billing or plan vocabulary lives here. These state a UI fact — a cap was reached,
a feature is switched off — and it is the caller's job to decide that the reason is
"not on your plan".
"""


class LimitError(Exception):
    """Raised when a count would exceed its cap."""


class FeatureDisabledError(Exception):
    """Raised when a feature turned off by the injected ``Limits`` is used."""
