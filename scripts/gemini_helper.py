import os
import requests

def get_gemini_summary(report_text: str) -> str:
    """
    Fetches AI summary from Gemini API with fallback mechanisms.
    Tries the following models in sequence:
      1. gemini-3.5-flash
      2. gemini-3.1-pro-preview
      3. gemini-3.1-flash-lite
      4. gemini-3-flash-preview
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not found in environment. Skipping AI summary.")
        return "AI Summary unavailable (No API Key in environment)."

    models = [
        "gemini-3.5-flash",
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview"
    ]
    
    prompt = (
        "Provide a concise, high-level summary of the market context, top entry candidates, "
        "and any critical warnings or exits. Format your response in clean markdown with bullet points. "
        "Keep it punchy, clear, and actionable for a layman."
    )
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "systemInstruction": {
                "parts": [{"text": f"You are an expert quantitative trading analyst. Review the following automated trading report.\n\nReport Context:\n{report_text}"}]
            },
            "contents": [
                { "role": "user", "parts": [{"text": prompt}] }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            }
        }
        try:
            print(f"Trying Gemini model {model}...")
            response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                summary = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if summary:
                    print(f"Success with model {model}!")
                    return summary.strip()
            print(f"Model {model} failed with status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Model {model} generated an exception: {e}")
            
    return "AI Summary unavailable (All Gemini models failed)."
