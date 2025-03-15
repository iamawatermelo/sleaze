from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import dataclasses
from typing import ClassVar, Self
import aiohttp

@dataclass
class Pronouns:
    subject: str
    object: str
    posessive_determiner: str
    posessive_pronoun: str
    reflexive: str
    
    def format(self, f: str):
        return f.format(**dataclasses.asdict(self))

class Context:
    slack_session: aiohttp.ClientSession
    ctx: ClassVar[ContextVar[Self]] = ContextVar("sleaze_session")
    
    slack_token: str
    slack_channel: str
    slack_ping_user: str
    
    user_pronoun: Pronouns
    
    webhook_auth_token: str
    
    def __init__(
        self,
        slack_token: str,
        slack_channel: str,
        slack_ping_user: str,
        webhook_auth_token: str,
        user_pronoun: str,
    ):
        self.slack_token = slack_token
        self.slack_channel = slack_channel
        self.slack_ping_user = slack_ping_user
        self.webhook_auth_token = webhook_auth_token
        
        pronoun_parts = user_pronoun.split("/")
        assert len(pronoun_parts) == 5, "Pronoun specifier must be in the format subject/object/posessive determiner/posessive pronoun/reflexive"
        self.user_pronoun = Pronouns(*pronoun_parts)
    
    @asynccontextmanager
    async def enter(self):
        async with (
            aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.slack_token}"
                }
            ) as slack_session
        ):
            self.slack_session = slack_session
            
            reset_token = self.ctx.set(self)
            
            yield
            
            self.ctx.reset(reset_token)
    
    @classmethod
    def from_context(cls) -> Self:
        return cls.ctx.get()