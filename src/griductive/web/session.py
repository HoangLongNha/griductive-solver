"""Commit proof work only while its session revision remains current."""
from threading import Lock

from .controller import WebController


class StaleOperation(Exception):
    """A reset, load or competing command superseded the result."""


class SessionHost:
    """Own one local session; private work never mutates its published state."""

    def __init__(self, controller: WebController) -> None:
        self._controller = controller
        self._revision = 0
        self._lock = Lock()

    def execute(self, action: str, *args):
        with self._lock:
            if action in ('list_puzzles', 'get_public_state_dict'):
                return getattr(self._controller, action)(*args)
            if action in ('load_puzzle', 'restart'):
                # A failed load preserves the board but still supersedes pending work.
                self._revision += 1
                result = getattr(self._controller, action)(*args)
                return result
            if action not in ('get_hint', 'step', 'submit_verdict', 'auto_solve'):
                raise ValueError('Unknown session action')
            revision = self._revision
            worker = self._controller.fork()

        # SAT work runs outside the lock, so Load/Restart can invalidate it.
        try:
            result = getattr(worker, action)(*args)
        except Exception:
            with self._lock:
                if revision != self._revision:
                    raise StaleOperation('Session changed; result discarded') from None
            raise
        with self._lock:
            if revision != self._revision:
                raise StaleOperation('Session changed; result discarded')
            if action != 'get_hint':
                self._controller = worker
                self._revision += 1
            return result
