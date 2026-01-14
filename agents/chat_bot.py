from mcpi.minecraft import Minecraft
from core.base_agent import BaseAgent
from core.messaging import Message
import time


class ChatBot(BaseAgent):
    """
    Agent responsible for listening to in-game chat commands and issuing control messages.
    """

    def __init__(self, name, message_bus=None):
        super().__init__(name, message_bus)
        try:
            self.mc = Minecraft.create()
        except Exception as e:
            self.logger.error(f"Failed to connect to Minecraft: {e}")
            self.mc = None

        if self.bus:
            self.bus.subscribe("map.v1", self.on_map_event)
            self.bus.subscribe("materials.requirements.v1", self.on_requirements_event)
            self.bus.subscribe("inventory.v1", self.on_inventory_event)
            self.bus.subscribe("control.agent.status.report", self.on_status_report)

        self.last_processed_signature = ""
        self.last_processed_time = 0

    def post_help_message(self, topic=None):
        """Posts help syntax to the chat."""
        if not self.mc:
            return

        if topic == "explorer":
            self.mc.postToChat("--- ExplorerBot Commands ---")
            self.mc.postToChat("/explorer start [range=20] : Start scanning")
            self.mc.postToChat("/explorer stop : Stop scanning")
            self.mc.postToChat("/explorer set range <N> : Set scan range")
            self.mc.postToChat("/explorer status : Check queue/state")
        elif topic == "miner":
            self.mc.postToChat("--- MinerBot Commands ---")
            self.mc.postToChat("/miner start : Start default mining")
            self.mc.postToChat("/miner set strategy <name> : Change strategy")
            self.mc.postToChat("/miner fulfill : Force inventory delivery")
            self.mc.postToChat("/miner pause|resume : Control execution")
        elif topic == "builder":
            self.mc.postToChat("--- BuilderBot Commands ---")
            self.mc.postToChat("/builder plan list : List available buildings")
            self.mc.postToChat("/builder plan set <template> : Select building")
            self.mc.postToChat("/builder bom : Check material needs")
            self.mc.postToChat("/builder build : Start construction")
        elif topic == "workflow":
            self.mc.postToChat("--- Workflow Commands ---")
            self.mc.postToChat("/workflow run : Start full lifecycle")
        else:
            self.mc.postToChat("--- Available Agents ---")
            self.mc.postToChat("Cmds: /agent, /explorer, /miner, /builder, /workflow")
            self.mc.postToChat("Type '/agent help <name>' for details.")
            self.mc.postToChat("e.g., '/agent help builder'")

    def on_map_event(self, message: Message):
        if not self.mc:
            return
        flat_spots = message.payload.get("flat_spots", [])
        if flat_spots:
            self.mc.postToChat(f"[Explorer] Found {len(flat_spots)} sites.")
            self.mc.postToChat("Scan complete. Ready for construction.")
        else:
            self.mc.postToChat(
                "[Explorer] partial scan complete - no flat spots found."
            )

    def on_requirements_event(self, message: Message):
        if not self.mc:
            return
        reqs = message.payload.get("requirements", {})
        count = sum(reqs.values())
        self.mc.postToChat(f"[Builder] Order placed: {count} blocks needed.")

    def on_inventory_event(self, message: Message):
        if not self.mc:
            return
        self.mc.postToChat("[Miner] Delivery complete. Materials sent to Builder.")

    def on_status_report(self, message: Message):
        if not self.mc:
            return
        sender = message.source
        payload = message.payload
        state = payload.get("state", "UNKNOWN")

        # Format basics
        info = f"[{sender}] State: {state}"

        # Add details if available
        if "strategy" in payload:
            info += f" | Strat: {payload['strategy']}"
        if "queue_length" in payload:
            info += f" | Q: {payload['queue_length']}"
        if "inventory" in payload:
            # Inventory might be long, so maybe truncate?
            inv = str(payload["inventory"]).replace("{", "").replace("}", "")
            if len(inv) > 30:
                inv = inv[:25] + "..."
            info += f" | Inv: {inv}"
        if "current_job" in payload:
            info += f" | Job: {payload['current_job']}"

        self.mc.postToChat(info)

    def on_pause_command(self, message: Message):
        # Override BaseAgent behavior: ChatBot must NOT pause, or it waits forever and can't hear "resume"
        self.logger.info(
            "ChatBot received pause request - ignoring to maintain control loop."
        )

    def on_resume_command(self, message: Message):
        # Override BaseAgent behavior: ChatBot never paused, effectively
        self.logger.info("ChatBot broadcasting resume.")

    def perceive(self):
        if not self.mc:
            return

        # Poll chat posts
        try:
            chat_events = self.mc.events.pollChatPosts()
            for event in chat_events:
                self.handle_chat(event)
        except Exception as e:
            self.logger.error(f"Error polling chat: {e}")

    def parse_command_args(self, args_list):
        """Parses a list of strings into positional args and a kwargs dictionary."""
        positional = []
        kwargs = {}
        for arg in args_list:
            if "=" in arg:
                key, val = arg.split("=", 1)
                # Try to convert to int if possible
                try:
                    val = int(val)
                except ValueError:
                    pass
                kwargs[key] = val
            else:
                positional.append(arg)
        return positional, kwargs

    def handle_chat(self, event):
        raw_message = event.message.strip()

        # Debounce: Ignore identical commands from same entity within 1 second
        # event might differ in structure, checking attributes
        entity_id = getattr(event, "entityId", 0)
        signature = f"{entity_id}:{raw_message}"
        if (
            signature == self.last_processed_signature
            and (time.time() - self.last_processed_time) < 1.0
        ):
            self.logger.debug(f"Ignored duplicate command: {raw_message}")
            return

        self.last_processed_signature = signature
        self.last_processed_time = time.time()

        # Clean up leading slash
        message = raw_message.lstrip("/")
        parts = message.split()
        if not parts:
            return

        cmd = parts[0].lower()
        # Handle common plurals/typos
        if cmd.endswith("s"):
            cmd = cmd[:-1]  # agents -> agent
        if cmd == "builer":
            cmd = "builder"  # common typo

        args = parts[1:]

        positional, kwargs = self.parse_command_args(args)
        self.logger.info(f"Processing command: {cmd} {args}")

        # 0. Help Command
        if cmd == "help":
            topic = positional[0].lower() if positional else None
            self.post_help_message(topic)

        # 1. Common Commands
        elif cmd == "agent":
            if not positional:
                return
            subcmd = positional[0].lower()

            if subcmd == "pause":
                self.publish_control("control.agent.pause")
                self.mc.postToChat("[System] Pausing all agents.")
            elif subcmd == "resume":
                self.publish_control("control.agent.resume")
                self.mc.postToChat("[System] Resuming all agents.")
            elif subcmd == "stop":
                self.publish_control("control.agent.stop")
                self.mc.postToChat("[System] Stopping all agents.")
            elif subcmd == "status":
                self.publish_control("control.agent.status.request")
                self.mc.postToChat("[System] Requesting status...")
            elif subcmd == "help":
                topic = positional[1].lower() if len(positional) > 1 else None
                self.post_help_message(topic)

        # 2. Workflow
        elif cmd == "workflow":
            if positional and positional[0].lower() == "run":
                self.publish_control("control.workflow.run", payload=kwargs)
                self.mc.postToChat("[Workflow] Run sequence initiated.")

        # 3. ExplorerBot
        elif cmd == "explorer":
            if not positional:
                return
            subcmd = positional[0].lower()
            if subcmd == "start":
                self.publish_control("control.explorerbot.start", payload=kwargs)
                self.mc.postToChat("[Explorer] Start sent.")
            elif subcmd == "stop":
                self.publish_control("control.explorerbot.stop")
                self.mc.postToChat("[Explorer] Stop sent.")
            elif subcmd == "set":
                if len(positional) > 1 and positional[1].lower() == "range":
                    # Support "range=X" or "range X"
                    val = kwargs.get("range")
                    if val is None and len(positional) > 2:
                        try:
                            val = int(positional[2])
                        except ValueError:
                            pass
                    if val:
                        self.publish_control(
                            "control.explorerbot.config", payload={"range": val}
                        )
                        self.mc.postToChat(f"[Explorer] Range set: {val}")
            elif subcmd == "status":
                self.publish_control("control.agent.status.request")

        # 4. MinerBot
        elif cmd == "miner":
            if not positional:
                return
            subcmd = positional[0].lower()
            if subcmd == "start":
                self.publish_control("control.minerbot.start", payload=kwargs)
                self.mc.postToChat("[Miner] Start sent.")
            elif (
                subcmd == "set"
                and len(positional) > 1
                and positional[1].lower() == "strategy"
            ):
                strat = kwargs.get("strategy")
                if not strat and len(positional) > 2:
                    strat = positional[2]
                if strat:
                    self.publish_control(
                        "control.minerbot.strategy", payload={"strategy": strat}
                    )
                    self.mc.postToChat(f"[Miner] Strategy: {strat}")
            elif subcmd == "fulfill":
                self.publish_control("control.minerbot.fulfill")
                self.mc.postToChat("[Miner] Fulfill requested.")
            elif subcmd == "pause":
                self.publish_control("control.minerbot.pause")
                self.mc.postToChat("[Miner] Paused.")
            elif subcmd == "resume":
                self.publish_control("control.minerbot.resume")
                self.mc.postToChat("[Miner] Resumed.")
            elif subcmd == "status":
                self.publish_control("control.agent.status.request")

        # 5. BuilderBot
        elif cmd == "builder":
            if not positional:
                return
            subcmd = positional[0].lower()
            if subcmd == "plan":
                if len(positional) > 1:
                    action = positional[1].lower()
                    if action == "list":
                        self.publish_control("control.builderbot.plan.list")
                    elif action == "set":
                        template = kwargs.get("template")
                        if not template and len(positional) > 2:
                            template = positional[2]
                        if template:
                            self.publish_control(
                                "control.builderbot.plan.set",
                                payload={"template": template},
                            )
                            self.mc.postToChat(f"[Builder] Plan: {template}")
            elif subcmd == "bom":
                self.publish_control("control.builderbot.bom")
            elif subcmd == "build":
                self.publish_control("control.builderbot.build")
                self.mc.postToChat("[Builder] Build sent.")
            elif subcmd == "pause":
                self.publish_control("control.builderbot.pause")
                self.mc.postToChat("[Builder] Paused.")
            elif subcmd == "resume":
                self.publish_control("control.builderbot.resume")
                self.mc.postToChat("[Builder] Resumed.")

    def publish_control(self, msg_type, payload=None):
        if self.bus:
            if payload is None:
                payload = {}
            msg = Message(
                type=msg_type, source=self.name, target="all", payload=payload
            )
            self.bus.publish(msg)

    def decide(self):
        pass

    def act(self):
        pass
