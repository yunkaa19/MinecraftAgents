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
        self.selected_strategy_key = None
        
        # Layer tracking
        self.current_layer_y = None
        self.current_layer_stats = {}

        if self.bus:
            self.bus.subscribe("map.v1", self.on_map_received)
            self.bus.subscribe("inventory.v1", self.on_inventory_received)
            self.bus.subscribe("control.builderbot.plan.list", self.on_list_plans)
            self.bus.subscribe("control.builderbot.plan.set", self.on_set_plan)
            self.bus.subscribe("control.builderbot.bom", self.on_bom_request)
            self.bus.subscribe("control.builderbot.build", self.on_build_command)
            self.bus.subscribe("control.workflow.run", self.on_workflow_run)

    def _get_checkpoint_data(self):
        # We can't easily serialize 'strategy' objects in pending_builds.
        # So we'll save the 'template_key' and recreate it.
        serializable_builds = []
        for b in self.pending_builds:
            item = b.copy()
            if "strategy" in item:
                # Save the key name instead of object
                # We need to find the key for this strategy instance
                for key, val in self.strategy_map.items():
                    if val == item["strategy"]:
                        item["strategy_key"] = key
                        break
                del item["strategy"]
            serializable_builds.append(item)

        return {
            "pending_builds": serializable_builds,
            "selected_strategy_key": self.selected_strategy_key,
            "current_scan_results": self.current_scan_results,  # Assuming tuples/lists
        }

    def _apply_checkpoint_data(self, data):
        self.selected_strategy_key = data.get("selected_strategy_key")
        self.current_scan_results = data.get("current_scan_results", [])

        saved_builds = data.get("pending_builds", [])
        restored_builds = []
        for b in saved_builds:
            item = b.copy()
            if "strategy_key" in item:
                key = item["strategy_key"]
                if key in self.strategy_map:
                    item["strategy"] = self.strategy_map[key]
                del item["strategy_key"]
            restored_builds.append(item)

        self.pending_builds = restored_builds

    def load_strategies(self):
        """
        Dynamically loads building strategies from the 'strategies.building' package.
        """
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
                self.logger.error(
                    f"Failed to instantiate strategy {strat_cls.__name__}: {e}"
                )

    def on_map_received(self, message: Message):
        """
        Handles map data from the ExplorerBot.

        Args:
            message (Message): The message containing the flat spots and other map info.
        """
        self.logger.info(f"Received map data from {message.source}")
        flat_spots = message.payload.get("flat_spots", [])

        if flat_spots:
            self.current_scan_results = flat_spots
            self.logger.info(f"Stored {len(flat_spots)} build sites.")

            if getattr(self, "auto_build_next_map", False):
                self.auto_build_next_map = False
                self.logger.info("Auto-building due to workflow.")
                self.on_build_command(message)
            else:
                if self.mc:
                    self.mc.postToChat(
                        "[Builder] Sites found. Use '/builder plan set' then '/builder build'."
                    )
        else:
            self.logger.warning("No flat spots received.")

    def on_workflow_run(self, msg):
        payload = msg.payload or {}
        template = payload.get("template", "simplehut").lower()

        # Determine strategy
        if template in self.strategy_map:
            self.selected_strategy_key = template
        elif self.strategy_map:
            self.selected_strategy_key = list(self.strategy_map.keys())[0]

        self.auto_build_next_map = True
        if self.mc:
            self.mc.postToChat(
                f"[Builder] Workflow active. Will build {self.selected_strategy_key} when map arrives."
            )

    def on_list_plans(self, msg):
        plans = ", ".join(self.strategy_map.keys())
        if self.mc:
            self.mc.postToChat(f"[Builder] Plans: {plans}")

    def on_set_plan(self, msg):
        template = msg.payload.get("template", "").lower()
        if template in self.strategy_map:
            self.selected_strategy_key = template
            if self.mc:
                self.mc.postToChat(f"[Builder] Selected: {template}")
        else:
            if self.mc:
                self.mc.postToChat(f"[Builder] Unknown: {template}")

    def on_bom_request(self, msg):
        if not self.selected_strategy_key:
            if self.mc:
                self.mc.postToChat("[Builder] No plan selected.")
            return

        strat = self.strategy_map[self.selected_strategy_key]
        bom = strat.get_bom()
        if self.mc:
            self.mc.postToChat(f"[Builder] BOM: {bom}")

    def on_build_command(self, msg):
        """
        Triggered when user types '/builder build'
        """
        if not self.selected_strategy_key:
            if self.mc:
                self.mc.postToChat("[Builder] Select a plan first!")
            return

        if not self.current_scan_results:
            self.logger.warning("Cannot build: No site selected/scanned yet.")
            if self.mc:
                self.mc.postToChat("[Builder] Scan required first.")
            return

        strategy = self.strategy_map[self.selected_strategy_key]
        target = self.current_scan_results[0]

        # BOM Recalculation & Republishing Logic
        # Check if we already have a pending build at this location
        existing_idx = -1
        for i, b in enumerate(self.pending_builds):
            # Compare locations (Vec3 or tuple)
            # target is likely a tuple or Vec3 from Explorer
            # Let's assume strict equality or close proximity
            loc = b["location"]
            if loc == target:  # Simple equality check
                existing_idx = i
                break

        bom = strategy.get_bom()

        if existing_idx != -1:
            self.logger.info(
                f"Updating existing build plan at {target} to {self.selected_strategy_key}"
            )
            if self.mc:
                self.mc.postToChat(
                    f"[Builder] Updating plan to {self.selected_strategy_key}. Re-sending BOM."
                )

            # Update the entry
            self.pending_builds[existing_idx]["strategy"] = strategy
            self.pending_builds[existing_idx]["bom"] = bom
            self.pending_builds[existing_idx]["status"] = "waiting_for_materials"
            # Reset status to ensure we wait for new mats if needed
            self.pending_builds[existing_idx]["retry_count"] = 0
        else:
            self.logger.info(
                f"Initiating build of {self.selected_strategy_key} at {target}"
            )
            if self.mc:
                self.mc.postToChat(
                    f"BuilderBot: Calculating BOM for {self.selected_strategy_key}..."
                )
            if self.mc:
                self.mc.postToChat(f"BuilderBot: Need {bom}")

            self.pending_builds.append(
                {
                    "location": target,
                    "strategy": strategy,
                    "bom": bom,
                    "status": "waiting_for_materials",
                    "retry_count": 0,
                }
            )

        # Publish requirements (always republish on update)
        req_msg = Message(
            type="materials.requirements.v1",
            source=self.name,
            target="MinerBot",
            payload={"requirements": bom},
        )
        if self.bus:
            self.bus.publish(req_msg)

    def on_inventory_received(self, message: Message):
        self.logger.info(f"Received inventory update from {message.source}")
        inventory = message.payload.get("inventory", {})

        if not self.pending_builds:
            self.logger.warning("Received inventory but no pending builds.")
            return

        build_job = self.pending_builds[0]

        # Initialize collected if new
        if "collected" not in build_job:
            build_job["collected"] = {}

        # Accumulate materials
        for item, count in inventory.items():
            current = build_job["collected"].get(item, 0)
            build_job["collected"][item] = current + count

        self.logger.info(
            f"Current Job Status: Collected {build_job['collected']} / Needed {build_job['bom']}"
        )

        # Check against BOM
        bom = build_job["bom"]
        complete = True

        for item, needed in bom.items():
            have = build_job["collected"].get(item, 0)

            # Interchangeable Stone/Cobblestone
            if item in ["STONE", "COBBLESTONE"]:
                stone = build_job["collected"].get("STONE", 0)
                cobble = build_job["collected"].get("COBBLESTONE", 0)
                if (stone + cobble) < needed:
                    complete = False
                    break

            # Special conversion for Wood -> Planks
            elif item == "WOOD_PLANKS":
                wood_have = build_job["collected"].get("WOOD", 0)
                # 1 Wood gives 4 Planks
                # So total planks available = planks_have + (wood_have * 4)
                total_planks = have + (wood_have * 4)
                if total_planks < needed:
                    complete = False
                    break
            # Logic for TORCH crafting from COAL_ORE and WOOD
            elif item == "TORCH":
                coal_have = build_job["collected"].get("COAL_ORE", 0)
                wood_have = build_job["collected"].get("WOOD", 0)
                # 1 Coal + 1 Stick (~0.5 Wood) = 4 Torches
                # Simplification: 1 Coal + 1 Wood -> 4 Torches
                potential_torches = have + (min(coal_have, wood_have) * 4)
                if potential_torches < needed:
                    complete = False
                    break
            elif have < needed:
                complete = False
                break

        if complete:
            self.logger.info("All materials collected. Ready to build.")
            if self.mc:
                self.mc.postToChat(
                    "BuilderBot: All materials collected! Ready to start construction..."
                )
            # Update status instead of building immediately
            build_job["status"] = "READY_TO_BUILD"
        else:
            # Check for retry limit simulation
            build_job["retry_count"] = build_job.get("retry_count", 0) + 1
            if build_job["retry_count"] >= 10:
                self.logger.warning(
                    "Retry limit reached (10). Simulating remaining materials."
                )
                if self.mc:
                    self.mc.postToChat(
                        "[Builder] Material collection failed 10 times. Simulating..."
                    )
                build_job["status"] = "READY_TO_BUILD"
                return

            self.logger.info(
                f"Still missing materials. Waiting for more. (Try {build_job['retry_count']}/10)"
            )
            if self.mc:
                missing_str = []
                for item, needed in bom.items():
                    have = build_job["collected"].get(item, 0)
                    # Quick approximate check for user info
                    if item in ["STONE", "COBBLESTONE"]:
                        if (
                            build_job["collected"].get("STONE", 0)
                            + build_job["collected"].get("COBBLESTONE", 0)
                        ) < needed:
                            missing_str.append(f"{item}")
                    elif have < needed:
                        missing_str.append(f"{item}")

                # Only post if strict missing to avoid spamming "WOOD_PLANKS" when we have wood
                # self.mc.postToChat(f"BuilderBot: Missing {missing_str}")
                pass

    def perceive(self):
        """
        Process incoming messages and update state.
        This is handled by the message bus callbacks in this architecture,
        but we can add other sensor checks here if needed.
        """
        pass

    def decide(self):
        """
        Decide the next action based on current state.
        """
        if not self.pending_builds:
            return "IDLE"

        current_job = self.pending_builds[0]
        if current_job["status"] == "READY_TO_BUILD":
            return "BUILD"
        elif current_job["status"] == "waiting_for_materials":
            # Check if we have materials again? or just wait
            # We already check in on_inventory_received
            return "WAIT"

        return "IDLE"

    def act(self):
        """
        Execute the decided action.
        """
        decision = self.decide()

        if decision == "BUILD":
            self.build_structure()
        elif decision == "WAIT":
            # Optional logging, maybe rate limited
            pass
        elif decision == "IDLE":
            pass

    def place_block(self, x, y, z, block_id, meta=0):
        """
        Places a block in the world and logs the action for compliance.

        Args:
            x, y, z: Coordinates.
            block_id: The ID of the block to place.
            meta: Optional metadata/damage value.
        """
        if not self.mc:
            return

        # Layer Summary Logic
        if self.current_layer_y is None:
            self.current_layer_y = y

        if y != self.current_layer_y:
            try:
                # Log Summary for the completed layer
                summary_payload = {
                    "event": "layer_summary",
                    "agent": self.name,
                    "layer_y": self.current_layer_y,
                    "materials_used": self.current_layer_stats,
                    "timestamp": time.time()
                }
                self.logger.info(f"Layer Complete: {summary_payload}")
            except Exception as e:
                self.logger.error(f"Failed to log layer summary: {e}")
            
            # Reset for new layer
            self.current_layer_y = y
            self.current_layer_stats = {}

        # Update stats
        key = f"{block_id}:{meta}"
        self.current_layer_stats[key] = self.current_layer_stats.get(key, 0) + 1

        self.mc.setBlock(x, y, z, block_id, meta)

        # Structured Logging of Placement
        log_payload = {
            "event": "block_placement",
            "agent": self.name,
            "x": x,
            "y": y,
            "z": z,
            "block_id": block_id,
            "meta": meta,
            "timestamp": time.time(),
        }
        self.logger.info(f"Block Placed: {log_payload}")

    def build_structure(self):
        """
        Executes the building process for the current task.
        Advances the FSM and consumes materials as blocks are placed.
        """
        if not self.pending_builds:
            return

        build_task = self.pending_builds[0]
        # Check status explicitly
        if build_task["status"] == "READY_TO_BUILD":
            self.logger.info("Starting construction...")
            if self.mc:
                self.mc.postToChat(
                    f"BuilderBot: Building {build_task.get('strategy_name', 'Structure')}..."
                )

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
            if self.mc:
                self.mc.postToChat("BuilderBot: Build Complete!")
            self.pending_builds.pop(0)
