from pathlib import Path

import pandas as pd
import pytest

from knowledge.events.base import MacroEvent
from knowledge.events.cpi import CPIEvent
from knowledge.events.fomc import FOMCEvent
from knowledge.events.gdp import GDPEvent
from knowledge.events.interest_rate import InterestRateEvent
from knowledge.events.nfp import NFPEvent
from knowledge.events.pmi import PMIEvent
from knowledge.events.ppi import PPIEvent
from knowledge.events.registry import (
    DuplicateEventError,
    EventRegistry,
    UnknownEventError,
)


# --------------------------------------------------------------------------
# Fixture: restore real event registrations after each test that
# clears the registry or registers dummy events with the same type key.
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_registered_events() -> None:
    yield
    originals = [
        ("CPI", CPIEvent),
        ("NFP", NFPEvent),
        ("GDP", GDPEvent),
        ("INTEREST_RATE", InterestRateEvent),
        ("PPI", PPIEvent),
        ("PMI", PMIEvent),
        ("FOMC", FOMCEvent),
    ]
    for event_type, cls in originals:
        current = EventRegistry.get(event_type)
        if current is not cls:
            if EventRegistry.is_registered(event_type):
                EventRegistry.register(cls, replace=True)
            else:
                EventRegistry.register(cls)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_dummy_event(name: str, version: str = "v1") -> type[MacroEvent]:
    class DummyEvent(MacroEvent):
        event_type = name
        lesson_version = f"dummy_{name}_{version}"
        condition_columns = [f"{name.lower()}_pressure"]
        knowledge_version = f"dummy_{name}_summary_{version}"

        def load_and_extract(self, path: Path) -> pd.DataFrame:
            return pd.DataFrame({"Date": ["2020-01-01"], "Value": [100.0]})

        def build_lesson_fields(self, event_row, anchor_date):
            return {"value": float(event_row["Value"])}

        def lesson_text(self, lesson):
            return f"Dummy {event_type} lesson."

    return DummyEvent


def _fresh_registry() -> None:
    EventRegistry.clear()
    assert not EventRegistry.is_registered("CPI")


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

def test_register_event() -> None:
    _fresh_registry()
    cls = _make_dummy_event("NFP")
    EventRegistry.register(cls)
    assert EventRegistry.is_registered("NFP")
    assert EventRegistry.get("NFP") is cls


def test_register_multiple_events() -> None:
    _fresh_registry()
    nfp = _make_dummy_event("NFP")
    fomc = _make_dummy_event("FOMC")
    EventRegistry.register(nfp)
    EventRegistry.register(fomc)
    assert EventRegistry.list_events() == ["FOMC", "NFP"]


def test_register_rejects_non_macro_event() -> None:
    _fresh_registry()

    class NotAnEvent:
        event_type = "FAKE"

    with pytest.raises(TypeError):
        EventRegistry.register(NotAnEvent)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Duplicate prevention
# --------------------------------------------------------------------------

def test_duplicate_registration_raises_error() -> None:
    _fresh_registry()
    cls = _make_dummy_event("NFP")
    EventRegistry.register(cls)
    with pytest.raises(DuplicateEventError):
        EventRegistry.register(cls)


def test_duplicate_registration_with_replace() -> None:
    _fresh_registry()
    cls_a = _make_dummy_event("NFP", version="a")
    cls_b = _make_dummy_event("NFP", version="b")
    EventRegistry.register(cls_a)
    EventRegistry.register(cls_b, replace=True)
    assert EventRegistry.get("NFP") is cls_b


def test_duplicate_error_message() -> None:
    _fresh_registry()
    cls = _make_dummy_event("PMI")
    EventRegistry.register(cls)
    with pytest.raises(DuplicateEventError) as exc:
        EventRegistry.register(cls)
    assert "PMI" in str(exc.value)
    assert cls.__name__ in str(exc.value)


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

def test_get_returns_none_for_unknown() -> None:
    _fresh_registry()
    assert EventRegistry.get("NONEXISTENT") is None


def test_get_or_raise_returns_class() -> None:
    _fresh_registry()
    cls = _make_dummy_event("GDP")
    EventRegistry.register(cls)
    assert EventRegistry.get_or_raise("GDP") is cls


def test_get_or_raise_raises_for_unknown() -> None:
    _fresh_registry()
    with pytest.raises(UnknownEventError):
        EventRegistry.get_or_raise("NONEXISTENT")


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------

def test_list_events_empty() -> None:
    _fresh_registry()
    assert EventRegistry.list_events() == []


def test_list_events_returns_sorted() -> None:
    _fresh_registry()
    pmi = _make_dummy_event("PMI")
    cpi = _make_dummy_event("CPI")
    gdp = _make_dummy_event("GDP")
    EventRegistry.register(pmi)
    EventRegistry.register(cpi)
    EventRegistry.register(gdp)
    assert EventRegistry.list_events() == ["CPI", "GDP", "PMI"]


# --------------------------------------------------------------------------
# is_registered
# --------------------------------------------------------------------------

def test_is_registered_true() -> None:
    _fresh_registry()
    cls = _make_dummy_event("FOMC")
    EventRegistry.register(cls)
    assert EventRegistry.is_registered("FOMC")


# --------------------------------------------------------------------------
# Clear
# --------------------------------------------------------------------------

def test_clear_removes_all() -> None:
    _fresh_registry()
    cls = _make_dummy_event("CPI")
    EventRegistry.register(cls)
    assert EventRegistry.is_registered("CPI")
    EventRegistry.clear()
    assert not EventRegistry.is_registered("CPI")
    assert EventRegistry.list_events() == []


def test_clear_is_idempotent() -> None:
    _fresh_registry()
    EventRegistry.clear()
    EventRegistry.clear()
    assert EventRegistry.list_events() == []


# --------------------------------------------------------------------------
# CPI integration (relies on module-level registration in events/__init__.py)
# --------------------------------------------------------------------------

def test_cpi_is_registered_by_default() -> None:
    assert EventRegistry.is_registered("CPI")
    cls = EventRegistry.get("CPI")
    assert cls is not None
    assert cls.event_type == "CPI"
    assert cls.lesson_version == "cpi_gold_v1"
    assert cls.knowledge_version == "cpi_gold_summary_v1"
    assert cls.condition_columns == ["cpi_pressure"]


def test_cpi_can_be_instantiated_from_registry() -> None:
    cls = EventRegistry.get("CPI")
    instance = cls()
    assert instance.event_type == "CPI"
    assert instance.lesson_version == "cpi_gold_v1"
    assert instance.condition_columns == ["cpi_pressure"]
    assert instance.metadata.country == "US"
    assert instance.metadata.importance == 3


def test_cpi_behavior_unchanged() -> None:
    instance = CPIEvent()
    path = Path(__file__).resolve().parent / "_runtime" / "cpi_test_data.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Date": ["2020-01-01", "2020-02-01"], "Value": [100.0, 102.5]}).to_csv(path, index=False)
    df = instance.load_and_extract(path)
    assert "cpi_pressure" in df.columns
    assert "cpi_change_pct" in df.columns
    assert len(df) >= 1
    fields = instance.build_lesson_fields(df.iloc[-1], "2020-02-02")
    assert "cpi_pressure" in fields
    text = instance.lesson_text({
        "event_date": "2020-01-01",
        "primary_horizon_days": 5,
        "gold_direction_5d": "UP",
        "gold_return_5d_pct": 1.5,
        "cpi_change_pct": 0.25,
    })
    assert "CPI" in text
    path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Future event types (no implementation required)
# --------------------------------------------------------------------------

def test_future_event_type_works() -> None:
    _fresh_registry()
    cls = _make_dummy_event("PMI")
    EventRegistry.register(cls)
    assert EventRegistry.is_registered("PMI")
    assert issubclass(cls, MacroEvent)


def test_registry_supports_all_expected_future_events() -> None:
    _fresh_registry()
    for name in ["CPI", "NFP", "FOMC", "GDP", "PMI"]:
        cls = _make_dummy_event(name)
        EventRegistry.register(cls)
    assert EventRegistry.list_events() == ["CPI", "FOMC", "GDP", "NFP", "PMI"]
    for name in ["CPI", "NFP", "FOMC", "GDP", "PMI"]:
        assert EventRegistry.is_registered(name)
