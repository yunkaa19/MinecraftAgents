from abc import ABC, abstractmethod
import time
import logging
from typing import Optional
from core.fsm import AgentState
from core.messaging import MessageBus, Message

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    
    Manages the agent's lifecycle (FSM), message bus connection, and the main execution loop.
    """
    def __init__(self, name: str, message_bus: Optional[MessageBus] = None):
        self.name = name
        self.state = AgentState.IDLE
        self.logger = logging.getLogger(name)
        self.bus = message_bus
        
        if self.bus:
            self.bus.subscribe("control.agent.pause", self.on_pause_command)
            self.bus.subscribe("control.agent.resume", self.on_resume_command)
            self.bus.subscribe("control.agent.status.request", self.on_status_request)

    def on_status_request(self, message: Message):
        """Responds with the current status."""
        if self.bus:
            response = Message(
                type="control.agent.status.report",
                source=self.name,
                target="ChatBot",
                payload={"state": self.state.name}
            )
            self.bus.publish(response)
    
    def on_pause_command(self, message: Message):
        self.pause()

    def on_resume_command(self, message: Message):
        self.resume()

    def start(self):
        """Starts the agent loop."""
        self.state = AgentState.RUNNING
        self.logger.info(f"{self.name} started.")
        self._run_loop()

    def stop(self):
        """Stops the agent."""
        self.state = AgentState.STOPPED
        self.logger.info(f"{self.name} stopped.")

    def pause(self):
        """Pauses the agent."""
        if self.state == AgentState.RUNNING:
            self.state = AgentState.PAUSED
            self.logger.info(f"{self.name} paused.")

    def resume(self):
        """Resumes the agent."""
        if self.state == AgentState.PAUSED:
            self.state = AgentState.RUNNING
            self.logger.info(f"{self.name} resumed.")

    def _run_loop(self):
        """Internal loop handling the agent cycle."""
        try:
            while self.state != AgentState.STOPPED:
                if self.state == AgentState.RUNNING:
                    self.perceive()
                    self.decide()
                    self.act()
                elif self.state == AgentState.PAUSED:
                    time.sleep(0.1)  # Sleep to prevent busy waiting
                elif self.state == AgentState.IDLE:
                    time.sleep(0.1)
                
                # Small delay to prevent CPU hogging
                time.sleep(0.05)
                
        except Exception as e:
            self.state = AgentState.ERROR
            self.logger.error(f"Agent {self.name} encountered an error: {e}")
            self.handle_error(e)

    @abstractmethod
    def perceive(self):
        """Gather information from the environment."""
        pass

    @abstractmethod
    def decide(self):
        """Process information and make decisions."""
        pass

    @abstractmethod
    def act(self):
        """Execute actions based on decisions."""
        pass

    def handle_error(self, error: Exception):
        """Optional error handling hook."""
        pass
