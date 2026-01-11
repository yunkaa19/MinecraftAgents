from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent
from core.utils import load_classes
from core.messaging import Message
from strategies import MiningStrategy
import time

class MinerBot(BaseAgent):
    """
    Agent responsible for gathering resources using various mining strategies.
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
        
        self.mining_queue = []
        self.locked_sectors = set()
        
        if self.bus:
            self.bus.subscribe("materials.requirements.v1", self.on_requirements_received)

    def load_strategies(self):
        self.logger.info("Loading mining strategies...")
        # We look for strategies in the 'strategies.mining' package
        strategy_classes = load_classes("strategies.mining", MiningStrategy)
        for strat_cls in strategy_classes:
            try:
                strategy = strat_cls()
                self.strategies.append(strategy)
                self.logger.info(f"Loaded strategy: {strat_cls.__name__}")
            except Exception as e:
                self.logger.error(f"Failed to instantiate strategy {strat_cls.__name__}: {e}")

    def on_requirements_received(self, message: Message):
        self.logger.info(f"Received material requirements from {message.source}")
        reqs = message.payload.get("requirements", {})
        if reqs:
            self.mining_queue.append(reqs)

    def perceive(self):
        pass

    def decide(self):
        if self.mining_queue and self.strategies:
            return "mine"
        return None

    def act(self):
        decision = self.decide()
        if decision == "mine":
            self.mine()

    def mine(self):
        if not self.mc:
            return

        req = self.mining_queue[0]
        self.logger.info(f"Processing mining request: {req}")
        
        # Simple locking mechanism: Lock the chunk the player is in
        pos = self.mc.player.getTilePos()
        sector = (pos.x // 16, pos.z // 16)
        
        if sector in self.locked_sectors:
            self.logger.warning(f"Sector {sector} is locked. Waiting...")
            return

        self.locked_sectors.add(sector)
        self.logger.info(f"Locked sector {sector}")
        
        try:
            # Execute the first available strategy
            # In a real system, we'd choose the best strategy for the material
            strategy = self.strategies[0]
            self.logger.info(f"Executing strategy: {strategy.__class__.__name__}")
            strategy.execute(self)
            
            # Simulate mining time
            time.sleep(2)
            
            # Notify completion
            msg = Message(
                type="inventory.v1",
                source=self.name,
                target="BuilderBot",
                payload={"inventory": req} # Mocking that we got everything
            )
            if self.bus:
                self.bus.publish(msg)
                
            self.mining_queue.pop(0)
            
        except Exception as e:
            self.logger.error(f"Mining failed: {e}")
        finally:
            self.locked_sectors.remove(sector)
            self.logger.info(f"Unlocked sector {sector}")

