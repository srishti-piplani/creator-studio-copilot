"""Small bounded, process-local request cache for SSE → POST fallback.

Both transports join the same job. No prompts, evidence, credentials or private
reasoning enter progress events. Completed requests expire after 15 minutes.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Condition, Lock
import time
from app.graph.progress import progress_sink
from app.rag.generate import ChatError
from app.rag.pinecone_store import PineconeOperationError


class ChatJobError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class ChatJob:
    def __init__(self, signature):
        self.signature = signature
        self.condition = Condition()
        self.events = []
        self.finished_at = None
        self.future = None

    def publish(self, event, data):
        with self.condition:
            self.events.append((event, data))
            self.condition.notify_all()

    def execute(self, call):
        token = progress_sink.set(lambda data: self.publish('progress', data))
        try:
            result = call()
            self.publish('final', result)
            return result
        except Exception as error:
            if isinstance(error, KeyError):
                status, message = 404, 'Session not found'
            elif isinstance(error, ValueError):
                status, message = 400, 'Invalid request or missing service configuration'
            elif isinstance(error, (ChatError, PineconeOperationError)):
                status, message = 503, 'Assistant is temporarily unavailable'
            else:
                status, message = 503, 'Assistant could not complete this request'
            self.publish('error', {'status': status, 'message': message})
            raise ChatJobError(status, message) from None
        finally:
            progress_sink.reset(token)
            self.finished_at = time.monotonic()

    def events_since_start(self):
        index = 0
        while True:
            with self.condition:
                if index == len(self.events):
                    self.condition.wait(timeout=15)
                batch = self.events[index:]
                index += len(batch)
            if not batch:
                # Transport keepalive only: never interpreted as agent progress.
                yield ': keepalive\n\n'
                continue
            import json
            for event, data in batch:
                yield f'event: {event}\ndata: {json.dumps(data)}\n\n'
                if event in ('final', 'error'):
                    return


class ChatJobs:
    def __init__(self, max_jobs=64, ttl=900):
        self.jobs = {}
        self.lock = Lock()
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='chat-job')
        self.max_jobs, self.ttl = max_jobs, ttl

    def get_or_start(self, request_id, signature, call):
        with self.lock:
            now = time.monotonic()
            self.jobs = {key: job for key, job in self.jobs.items()
                         if job.finished_at is None or now - job.finished_at < self.ttl}
            if request_id in self.jobs:
                job = self.jobs[request_id]
                if job.signature != signature:
                    raise ChatJobError(409, 'Request ID was already used for different input')
                return job
            if len(self.jobs) >= self.max_jobs:
                # Evict completed work only; never duplicate a still-running request.
                completed = next((key for key, job in self.jobs.items() if job.finished_at is not None), None)
                if completed is None:
                    raise ChatJobError(429, 'Assistant is busy; please try again later')
                del self.jobs[completed]
            job = ChatJob(signature)
            self.jobs[request_id] = job
            job.future = self.pool.submit(job.execute, call)
            return job


chat_jobs = ChatJobs()
