export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { mode } = req.body;
  const validModes = ['stock', 'etf', 'intraday'];
  const targetMode = validModes.includes(mode) ? mode : 'etf';

  // We re-use the workflow_dispatch trigger for the respective workflow.
  // On workflow_dispatch, the email step always fires (no schedule condition).
  const workflowMap = {
    stock:    'stock_intraday.yml',
    etf:      'etf_daily.yml',
    intraday: 'intraday.yml',
  };

  const url = `https://api.github.com/repos/Adityak2002/trading-advisor/actions/workflows/${workflowMap[targetMode]}/dispatches`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.GITHUB_PAT}`,
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: { reason: `Manual email trigger for ${targetMode} mode` }
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return res.status(response.status).json({ error: `GitHub API Error: ${errorText}` });
    }

    res.status(200).json({
      message: `✅ Email workflow triggered for ${targetMode.toUpperCase()} mode! The report will be generated and emailed in ~2-3 minutes.`
    });

  } catch (error) {
    res.status(500).json({ error: `Server Error: ${error.message}` });
  }
}
