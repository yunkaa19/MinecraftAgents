from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent, AgentState
from core.utils import load_classes, CRAFTING_RECIPES
from core.messaging import Message
from strategies import MiningStrategy
from functools import reduce
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
        self.strategy_map = {}
        self.selected_strategy = None
        self.auto_mine = False  # Default to False to prevent destruction

        self.load_strategies()

        self.mining_queue = []
        # Current inventory of gathered resources
        self.inventory = {}
        self.locked_sectors = set()
        self.global_locks = set()
        self.force_delivery = False

        if self.bus:
            self.bus.subscribe(
                "materials.requirements.v1", self.on_requirements_received
            )
            self.bus.subscribe("control.minerbot.start", self.on_manual_start)
            self.bus.subscribe("control.minerbot.strategy", self.on_set_strategy)
            self.bus.subscribe("control.minerbot.fulfill", self.on_fulfill)
            self.bus.subscribe("lock.acquire", self.on_lock_activity)
            self.bus.subscribe("lock.release", self.on_lock_activity)
            self.bus.subscribe("control.minerbot.automine", self.on_automine_toggle)

    def on_automine_toggle(self, message: Message):
        """Enable or Disable Auto-Mining (Free Mine)."""
        enabled = message.payload.get("enabled", True)
        self.auto_mine = enabled
        state_str = "ENABLED" if enabled else "DISABLED"
        self.logger.info(f"Auto-mine {state_str}")
        if self.mc:
            self.mc.postToChat(f"[Miner] Auto-mine {state_str}")

    def transition_state(self, new_state, reason):
        super().transition_state(new_state, reason)
        if new_state in [AgentState.STOPPED, AgentState.ERROR]:
            if self.locked_sectors:
                self.logger.warning(
                    f"Force releasing {len(self.locked_sectors)} sector locks due to {new_state.name} state."
                )
                # Broadcast release of all owned locks
                for sector in self.locked_sectors:
                     self._publish_lock_event("lock.release", sector)
                self.locked_sectors.clear()

    def on_lock_activity(self, message: Message):
        """
        Maintains the global lock registry based on broadcasts from other miners.
        """
        # Ignore our own messages
        if message.source == self.name:
            return

        payload = message.payload
        sector = tuple(payload.get("sector", []))
        if not sector:
            return

        if message.type == "lock.acquire":
            self.global_locks.add(sector)
            self.logger.debug(f"Registered global lock on sector {sector} by {message.source}")
        elif message.type == "lock.release":
            self.global_locks.discard(sector)
            self.logger.debug(f"Released global lock on sector {sector} by {message.source}")

    def _publish_lock_event(self, event_type, sector):
        if self.bus:
            msg = Message(
                type=event_type,
                source=self.name,
                target="all",
                payload={"sector": sector}
            )
            self.bus.publish(msg)

    def _get_checkpoint_data(self):
        return {
            "inventory": self.inventory,
            "mining_queue": self.mining_queue,
            "selected_strategy": (
                self.selected_strategy.__class__.__name__
                if self.selected_strategy
                else None
            ),
        }

    def _apply_checkpoint_data(self, data):
        self.inventory = data.get("inventory", {})
        self.mining_queue = data.get("mining_queue", [])

        # Restore strategy if possible
        strat_name = data.get("selected_strategy")
        if strat_name:
            # Map class name back to instance?
            # Our strategy_map keys are 'vertical', 'grid' etc... not ClassName
            # We stored instance last time.
            # Let's simple try to find it in self.strategies list by class name
            for s in self.strategies:
                if s.__class__.__name__ == strat_name:
                    self.selected_strategy = s
                    break

    def load_strategies(self):
        """
        Dynamically loads mining strategies from the 'strategies.mining' package.
        """
        self.logger.info("Loading mining strategies...")
        # We look for strategies in the 'strategies.mining' package
        strategy_classes = load_classes("strategies.mining", MiningStrategy)
        for strat_cls in strategy_classes:
            try:
                strategy = strat_cls()
                self.strategies.append(strategy)

                # Create a simple key (e.g., "vertical")
                key = (
                    strat_cls.__name__.lower()
                    .replace("search", "")
                    .replace("strategy", "")
                )
                self.strategy_map[key] = strategy

                self.logger.info(f"Loaded strategy: {strat_cls.__name__} as '{key}'")
            except Exception as e:
                self.logger.error(
                    f"Failed to instantiate strategy {strat_cls.__name__}: {e}"
                )

    def on_set_strategy(self, message: Message):
        """
        Handles requests to switch the mining strategy.

        Args:
            message (Message): The control message containing the strategy name.
        """
        strat_name = message.payload.get("strategy", "").lower()
        if strat_name in self.strategy_map:
            self.selected_strategy = self.strategy_map[strat_name]
            self.logger.info(f"Switched strategy: {strat_name}")
            if self.mc:
                self.mc.postToChat(f"[Miner] Switched to {strat_name}")
        else:
            if self.mc:
                self.mc.postToChat(f"[Miner] Unknown strategy: {strat_name}")

    def on_manual_start(self, message: Message):
        self.transition_state(AgentState.RUNNING, "Manual start override command")
        # Default strategy if needed
        if not self.selected_strategy and "grid" in self.strategy_map:
            self.selected_strategy = self.strategy_map["grid"]

        # Add generic task if empty
        if not self.mining_queue:
            self.mining_queue.append({"MANUAL": 1})

        self.logger.info("Miner forced start.")

    def on_fulfill(self, message: Message):
        self.force_delivery = True
        self.logger.info("Force delivery requested.")

    def get_inventory_statistics(self):
        """
        Calculates aggregate statistics for the current inventory using functional paradigm.

        Returns:
            tuple: (total_item_count, distinct_item_types)
        """
        if not self.inventory:
            return 0, 0

        # Functional reduction to get total item count
        total_items = reduce(lambda acc, count: acc + count, self.inventory.values(), 0)
        return total_items, len(self.inventory)

    def get_additional_status(self):
        """Overrides BaseAgent status to add miner info."""
        strat = (
            self.selected_strategy.__class__.__name__
            if self.selected_strategy
            else "None"
        )
        total_items, _ = self.get_inventory_statistics()

        return {
            "strategy": strat,
            "queue_length": len(self.mining_queue),
            "inventory": str(self.inventory),
            "total_items_mined": total_items,
        }

    def on_requirements_received(self, message: Message):
        """
        Ingests a bill of materials from the BuilderBot.

        Args:
           message (Message): The message containing the requirements dictionary.
        """
        self.logger.info(f"Received material requirements from {message.source}")
        reqs = message.payload.get("requirements", {})

        # Filter out wood related items (Delegated to LumberBot)
        # Note: LumberBot is currently inactive/stubbed, so MinerBot must handle everything
        # per Update.txt Section 3.
        # filtered_reqs = {}
        # for item, count in reqs.items():
        #    if item in ["WOOD", "WOOD_PLANKS", "LOG", "LOG_2"]:
        #        self.logger.info(f"Delegating {item} requirement to LumberBot.")
        #    else:
        #        filtered_reqs[item] = count
        
        # Fallback: MinerBot accepts all requirements
        filtered_reqs = reqs

        if filtered_reqs:
            self.mining_queue.append(filtered_reqs)
        elif reqs:
            self.logger.info("All requirements were delegated to other bots.")

    def perceive(self):
        pass

    def decide(self):
        if self.mining_queue:
            if self.selected_strategy:
                return "mine"
            else:
                return "wait_for_strategy"
        
        # Free Mode: check flag
        if getattr(self, "auto_mine", False):
            # If empty inventory and empty queue, mine around player
            return "free_mine"

        return None

    def act(self):
        decision = self.decide()
        if decision == "mine":
            self.mine()
        elif decision == "wait_for_strategy":
            if self.mc:
                # Announce once every few seconds
                now = time.time()
                # Use getattr to initialize last_announce if not present
                if not hasattr(self, "_last_announce"):
                    self._last_announce = 0

                if now - self._last_announce > 15:
                    msg = f"MinerBot: Waiting for strategy. Type 'mine <{', '.join(self.strategy_map.keys())}>' to start."
                    self.mc.postToChat(msg)
                    self._last_announce = now

            self.logger.info("Waiting for mining strategy selection...")
            time.sleep(2)
        elif decision == "deposit":
            self.deposit_items()
        elif decision == "free_mine":
            self.free_mine()

    def _check_pause(self):
        """Checks and handles agent pause state."""
        while self.state == AgentState.PAUSED:
            time.sleep(1)
        if self.state == AgentState.STOPPED:
            raise InterruptedError("Stopped")

    def deposit_items(self):
        """Deposits all items to the player (Simulated via Chest)."""
        self.logger.info("Depositing items to player...")
        self._check_pause()

        if self.mc:
            try:
                pos = self.mc.player.getTilePos()
                # Place a chest at player's feet (or next to)
                # self.mc.setBlock(pos.x, pos.y, pos.z, 54) # 54 is Chest
                # Actually, let's just claim we gave it to them, or put in a chest at offset
                chest_pos = (pos.x + 1, pos.y, pos.z)
                self.mc.setBlock(chest_pos[0], chest_pos[1], chest_pos[2], 54)
                
                # We can't fill it with MCPI, so we just clear inventory and notify
                self.mc.postToChat(f"MinerBot: Deposited {dict(self.inventory)} in chest at {chest_pos}.")
            except Exception as e:
                self.logger.error(f"Failed to post chat/block: {e}")

        # Clear inventory
        self.inventory.clear()
        time.sleep(2) # Simulation delay

    def free_mine(self):
        """Mines around the player's current position."""
        self.logger.info("Starting Free Mine operation...")
        self._check_pause()

        if not self.mc:
            time.sleep(1)
            return

        # Default to Grid strategy if none selected
        if not self.selected_strategy:
            if "grid" in self.strategy_map:
                self.selected_strategy = self.strategy_map["grid"]
            else:
                self.logger.warning("No strategy available for free mine.")
                time.sleep(2)
                return

        # Calculate target: Player + 3 blocks forward
        try:
            pos = self.mc.player.getTilePos()
            direction = self.mc.player.getDirection()
            
            # Target is 3 blocks away
            target_vec = pos + (direction * 3)
            # Rounding might be needed if direction is float
            target = (int(target_vec.x), int(target_vec.y), int(target_vec.z))
            
            self.logger.info(f"Free mining at {target} (Player at {pos})")
            
            # Execute ONE cycle of the strategy
            loot = self.selected_strategy.execute(self, start_loc=target)
            
            if loot:
                self.logger.info(f"Free mine yield: {loot}")
                for item, count in loot.items():
                    self.inventory[item] = self.inventory.get(item, 0) + count
            
            time.sleep(1)

        except Exception as e:
            if isinstance(e, InterruptedError) or str(e) == "Stopped":
                 self.logger.info("Free mining operation stopped.")
            else:
                 self.logger.error(f"Free mine error: {e}")
            time.sleep(1)


    def handle_error(self, error: Exception):
        """
        Handles errors by ensuring all acquired locks are released.
        """
        self.logger.error(f"MinerBot error handler caught: {error}")
        if self.locked_sectors:
            self.logger.warning(f"Releasing {len(self.locked_sectors)} locks due to error.")
            for sector in list(self.locked_sectors):
                self._publish_lock_event("lock.release", sector)
                self.locked_sectors.remove(sector)
            self.logger.info("All locks released.")

    def _requirements_met(self, reqs):
        """Checks if the current inventory meets the requirements, considering crafting."""

        # Calculate total available of each item including what can be crafted
        available = self.inventory.copy()

        # Aggregate Interchangeable Blocks
        # Combine STONE and COBBLESTONE into "STONE" bucket for checking
        # But wait, requirements might ask for COBBLESTONE explicitly.
        # Let's just treat them as one pool.
        stone_pool = available.get("STONE", 0) + available.get("COBBLESTONE", 0)

        # Check raw numbers first
        missing = {}
        for item, count in reqs.items():
            current = available.get(item, 0)

            # Special Handling for Stone/Cobble
            if item in ["STONE", "COBBLESTONE"]:
                current = stone_pool

            if current < count:
                missing[item] = count - current

        if not missing:
            return True

        # Try to satisfy missing items via crafting
        for item, amount_needed in missing.items():
            if item in CRAFTING_RECIPES:
                # Basic check if it's craftable (doesn't check ingredient inventory strictly here)
                return False 
        
        return False

    def _try_craft(self, reqs):
        """Attempts to craft items to fulfill requirements."""
        self.logger.info("Attempting to craft missing items...")

        for item, count in reqs.items():
            if self.inventory.get(item, 0) >= count:
                continue

            if item in CRAFTING_RECIPES:
                recipe = CRAFTING_RECIPES[item]
                needed = count - self.inventory.get(item, 0)

                # Check ingredients
                can_craft = True
                for ingred, qty in recipe.items():
                    ingredient_needed = needed * qty
                    if self.inventory.get(ingred, 0) < ingredient_needed:
                        can_craft = False
                        break

                if can_craft:
                    self.logger.info(f"Crafting {needed} {item} from {recipe}")
                    # Consume ingredients
                    for ingred, qty in recipe.items():
                        self.inventory[ingred] -= needed * qty

                    # Add product
                    self.inventory[item] = self.inventory.get(item, 0) + needed
                    time.sleep(1)  # Simulation time

    def mine(self):
        if not self.mc:
            return

        req = self.mining_queue[0]
        self.logger.info(f"Processing mining request: {req}")

        # Define a mining location
        # If the request doesn't specify (it usually doesn't yet), pick a random nearby spot
        # or just offset from the current position to avoid digging under self.
        # But wait, we want to simulate an autonomous agent.
        # Let's try to mine at (x+5, z+5) from current pos.
        pos = self.mc.player.getTilePos()

        # Better yet: Create a "Quarry" location offset from the player
        # so we don't fall into our own hole.
        mining_loc = (pos.x + 10, pos.y, pos.z + 10)

        # Spatial Locking Mechanism:
        # A sector is defined as a 16x16 chunk (x//16, z//16).
        # We must check GLOBAL locks to avoid multiple MinerBots overlapping.
        # Currently, self.locked_sectors is local instance only.
        # To truly coordinate multiple miners, we'd need a shared backend or broadcast queries.
        # Given this is a local swarm, we can assume locks are respected if communicated.
        # But for now, we enforce local consistency so THIS miner doesn't dig in its own prior hole.

        sector = (mining_loc[0] // 16, mining_loc[2] // 16)

        # Check existing locks (Local)
        if sector in self.locked_sectors:
            self.logger.warning(
                f"Sector {sector} is already locked by this agent. Shifting quarry site."
            )
            # Try shifting to next sector
            mining_loc = (pos.x + 26, pos.y, pos.z + 10)
            sector = (mining_loc[0] // 16, mining_loc[2] // 16)

        if sector in self.locked_sectors:
            self.logger.warning(
                "Alternative sector also locked. Aborting mine cycle to find new spot."
            )
            return
        
        # Check Global Locks
        if sector in self.global_locks:
            self.logger.warning(
                f"Sector {sector} is globally locked by another MinerBot. Aborting."
            )
            return

        # Announce Lock to other agents
        self.locked_sectors.add(sector)
        self._publish_lock_event("lock.acquire", sector)
        self.logger.info(f"Locked sector {sector} for mining at {mining_loc}")

        try:
            # Mining Loop: Continue until requirements are met or max attempts reached
            max_attempts = 10
            attempts = 0

            while not self._requirements_met(req) and attempts < max_attempts:
                # Force delivery check
                if self.force_delivery:
                    break

                # Try to craft first (e.g. if we mined Wood, make Planks)
                self._try_craft(req)
                if self._requirements_met(req):
                    break

                # Check for Pause/Stop
                while self.state == AgentState.PAUSED:
                    time.sleep(1)

                if self.state == AgentState.STOPPED:
                    self.logger.info("Mining operation stopped by command.")
                    break

                attempts += 1
                self.logger.info(
                    f"Mining attempt {attempts}/{max_attempts}. Inventory: {self.inventory}"
                )

                # Execute the selected strategy
                if not self.selected_strategy:
                    self.logger.warning("No strategy selected!")
                    break

                strategy = self.selected_strategy

                # Execute returns the loot dict
                loot = strategy.execute(self, start_loc=mining_loc)

                if loot:
                    # Merge loot into inventory
                    for item, count in loot.items():
                        self.inventory[item] = self.inventory.get(item, 0) + count

                    if self.mc and str(loot) != "{}":
                        self.mc.postToChat(
                            f"MinerBot: Mined {loot}. Total: {self.inventory}"
                        )

                    # Move the mining site slightly for next attempt.
                    if req.get("WOOD") and not loot.get("WOOD"):
                        self.logger.info(
                            "Seeking WOOD - Moving effective query site drastically."
                        )
                        mining_loc = (mining_loc[0] + 20, mining_loc[1], mining_loc[2])
                    else:
                        mining_loc = (mining_loc[0] + 8, mining_loc[1], mining_loc[2])

                else:
                    self.logger.warning(
                        "Strategy yielded nothing. Creating new quarry site."
                    )
                    mining_loc = (mining_loc[0] + 8, mining_loc[1], mining_loc[2])

                # Check again if we can craft now
                self._try_craft(req)

                # Simulate move delay or cooldown
                time.sleep(1)

            # --- SIMULATION FALLBACK START ---
            if not self._requirements_met(req) and not self.force_delivery:
                self.logger.warning(
                    f"Failed to fulfill BOM naturally after {max_attempts} attempts. Simulating resource acquisition."
                )
                if self.mc:
                    self.mc.postToChat("MinerBot: Simulating resources (Creative Mode fallback).")
                
                # Artificially fill the inventory with the required missing items
                missing_items = {}
                available = self.inventory.copy() # Re-calc what we have
                stone_pool = available.get("STONE", 0) + available.get("COBBLESTONE", 0)

                for item, count in req.items():
                    current = available.get(item, 0)
                    if item in ["STONE", "COBBLESTONE"]:
                        current = stone_pool
                    
                    if current < count:
                        missing_qty = count - current
                        # Inject into inventory
                        # For stone/cobble, just inject COBBLESTONE as it's easier to verify
                        target_item = item
                        if item == "STONE": target_item = "COBBLESTONE"
                        
                        self.inventory[target_item] = self.inventory.get(target_item, 0) + missing_qty
                        self.logger.info(f"Simulated finding {missing_qty} {target_item}")

            # --- SIMULATION FALLBACK END ---

            if self._requirements_met(req) or self.force_delivery:
                self.logger.info("BOM fulfilled or forced.")
                self.force_delivery = False  # Reset flag

                if self.mc:
                    self.mc.postToChat("MinerBot: Delivering materials.")

                # Deduct from inventory (simulate handing it over)
                for item, count in req.items():
                    # Check for interchangeable pools first
                    if item in ["STONE", "COBBLESTONE"]:
                        deducted = 0
                        # Try taking from specific item first
                        have = self.inventory.get(item, 0)
                        to_take = min(have, count)
                        if to_take > 0:
                            self.inventory[item] -= to_take
                            deducted += to_take

                        remaining = count - deducted
                        if remaining > 0:
                            # Take from the other sibling
                            sibling = (
                                "STONE" if item == "COBBLESTONE" else "COBBLESTONE"
                            )
                            self.inventory[sibling] = (
                                self.inventory.get(sibling, 0) - remaining
                            )
                    else:
                        # Standard deduction
                        self.inventory[item] = self.inventory.get(item, 0) - count

                # Notify completion
                msg = Message(
                    type="inventory.v1",
                    source=self.name,
                    target="BuilderBot",
                    payload={"inventory": req},
                )
                if self.bus:
                    self.bus.publish(msg)

                # Complete the request
                self.mining_queue.pop(0)
            else:
                self.logger.warning(
                    f"Failed to fulfill BOM after {max_attempts} attempts. Missing items."
                )

        except Exception as e:
            if isinstance(e, InterruptedError) or str(e) == "Stopped":
                 self.logger.info("Mining operation stopped.")
            else:
                 self.logger.error(f"Mining failed: {e}")
        finally:
            if sector in self.locked_sectors:
                self.locked_sectors.remove(sector)
                self._publish_lock_event("lock.release", sector)
                self.logger.info(f"Unlocked sector {sector}")
