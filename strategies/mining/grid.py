from strategies import MiningStrategy
import time

class GridSearch(MiningStrategy):
    """
    Implements a surface grid mining strategy.
    
    Scans and mines a 3x3 grid area at the agent's current level.
    """
    def execute(self, agent):
        """
        Executes the grid mining strategy.
        
        Args:
            agent: The agent executing the strategy.
        """
        agent.logger.info("Starting Grid Search...")
        if not agent.mc:
            return

        pos = agent.mc.player.getTilePos()
        start_x, y, start_z = pos.x, pos.y, pos.z
        
        # 3x3 Grid
        for x_offset in range(3):
            for z_offset in range(3):
                target_x = start_x + x_offset
                target_z = start_z + z_offset
                
                # Check block below feet
                check_y = y - 1
                
                agent.logger.info(f"Checking surface at {target_x}, {check_y}, {target_z}")
                block_id = agent.mc.getBlock(target_x, check_y, target_z)
                
                # If it's not Air (0) or Bedrock (7), mine it
                if block_id != 0 and block_id != 7:
                    agent.logger.info(f"Mining block ID {block_id}")
                    agent.mc.setBlock(target_x, check_y, target_z, 0)
                
                time.sleep(0.2)
                
        agent.logger.info("Grid Search complete.")
