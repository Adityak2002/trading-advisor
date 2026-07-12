export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { reportText, messages } = req.body;
  if (!reportText) {
    return res.status(400).json({ error: 'Missing reportText in request body' });
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'GEMINI_API_KEY is not configured on the server.' });
  }

  const models = [
    'gemini-3.5-flash',
    'gemini-3.1-pro-preview',
    'gemini-3.1-flash-lite',
    'gemini-3-flash-preview'
  ];

  // If no messages were sent, default to the initial "Generate Insights" behavior
  const chatHistory = messages && messages.length > 0 ? messages : [
    {
      role: "user",
      parts: [{ text: "Provide a concise, high-level summary of the market context, top entry candidates, and any critical warnings or exits. Format your response in clean markdown with bullet points. Keep it punchy and actionable." }]
    }
  ];

  let lastError = null;
  for (const model of models) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          systemInstruction: {
            parts: [{ text: `You are an expert quantitative trading analyst. You are chatting with a trader. Answer their questions based strictly on the following automated trading report.\n\nReport Context:\n${reportText}` }]
          },
          contents: chatHistory,
          generationConfig: {
            temperature: 0.2,
            maxOutputTokens: 2048,
          }
        })
      });

      if (response.ok) {
        const data = await response.json();
        const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text || "No insights generated.";
        return res.status(200).json({ reply: generatedText });
      } else {
        const errorData = await response.text();
        lastError = `Gemini API Error for ${model} (status ${response.status}): ${errorData}`;
        console.warn(lastError);
      }
    } catch (error) {
      lastError = `Fetch error for ${model}: ${error.message}`;
      console.warn(lastError);
    }
  }

  return res.status(500).json({ error: `All Gemini models failed. Last error: ${lastError}` });
}
