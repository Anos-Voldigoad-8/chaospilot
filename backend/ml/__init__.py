"""Phase 5 dataset generation and anomaly detection package.

The legacy ``core.ml`` scaffold is kept for the older API; this package is the
reproducible pipeline used by ``ml/scripts/generate_dataset.py`` and
``ml/train.py``.
"""

from __future__ import annotations

__all__ = ["features", "detector"]
