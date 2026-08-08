"""NextBrain AutoResearch public API."""

from .agent import Agent, AgentReply, CommandAgent, OpenAIAgent
from .journal import UserMessageJournal
from .host import HostRoundManager
from .installer import ConversationSkillInstaller
from .doctor import Doctor
from .evaluation import CapabilityEvaluator
from .orchestrator import AutoResearch
from .topic import TopicDocument
from .workspace import ResearchWorkspace

__all__ = [
    "Agent",
    "AgentReply",
    "AutoResearch",
    "CommandAgent",
    "ConversationSkillInstaller",
    "CapabilityEvaluator",
    "Doctor",
    "HostRoundManager",
    "OpenAIAgent",
    "ResearchWorkspace",
    "TopicDocument",
    "UserMessageJournal",
]

__version__ = "0.3.0"
