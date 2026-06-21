from app.services.ai_client import get_client, CHATBOT_MODEL

_client = get_client()


def generate_medical_note(raw_text: str) -> dict:
    if _client is None:
        return {"structured_note": "AI notes unavailable: no AI provider configured. Set GEMINI_API_KEY (free) or OPENAI_API_KEY in backend/.env."}

    prompt = f"""
    You are a medical assistant. Read the doctor's free-form notes. 
    Extract the information and structure it into a standard SOAP format:
    - Subjective (Patient's reported symptoms)
    - Objective (Doctor's observations, if any)
    - Assessment (Potential diagnosis)
    - Plan (Medication, tests, and follow-up)

    Format the output cleanly with bold headers. Use professional medical terminology.

    Free-form input: {raw_text}
    """

    try:
        response = _client.chat.completions.create(
            model=CHATBOT_MODEL,
            messages=[
                {"role": "system", "content": "You are a medical assistant."},
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        # Don't let a quota/billing/network/model error from OpenAI crash
        # the whole request with an opaque 500 — surface a clear message.
        return {"structured_note": f"AI notes unavailable: {e}"}

    return {"structured_note": response.choices[0].message.content}
