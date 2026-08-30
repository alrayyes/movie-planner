"""Test doubles shared across test modules."""

from dataclasses import dataclass, field

import icalendar


@dataclass
class FakeEvent:
    data: str
    deleted: bool = False

    def save(self) -> None:
        pass

    def delete(self) -> None:
        self.deleted = True


@dataclass
class FakeCalendar:
    """Duck-types the slice of caldav.Calendar this module uses."""

    events_by_uid: dict[str, FakeEvent] = field(default_factory=dict)
    fail_next: bool = False

    def events(self) -> list[FakeEvent]:
        if self.fail_next:
            raise ConnectionError("simulated failure")
        return list(self.events_by_uid.values())

    def add_event(self, ical: str) -> FakeEvent:
        if self.fail_next:
            raise ConnectionError("simulated failure")
        uid = str(icalendar.Calendar.from_ical(ical).walk("VEVENT")[0]["uid"])
        event = FakeEvent(data=ical)
        self.events_by_uid[uid] = event
        return event

    def event_by_uid(self, uid: str) -> FakeEvent:
        if self.fail_next:
            raise ConnectionError("simulated failure")
        return self.events_by_uid[uid]
