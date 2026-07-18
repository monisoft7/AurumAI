from __future__ import annotations

from knowledge.events.base import MacroEvent


class DuplicateEventError(Exception):
    """Raised when attempting to register a MacroEvent subclass whose
    *event_type* is already registered in this registry."""


class UnknownEventError(KeyError):
    """Raised when looking up an event type that has not been registered."""


class EventRegistry:
    """Lightweight registry for MacroEvent subclasses.

    Maps *event_type* string -> MacroEvent subclass.
    Does NOT instantiate events — callers instantiate as needed.
    """

    _events: dict[str, type[MacroEvent]] = {}

    @classmethod
    def register(
        cls, event_cls: type[MacroEvent], *, replace: bool = False
    ) -> None:
        if not (isinstance(event_cls, type) and issubclass(event_cls, MacroEvent)):
            raise TypeError(
                f"{event_cls.__name__} is not a MacroEvent subclass"
            )

        raw = getattr(event_cls, "event_type", None)
        if isinstance(raw, str):
            event_type = raw
        elif isinstance(raw, property):
            event_type = event_cls().event_type
        else:
            raise ValueError(
                f"Cannot determine event_type for {event_cls.__name__}"
            )

        if not isinstance(event_type, str) or not event_type:
            raise ValueError(
                f"event_type must be a non-empty string, got {event_type!r}"
            )

        if not replace and event_type in cls._events:
            raise DuplicateEventError(
                f"Event type {event_type!r} is already registered by "
                f"{cls._events[event_type].__name__}. "
                "Use replace=True to override."
            )

        cls._events[event_type] = event_cls

    @classmethod
    def get(cls, event_type: str) -> type[MacroEvent] | None:
        return cls._events.get(event_type)

    @classmethod
    def get_or_raise(cls, event_type: str) -> type[MacroEvent]:
        if event_type not in cls._events:
            raise UnknownEventError(f"Unknown event type: {event_type!r}")
        return cls._events[event_type]

    @classmethod
    def list_events(cls) -> list[str]:
        return sorted(cls._events.keys())

    @classmethod
    def is_registered(cls, event_type: str) -> bool:
        return event_type in cls._events

    @classmethod
    def clear(cls) -> None:
        cls._events.clear()
