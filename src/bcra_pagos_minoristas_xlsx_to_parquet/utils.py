"""Shared utility functions used across pipeline stages."""

from __future__ import annotations

import math
from typing import Any


def is_blank(value: Any) -> bool:
    """Return ``True`` if *value* should be treated as blank/missing.

    Handles ``None``, NaN, whitespace-only strings, and common numpy/pandas
    missing-value types.  For edge cases (e.g. :class:`pandas.NaT`) it falls
    back to :func:`pandas.isna` when the library is available.
    """

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return math.isnan(float(value))  # float('nan') or numpy nan
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        from pandas import isna as _is_na

        return bool(_is_na(value))
    except ImportError:
        pass
    return False
