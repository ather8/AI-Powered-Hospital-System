import pandas as pd


def load_department_map(path="data/Doctor_Versus_Disease.csv"):
    # This CSV has no header row — it's plain (Disease, Department) pairs
    # from the first line. Letting pandas treat row 1 as a header would
    # silently drop that first disease/department mapping.
    #
    # It's also not UTF-8 — it's Latin-1/cp1252-style and contains a stray
    # non-breaking-space byte (0xA0) that crashes a default-encoding read.
    df = pd.read_csv(path, header=None, names=["Disease", "Department"], encoding="latin-1")
    # Normalize keys (strip whitespace, capitalize) to match the normalization
    # app/services/disease_labels.py applies to the same source file. Without
    # this, keys here keep raw casing/whitespace (e.g. "Hypertension ",
    # "Drug Reaction") while disease_labels.py produces normalized values
    # (e.g. "Hypertension", "Drug reaction") — every lookup from
    # get_department(disease) would then silently miss and fall back to
    # "General Medicine" for every disease, misrouting every triaged patient.
    mapping = {
        str(disease).strip().capitalize(): department
        for disease, department in zip(df["Disease"], df["Department"])
    }
    return mapping


try:
    DEPARTMENT_MAP = load_department_map()
except Exception:
    # Don't let a data file problem crash the entire FastAPI app at import
    # time — get_department() below already has a safe fallback for any
    # disease key it doesn't recognize, so an empty map degrades gracefully.
    DEPARTMENT_MAP = {}


def get_department(disease: str):
    return DEPARTMENT_MAP.get(str(disease).strip().capitalize(), "General Medicine")