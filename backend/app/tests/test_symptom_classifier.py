"""Tests for app/services/symptom_classifier.py.

Covers the "honest fallback" this module exists for: when no trained model
is present at MODEL_PATH (the default, out-of-the-box state of this repo),
_ensure_loaded must raise a clear, catchable RuntimeError rather than
crashing the app or silently returning garbage -- and it must not re-attempt
the (expensive, slow-to-fail) load on every subsequent call once it's known
to fail. The happy path (a model present and returning predictions) is
exercised with a mocked tokenizer/model so these tests don't need an actual
trained model checkpoint.
"""
import pytest
import torch
from unittest.mock import MagicMock, patch

import app.services.symptom_classifier as mod


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Each test starts from a clean slate: no cached tokenizer/model/error.
    Without this, the load-failure caching behavior under test would leak
    between tests (and between this module and any other code that happens
    to import symptom_classifier first)."""
    mod._tokenizer = None
    mod._model = None
    mod._load_error = None
    yield
    mod._tokenizer = None
    mod._model = None
    mod._load_error = None


class _FakeModelOutput:
    def __init__(self, logits):
        self.logits = logits


def _patch_pretrained(tokenizer_side_effect=None, model_side_effect=None):
    """Patch the two from_pretrained calls _ensure_loaded makes."""
    tok_patch = patch.object(
        mod.AutoTokenizer, "from_pretrained",
        side_effect=tokenizer_side_effect or (lambda *a, **k: MagicMock()),
    )
    model_patch = patch.object(
        mod.AutoModelForSequenceClassification, "from_pretrained",
        side_effect=model_side_effect or (lambda *a, **k: MagicMock()),
    )
    return tok_patch, model_patch


# ---------------------------------------------------------------------------
# Honest fallback when no model is present
# ---------------------------------------------------------------------------

class TestLoadFailureFallback:
    def test_missing_model_raises_runtime_error_mentioning_model_path(self):
        tok_patch, model_patch = _patch_pretrained(
            tokenizer_side_effect=OSError("no such file or directory"),
        )
        with tok_patch, model_patch:
            with pytest.raises(RuntimeError) as exc_info:
                mod.classify_symptom("fever and cough")
        assert mod.MODEL_PATH in str(exc_info.value)
        assert "train_clinicalbert" in str(exc_info.value)

    def test_load_failure_is_cached_not_retried(self):
        """A second call after a load failure must not call from_pretrained
        again -- it should immediately re-raise the cached error. Retrying a
        guaranteed-to-fail disk/network load on every chatbot message would
        be needlessly slow."""
        tok_patch, model_patch = _patch_pretrained(
            tokenizer_side_effect=OSError("no such file or directory"),
        )
        with tok_patch as tok_mock, model_patch:
            with pytest.raises(RuntimeError):
                mod.classify_symptom("fever")
            assert tok_mock.call_count == 1

            with pytest.raises(RuntimeError):
                mod.classify_symptom("still fever")
            # Not called again -- the cached _load_error was raised instead.
            assert tok_mock.call_count == 1

    def test_cached_error_is_the_same_exception_instance(self):
        tok_patch, model_patch = _patch_pretrained(
            tokenizer_side_effect=OSError("missing"),
        )
        with tok_patch, model_patch:
            with pytest.raises(RuntimeError) as first:
                mod.classify_symptom("a")
            with pytest.raises(RuntimeError) as second:
                mod.classify_symptom("b")
        assert first.value is second.value

    def test_model_load_failure_also_caught(self):
        """The tokenizer can load fine while the model checkpoint itself is
        missing/corrupt -- that must fail the same way."""
        tok_patch, model_patch = _patch_pretrained(
            model_side_effect=OSError("model weights not found"),
        )
        with tok_patch, model_patch:
            with pytest.raises(RuntimeError):
                mod.classify_symptom("headache")


# ---------------------------------------------------------------------------
# Happy path: a model is available
# ---------------------------------------------------------------------------

class TestClassifySuccess:
    def _patch_loaded(self, logits_row, disease_labels):
        """Patch in a fake tokenizer + model pair that always returns
        `logits_row`, and a fake DISEASE_LABELS list so the test doesn't
        depend on the real data/Doctor_Versus_Disease.csv contents."""
        fake_tokenizer = MagicMock(return_value={})
        fake_model = MagicMock(return_value=_FakeModelOutput(torch.tensor([logits_row])))
        tok_patch = patch.object(mod.AutoTokenizer, "from_pretrained", return_value=fake_tokenizer)
        model_patch = patch.object(
            mod.AutoModelForSequenceClassification, "from_pretrained", return_value=fake_model
        )
        labels_patch = patch.object(mod, "DISEASE_LABELS", disease_labels)
        return tok_patch, model_patch, labels_patch

    def test_returns_predicted_disease_and_confidence(self):
        tok_patch, model_patch, labels_patch = self._patch_loaded(
            logits_row=[5.0, 0.1, 0.1], disease_labels=["Flu", "Migraine", "Allergy"]
        )
        with tok_patch, model_patch, labels_patch:
            result = mod.classify_symptom("runny nose and fever")
        assert result["disease"] == "Flu"
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["severity"] in {"High", "Medium", "Low"}

    @pytest.mark.parametrize(
        "logits_row,expected_severity",
        [
            ([10.0, -10.0], "High"),  # softmax ~1.0 -> > 0.8
            ([0.7, 0.3], "Medium"),   # softmax ~0.6 -> > 0.5, <= 0.8
            ([0.0, 0.0], "Low"),      # tied logits -> softmax exactly 0.5, not > 0.5
        ],
    )
    def test_severity_buckets_follow_confidence_thresholds(self, logits_row, expected_severity):
        tok_patch, model_patch, labels_patch = self._patch_loaded(
            logits_row=logits_row, disease_labels=["DiseaseA", "DiseaseB"]
        )
        with tok_patch, model_patch, labels_patch:
            result = mod.classify_symptom("some symptom")
        if result["confidence"] > 0.8:
            assert expected_severity == "High"
        elif result["confidence"] > 0.5:
            assert expected_severity == "Medium"
        else:
            assert expected_severity == "Low"

    def test_loaded_tokenizer_and_model_are_reused_across_calls(self):
        """Once loaded successfully, subsequent calls must not reload from
        disk -- _ensure_loaded should short-circuit when _tokenizer/_model
        are already set."""
        tok_patch, model_patch, labels_patch = self._patch_loaded(
            logits_row=[5.0, 0.1], disease_labels=["DiseaseA", "DiseaseB"]
        )
        with tok_patch as tok_mock, model_patch, labels_patch:
            mod.classify_symptom("first call")
            mod.classify_symptom("second call")
            assert tok_mock.call_count == 1
