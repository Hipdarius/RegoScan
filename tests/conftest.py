"""Shared pytest fixtures for VERA.

Putting a real `conftest.py` here also makes pytest discover the
`tests/` directory as a proper package — useful for the few tests that
import sibling helpers across files.
"""

import numpy as np
import pytest


@pytest.fixture(scope="session")
def rng():
    """Default pseudo-random generator. Same seed every session for
    deterministic test output."""
    return np.random.default_rng(seed=0xC0FFEE)


@pytest.fixture
def uniform_probs():
    """A flat 6-class posterior. Useful for max-entropy edge cases."""
    return np.full(6, 1.0 / 6.0)


@pytest.fixture
def one_hot_probs():
    """A confident posterior — class 0 is certain. Useful for
    zero-entropy / max-margin edge cases."""
    p = np.zeros(6)
    p[0] = 1.0
    return p
