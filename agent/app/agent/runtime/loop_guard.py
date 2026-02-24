"""Loop guard for bounded ReAct execution."""

from __future__ import annotations


class LoopGuard:
    """Track loop progression and enforce max step limits."""

    def __init__(self, max_steps: int) -> None:
        self._max_steps = max(1, max_steps)
        self._step = 0

    def next(self) -> int:
        if self._step >= self._max_steps:
            raise RuntimeError("max_steps_reached")
        self._step += 1
        return self._step

    @property
    def exhausted(self) -> bool:
        return self._step >= self._max_steps

