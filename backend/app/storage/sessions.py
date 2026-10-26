"""Local thread locks. Conversation data lives in the LangGraph memory checkpointer.

No disk persistence: restarting the backend loses sessions. Use one backend worker.
"""
from contextlib import contextmanager
from threading import Lock, RLock
from uuid import UUID, uuid4

class Sessions:
    def __init__(self):
        self._guard = Lock()
        self._locks = {}

    def identity(self, supplied=None):
        if supplied is None:
            return str(uuid4())
        try:
            return str(UUID(supplied))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Session ID must be a UUID') from None

    @contextmanager
    def locked(self, identity):
        with self._guard:
            lock = self._locks.setdefault(identity, RLock())
        with lock:
            yield

    @staticmethod
    def config(identity):
        return {'configurable': {'thread_id': identity}, 'recursion_limit': 12}
