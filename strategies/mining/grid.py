from strategies import MiningStrategy
import time

class GridSearch(MiningStrategy):
    def execute(self, agent):
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
                agent.logger.info(f"Checking surface at {target_x}, {y}, {target_z}")
                # block_id = agent.mc.getBlock(target_x, y - 1, target_z)
                time.sleep(0.2)
                
        agent.logger.info("Grid Search complete.")
