import unittest
from core.messaging import MessageBus, Message, MessageValidator
from core.base_agent import BaseAgent


class MockAgent(BaseAgent):
    def __init__(self, name, bus):
        super().__init__(name, bus)
        self.received_messages = []
        if self.bus:
            self.bus.subscribe("test.topic", self.on_message)

    def on_message(self, message):
        self.received_messages.append(message)

    def perceive(self):
        pass

    def decide(self):
        pass

    def act(self):
        pass


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus()
        import time 

    def test_pub_sub(self):
        """Test the publish-subscribe mechanism."""
        agent = MockAgent("receiver", self.bus)

        msg = Message(
            type="test.topic",
            source="sender",
            target="receiver",
            payload={"info": "hello"},
        )

        self.bus.publish(msg)
        
        # Wait for async dispatch
        import time
        time.sleep(0.1)

        self.assertEqual(len(agent.received_messages), 1)
        self.assertEqual(agent.received_messages[0].payload["info"], "hello")

    def test_multiple_subscribers(self):
        """Test that multiple subscribers receive the same message."""
        agent1 = MockAgent("agent1", self.bus)
        agent2 = MockAgent("agent2", self.bus)

        msg = Message(type="test.topic", source="sender", target="all", payload={})

        self.bus.publish(msg)
        
        # Wait for async dispatch
        import time
        time.sleep(0.1)

        self.assertEqual(len(agent1.received_messages), 1)
        self.assertEqual(len(agent2.received_messages), 1)

    def test_message_validation_rejection(self):
        """Test that the validator rejects messages with missing fields."""
        invalid_data = {
            "type": "broken.topic",
            "source": "malicious_actor",
            # Missing target, payload, timestamp, etc.
        }

        # Ensure the validator raises ValueError for the bad data
        with self.assertRaises(ValueError):
            MessageValidator.validate(invalid_data)


if __name__ == "__main__":
    unittest.main()
