import unittest
import threading
import time
from core.fsm import AgentState
from core.base_agent import BaseAgent
from core.messaging import MessageBus


class MockFsmAgent(BaseAgent):
    """Simple agent for testing FSM transitions."""
    def perceive(self): pass
    def decide(self): pass
    def act(self): pass


class TestFSM(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus()
        self.agent = MockFsmAgent("TestAgent", self.bus)

    def test_initial_state(self):
        """Test that a new agent starts in IDLE state."""
        self.assertEqual(self.agent.state, AgentState.IDLE)

    def test_valid_transition(self):
        """Test a standard valid transition update."""
        self.agent.transition_state(AgentState.RUNNING, "Starting up")
        self.assertEqual(self.agent.state, AgentState.RUNNING)

    def test_state_change_event(self):
        """Test that a transition publishes the correct event."""
        # Create a subscriber to verify the message
        received = []
        def on_change(msg):
            received.append(msg)
        
        self.bus.subscribe("agent.state_change.v1", on_change)

        self.agent.transition_state(AgentState.PAUSED, "Pausing for test")
        
        # Allow async bus to process
        time.sleep(0.1)
        
        self.assertEqual(len(received), 1)
        msg = received[0]
        self.assertEqual(msg.payload["previous_state"], "IDLE") # Starts IDLE
        self.assertEqual(msg.payload["new_state"], "PAUSED")
        self.assertEqual(msg.payload["reason"], "Pausing for test")

    def test_idempotent_transition(self):
        """Test that transitioning to the same state does not trigger new events."""
        # First transition
        self.agent.transition_state(AgentState.RUNNING, "Start")
        
        received = []
        def on_change(msg):
            received.append(msg)
        self.bus.subscribe("agent.state_change.v1", on_change)
        
        # Redundant transition
        self.agent.transition_state(AgentState.RUNNING, "Redundant start")
        
        time.sleep(0.1)
        self.assertEqual(len(received), 0, "Should not publish event if state is unchanged")

    def test_thread_safety(self):
        """Test that concurrent transitions do not corrupt state."""
        # We try to transition rapidly from multiple threads
        # The agent lock should ensure sequential processing, 
        # but mostly we want to ensure no crash and final state is valid.
        
        def task():
            for _ in range(100):
                self.agent.transition_state(AgentState.RUNNING, "Stress test")
                self.agent.transition_state(AgentState.IDLE, "Stress test")

        threads = [threading.Thread(target=task) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # Just ensure we verify it's a valid enum
        self.assertIsInstance(self.agent.state, AgentState)

if __name__ == "__main__":
    unittest.main()
