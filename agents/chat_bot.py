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

    def on_map_event(self, message: Message):
        if not self.mc: return
        flat_spots = message.payload.get("flat_spots", [])
        center = message.payload.get("center", {})
        if flat_spots:
            self.mc.postToChat(f"[Explorer] Found {len(flat_spots)} sites.")
            self.mc.postToChat("Type 'build <simplehut|stonetower>' to begin.")
        else:
            self.mc.postToChat("[Explorer] partial scan complete - no flat spots found.")

    def on_requirements_event(self, message: Message):
        if not self.mc: return
        reqs = message.payload.get("requirements", {})
        count = sum(reqs.values())
        self.mc.postToChat(f"[Builder] Order placed: {count} blocks needed.")

    def on_inventory_event(self, message: Message):
        if not self.mc: return
        self.mc.postToChat(f"[Miner] Delivery complete. Materials sent to Builder.")

    def on_status_report(self, message: Message):
        if not self.mc: return
        sender = message.source
        state = message.payload.get("state", "UNKNOWN")
        self.mc.postToChat(f"[{sender}] Status: {state}")

    def on_pause_command(self, message: Message):
        # Override BaseAgent behavior: ChatBot must NOT pause, or it waits forever and can't hear "resume"
        self.logger.info("ChatBot received pause request - ignoring to maintain control loop.")

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

    def handle_chat(self, event):
        message = event.message.lower().strip()
        # Remove leading slash if present to support both "/cmd" and "cmd"
        if message.startswith("/"):
            message = message[1:]

        self.logger.info(f"Processing command: {message}")
        
        if message.startswith("workflow run"):
            self.publish_control("control.workflow.run")
            self.mc.postToChat("Starting workflow...")
        elif message.startswith("agent pause"):
            self.publish_control("control.agent.pause")
            self.mc.postToChat("Pausing all agents...")
        elif message.startswith("agent resume"):
            self.publish_control("control.agent.resume")
            self.mc.postToChat("Resuming all agents...")
        elif message.startswith("agent status"):
            self.publish_control("control.agent.status.request")
            self.mc.postToChat("Requesting agent status...")
        elif message.startswith("build "):
            # Format: build <type>
            structure_type = message.split(" ")[1]
            self.logger.info(f"User requested build: {structure_type}")
            if self.bus:
                msg = Message(
                    type="control.build.select",
                    source=self.name,
                    target="BuilderBot",
                    payload={"structure_type": structure_type}
                )
                self.bus.publish(msg)
                self.mc.postToChat(f"Requested construction of {structure_type}")

    def publish_control(self, msg_type):
        if self.bus:
            msg = Message(
                type=msg_type,
                source=self.name,
                target="all",
                payload={}
            )
            self.bus.publish(msg)

    def decide(self):
        pass

    def act(self):
        pass
