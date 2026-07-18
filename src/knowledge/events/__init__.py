from enum import Enum

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.events.registry import (
    DuplicateEventError,
    EventRegistry,
    UnknownEventError,
)
from knowledge.events.cpi import CPIEvent
from knowledge.events.nfp import NFPEvent
from knowledge.events.gdp import GDPEvent
from knowledge.events.interest_rate import InterestRateEvent
from knowledge.events.ppi import PPIEvent
from knowledge.events.pmi import PMIEvent
from knowledge.events.fomc import FOMCEvent


class EconomicEvent(Enum):

    CPI = "Consumer Price Index"

    PPI = "Producer Price Index"

    NFP = "Non Farm Payroll"

    FOMC = "Federal Reserve Meeting"

    GDP = "Gross Domestic Product"

    INTEREST_RATE = "Interest Rate"

    UNEMPLOYMENT = "Unemployment"

    PMI = "PMI"

    DXY = "Dollar Index"

    YIELD10 = "US10Y Treasury"


# Register CPIEvent so it is discoverable through the public registry.
# Future MacroEvent subclasses should be registered here as well.
EventRegistry.register(CPIEvent)
EventRegistry.register(NFPEvent)
EventRegistry.register(GDPEvent)
EventRegistry.register(InterestRateEvent)
EventRegistry.register(PPIEvent)
EventRegistry.register(PMIEvent)
EventRegistry.register(FOMCEvent)


__all__ = [
    "EconomicEvent",
    "MacroEvent",
    "StandardEventMetadata",
    "EventRegistry",
    "DuplicateEventError",
    "UnknownEventError",
    "CPIEvent",
    "NFPEvent",
    "GDPEvent",
    "InterestRateEvent",
    "PPIEvent",
    "PMIEvent",
    "FOMCEvent",
]
