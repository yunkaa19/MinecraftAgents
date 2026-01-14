from strategies import MiningStrategy
import time

class VerticalSearch(MiningStrategy):
    """
    Implements a vertical strip-mining strategy.
    
    Digs straight down from the agent's current position to uncover resources.
    """
    def execute(self, agent):
        """
        Executes the vertical mining strategy.
        
        Args:
            agent: The agent executing the strategy.
        """
        agent.logger.info("Starting Vertical Search...")
        if not agent.mc:
            return

        pos = agent.mc.player.getTilePos()
        x, y, z = pos.x, pos.y, pos.z
        
        # Dig down 5 blocks
        for i in range(1, 6):
            target_y = y - i
            agent.logger.info(f"Digging at {x}, {target_y}, {z}")
            
            # Get block type before breaking
            block_id = agent.mc.getBlock(x, target_y, z)
            
            # Mine the block (Set to Air)
            agent.mc.setBlock(x, target_y, z, 0) # 0 is Air
            
            # TODO: Store 'block_id' in a real inventory system
            time.sleep(0.5)
            
        agent.logger.info("Vertical Search complete.")
