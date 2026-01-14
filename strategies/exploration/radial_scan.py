from strategies import ExplorationStrategy


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

        # Determine scan center
        center_pos = getattr(agent, "scan_target", None)
        if not center_pos:
            center_pos = agent.mc.player.getTilePos()

        # Determine scan range
        scan_range = getattr(agent, "scan_range", 10)

        agent.logger.info(
            f"Scanning range {scan_range} around {center_pos.x}, {center_pos.z}"
        )

        pos = center_pos

        # Generate coordinates
        coords = [
            (pos.x + x, pos.z + z)
            for x in range(-scan_range, scan_range)
            for z in range(-scan_range, scan_range)
        ]

        # Functional Programming: Use map() to transform coordinates to (x, z, height)
        def get_terrain_data(c):
            return (c[0], c[1], agent.mc.getHeight(c[0], c[1]))

        flat_spots = []
        batch_size = 20 # Small batches for responsiveness
        
        from core.messaging import Message
        import time

        total_batches = len(coords) // batch_size + 1
        
        for i in range(0, len(coords), batch_size):
            # Interruption Check
            if getattr(agent, "_cancel_scan", False):
                agent.logger.info("Radial Scan cancelled by agent.")
                return None

            chunk = coords[i : i + batch_size]
            
            # Apply functional transformations on the chunk
            chunk_data = list(map(get_terrain_data, chunk))
            chunk_flat = list(filter(lambda d: abs(d[2] - pos.y) <= 1, chunk_data))
            flat_spots.extend(chunk_flat)

            # Periodic Update (every 5 batches ~100 blocks)
            if chunk_flat and (i // batch_size) % 5 == 0:
                if agent.bus:
                     # Helper to publish partial
                     payload = {
                        "center": {"x": pos.x, "y": pos.y, "z": pos.z},
                        "flat_spots": chunk_flat, # Only new ones
                        "status": "partial",
                        "timestamp": time.time()
                     }
                     msg = Message(type="map.v1", source=agent.name, target="all", payload=payload)
                     agent.bus.publish(msg)

        agent.logger.info(f"Radial Scan complete. Found {len(flat_spots)} spots.")

        return {
            "center": {"x": pos.x, "y": pos.y, "z": pos.z},
            "flat_spots": flat_spots, # Full list
            "status": "complete"
        }
