const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE = process.env.JARB_API_BASE || 'http://localhost:5000';

// Serve static assets for the browser UI.
app.use(express.static(path.join(__dirname, 'public')));

// Expose runtime configuration so the browser knows which backend to call.
app.get('/config.js', (_req, res) => {
    res.type('application/javascript');
    res.send(`window.APP_CONFIG = { API_BASE: ${JSON.stringify(API_BASE)} };`);
});

app.listen(PORT, () => {
    console.log(`JARB Browser UI available at http://localhost:${PORT}`);
    console.log(`Proxying requests directly to ${API_BASE}`);
});
