"""Stigma — pheromone-style signal coordination on top of mycelium."""
from __future__ import annotations

from typing import Optional

from ormica.mycelium import Entry, Mycelium

from .signal import Signal


class Stigma:
    """Emergent coordination via pheromone trails.

    Agents ``emit`` or ``reinforce`` signals on topics; intensity decays
    exponentially with the configured ``half_life``; selection picks the
    strongest trails. ``evaporate`` purges signals below ``floor``.

    Signals are stored in the supplied :class:`Mycelium` under the
    ``stigma/`` key prefix, so they co-exist with regular memory entries.
    """

    KEY_PREFIX = "stigma/"

    def __init__(
        self,
        mycelium: Mycelium,
        *,
        half_life: float = 60.0,
        floor: float = 0.01,
    ) -> None:
        if half_life <= 0:
            raise ValueError("half_life must be > 0")
        if floor < 0:
            raise ValueError("floor must be >= 0")
        self.mycelium = mycelium
        self.half_life = half_life
        self.floor = floor

    # --- writes ---

    def emit(
        self,
        topic: str,
        *,
        strength: float = 1.0,
        by: Optional[str] = None,
    ) -> Signal:
        """Leave a fresh signal, replacing any existing trail on this topic."""
        return self._write(topic, strength=strength, sources={by} if by else set())

    def reinforce(
        self,
        topic: str,
        *,
        amount: float = 1.0,
        by: Optional[str] = None,
    ) -> Signal:
        """Add ``amount`` to a topic's current (decay-adjusted) strength.

        Creates the trail if it does not yet exist.
        """
        existing = self._load(topic)
        if existing is None:
            return self._write(topic, strength=amount, sources={by} if by else set())
        current = existing.strength_at(self.mycelium.now(), self.half_life)
        sources = existing.sources | ({by} if by else set())
        return self._write(topic, strength=current + amount, sources=sources)

    # --- reads ---

    def sense(self, topic: str) -> Optional[Signal]:
        """Current (decayed) signal on a topic. ``None`` if absent or below floor."""
        signal = self._load(topic)
        if signal is None:
            return None
        return self._as_current(signal)

    def trails(self) -> list[Signal]:
        """All live signals with current strengths, strongest first."""
        out = [s for s in self._iter_live()]
        out.sort(key=lambda s: s.strength, reverse=True)
        return out

    def top(self, n: int = 1) -> list[Signal]:
        return self.trails()[:n]

    def evaporate(self) -> int:
        """Delete signals whose decayed strength has fallen below ``floor``.

        Returns the number of trails removed.
        """
        now = self.mycelium.now()
        dropped = 0
        for entry in list(self.mycelium.all()):
            if not entry.key.startswith(self.KEY_PREFIX):
                continue
            signal = _signal_from_entry(entry)
            if signal.strength_at(now, self.half_life) < self.floor:
                self.mycelium.delete(entry.key)
                dropped += 1
        return dropped

    # --- internals ---

    def _key(self, topic: str) -> str:
        return f"{self.KEY_PREFIX}{topic}"

    def _write(self, topic: str, *, strength: float, sources: set[str]) -> Signal:
        self.mycelium.write(
            self._key(topic),
            value={"strength": strength, "sources": list(sources)},
            meta={"kind": "stigma.signal", "topic": topic},
        )
        return Signal(
            topic=topic,
            strength=strength,
            sources=set(sources),
            last_touched=self.mycelium.now(),
        )

    def _load(self, topic: str) -> Optional[Signal]:
        entry = self.mycelium.read(self._key(topic))
        if entry is None:
            return None
        return _signal_from_entry(entry)

    def _iter_live(self):
        now = self.mycelium.now()
        for entry in self.mycelium.all():
            if not entry.key.startswith(self.KEY_PREFIX):
                continue
            signal = _signal_from_entry(entry)
            current = signal.strength_at(now, self.half_life)
            if current < self.floor:
                continue
            yield Signal(
                topic=signal.topic,
                strength=current,
                sources=signal.sources,
                last_touched=signal.last_touched,
            )

    def _as_current(self, signal: Signal) -> Optional[Signal]:
        now = self.mycelium.now()
        current = signal.strength_at(now, self.half_life)
        if current < self.floor:
            return None
        return Signal(
            topic=signal.topic,
            strength=current,
            sources=signal.sources,
            last_touched=signal.last_touched,
        )


def _signal_from_entry(entry: Entry) -> Signal:
    topic = entry.meta.get("topic") or entry.key.removeprefix(Stigma.KEY_PREFIX)
    return Signal(
        topic=topic,
        strength=entry.value["strength"],
        sources=set(entry.value["sources"]),
        last_touched=entry.written_at,
    )
