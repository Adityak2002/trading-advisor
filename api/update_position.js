export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  const { mode, ticker, entryDate, entryPrice, shares, targetPrice, stopPrice } = req.body;

  if (!mode || !ticker || !entryPrice || !shares || !targetPrice || !stopPrice) {
    return res.status(400).json({ error: 'Missing required parameters' });
  }

  const token = process.env.GITHUB_PAT;
  if (!token) {
    return res.status(500).json({ error: 'GITHUB_PAT is not configured on the server.' });
  }

  const formattedTicker = ticker.toUpperCase().endsWith('.NS') ? ticker.toUpperCase() : `${ticker.toUpperCase()}.NS`;
  const targetFile = `positions_${mode}.json`;
  const url = `https://api.github.com/repos/Adityak2002/trading-advisor/contents/data/${targetFile}`;

  try {
    // 1. Fetch the current positions file from GitHub (to get the content and SHA)
    let currentPositions = [];
    let fileSha = null;

    const getResponse = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28'
      }
    });

    if (getResponse.ok) {
      const fileData = await getResponse.json();
      fileSha = fileData.sha;
      // Decode base64 content
      const decodedContent = Buffer.from(fileData.content, 'base64').toString('utf-8');
      try {
        currentPositions = JSON.parse(decodedContent);
        if (!Array.isArray(currentPositions)) {
          currentPositions = [];
        }
      } catch (e) {
        currentPositions = [];
      }
    } else if (getResponse.status !== 404) {
      const errorText = await getResponse.text();
      return res.status(getResponse.status).json({ error: `Failed to fetch existing positions: ${errorText}` });
    }

    // 2. Remove any existing open position for the same ticker
    currentPositions = currentPositions.filter(p => !(p.instrument === formattedTicker && p.status === 'open'));

    // 3. Add the new position
    const capitalDeployed = parseFloat((entryPrice * shares).toFixed(2));
    const newPos = {
      instrument: formattedTicker,
      entry_date: entryDate || new Date().toISOString().split('T')[0],
      entry_price: parseFloat(entryPrice),
      shares: parseInt(shares, 10),
      capital_deployed: capitalDeployed,
      target_price: parseFloat(targetPrice),
      stop_price: parseFloat(stopPrice),
      status: 'open',
      days_held: 0,
      mode: mode
    };

    currentPositions.push(newPos);

    // 4. Base64 encode the updated JSON
    const updatedContentBase64 = Buffer.from(JSON.stringify(currentPositions, null, 2)).toString('base64');

    // 5. Commit/Write back to GitHub
    const putResponse = await fetch(url, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28'
      },
      body: JSON.stringify({
        message: `📈 Add position ${formattedTicker} via web dashboard`,
        content: updatedContentBase64,
        sha: fileSha || undefined,
        branch: 'main'
      })
    });

    if (!putResponse.ok) {
      const errorText = await putResponse.text();
      return res.status(putResponse.status).json({ error: `Failed to save position to GitHub: ${errorText}` });
    }

    res.status(200).json({ message: `✅ Position logged successfully for ${formattedTicker}!` });

  } catch (error) {
    res.status(500).json({ error: `Server Error: ${error.message}` });
  }
}
