from strategies import BuildingStrategy
from core.fsm import AgentState
import mcpi.block as block
import time

class SimpleHutStrategy(BuildingStrategy):
    """A strategy for building a simple small hut."""

    def _check_pause(self, agent):
        """Helper to pause execution if agent is paused."""
        while agent.state == AgentState.PAUSED:
            time.sleep(1)
        if agent.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def get_bom(self):
        """Returns the Bill of Materials needed for the hut."""
        # 5x5 floor = 25 blocks
        # Walls: 5*4 perimeter * 3 height = 60 blocks - door (2) = 58
        return {"COBBLESTONE": 25, "WOOD_PLANKS": 58}

    def execute(self, agent, location):
        """Builds the hut at the specified location."""
        if not agent.mc:
            return

        x, z, y = location
        # Adjust y to be on the ground (since we got height, likely the surface block)
        # We want to build *on top* of the reported height?
        # Explorer sent (x, z, height). Height is usually the y of the highest non-air block.
        # So we build starting at y+1? Or replace the surface?
        # Let's assume y is the surface block, so floor replaces it? Or goes on top?
        # Let's build ON TOP for safety.
        
        agent.logger.info(f"Building Simple Hut at {x}, {y}, {z}")
        
        # Floor (5x5) centered on x,z
        # Let's say x,z is the center
        start_x = x - 2
        start_z = z - 2
        floor_y = y
        
        mc = agent.mc
        
        # Build Floor
        agent.logger.info("Building floor...")
        for dx in range(5):
            for dz in range(5):
                mc.setBlock(start_x + dx, floor_y, start_z + dz, block.COBBLESTONE.id)
                time.sleep(0.1) # Cool effect

        # Build Walls
        agent.logger.info("Building walls...")
        try:
            for dy in range(1, 4): # Height 1, 2, 3 above floor
                self._check_pause(agent)
                agent.mc.postToChat(f"[Builder] Building Hut Walls (Layer {dy}/3)...")
                for dx in range(5):
                    for dz in range(5):
                        # Only edges
                        if dx == 0 or dx == 4 or dz == 0 or dz == 4:
                            # Leave door gap at one side
                            if dx == 2 and dz == 0 and dy < 3: # Front door
                                 mc.setBlock(start_x + dx, floor_y + dy, start_z + dz, block.AIR.id)
                            else:
                                 mc.setBlock(start_x + dx, floor_y + dy, start_z + dz, block.WOOD_PLANKS.id)
                time.sleep(1.0)
    
            # Build Roof (Pyramid)
            agent.logger.info("Building roof...")
            roof_y = floor_y + 4
            # Layer 1 (5x5, Air inside? No, let's just do blocks)
            # Actually easiest is concentric squares
            for i in range(3): # 2 layers
                self._check_pause(agent)
                agent.mc.postToChat(f"[Builder] Building Roof (Layer {i+1}/3)...")
                # width 5, 3, 1
                width = 5 - (i*2)
                current_y = roof_y + i
                start_off = i
                for r_dx in range(width):
                     for r_dz in range(width):
                         mc.setBlock(start_x + start_off + r_dx, current_y, start_z + start_off + r_dz, block.WOOD.id)
                time.sleep(1.0)
                
        except InterruptedError:
            agent.logger.info("Build interrupted.")
            return

        agent.logger.info("Simple Hut complete.")
        agent.mc.postToChat("[Builder] Simple Hut finished!")
