from strategies import MiningStrategy
import mcpi.block as block
from core.fsm import AgentState
import time


class VeinMiner(MiningStrategy):
    """
    Mines an entire vein of ore by recursively checking neighbors.
    """

    def _check_pause(self, agent):
        """Helper to pause execution if agent is paused."""
        while agent.state == AgentState.PAUSED:
            time.sleep(1)
        if agent.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def execute(self, agent, start_loc=None):
        """
        Executes the vein mining strategy.

        Args:
            agent: The agent executing the strategy.
            start_loc: Optional (x, y, z) tuple to start mining from.
        """
        agent.logger.info("Starting Vein Miner Strategy...")
        if not agent.mc:
            return

        # Start at provided location or player's position
        if start_loc:
            x, y, z = start_loc
        else:
            pos = agent.mc.player.getTilePos()
            x, y, z = pos.x, pos.y, pos.z

        # Check the block directly below
        target_block_id = agent.mc.getBlock(x, y - 1, z)

        # We only want to vein mine valuable ores (e.g., Coal, Iron, Gold, Diamond)
        # IDs: Coal=16, Iron=15, Gold=14, Diamond=56
        valuable_ores = [16, 15, 14, 56]

        if target_block_id not in valuable_ores:
            agent.logger.info(
                f"Block below (ID {target_block_id}) is not a target ore. Aborting."
            )
            # Returns empty loot
            return {}

        agent.logger.info(
            f"Found valuable ore (ID {target_block_id}). Starting vein mine."
        )
        try:
            return self._mine_vein(agent, x, y - 1, z, target_block_id, set())
        except InterruptedError:
            agent.logger.info("Strategy execution interrupted.")
            return {}

    def _mine_vein(self, agent, x, y, z, target_id, visited):
        """
        Recursive function to mine connected blocks of the same ID.
        """
        self._check_pause(agent)

        loot = {}
        if (x, y, z) in visited:
            return loot

        visited.add((x, y, z))

        # Verify block is still the target (it might have changed or we might have drifted)
        current_id = agent.mc.getBlock(x, y, z)
        if current_id != target_id:
            return loot

        # Mine the block
        agent.mc.setBlock(x, y, z, block.AIR.id)
        agent.logger.info(f"Mined ore at {x}, {y}, {z}")

        # Only counting the target ore for simplicity
        # We need to map ID to name for loot
        # Assuming we don't have access to get_block_name easily here unless we import it
        # Since this file didn't have it imported, let's just use string key "ORE" for now or fix imports
        loot["ORE"] = 1

        time.sleep(0.5)

        # Check neighbors (Standard 6 directions)
        neighbors = [
            (x + 1, y, z),
            (x - 1, y, z),
            (x, y + 1, z),
            (x, y - 1, z),
            (x, y, z + 1),
            (x, y, z - 1),
        ]

        for nx, ny, nz in neighbors:
            if agent.mc.getBlock(nx, ny, nz) == target_id:
                res = self._mine_vein(agent, nx, ny, nz, target_id, visited)
                for k, v in res.items():
                    loot[k] = loot.get(k, 0) + v

        return loot
