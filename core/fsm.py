from enum import Enum, auto

class AgentState(Enum):
    """
    Enumeration representing the possible states of an agent.
    """
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    WAITING = auto()
    STOPPED = auto()
    ERROR = auto()
