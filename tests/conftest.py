from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _clear_global_extractors() -> None:
    from knowledge.features.engine import FeatureExtractionEngine
    FeatureExtractionEngine.clear_global()
    yield
    FeatureExtractionEngine.clear_global()
