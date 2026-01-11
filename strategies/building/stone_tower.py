from strategies import BuildingStrategy
from core.fsm import AgentState
import mcpi.block as block
import time

class StoneTower(BuildingStrategy):
    def _check_pause(self, agent):
        """Helper to pause execution if agent is paused."""
        while agent.state == AgentState.PAUSED:
            time.sleep(1)
        if agent.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def get_bom(self):
        # 4x4 base, 10 high. 
        # Perimeter 12 blocks per layer. 12 * 10 = 120 blocks.
        return {"STONE": 120}

    def execute(self, agent, location):
        if not agent.mc:
            return

        x, z, y = location
        mc = agent.mc
        
        agent.logger.info(f"Building Stone Tower at {x}, {y}, {z}")
        
        start_x = x - 1
        start_z = z - 1
        floor_y = y

        height = 10
        
        try:
            for h in range(height):
                self._check_pause(agent)
                agent.mc.postToChat(f"[Builder] Building Tower Layer {h+1}/{height}...")
                # 4x4 Ring
                for dx in range(4):
                    for dz in range(4):
                        # Edges
                        if dx == 0 or dx == 3 or dz == 0 or dz == 3:
                            # Add some "battlements" at the top
                            if h == height - 1:
                                if (dx+dz) % 2 == 0:
                                    mc.setBlock(start_x + dx, floor_y + h, start_z + dz, block.STONE.id)
                            else:
                                # Standard wall
                                # Leave space for a "window"
                                if h == 8 and (dx == 1 or dx == 2) and (dz == 0):
                                    pass # Window
                                else:
                                    mc.setBlock(start_x + dx, floor_y + h, start_z + dz, block.STONE.id)
                time.sleep(1.0)
                
        except InterruptedError:
            agent.logger.info("Build interrupted.")
            return
            
        agent.logger.info("Stone Tower complete.")
        agent.mc.postToChat("[Builder] Stone Tower finished!")
