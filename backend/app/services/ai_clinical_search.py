"""AI clinical search service — RAG pipeline backed by a pre-built FAISS index.

The FAISS index is expensive to build (it calls the embeddings API for every
chunk of the source data). Previously the code tried to build it at import
time, which meant every cold start re-computed it from scratch. Now:

  * At startup we try to *load* a pre-built index from disk
    (``medical_guidelines_index/`` relative to the working directory, or the
    path in the ``FAISS_INDEX_PATH`` env var).
  * If no index is found we fall back gracefully with a clear ``status:
    disabled`` response rather than crashing the whole app.
  * To build / rebuild the index run ``python build_faiss_index.py`` from
    the backend directory (see that script for full usage).

Import paths
------------
This file uses the current (post-0.1) LangChain split:
  * ``langchain_community.vectorstores.FAISS``  (was ``langchain.vectorstores``)
  * ``langchain.chains.RetrievalQA`` still lives in the core package for now
    but is deprecated; we use LCEL-style ``retriever | llm`` instead.
"""
from __future__ import annotations

import os
from app.services.ai_client import CHATBOT_MODEL, EMBEDDING_MODEL, langchain_kwargs

# ---------------------------------------------------------------------------
# Lazy / optional setup — all heavy imports live inside the try block
# ---------------------------------------------------------------------------

_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "medical_guidelines_index")

_clinical_search_fn = None   # set below


def _build_search_fn():
    """Attempt to load the FAISS index and wire the RAG chain.

    Returns a callable(query: str) -> dict on success, or raises with a
    descriptive message so the outer try/except can produce a good status.
    """
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_community.vectorstores import FAISS
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnablePassthrough
    except ImportError as e:
        raise RuntimeError(
            f"LangChain dependencies not installed: {e}. "
            "Run: pip install langchain langchain-openai langchain-community faiss-cpu"
        )

    kw = langchain_kwargs()
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, **kw)

    # Load pre-built index — allow_dangerous_deserialization is required by
    # newer langchain-community because the index file uses pickle.
    if not os.path.isdir(_INDEX_PATH):
        raise RuntimeError(
            f"FAISS index not found at '{_INDEX_PATH}'. "
            "Run 'python build_faiss_index.py' from the backend directory to build it."
        )

    vectorstore = FAISS.load_local(
        _INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    llm = ChatOpenAI(model=CHATBOT_MODEL, temperature=0, **kw)

    prompt = ChatPromptTemplate.from_template(
        "You are a clinical decision-support assistant. "
        "Answer the question using ONLY the provided context. "
        "If the context doesn't cover the question, say so explicitly.\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}"
    )

    def _format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    def _search(query: str) -> dict:
        answer = chain.invoke(query)
        return {"answer": answer}

    return _search


# ---------------------------------------------------------------------------
# Module-level init (lazy, non-fatal)
# ---------------------------------------------------------------------------

_init_error: str | None = None

try:
    _clinical_search_fn = _build_search_fn()
except Exception as _e:
    _init_error = str(_e)


def clinical_search(query: str) -> dict:
    """Public entry point for the clinical search route.

    Returns ``{"answer": str}`` on success or
    ``{"status": "disabled", "detail": str}`` when the RAG pipeline is
    unavailable (missing index, missing deps, or no API key).
    """
    if _clinical_search_fn is not None:
        return _clinical_search_fn(query)
    return {
        "status": "disabled",
        "detail": (
            _init_error
            or "RAG pipeline is disabled. Run 'python build_faiss_index.py' to enable it."
        ),
    }
