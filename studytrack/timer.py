"""A pauseable stopwatch with an injectable monotonic clock."""
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4


@dataclass
class FocusTimer:
    subject_id: int
    study_date: str
    accumulated: float = 0
    started: float | None = None
    token: str = field(default_factory=lambda: str(uuid4()))

    def elapsed(self, now=None):
        now = monotonic() if now is None else now
        return self.accumulated + (max(0, now - self.started) if self.started is not None else 0)

    def start(self, now=None):
        if self.started is None:
            self.started = monotonic() if now is None else now

    def pause(self, now=None):
        self.accumulated = self.elapsed(now)
        self.started = None
