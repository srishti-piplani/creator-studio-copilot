"""Request-local public activity signals; never model output or graph state."""
from contextvars import ContextVar
from functools import wraps

progress_sink = ContextVar('chat_progress_sink', default=None)


def operation(action, label, call):
    sink = progress_sink.get()
    def emit(status):
        if sink:
            sink({'action': action, 'label': label, 'status': status})
    emit('started')
    try:
        result = call()
    except Exception:
        emit('failed')
        raise
    emit('completed')
    return result


def tracked(action, label):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            return operation(action, label, lambda: function(*args, **kwargs))
        return wrapped
    return decorate
