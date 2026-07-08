export default async function handler(req, res) {
  const mode = req.query.mode === 'stock' ? 'stock' : 'etf';
  const workflowFile = mode === 'stock' ? 'stock_intraday.yml' : 'etf_daily.yml';
  
  // GitHub API endpoint to trigger a workflow_dispatch event
  const url = `https://api.github.com/repos/Adityak2002/trading-advisor/actions/workflows/${workflowFile}/dispatches`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.GITHUB_PAT}`,
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: {
          reason: 'Manual trigger via Vercel API / Claude'
        }
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      return res.status(response.status).send(`Error triggering workflow: ${response.statusText}\n${errorText}`);
    }

    // Serve a simple plain text response confirming the trigger
    const host = req.headers.host || 'your-app.vercel.app';
    res.setHeader('Content-Type', 'text/plain');
    res.status(200).send(`✅ Triggered ${mode.toUpperCase()} workflow successfully!

The GitHub Action is now running in the background. It will take about 2-3 minutes to complete.

After 3 minutes, you can fetch the updated report by asking me to read:
https://${host}/api/report?mode=${mode}`);
    
  } catch (error) {
    res.status(500).send(`Server Error: ${error.message}`);
  }
}
