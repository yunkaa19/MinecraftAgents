from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent, AgentState
from core.messaging import Message
import time
import mcpi.block as block


class LumberBot(BaseAgent):
    """
    Agent dedicated to finding and harvesting wood/trees.
    """

    def __init__(self, name, message_bus=None):
        super().__init__(name, message_bus)
        try:
            self.mc = Minecraft.create()
        except Exception as e:
            self.logger.error(f"Failed to connect to Minecraft: {e}")
            self.mc = None

        self.wood_inventory = 0
        self.pending_req = 0

        if self.bus:
            self.bus.subscribe(
                "materials.requirements.v1", self.on_requirements_received
            )

    def on_requirements_received(self, message: Message):
        """Checks if WOOD is needed."""
        reqs = message.payload.get("requirements", {})

        # We handle WOOD and WOOD_PLANKS (converted to wood equivalent)
        needed = reqs.get("WOOD", 0)

        # 1 Wood = 4 Planks. So if we need 40 Planks, we need 10 Wood.
        if "WOOD_PLANKS" in reqs:
            needed += reqs["WOOD_PLANKS"] / 4

        if needed > 0:
            self.logger.info(f"LumberBot activated. Need approx {needed} wood blocks.")
            self.pending_req += needed

    def perceive(self):
        pass

    def decide(self):
        if self.pending_req > 0:
            return "chop"
        return None

    def act(self):
        decision = self.decide()
        if decision == "chop":
            self.harvest_wood()

    def _check_pause(self):
        """Helper to pause execution."""
        while self.state == AgentState.PAUSED:
            time.sleep(1)
        if self.state == AgentState.STOPPED:
            raise InterruptedError("Agent stopped")

    def harvest_wood(self):
        if not self.mc:
            return

        # Strategy: Look for wood blocks above ground
        # Scan a wide area around player
        pos = self.mc.player.getTilePos()
        search_radius = 20
        height_search = 10

        self.logger.info("Scanning for trees...")

        try:
            found_tree = False
            for x in range(-search_radius, search_radius):
                for z in range(-search_radius, search_radius):
                    for y in range(0, height_search):
                        self._check_pause()

                        target_x = pos.x + x
                        target_y = pos.y + y
                        target_z = pos.z + z

                        block_id = self.mc.getBlock(target_x, target_y, target_z)

                        if block_id == 17:  # Wood ID
                            self.logger.info(f"Tree found at {target_x}, {target_z}!")
                            self._chop_tree(target_x, target_y, target_z)
                            found_tree = True

                            # Check if we have enough
                            if self.wood_inventory >= self.pending_req:
                                self._deliver_wood()
                                return

            if not found_tree:
                self.logger.warning(
                    "No trees found in immediate area. Waiting before rescanning..."
                )
                time.sleep(5)

        except InterruptedError:
            self.logger.info("Lumbering stopped.")

    def _chop_tree(self, x, y, z):
        """Chops a vertical column of wood."""
        # Check up to 10 blocks high for the tree trunk
        for i in range(10):
            current_y = y + i
            bid = self.mc.getBlock(x, current_y, z)

            if bid == 17:  # Wood
                self.mc.setBlock(x, current_y, z, block.AIR.id)
                self.wood_inventory += 1
                self.logger.info(f"Chopped wood. Total: {self.wood_inventory}")
                time.sleep(0.5)
            else:
                # Top of trunk reached
                break

    def _deliver_wood(self):
        self.logger.info(f"Delivering {self.wood_inventory} wood blocks.")
        if self.mc:
            self.mc.postToChat(
                f"LumberBot: Harvesting complete. Delivering {self.wood_inventory} Wood."
            )

        # We send what we have as raw WOOD
        payload = {"WOOD": self.wood_inventory}

        msg = Message(
            type="inventory.v1",
            source=self.name,
            target="MinerBot",  # Send to MinerBot so it can craft/distribute? Or Builder directly?
            # Actually, let's send to MinerBot so MinerBot can merge it into his inventory logic
            # OR send to BuilderBot directly.
            # But the system expectation is MinerBot fulfills BOM.
            # Let's effectively "give" it to the MinerBot's inventory by sending a special internal update
            # OR just send to BuilderBot and hope BuilderBot aggregates.
            # The cleanest way given current architecture:
            payload={"inventory": payload},
        )
        if self.bus:
            # We publish to BuilderBot just like MinerBot does.
            # Use same message type so BuilderBot accepts it.
            # BuilderBot receives inventory.v1 and logs/stores it.
            self.bus.publish(msg)

        self.wood_inventory = 0
        self.pending_req = 0
