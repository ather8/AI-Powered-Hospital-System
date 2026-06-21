#!/usr/bin/env python3
"""Pre-build the FAISS index for the clinical search RAG pipeline.

Run this script once (or after changing the source data) to produce the
`medical_guidelines_index/` directory that ai_clinical_search.py loads at
startup. Building the index is slow (it calls the embedding API for every
chunk), so doing it offline avoids re-doing it on every cold start.

Usage
-----
    cd backend
    python build_faiss_index.py [--csv data/Healthcare.csv] [--out medical_guidelines_index]

Environment
-----------
    Requires GEMINI_API_KEY or OPENAI_API_KEY to be set (same as the app).
    Install the full deps first: pip install -r requirements.txt faiss-cpu

The script:
    1. Loads the CSV (or a stub if the file is absent).
    2. Splits text into ~500-token chunks with 50-token overlap.
    3. Calls the embeddings API for each chunk.
    4. Saves the FAISS index to --out (two files: index.faiss + index.pkl).
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure app config is importable
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(override=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS index for clinical search.")
    parser.add_argument("--csv", default="data/Healthcare.csv", help="Source CSV file")
    parser.add_argument("--out", default="medical_guidelines_index", help="Output directory")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    args = parser.parse_args()

    # Late imports so missing deps give a clear error
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import FAISS
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError as e:
        sys.exit(
            f"Missing dependency: {e}\n"
            "Install: pip install langchain langchain-openai langchain-community faiss-cpu"
        )

    from app.services.ai_client import EMBEDDING_MODEL, langchain_kwargs

    kw = langchain_kwargs()
    if not kw.get("api_key"):
        sys.exit("No API key found. Set GEMINI_API_KEY or OPENAI_API_KEY in backend/.env")

    # ── Load source documents ──────────────────────────────────────────────
    csv_path = Path(args.csv)
    if csv_path.exists():
        import pandas as pd
        df = pd.read_csv(csv_path)
        # Combine all text columns into one string per row
        texts = df.astype(str).apply(lambda row: " | ".join(row.values), axis=1).tolist()
        print(f"Loaded {len(texts)} rows from {csv_path}")
    else:
        print(f"Warning: {csv_path} not found — using built-in medical stub data.")
        texts = [
            "Community-acquired pneumonia (CAP) first-line treatment: Amoxicillin 500mg TDS for 5 days in low-severity cases (CURB-65 score 0-1). Add clarithromycin if atypical organisms suspected.",
            "Type 2 Diabetes management: Metformin is first-line pharmacotherapy. Target HbA1c <7% for most patients. Add SGLT-2 inhibitor or GLP-1 agonist if cardiovascular risk is high.",
            "Hypertension first-line: ACE inhibitor or ARB for diabetics and those with CKD. Calcium channel blocker or thiazide for others. Target BP <140/90 mmHg.",
            "Sepsis (Sepsis-3): Give IV antibiotics within 1 hour of recognition. Obtain blood cultures before antibiotics. IV fluid bolus 30 mL/kg crystalloid within 3 hours if hypotensive.",
            "Acute MI (STEMI): Primary PCI within 90 minutes door-to-balloon. Dual antiplatelet therapy (aspirin + P2Y12 inhibitor). Anticoagulation with heparin.",
            "Asthma acute exacerbation: Short-acting beta-agonist (salbutamol) via nebuliser. Oral prednisolone 40-50mg for 5 days. Consider IV magnesium for severe attacks.",
            "Stroke (ischaemic): IV alteplase within 4.5 hours of symptom onset if no contraindications. Aspirin 300mg after haemorrhage excluded by CT. Admit to stroke unit.",
            "Heart failure with reduced ejection fraction: ACE inhibitor/ARB + beta-blocker + aldosterone antagonist. Loop diuretic for fluid overload. ICD if EF <35%.",
            "DVT treatment: Low-molecular-weight heparin (LMWH) or direct oral anticoagulants (DOACs) such as rivaroxaban or apixaban. Duration: 3 months for provoked, 6+ months for unprovoked.",
            "Urinary tract infection (uncomplicated): Trimethoprim 200mg BD for 7 days or nitrofurantoin 100mg MR BD for 5 days. Avoid fluoroquinolones for uncomplicated UTI.",
        ]
        print(f"Using {len(texts)} built-in stub documents.")

    # ── Split into chunks ──────────────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    chunks = splitter.create_documents(texts)
    print(f"Split into {len(chunks)} chunks (chunk_size={args.chunk_size}, overlap={args.chunk_overlap})")

    # ── Build and save FAISS index ─────────────────────────────────────────
    print(f"Building FAISS index with model '{EMBEDDING_MODEL}' (this may take a moment)…")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, **kw)
    vectorstore = FAISS.from_documents(chunks, embeddings)

    out_dir = args.out
    vectorstore.save_local(out_dir)
    print(f"✓ FAISS index saved to ./{out_dir}/")
    print("  Commit this directory or copy it to the server before starting the app.")


if __name__ == "__main__":
    main()
