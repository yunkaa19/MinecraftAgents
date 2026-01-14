from strategies import MiningStrategy
import mcpi.block as block
import time

class VeinMiner(MiningStrategy):
    """
    Mines an entire vein of ore by recursively checking neighbors.
    """
    
    def execute(self, agent):
        """
        Executes the vein mining strategy.
        
        Args:
            agent: The agent executing the strategy.
        """
        agent.logger.info("Starting Vein Miner Strategy...")
        if not agent.mc:
            return

        # Start at player's position
        pos = agent.mc.player.getTilePos()
        
        # Check the block directly below
        target_block_id = agent.mc.getBlock(pos.x, pos.y - 1, pos.z)
        
        # We only want to vein mine valuable ores (e.g., Coal, Iron, Gold, Diamond)
        # IDs: Coal=16, Iron=15, Gold=14, Diamond=56
        valuable_ores = [16, 15, 14, 56]
        
        if target_block_id not in valuable_ores:
            agent.logger.info(f"Block below (ID {target_block_id}) is not a target ore. Aborting.")
            return

        agent.logger.info(f"Found valuable ore (ID {target_block_id}). Starting vein mine.")
        self._mine_vein(agent, pos.x, pos.y - 1, pos.z, target_block_id, set())

    def _mine_vein(self, agent, x, y, z, target_id, visited):
        """
        Recursive function to mine connected blocks of the same ID.
        """
        if (x, y, z) in visited:
            return
        
        visited.add((x, y, z))
        
        # Verify block is still the target (it might have changed or we might have drifted)
        current_id = agent.mc.getBlock(x, y, z)
        if current_id != target_id:
            return

        # Mine the block
        agent.mc.setBlock(x, y, z, block.AIR.id)
        agent.logger.info(f"Mined ore at {x}, {y}, {z}")
        time.sleep(0.5)

        # Check neighbors (Standard 6 directions)
        neighbors = [
            (x+1, y, z), (x-1, y, z),
            (x, y+1, z), (x, y-1, z),
            (x, y, z+1), (x, y, z-1)
        ]

        for nx, ny, nz in neighbors:
            if agent.mc.getBlock(nx, ny, nz) == target_id:
                self._mine_vein(agent, nx, ny, nz, target_id, visited)
