from strategies import ExplorationStrategy
import time

class RadialScan(ExplorationStrategy):
    """
    Scans the terrain in a radial pattern around the agent.
    
    This strategy finds flat spots where the terrain height is level with the agent's current position.
    """
    def execute(self, agent):
        """
        Executes the radial scan.
        
        Args:
            agent: The agent instance executing the strategy.
            
        Returns:
            dict: The scan results containing the center position and list of flat spots.
        """
        if not agent.mc:
            return None

        agent.logger.info("Strategies: Radial Scan started...")
        pos = agent.mc.player.getTilePos()
        
        # Scan a 10x10 grid centered on the player
        scan_range = 5
        
        # Generate coordinates
        coords = [(pos.x + x, pos.z + z) 
                  for x in range(-scan_range, scan_range) 
                  for z in range(-scan_range, scan_range)]
        
        # Map to (x, z, height)
        # Using a tuple for immutable coordinates
        terrain_data = []
        for c in coords:
            h = agent.mc.getHeight(c[0], c[1])
            terrain_data.append((c[0], c[1], h))
        
        # Filter for "flat" spots (heuristic: height is close to player height)
        flat_spots = list(filter(lambda d: abs(d[2] - pos.y) <= 1, terrain_data))
        
        agent.logger.info(f"Radial Scan complete. Found {len(flat_spots)} spots.")
        
        return {
            "center": {"x": pos.x, "y": pos.y, "z": pos.z},
            "flat_spots": flat_spots
        }
