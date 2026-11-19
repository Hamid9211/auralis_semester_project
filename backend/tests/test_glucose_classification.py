"""FR-TA-01 / NFR-01: classification at every boundary (BVA)."""

import pytest

from app.domain.trends import GlucoseLevel, classify


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (20, GlucoseLevel.LOW),
        (69, GlucoseLevel.LOW),
        (69.9, GlucoseLevel.LOW),
        (70, GlucoseLevel.IN_RANGE),
        (120, GlucoseLevel.IN_RANGE),
        (180, GlucoseLevel.IN_RANGE),
        (180.1, GlucoseLevel.HIGH),
        (181, GlucoseLevel.HIGH),
        (600, GlucoseLevel.HIGH),
    ],
)
def test_classification_boundaries(value, expected):
    assert classify(value) is expected
