from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent
from core.messaging import Message
from core.utils import load_classes
from strategies import BuildingStrategy
import time

class BuilderBot(BaseAgent):
    """
    Agent responsible for constructing buildings based on map data and available materials.
    """
    def __init__(self, name, message_bus=None):
        super().__init__(name, message_bus)
        try:
            self.mc = Minecraft.create()
        except Exception as e:
            self.logger.error(f"Failed to connect to Minecraft: {e}")
            self.mc = None
        
        self.strategies = []
        # Store strategies as a dict for lookup: name -> instance
        self.strategy_map = {}
        self.load_strategies()
        self.pending_builds = []
        self.current_scan_results = []
        
        if self.bus:
            self.bus.subscribe("map.v1", self.on_map_received)
            self.bus.subscribe("inventory.v1", self.on_inventory_received)
            self.bus.subscribe("control.build.select", self.on_build_select)

    def load_strategies(self):
        self.logger.info("Loading building strategies...")
        strategy_classes = load_classes("strategies.building", BuildingStrategy)
        for strat_cls in strategy_classes:
            try:
                # Assuming strategies don't need args for now
                strategy = strat_cls()
                self.strategies.append(strategy)
                # Key: Class name lower, e.g. "simplehutstrategy", "simplehut", "stonetower"
                # Let's map "SimpleHutStrategy" -> simplehut, "StoneTower" -> stonetower
                key = strat_cls.__name__.lower().replace("strategy", "")
                self.strategy_map[key] = strategy
                self.logger.info(f"Loaded strategy: {strat_cls.__name__} as '{key}'")
            except Exception as e:
                self.logger.error(f"Failed to instantiate strategy {strat_cls.__name__}: {e}")

    def on_map_received(self, message: Message):
        self.logger.info(f"Received map data from {message.source}")
        flat_spots = message.payload.get("flat_spots", [])
        
        if flat_spots:
            self.current_scan_results = flat_spots
            self.logger.info(f"Stored {len(flat_spots)} build sites.")
            
            # Announce available strategies
            options = list(self.strategy_map.keys())
            options_str = ", ".join(options)
            
            # We can't post to chat easily unless we implement it or send a message to ChatBot
            # Let's send a notification
            if self.bus:
                 # Hack: using ChatBot to announce
                 # Or just wait for user. A notification message type would be cleaner.
                 # For now, let's just log it, assuming ChatBot already said "Found spots"
                 pass
        else:
             self.logger.warning("No flat spots received.")

    def on_build_select(self, message: Message):
        """
        Triggered when user types 'build <type>'
        """
        struct_type = message.payload.get("structure_type", "").lower()
        self.logger.info(f"Received build request for '{struct_type}'")
        
        if not self.current_scan_results:
            self.logger.warning("Cannot build: No site selected/scanned yet.")
            return

        if struct_type in self.strategy_map:
            strategy = self.strategy_map[struct_type]
            target = self.current_scan_results[0]
            
            self.logger.info(f"Initiating build of {struct_type} at {target}")
            
            bom = strategy.get_bom()
            
            self.pending_builds.append({
                "location": target,
                "strategy": strategy,
                "bom": bom,
                "status": "waiting_for_materials"
            })
            
            # Publish requirements
            req_msg = Message(
                type="materials.requirements.v1",
                source=self.name,
                target="MinerBot",
                payload={"requirements": bom}
            )
            if self.bus:
                self.bus.publish(req_msg)
        else:
            self.logger.warning(f"Unknown structure type: {struct_type}. Available: {list(self.strategy_map.keys())}")

    def on_inventory_received(self, message: Message):
        self.logger.info(f"Received inventory update from {message.source}")
        # In a real implementation, we would check if we have enough materials
        # For now, we'll assume if we get an inventory update, we can build
        self.build_structure()

    def perceive(self):
        pass

    def decide(self):
        pass

    def act(self):
        pass

    def build_structure(self):
        if not self.pending_builds:
            return

        build_task = self.pending_builds[0]
        if build_task["status"] == "waiting_for_materials":
            self.logger.info("Starting construction...")
            
            # Unpack
            target = build_task["location"]
             # Explorer sent (x, z, height)
             # Our strategy expects (x, z, height) or (x, z, y)?
             # In explorer_bot.py: (c[0], c[1], self.mc.getHeight(c[0], c[1]))
             # So target is (x, z, y)
             # But strategy.execute expects (x, z, y) or (x, y, z)?
             # Let's check SimpleHutStrategy.execute: x, z, y = location.
             # Wait, explorer sends (x, z, y_height).
             # So unpacking x, z, y = target works perfect.
            
            strategy = build_task["strategy"]
            
            self.logger.info(f"Executing {strategy.__class__.__name__} at {target}")
            strategy.execute(self, target)
            
            self.logger.info("Construction complete.")
            self.pending_builds.pop(0)
