from strategies import MiningStrategy
from core.utils import get_block_name
from core.fsm import AgentState
import time


class VerticalSearch(MiningStrategy):
    """
    Implements a vertical shaft mining strategy.

    Digs a single 1x1 shaft straight down from the starting coordinates until bedrock or a max depth is reached.
    """

    def _check_pause(self, agent):
        """Helper to pause execution if agent is paused."""
        while agent.state == AgentState.PAUSED:
            time.sleep(1)
        if agent.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def execute(self, agent, start_loc=None):
        """
        Executes the vertical mining strategy.

        Args:
            agent: The agent executing the strategy.
            start_loc: Optional (x, y, z) tuple to start mining from.

        Returns:
            dict: The resources mined.
        """
        agent.logger.info("Starting Vertical Excavation...")
        if not agent.mc:
            return {}

        if start_loc:
            start_x, y, start_z = start_loc
        else:
            pos = agent.mc.player.getTilePos()
            start_x, y, start_z = pos.x, pos.y, pos.z

        loot = {}
        max_depth = 50

        try:
            for depth in range(max_depth):
                self._check_pause(agent)
                target_y = y - depth

                block_id = agent.mc.getBlock(start_x, target_y, start_z)

                if block_id == 7:  # Bedrock
                    agent.logger.info("Hit Bedrock. Stopping.")
                    break

                if block_id != 0:
                    block_name = get_block_name(block_id)
                    loot[block_name] = loot.get(block_name, 0) + 1
                    agent.mc.setBlock(start_x, target_y, start_z, 0)

                time.sleep(0.5)

        except InterruptedError:
            agent.logger.info("Strategy execution interrupted.")
            return loot

        agent.logger.info(f"Vertical Search complete. Yield: {loot}")
        return loot
