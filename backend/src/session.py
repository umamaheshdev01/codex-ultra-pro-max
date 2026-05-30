import asyncio

from src.skills import SkillRegistry

SYSTEM_PROMPT = (
    "You are an expert coding assistant. You have tools to read/write files and run "
    "shell commands. You may also have external MCP tools such as Notion if they "
    "are configured by the server. If a user asks about Notion, MCPs, or another "
    "configured external service, inspect and use the available tools instead of "
    "saying you cannot access external services. If no matching tool is available, "
    "say that the tool is not connected yet. Work step by step. Always show what "
    "you're doing."
)

SESSION_TTL_SECONDS = 7200


class SessionStore:
    def __init__(self, skill_registry: SkillRegistry | None = None):
        self.sessions: dict[str, list[dict]] = {}
        self.session_skills: dict[str, str | None] = {}
        self.expiry_handles: dict[str, asyncio.TimerHandle] = {}
        self.skill_registry = skill_registry or SkillRegistry()

    def get_or_create(self, session_id, skill_name=None):
        normalized_skill_name = self.resolve_skill_name(skill_name)
        if session_id not in self.sessions:
            self.session_skills[session_id] = normalized_skill_name
            self.sessions[session_id] = [
                self._system_message(normalized_skill_name),
            ]
        elif self.session_skills.get(session_id) != normalized_skill_name:
            self.session_skills[session_id] = normalized_skill_name
            self.sessions[session_id] = [
                self._system_message(normalized_skill_name),
            ]
        self._schedule_expiry(session_id)
        return self.sessions[session_id]

    def append(self, session_id, message, skill_name=None):
        messages = self.get_or_create(session_id, skill_name)
        messages.append(message)
        self._schedule_expiry(session_id)

    def clear(self, session_id):
        skill_name = self.session_skills.get(session_id)
        self.sessions[session_id] = [self._system_message(skill_name)]
        self._schedule_expiry(session_id)

    def active_skill(self, session_id):
        return self.session_skills.get(session_id)

    def resolve_skill_name(self, skill_name):
        return self._normalize_skill_name(skill_name)

    def _normalize_skill_name(self, skill_name):
        if not skill_name:
            return None
        if not self.skill_registry.get(skill_name):
            return None
        return skill_name

    def _system_message(self, skill_name=None):
        skill = self.skill_registry.get(skill_name) if skill_name else None
        prompt = skill.system_prompt if skill else SYSTEM_PROMPT
        return {"role": "system", "content": prompt}

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
        self.session_skills.pop(session_id, None)
        self.expiry_handles.pop(session_id, None)
