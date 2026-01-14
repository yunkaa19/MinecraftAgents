import time
import logging
import threading
from core.messaging import MessageBus
from core.base_agent import BaseAgent
from core.utils import load_classes


def main():
    """
    Main entry point for the Minecraft Multi-Agent System.

    Initializes the logging system, creates the central message bus,
    dynamically discovers and loads agent classes, and starts each agent
    in its own thread.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("Main")

    logger.info("Initializing Minecraft Multi-Agent System...")

    bus = MessageBus()
    logger.info("Discovering agents in 'agents' package...")
    agent_classes = load_classes("agents", BaseAgent)

    agents = []

    if not agent_classes:
        logger.warning("No agents found in 'agents' directory.")

    for agent_cls in agent_classes:
        try:
            # Instantiate agent with the bus
            agent = agent_cls(name=agent_cls.__name__, message_bus=bus)
            agents.append(agent)
            logger.info(f"Loaded agent: {agent.name}")

            t = threading.Thread(target=agent.start, daemon=True)
            t.start()

        except Exception as e:
            logger.error(f"Failed to load/start agent {agent_cls.__name__}: {e}")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for agent in agents:
            agent.stop()


if __name__ == "__main__":
    main()
