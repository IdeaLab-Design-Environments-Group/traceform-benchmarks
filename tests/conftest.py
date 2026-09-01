import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

import pytest  # noqa: E402
import yaml  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    c = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
    c["unfold"].setdefault("candidate_directions", 96)
    c["_hash"] = "test"
    return c


@pytest.fixture(scope="session")
def root():
    return ROOT
