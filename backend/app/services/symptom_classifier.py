"""Symptom classification using a fine-tuned ClinicalBERT model.

The model is loaded lazily on first use rather than at import time. This
repo does not ship a trained model at MODEL_PATH (see
app/services/train_clinicalbert.py to train and save one) — eagerly
loading it at import time would crash the whole FastAPI app on startup
just because this one feature isn't set up yet. Instead, classify_symptom
raises a clear, catchable error only when actually called.
"""
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from app.services.disease_labels import DISEASE_LABELS

MODEL_PATH = "./models/clinicalbert-disease"

_tokenizer = None
_model = None
_load_error: Exception | None = None


def _ensure_loaded():
    global _tokenizer, _model, _load_error
    if _tokenizer is not None and _model is not None:
        return
    if _load_error is not None:
        raise _load_error
    try:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
    except Exception as e:
        _load_error = RuntimeError(
            f"ClinicalBERT model not available at '{MODEL_PATH}'. "
            "Train and save a model there first (see train_clinicalbert.py). "
            f"Original error: {e}"
        )
        raise _load_error


def classify_symptom(symptoms: str) -> dict:
    _ensure_loaded()
    inputs = _tokenizer(symptoms, return_tensors="pt", truncation=True, padding=True)
    outputs = _model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
    pred_idx = torch.argmax(probs, dim=-1).item()
    disease = DISEASE_LABELS[pred_idx]
    confidence = probs[0][pred_idx].item()

    # Simple severity classification (can be replaced with a trained severity model)
    if confidence > 0.8:
        severity = "High"
    elif confidence > 0.5:
        severity = "Medium"
    else:
        severity = "Low"

    return {"disease": disease, "severity": severity, "confidence": confidence}