import sys
import logging
from unittest.mock import MagicMock

# Mocking mcpi before importing agents
sys.modules["mcpi.minecraft"] = MagicMock()
sys.modules["mcpi.minecraft"].Minecraft.create.return_value = MagicMock()

from core.messaging import MessageBus  # noqa: E402
from core.utils import load_classes  # noqa: E402
from core.base_agent import BaseAgent  # noqa: E402

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DebugScript")


def run_debug():
    logger.info("Starting Debug Diagnosis...")

    # 1. Initialize Bus
    bus = MessageBus()

    # 2. Load Agents
    logger.info("Loading agents...")
    agent_classes = load_classes("agents", BaseAgent)
    logger.info(
        f"Found {len(agent_classes)} agent classes: {[cls.__name__ for cls in agent_classes]}"
    )

    agents = []
    chat_bot = None
    explorer_bot = None

    # 3. Instantiate Agents
    for cls in agent_classes:
        agent = cls(name=cls.__name__, message_bus=bus)
        agents.append(agent)
        logger.info(f"Instantiated {agent.name}")

        if agent.name == "ChatBot":
            chat_bot = agent
        elif agent.name == "ExplorerBot":
            explorer_bot = agent

    if not chat_bot:
        logger.error("ChatBot not found!")
        return

    if not explorer_bot:
        logger.error("ExplorerBot not found!")
        return

    # 4. Check Subscriptions
    # Accessing private _subscribers for debugging
    logger.info(f"Bus subscribers: {bus._subscribers.keys()}")

    if "control.workflow.run" in bus._subscribers:
        logger.info("SUCCESS: 'control.workflow.run' has subscribers.")
    else:
        logger.error("FAILURE: 'control.workflow.run' has NO subscribers.")

    # 5. Simulate Chat Command
    logger.info("Simulating '/workflow run' command...")
    # ChatBot logic: calls self.publish_control("control.workflow.run")
    chat_bot.publish_control("control.workflow.run")

    # 6. Verify ExplorerBot Reaction
    # In the mock environment, ExplorerBot won't actually scan (mc is mocked),
    # but it should log "Workflow started. Initiating scan."
    # Since we are running in the same thread here (publish is synchronous), we should see the log immediately.


if __name__ == "__main__":
    try:
        run_debug()
    except Exception as e:
        logger.exception("An error occurred during debug execution.")
