from abc import ABC, abstractmethod
import time
import logging
import json
import os
import threading
from typing import Optional, Dict, Any
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
        self._state_lock = threading.Lock()

        if self.bus:
            self.bus.subscribe("control.agent.pause", self.on_pause_command)
            self.bus.subscribe("control.agent.resume", self.on_resume_command)
            self.bus.subscribe("control.agent.stop", self.on_stop_command)
            self.bus.subscribe("control.agent.status.request", self.on_status_request)

            # Targeted commands
            target_name = self.name.lower()  # e.g. "minerbot"
            self.bus.subscribe(f"control.{target_name}.pause", self.on_pause_command)
            self.bus.subscribe(f"control.{target_name}.resume", self.on_resume_command)
            self.bus.subscribe(f"control.{target_name}.stop", self.on_stop_command)

    def transition_state(self, new_state: AgentState, reason: str):
        """
        Transitions the agent to a new state with structured logging.

        Args:
            new_state (AgentState): The target state.
            reason (str): The reason for the transition.
        """
        """
        Transition state logic with thread safety and notifications.
        """
        with self._state_lock:
            if self.state != new_state:
                previous_state = self.state
                self.state = new_state

                # Structured Log
                log_payload = {
                    "event": "state_transition",
                    "timestamp": time.time(),
                    "agent": self.name,
                    "previous_state": previous_state.name,
                    "new_state": new_state.name,
                    "reason": reason,
                }
                self.logger.info(f"State Transition: {log_payload}")

                # Notification
                if self.bus:
                    msg = Message(
                        type="agent.state_change.v1",
                        source=self.name,
                        target="all",
                        payload={
                            "previous_state": previous_state.name,
                            "new_state": new_state.name,
                            "reason": reason,
                        },
                    )
                    self.bus.publish(msg)

    def on_status_request(self, message: Message):
        """Responds with the current status."""
        if self.bus:
            try:
                payload = {"state": self.state.name}
                # Allow subclasses to inject more info
                if hasattr(self, "get_additional_status"):
                    try:
                        payload.update(self.get_additional_status())
                    except Exception as e:
                        self.logger.error(f"Error getting additional status: {e}")
                        payload["error"] = str(e)

                response = Message(
                    type="control.agent.status.report",
                    source=self.name,
                    target="ChatBot",
                    payload=payload,
                )
                self.bus.publish(response)
            except Exception as e:
                self.logger.error(f"Error sending status report: {e}")

    def on_pause_command(self, message: Message):
        self.pause()

    def on_resume_command(self, message: Message):
        self.resume()

    def on_stop_command(self, message: Message):
        self.stop()

    def start(self):
        """Starts the agent loop."""
        self.load_checkpoint()
        self.transition_state(AgentState.RUNNING, "Agent startup initiated")
        self._run_loop()

    def stop(self):
        """Stops the agent."""
        self.transition_state(AgentState.STOPPED, "Agent received stop command")
        self.save_checkpoint()

    def pause(self):
        """Pauses the agent."""
        if self.state == AgentState.RUNNING:
            self.transition_state(AgentState.PAUSED, "Agent received pause command")
            self.save_checkpoint()

    def resume(self):
        """Resumes the agent."""
        if self.state == AgentState.PAUSED:
            self.transition_state(AgentState.RUNNING, "Agent received resume command")

    def save_checkpoint(self):
        """Serializes current state to a JSON file."""
        try:
            data = {
                "state": self.state.name,
                "timestamp": time.time(),
                "custom_data": self._get_checkpoint_data(),
            }

            # Ensure checkpoints_dir exists
            if not os.path.exists("checkpoints"):
                os.makedirs("checkpoints")

            path = f"checkpoints/{self.name.lower()}_checkpoint.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            self.logger.info(f"Checkpoint saved to {path}")

        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self):
        """Restores state from a JSON file if available."""
        path = f"checkpoints/{self.name.lower()}_checkpoint.json"
        if not os.path.exists(path):
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            self.logger.info(
                f"Loading checkpoint from {path} (Timestamp: {data.get('timestamp')})"
            )

            # We don't necessarily want to restore "state" blindly (e.g. don't start in PAUSED/STOPPED)
            # But the requirement implies recovery after interruptions.
            if "state" in data:
                saved_state_name = data["state"]
                # If saved state was RUNNING or IDLE, restore it.
                # If it was STOPPED or ERROR, maybe we default to IDLE to allow restart.
                # If PAUSED, we restore PAUSED.
                if saved_state_name in ["RUNNING", "IDLE", "PAUSED"]:
                    try:
                        self.state = AgentState[saved_state_name]
                        self.logger.info(f"Restored state to {self.state.name}")
                    except KeyError:
                        self.logger.warning(f"Unknown state in checkpoint: {saved_state_name}")
                else:
                    self.logger.info(f"Ignored saved state '{saved_state_name}', defaulting to current ({self.state.name})")

            if "custom_data" in data:
                self._apply_checkpoint_data(data["custom_data"])

        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")

    def _get_checkpoint_data(self) -> Dict[str, Any]:
        """Hook for subclasses to provide data to save."""
        return {}

    def _apply_checkpoint_data(self, data: Dict[str, Any]):
        """Hook for subclasses to restore data."""
        pass

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
            self.transition_state(AgentState.ERROR, f"Crash in run loop: {str(e)}")
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
