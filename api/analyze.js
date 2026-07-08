export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { reportText } = req.body;
  if (!reportText) {
    return res.status(400).json({ error: 'Missing reportText in request body' });
  }

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'GEMINI_API_KEY is not configured on the server.' });
  }

  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=${apiKey}`;

    const prompt = `You are an expert quantitative trading analyst. Review the following automated trading report and provide a concise, high-level summary of the market context, top entry candidates, and any critical warnings or exits. Format your response in clean markdown with bullet points. Keep it punchy and actionable.\n\nReport:\n${reportText}`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: prompt }]
        }],
        generationConfig: {
          temperature: 0.2,
          maxOutputTokens: 1024,
        }
      })
    });

    if (!response.ok) {
      const errorData = await response.text();
      return res.status(response.status).json({ error: `Gemini API Error: ${errorData}` });
    }

    const data = await response.json();
    const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text || "No insights generated.";

    res.status(200).json({ insights: generatedText });

  } catch (error) {
    res.status(500).json({ error: `Server Error: ${error.message}` });
  }
}
