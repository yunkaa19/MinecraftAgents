from strategies import MiningStrategy
from core.utils import get_block_name
from core.fsm import AgentState
import time


class GridSearch(MiningStrategy):
    """
    Implements a surface grid mining strategy.

    Scans and mines a 9x9 grid area centered at the target location.
    """

    def _check_pause(self, agent):
        """Helper to pause execution if agent is paused."""
        while agent.state == AgentState.PAUSED:
            time.sleep(1)
        if agent.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def execute(self, agent, start_loc=None):
        """
        Executes the grid mining strategy.

        Args:
            agent: The agent executing the strategy.
            start_loc: Optional (x, y, z) tuple to start mining from.

        Returns:
            dict: The resources mined.
        """
        agent.logger.info("Starting Broad Grid Search (9x9)...")
        if not agent.mc:
            return {}

        if start_loc:
            start_x, y, start_z = start_loc
        else:
            pos = agent.mc.player.getTilePos()
            start_x, y, start_z = pos.x, pos.y, pos.z

        loot = {}

        # 3x3 Grid (Radius 1), Depth 15
        radius = 1
        max_depth = 15
        try:
            for x_offset in range(-radius, radius + 1):
                for z_offset in range(-radius, radius + 1):
                    for depth in range(max_depth):
                        self._check_pause(agent)

                        target_x = start_x + x_offset
                        target_z = start_z + z_offset
                        target_y = y - depth

                        block_id = agent.mc.getBlock(target_x, target_y, target_z)

                        # If it's not Air (0) or Bedrock (7), mine it
                        if block_id not in [0, 7]:
                            block_name = get_block_name(block_id)
                            loot[block_name] = loot.get(block_name, 0) + 1
                            agent.mc.setBlock(
                                target_x, target_y, target_z, 0
                            )  # Set to Air
                            # agent.logger.info(f"Mined {block_name}")

        except InterruptedError:
            agent.logger.info("Strategy execution interrupted.")
            return loot

        agent.logger.info(f"Grid Search complete. Yield: {loot}")
        return loot
