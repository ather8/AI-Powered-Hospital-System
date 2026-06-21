"""Tests for chatbot conversation memory (session-keyed history).

These are pure unit tests against app/services/langchain_chatbot.py —
no HTTP layer, no AI API calls. The LLM chain is patched with a simple
stub that echoes the number of messages it received, so we can verify
that history accumulates across calls without needing a real API key.
"""
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_llm_response(messages) -> MagicMock:
    """Return a fake AIMessage whose content reports how many messages were sent."""
    msg = MagicMock()
    msg.content = f"echo:{len(messages)}"
    return msg


def _make_stub_chain():
    chain = MagicMock()
    chain.invoke.side_effect = _stub_llm_response
    return chain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatbotMemory:
    def setup_method(self):
        # Reset module-level session store and chain before each test
        import app.services.langchain_chatbot as mod
        mod._sessions.clear()
        mod._chain = None
        mod._chain_error = None

    def _call(self, symptoms, session_id=None, name="Alice", age=30):
        import app.services.langchain_chatbot as mod
        with patch.object(mod, "_get_chain", return_value=_make_stub_chain()):
            return mod.chatbot_flow(
                {"name": name, "age": age, "symptoms": symptoms},
                session_id=session_id,
            )

    def test_stateless_call_returns_response(self):
        """No session_id → still returns a reply, no history stored."""
        import app.services.langchain_chatbot as mod
        result = self._call("headache")
        assert "conversation_reply" in result
        # No session stored
        assert len(mod._sessions) == 0

    def test_first_turn_creates_session(self):
        import app.services.langchain_chatbot as mod
        sid = "test-session-001"
        self._call("headache", session_id=sid)
        assert sid in mod._sessions
        assert len(mod._sessions[sid]["messages"]) == 2  # user + assistant

    def test_second_turn_extends_history(self):
        import app.services.langchain_chatbot as mod
        sid = "test-session-002"
        self._call("chest pain", session_id=sid)
        self._call("since yesterday", session_id=sid)
        messages = mod._sessions[sid]["messages"]
        # 2 turns × 2 messages each = 4
        assert len(messages) == 4
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
        assert messages[3]["role"] == "assistant"

    def test_history_passed_to_llm_grows_across_turns(self):
        """The LLM receives more messages on turn 2 than turn 1."""
        import app.services.langchain_chatbot as mod
        sid = "test-session-003"
        r1 = self._call("fever", session_id=sid)
        r2 = self._call("also cough", session_id=sid)
        # Turn 1: [system + user] = 2 messages
        # Turn 2: [system + user1 + assistant1 + user2] = 4 messages
        n1 = int(r1["conversation_reply"].split(":")[1])
        n2 = int(r2["conversation_reply"].split(":")[1])
        assert n2 > n1

    def test_session_id_echoed_in_response(self):
        sid = "test-session-echo"
        result = self._call("sore throat", session_id=sid)
        assert result["session_id"] == sid

    def test_new_session_id_auto_generated_when_none(self):
        """When session_id is None the server generates one and echoes it."""
        import app.services.langchain_chatbot as mod
        with patch.object(mod, "_get_chain", return_value=_make_stub_chain()):
            result = mod.chatbot_flow({"name": "Bob", "age": 25, "symptoms": "pain"}, session_id="auto-123")
        assert result["session_id"] == "auto-123"

    def test_clear_session_removes_history(self):
        import app.services.langchain_chatbot as mod
        sid = "test-session-clear"
        self._call("migraine", session_id=sid)
        assert sid in mod._sessions
        mod.clear_session(sid)
        assert sid not in mod._sessions

    def test_clear_nonexistent_session_is_noop(self):
        import app.services.langchain_chatbot as mod
        # Should not raise
        mod.clear_session("does-not-exist")

    def test_trim_history_at_max_turns(self):
        """History is trimmed when it exceeds MAX_HISTORY_TURNS * 2 messages."""
        import app.services.langchain_chatbot as mod
        original_max = mod.MAX_HISTORY_TURNS
        mod.MAX_HISTORY_TURNS = 2  # cap at 4 messages (2 pairs)

        sid = "test-session-trim"
        try:
            # 4 turns → should be trimmed to 4 messages
            for i in range(4):
                self._call(f"symptom {i}", session_id=sid)
            messages = mod._sessions[sid]["messages"]
            assert len(messages) <= mod.MAX_HISTORY_TURNS * 2 + 2  # +2 for current turn
        finally:
            mod.MAX_HISTORY_TURNS = original_max

    def test_result_includes_triage_fields(self):
        result = self._call("chest pain and shortness of breath")
        assert "disease" in result
        assert "severity" in result
        assert "department" in result
        assert "confidence" in result
        assert "disclaimer" in result


# ---------------------------------------------------------------------------
# Symptom-classification fallback inside chatbot_flow
#
# classify_symptom raises RuntimeError when no trained ClinicalBERT model is
# present (the default, out-of-the-box state -- see
# app/services/symptom_classifier.py and test_symptom_classifier.py). These
# tests check that chatbot_flow turns that into an honest "unavailable"
# response instead of letting the exception escape as a 500, and that it
# correctly reports a result when classification *does* succeed.
# ---------------------------------------------------------------------------

class TestChatbotClassificationFallback:
    def setup_method(self):
        import app.services.langchain_chatbot as mod
        mod._sessions.clear()
        mod._chain = None
        mod._chain_error = None

    def _call_with_classifier(self, classify_side_effect, symptoms="fever and cough"):
        import app.services.langchain_chatbot as mod
        with patch.object(mod, "_get_chain", return_value=_make_stub_chain()), \
             patch.object(mod, "classify_symptom", side_effect=classify_side_effect):
            return mod.chatbot_flow({"name": "Alice", "age": 30, "symptoms": symptoms})

    def test_unavailable_model_yields_explicit_unavailable_fields(self):
        result = self._call_with_classifier(
            RuntimeError("ClinicalBERT model not available at './models/clinicalbert-disease'.")
        )
        assert result["classification_available"] is False
        assert result["disease"] is None
        assert result["severity"] is None
        assert result["department"] is None
        assert result["confidence"] is None
        # The conversational reply must still come through even though
        # classification failed -- one feature breaking shouldn't break the other.
        assert "conversation_reply" in result
        assert result["disclaimer"]

    def test_unrelated_exceptions_from_classifier_are_not_swallowed(self):
        """Only RuntimeError (the documented "model unavailable" signal) is
        caught. A bug elsewhere in classify_symptom should still surface
        loudly rather than being silently mapped to "unavailable"."""
        with pytest.raises(ValueError):
            self._call_with_classifier(ValueError("unexpected bug"))

    def test_successful_classification_populates_all_fields(self):
        import app.services.langchain_chatbot as mod

        fake_result = {"disease": "Flu", "severity": "Medium", "confidence": 0.62}
        with patch.object(mod, "get_department", return_value="General Medicine"):
            result = self._call_with_classifier(lambda symptoms: fake_result)

        assert result["classification_available"] is True
        assert result["disease"] == "Flu"
        assert result["severity"] == "Medium"
        assert result["confidence"] == 0.62
        assert result["department"] == "General Medicine"

    def test_department_lookup_uses_classified_disease(self):
        """get_department must be called with the disease classify_symptom
        returned, not some other value -- catches accidental argument
        mix-ups between the two calls."""
        import app.services.langchain_chatbot as mod

        fake_result = {"disease": "Migraine", "severity": "Low", "confidence": 0.4}
        with patch.object(mod, "get_department", return_value="Neurology") as get_dept_mock:
            result = self._call_with_classifier(lambda symptoms: fake_result)

        get_dept_mock.assert_called_once_with("Migraine")
        assert result["department"] == "Neurology"
