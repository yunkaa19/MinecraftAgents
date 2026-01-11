import unittest
from core.messaging import MessageBus, Message
from core.base_agent import BaseAgent

class MockAgent(BaseAgent):
    def __init__(self, name, bus):
        super().__init__(name, bus)
        self.received_messages = []
        if self.bus:
            self.bus.subscribe("test.topic", self.on_message)

    def on_message(self, message):
        self.received_messages.append(message)

    def perceive(self): pass
    def decide(self): pass
    def act(self): pass

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.bus = MessageBus()

    def test_pub_sub(self):
        agent = MockAgent("receiver", self.bus)
        
        msg = Message(
            type="test.topic",
            source="sender",
            target="receiver",
            payload={"info": "hello"}
        )
        
        self.bus.publish(msg)
        
        self.assertEqual(len(agent.received_messages), 1)
        self.assertEqual(agent.received_messages[0].payload["info"], "hello")

    def test_multiple_subscribers(self):
        agent1 = MockAgent("agent1", self.bus)
        agent2 = MockAgent("agent2", self.bus)
        
        msg = Message(
            type="test.topic",
            source="sender",
            target="all",
            payload={}
        )
        
        self.bus.publish(msg)
        
        self.assertEqual(len(agent1.received_messages), 1)
        self.assertEqual(len(agent2.received_messages), 1)

if __name__ == '__main__':
    unittest.main()
