from app.services.ai_client import get_client, CHATBOT_MODEL

_client = get_client()


def summarize_medical_report(report_text: str) -> dict:
    if _client is None:
        return {"summary": "AI summary unavailable: no AI provider configured. Set GEMINI_API_KEY (free) or OPENAI_API_KEY in backend/.env."}

    prompt = f"""
    You are a medical assistant. Read the following medical report.

    Medical Report: {report_text}
    Please provide a concise summary in the following format:
    - Patient Overview
    - Key Findings
    - Diagnosis Summary
    - Recommended Follow-up
    """

    try:
        response = _client.chat.completions.create(
            model=CHATBOT_MODEL,
            messages=[
                {"role": "system", "content": "You are a medical summarization assistant."},
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        # Don't let a quota/billing/network/model error from OpenAI crash
        # the whole request with an opaque 500 — surface a clear message.
        return {"summary": f"AI summary unavailable: {e}"}

    return {"summary": response.choices[0].message.content}
