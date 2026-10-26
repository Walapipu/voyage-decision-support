import unittest
from unittest.mock import patch

from voyage.chat import chat_reply


def response(message):
    return {"model": "test/free", "choices": [{"message": message, "finish_reason": "stop"}]}


class ChatTests(unittest.TestCase):
    @patch("voyage.chat.load_settings", return_value=("test-secret", "openrouter/free"))
    def test_model_tools_engine_explanation(self, settings):
        first = response({"role": "assistant", "content": None, "tool_calls": [{"id": "one", "type": "function", "function": {
            "name": "compare_vessels", "arguments": '{"cargo_id":"CC-02","lift_tonnes":164000}'}}]})
        second = response({"role": "assistant", "content": "MF-02 has higher contribution."})
        with patch("voyage.chat.api_request", side_effect=[first, second]) as api:
            answer = chat_reply([{"role": "user", "content": "Compare CC-02 at 164000 tonnes"}])
        self.assertEqual(api.call_count, 2)
        self.assertEqual(answer["evidence"][0]["result"]["rows"][0]["vessel_id"], "MF-02")
        request = api.call_args.args[2]
        self.assertEqual(request["tool_choice"], "none")
        self.assertTrue(any(m["role"] == "tool" for m in request["messages"]))
        self.assertEqual(request["provider"]["max_price"], {"prompt": 0, "completion": 0})

    @patch("voyage.chat.load_settings", return_value=("test-secret", "openrouter/free"))
    def test_engine_results_survive_explanation_failure(self, settings):
        first = response({"role": "assistant", "tool_calls": [{"id": "one", "type": "function", "function": {
            "name": "compare_vessels", "arguments": '{"cargo_id":"CC-02","lift_tonnes":164000}'}}]})
        with patch("voyage.chat.api_request", side_effect=[first, ValueError("Rate limited")]):
            answer = chat_reply([{"role": "user", "content": "Compare"}])
        self.assertEqual(len(answer["evidence"][0]["result"]["rows"]), 4)
        self.assertIn("unavailable", answer["notice"])
        self.assertIn("186,749", answer["content"])

    @patch("voyage.chat.load_settings", return_value=("test-secret", "paid-model"))
    def test_paid_model_blocked_before_network(self, settings):
        with patch("voyage.chat.api_request") as api, self.assertRaises(ValueError):
            chat_reply([{"role": "user", "content": "Hello"}])
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
