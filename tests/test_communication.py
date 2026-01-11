import unittest
import json
import time
from core.messaging import Message, MessageValidator

class TestCommunication(unittest.TestCase):
    def test_message_creation(self):
        msg = Message(
            type="test.message",
            source="test_source",
            target="test_target",
            payload={"key": "value"}
        )
        self.assertEqual(msg.type, "test.message")
        self.assertEqual(msg.source, "test_source")
        self.assertEqual(msg.payload["key"], "value")
        self.assertIsInstance(msg.timestamp, float)

    def test_json_serialization(self):
        msg = Message(
            type="test.message",
            source="src",
            target="dst",
            payload={"data": 123}
        )
        json_str = msg.to_json()
        msg_back = Message.from_json(json_str)
        
        self.assertEqual(msg.type, msg_back.type)
        self.assertEqual(msg.payload, msg_back.payload)

    def test_validation_success(self):
        valid_data = {
            "type": "test",
            "source": "src",
            "target": "dst",
            "timestamp": time.time(),
            "payload": {},
            "status": "new",
            "context": {}
        }
        self.assertTrue(MessageValidator.validate(valid_data))

    def test_validation_failure(self):
        invalid_data = {
            "type": "test",
            # Missing source, target, etc.
        }
        with self.assertRaises(ValueError):
            MessageValidator.validate(invalid_data)

    def test_json_validation(self):
        valid_json = json.dumps({
            "type": "test",
            "source": "src",
            "target": "dst",
            "timestamp": 1.0,
            "payload": {},
            "status": "new",
            "context": {}
        })
        self.assertTrue(MessageValidator.validate_json(valid_json))

if __name__ == '__main__':
    unittest.main()
