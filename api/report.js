export default async function handler(req, res) {
  const validModes = ['stock', 'etf', 'intraday'];
  const mode = validModes.includes(req.query.mode) ? req.query.mode : 'etf';
  const fileMap = {
    stock:    'stock_report.md',
    etf:      'etf_report.md',
    intraday: 'intraday_report.md',
  };
  const targetFile = fileMap[mode];

  // Use GitHub API to fetch the file contents securely
  const url = `https://api.github.com/repos/Adityak2002/trading-advisor/contents/reports/${targetFile}`;

  try {
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${process.env.GITHUB_PAT}`,
        // Request the raw text format directly (bypasses base64 parsing)
        'Accept': 'application/vnd.github.v3.raw',
        'X-GitHub-Api-Version': '2022-11-28'
      }
    });

    if (!response.ok) {
      const errorText = await response.text();
      return res.status(response.status).send(`Error fetching report: ${response.statusText}\n${errorText}`);
    }

    const text = await response.text();
    
    // Serve as plain text so Claude can read it cleanly
    res.setHeader('Content-Type', 'text/plain');
    res.status(200).send(text);
    
  } catch (error) {
    res.status(500).send(`Server Error: ${error.message}`);
  }
}
