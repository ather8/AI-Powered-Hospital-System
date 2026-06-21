import pandas as pd


def load_disease_labels(path="data/Doctor_Versus_Disease.csv"):
    """Load the ordered list of disease labels used by the ClinicalBERT
    classifier's output indices.

    Doctor_Versus_Disease.csv has no header row (it's plain Disease,Department
    pairs starting from the first line) and is saved in a Latin-1/cp1252-style
    encoding, not UTF-8 — it contains stray non-breaking-space bytes (0xA0)
    that crash a default pd.read_csv() call. Both are fixed here to match the
    handling already used in app/services/department_mapper.py.
    """
    df = pd.read_csv(path, header=None, names=["Disease", "Department"], encoding="latin-1")
    diseases = df["Disease"].dropna().unique().tolist()
    diseases = [d.strip().capitalize() for d in diseases]
    return diseases


try:
    DISEASE_LABELS = load_disease_labels()
except Exception as e:
    # Don't let a data file problem crash the entire FastAPI app at import
    # time — symptom_classifier.py already guards model loading lazily;
    # this keeps that guarantee intact even if the CSV is missing/broken.
    DISEASE_LABELS = []
    _disease_labels_error = e
