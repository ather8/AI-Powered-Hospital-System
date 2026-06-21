"""Train the ClinicalBERT symptom classifier used by app/services/symptom_classifier.py.

WHY THIS EXISTS
----------------
By default this project does NOT ship a trained model. symptom_classifier.py
looks for one at ``./models/clinicalbert-disease`` and, if it's missing,
raises a clear RuntimeError that the chatbot route catches and turns into an
honest "classification unavailable" response instead of a crash. This script
is how you produce that model so classification actually starts working.

WHAT YOU NEED TO SUPPLY
------------------------
This repo ships `data/Doctor_Versus_Disease.csv`, but that file only maps
disease -> department; it has no symptom text, so it cannot be used to train
the classifier on its own. You need a separate labeled dataset with two
columns:

    1. A free-text symptom description, e.g. "fever, cough, sore throat"
    2. A disease label whose *name* matches one of the entries produced by
       app/services/disease_labels.py (these are the disease names already
       used by data/Doctor_Versus_Disease.csv, capitalized/stripped).

A good source is the "Disease and Symptoms" style datasets on Kaggle (search
for "disease symptom prediction dataset") — pick one whose disease names
overlap with data/Doctor_Versus_Disease.csv, or relabel rows that don't.
Save it as a CSV and point --csv at it. Rows whose label doesn't match a
known disease name are skipped (and counted) rather than silently mistrained.

INSTALL (training-only extras)
-------------------------------
`transformers` and `torch` are already in requirements.txt (symptom_classifier.py
needs them too, for inference). Training additionally needs:

    pip install datasets accelerate

USAGE
-----
    cd backend
    python -m app.services.train_clinicalbert --csv path/to/your_dataset.csv

    # Common overrides:
    python -m app.services.train_clinicalbert \\
        --csv path/to/your_dataset.csv \\
        --text-col symptoms --label-col disease \\
        --epochs 3 --batch-size 16 --val-split 0.1

On success the model and tokenizer are saved to --output-dir, which defaults
to ``./models/clinicalbert-disease`` — the exact path symptom_classifier.py's
MODEL_PATH already points at. Run this from the `backend/` directory (or pass
an absolute --output-dir) so the relative path lines up. No code changes or
restarts of symptom_classifier.py's MODEL_PATH are needed; just restart the
backend process afterward so it picks up the new files lazily on first use.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from app.services.disease_labels import DISEASE_LABELS

MODEL_NAME = "emilyalsentzer/Bio_ClinicalBERT"
DEFAULT_OUTPUT_DIR = "./models/clinicalbert-disease"  # must match symptom_classifier.MODEL_PATH


def _normalize_label(value: str) -> str:
    """Match the normalization disease_labels.py applies to CSV values, so a
    label like " Hypertension " or "hypertension" lines up with the official
    "Hypertension" entry in DISEASE_LABELS."""
    return str(value).strip().capitalize()


def load_and_prepare(csv_path: str, text_col: str, label_col: str):
    if not Path(csv_path).exists():
        sys.exit(
            f"--csv '{csv_path}' does not exist. This script needs a labeled "
            "symptom-text dataset; see the module docstring for what to provide."
        )
    df = pd.read_csv(csv_path)
    for col in (text_col, label_col):
        if col not in df.columns:
            sys.exit(
                f"Column '{col}' not found in {csv_path}. Available columns: "
                f"{list(df.columns)}. Use --text-col/--label-col to match your file."
            )

    label2id = {label: i for i, label in enumerate(DISEASE_LABELS)}
    df = df[[text_col, label_col]].dropna()
    df["__normalized_label"] = df[label_col].map(_normalize_label)

    known_mask = df["__normalized_label"].isin(label2id)
    skipped = int((~known_mask).sum())
    if skipped:
        unknown_examples = sorted(df.loc[~known_mask, "__normalized_label"].unique())[:10]
        print(
            f"Skipping {skipped} row(s) whose label doesn't match a known disease "
            f"name from disease_labels.py. Examples: {unknown_examples}",
            file=sys.stderr,
        )
    df = df[known_mask]
    if df.empty:
        sys.exit(
            "No rows had a label matching a known disease name. Check "
            "--label-col and that your labels overlap with "
            "data/Doctor_Versus_Disease.csv (see disease_labels.py)."
        )

    df["label"] = df["__normalized_label"].map(label2id)
    df = df.rename(columns={text_col: "symptom"})[["symptom", "label"]]
    print(f"Loaded {len(df)} labeled rows across {df['label'].nunique()} disease classes.")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune ClinicalBERT for symptom -> disease classification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", required=True, help="Path to a labeled symptom-text CSV (see module docstring).")
    parser.add_argument("--text-col", default="symptom", help="Column containing free-text symptoms (default: symptom).")
    parser.add_argument("--label-col", default="disease", help="Column containing the disease label (default: disease).")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Where to save the model (default: {DEFAULT_OUTPUT_DIR}).")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--val-split", type=float, default=0.0, help="Fraction held out for eval, e.g. 0.1. 0 = no eval split.")
    args = parser.parse_args()

    if not DISEASE_LABELS:
        sys.exit(
            "DISEASE_LABELS is empty (app/services/disease_labels.py failed to load "
            "data/Doctor_Versus_Disease.csv). Fix that first — the classifier's "
            "output indices are meaningless without it."
        )

    # Imported lazily so `--help` and arg-validation errors above don't pay
    # the cost (or require the extra `datasets`/`accelerate` installs) just
    # to print usage.
    import torch
    from datasets import Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        Trainer,
        TrainingArguments,
    )

    df = load_and_prepare(args.csv, args.text_col, args.label_col)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=len(DISEASE_LABELS)
    )

    if args.val_split > 0:
        full_ds = Dataset.from_pandas(df, preserve_index=False)
        split = full_ds.train_test_split(test_size=args.val_split, seed=42)
        train_ds, eval_ds = split["train"], split["test"]
    else:
        train_ds = Dataset.from_pandas(df, preserve_index=False)
        eval_ds = None

    def tokenize(batch):
        return tokenizer(batch["symptom"], padding="max_length", truncation=True)

    train_ds = train_ds.map(tokenize, batched=True)
    if eval_ds is not None:
        eval_ds = eval_ds.map(tokenize, batched=True)

    training_kwargs = dict(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        save_strategy="epoch",
    )
    if eval_ds is not None:
        # transformers renamed this kwarg from `evaluation_strategy` to
        # `eval_strategy` around v4.41. Try the current name first and fall
        # back so this script keeps working on either version.
        try:
            training_args = TrainingArguments(eval_strategy="epoch", **training_kwargs)
        except TypeError:
            training_args = TrainingArguments(evaluation_strategy="epoch", **training_kwargs)
    else:
        training_args = TrainingArguments(**training_kwargs)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"\nSaved model + tokenizer to '{args.output_dir}'.")
    print(
        "Restart the backend — symptom_classifier.py loads lazily on first "
        "use and will pick this up automatically since the path matches "
        "MODEL_PATH."
    )


if __name__ == "__main__":
    main()
