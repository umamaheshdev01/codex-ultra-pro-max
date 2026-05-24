import asyncio

SYSTEM_PROMPT = (
    "You are an expert coding assistant. You have tools to read/write files and run "
    "shell commands. Work step by step. Always show what you're doing."
)

SESSION_TTL_SECONDS = 7200


class SessionStore:
    def __init__(self):
        self.sessions: dict[str, list[dict]] = {}
        self.expiry_handles: dict[str, asyncio.TimerHandle] = {}

    def get_or_create(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = [self._system_message()]
        self._schedule_expiry(session_id)
        return self.sessions[session_id]

    def append(self, session_id, message):
        messages = self.get_or_create(session_id)
        messages.append(message)
        self._schedule_expiry(session_id)

    def clear(self, session_id):
        self.sessions[session_id] = [self._system_message()]
        self._schedule_expiry(session_id)

    def _system_message(self):
        return {"role": "system", "content": SYSTEM_PROMPT}

    def _schedule_expiry(self, session_id):
        existing_handle = self.expiry_handles.get(session_id)
        if existing_handle:
            existing_handle.cancel()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self.expiry_handles[session_id] = loop.call_later(
            SESSION_TTL_SECONDS,
            self._expire,
            session_id,
        )

    def _expire(self, session_id):
        self.sessions.pop(session_id, None)
        self.expiry_handles.pop(session_id, None)
