from strategies import BuildingStrategy
from core.fsm import AgentState
import mcpi.block as block
import time


class StoneTowerStrategy(BuildingStrategy):
    """Builds a simple vertical stone tower."""

    def get_bom(self):
        """Returns the Bill of Materials needed for the tower."""
        # 3x3 base, 10 high = 9*10 = 90 blocks (hollow? let's do solid for simplicity or hollow)
        # Hollow: 8 blocks per ring * 10 rings = 80 blocks.
        return {"STONE": 80, "TORCH": 4}

    def execute(self, agent, location):
        """Executes the building strategy at the given location."""
        if not agent.mc:
            return

        x, z, y = location
        agent.logger.info(f"Building Stone Tower at {x}, {y}, {z}")

        # Build 10 layers high
        for i in range(10):
            # Check for pause
            while agent.state == AgentState.PAUSED:
                time.sleep(1)
            if agent.state == AgentState.STOPPED:
                return

            current_y = y + i
            # 3x3 hollow square
            for dx in range(-1, 2):
                for dz in range(-1, 2):
                    # skip center
                    if dx == 0 and dz == 0:
                        continue
                    agent.place_block(x + dx, current_y, z + dz, block.STONE.id)

            time.sleep(0.5)

        # Add torches on top
        agent.place_block(x, y + 10, z, block.TORCH.id)
        agent.logger.info("Stone Tower complete.")
