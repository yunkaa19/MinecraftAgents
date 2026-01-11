from strategies import MiningStrategy
import time

class VerticalSearch(MiningStrategy):
    def execute(self, agent):
        agent.logger.info("Starting Vertical Search...")
        if not agent.mc:
            return

        pos = agent.mc.player.getTilePos()
        x, y, z = pos.x, pos.y, pos.z
        
        # Dig down 5 blocks
        for i in range(1, 6):
            target_y = y - i
            agent.logger.info(f"Digging at {x}, {target_y}, {z}")
            # agent.mc.setBlock(x, target_y, z, 0) # 0 is Air
            time.sleep(0.5)
            
        agent.logger.info("Vertical Search complete.")
