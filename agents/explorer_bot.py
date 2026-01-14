from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent
from core.messaging import Message
from core.utils import load_classes, log_execution
from strategies import ExplorationStrategy
import time

class ExplorerBot(BaseAgent):
    """
    Agent responsible for scanning the terrain and identifying build sites.
    """
    def __init__(self, name, message_bus=None):
        super().__init__(name, message_bus)
        try:
            self.mc = Minecraft.create()
        except Exception as e:
            self.logger.error(f"Failed to connect to Minecraft: {e}")
            self.mc = None
            
        self.strategies = []
        self.load_strategies()
        
        if self.bus:
            self.bus.subscribe("control.workflow.run", self.on_workflow_run)

    def load_strategies(self):
        self.logger.info("Loading exploration strategies...")
        strategy_classes = load_classes("strategies.exploration", ExplorationStrategy)
        for strat_cls in strategy_classes:
            try:
                strategy = strat_cls()
                self.strategies.append(strategy)
                self.logger.info(f"Loaded strategy: {strat_cls.__name__}")
            except Exception as e:
                self.logger.error(f"Failed to instantiate strategy {strat_cls.__name__}: {e}")

    def on_workflow_run(self, message: Message):
        self.logger.info("Workflow started. Initiating scan.")
        self.scan_terrain()

    def perceive(self):
        pass

    def decide(self):
        return None

    def act(self):
        pass

    @log_execution
    def scan_terrain(self):
        """Scans the terrain using the loaded exploration strategy."""
        if not self.mc:
            return

        if not self.strategies:
            self.logger.error("No exploration strategies loaded!")
            return

        # Execute the first available strategy
        strategy = self.strategies[0]
        self.logger.info(f"Executing exploration strategy: {strategy.__class__.__name__}")
        
        try:
            result = strategy.execute(self)
            
            if result and result.get("flat_spots"):
                flat_spots = result["flat_spots"]
                self.logger.info(f"Found {len(flat_spots)} flat spots at {flat_spots[0]}")
                
                # Publish map data
                msg = Message(
                    type="map.v1",
                    source=self.name,
                    target="all",
                    payload=result
                )
                if self.bus:
                    self.bus.publish(msg)
            else:
                pos = self.mc.player.getTilePos()
                self.logger.warning(f"No flat spots found using {strategy.__class__.__name__}.")
            
            self.last_scan_time = time.time()
            
        except Exception as e:
            self.logger.error(f"Error during scanning: {e}")
