from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent
from core.messaging import Message
from core.utils import load_classes, log_execution
from strategies import ExplorationStrategy
from mcpi.vec3 import Vec3
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

        self.scan_range = 20
        self.scan_target = None

        # New: Queue for incoming scan requests
        self.scan_queue = []
        self.is_scanning = False

        if self.bus:
            # Workflow run triggers scan too
            self.bus.subscribe("control.workflow.run", self.on_start_scan)

            # Specific commands
            self.bus.subscribe("control.explorerbot.start", self.on_start_scan)
            self.bus.subscribe("control.explorerbot.stop", self.on_stop_scan)
            self.bus.subscribe("control.explorerbot.config", self.on_config)
            
        self._cancel_scan = False

    def _get_checkpoint_data(self):
        return {
            "scan_range": self.scan_range,
            "scan_target_x": self.scan_target.x if self.scan_target else None,
            "scan_target_z": self.scan_target.z if self.scan_target else None,
            "scan_queue": [
                (v.x, v.z) for v in self.scan_queue
            ],  # Simple tuple serialization
        }

    def _apply_checkpoint_data(self, data):
        self.scan_range = data.get("scan_range", 20)
        tx = data.get("scan_target_x")
        tz = data.get("scan_target_z")

        from mcpi.vec3 import Vec3

        if tx is not None and tz is not None:
            self.scan_target = Vec3(tx, 0, tz)

        queue_data = data.get("scan_queue", [])
        self.scan_queue = [Vec3(q[0], 0, q[1]) for q in queue_data]

    def on_start_scan(self, message: Message):
        """
        Handles requests to start a terrain scan.
        Queues the scan if one is already in progress.

        Args:
            message (Message): The control message containing start parameters.
        """
        payload = message.payload or {}
        x = payload.get("x")
        z = payload.get("z")
        rng = payload.get("range")

        if rng:
            self.scan_range = int(rng)

        target = None
        if x is not None and z is not None:
            target = Vec3(int(x), 0, int(z))

        if self.is_scanning:
            # INTERRUPT CONFIRMATION LOGIC (Ref: 4.1)
            # We require 'interrupt' AND 'confirm' to be present to stop a running scan
            should_interrupt = payload.get("interrupt")
            is_confirmed = payload.get("confirm", False)

            if should_interrupt:
                if is_confirmed:
                    self.logger.info("Interrupting current scan for high-priority request (Confirmed).")
                    self._cancel_scan = True
                    # Small wait to allow the loop to exit
                    time.sleep(0.5)
                    # Restart with new target
                    self.scan_target = target
                    if self.bus:
                         self.bus.publish(Message(type="control.explorerbot.start_internal", source=self.name, target=self.name, payload=payload))
                    return
                else:
                    self.logger.warning("Interruption requested but NOT confirmed. Queuing request instead.")
                    if self.mc:
                        self.mc.postToChat("[Explorer] Interruption requires 'confirm=True'. Queuing.")

            if target:
                self.logger.info(f"Scan already in progress. Queuing target: {target}")
                self.scan_queue.append(target)
                if self.mc:
                    self.mc.postToChat("[Explorer] Scan queued.")
            else:
                self.logger.warning(
                    "Scan in progress and no specific target provided to queue."
                )
        else:
            self.scan_target = target
            self.logger.info("Starting scan.")
            self.scan_terrain()

    def on_stop_scan(self, message: Message):
        self.logger.info("Acknowledged stop request.")
        self._cancel_scan = True
        self.is_scanning = False
        # In a real threaded scenario, we'd need a flag to stop the loop in 'scan_terrain'
        # For now, this just acknowledges it.

    def on_config(self, message: Message):
        payload = message.payload or {}
        if "range" in payload:
            self.scan_range = int(payload["range"])
            self.logger.info(f"Scan range set to {self.scan_range}")

    def get_additional_status(self):
        return {
            "scan_range": self.scan_range,
            "target": str(self.scan_target) if self.scan_target else "Player",
            "queue_len": len(self.scan_queue),
            "is_scanning": self.is_scanning,
        }

    def load_strategies(self):
        """
        Dynamically loads exploration strategies from the 'strategies.exploration' package.
        """
        self.logger.info("Loading exploration strategies...")
        strategy_classes = load_classes("strategies.exploration", ExplorationStrategy)
        for strat_cls in strategy_classes:
            try:
                strategy = strat_cls()
                self.strategies.append(strategy)
                self.logger.info(f"Loaded strategy: {strat_cls.__name__}")
            except Exception as e:
                self.logger.error(
                    f"Failed to instantiate strategy {strat_cls.__name__}: {e}"
                )

    def perceive(self):
        pass

    def decide(self):
        return None

    def act(self):
        pass

    @log_execution
    def scan_terrain(self):
        """
        Executes the terrain scanning logic using the 'RadialScan' strategy.
        Identifies flat spots and publishes the findings to the message bus.
        """
        if not self.mc:
            return

        if not self.strategies:
            self.logger.error("No exploration strategies loaded!")
            return

        self.is_scanning = True
        self._cancel_scan = False

        # Determine actual target to scan (Current request OR player pos)
        center = self.scan_target or self.mc.player.getTilePos()

        # Execute the first available strategy
        strategy = self.strategies[0]
        self.logger.info(
            f"Executing exploration strategy: {strategy.__class__.__name__}"
        )

        try:
            result = strategy.execute(self)

            if result and result.get("flat_spots"):
                flat_spots = result["flat_spots"]
                self.logger.info(
                    f"Found {len(flat_spots)} flat spots at {flat_spots[0]}"
                )

                # Publish map data
                msg = Message(
                    type="map.v1", source=self.name, target="all", payload=result
                )
                if self.bus:
                    self.bus.publish(msg)
            else:
                self.logger.warning(
                    f"No flat spots found using {strategy.__class__.__name__}."
                )

            self.last_scan_time = time.time()

        except Exception as e:
            self.logger.error(f"Error during scanning: {e}")
        finally:
            self.is_scanning = False

            # Check queue!
            if self.scan_queue:
                next_target = self.scan_queue.pop(0)
                self.logger.info(f"Processing queued scan target: {next_target}")
                self.scan_target = next_target
                # Recursive call to process next item?
                # Safer to let the main loop handle it, but we are event driven here.
                # Let's call scan_terrain again immediately.
                self.scan_terrain()
