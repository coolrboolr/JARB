const express = require('express');
const axios = require('axios');
const bodyParser = require('body-parser');
const path = require('path');
const app = express();
const port = 3000;

// Serve static files from the "public" directory
app.use(express.static('public'));
app.use(bodyParser.json());

// Route to interact with the Python API to list tools
app.get('/data', async (req, res) => {
    try {
        const response = await axios.get('http://localhost:5000/api/list_tools');
        res.send(response.data);
    } catch (error) {
        res.status(500).send(error.message);
    }
});

// Route to interact with the Python API to create a tool
app.post('/create_tool', async (req, res) => {
    try {
        const { name, description } = req.body;
        const response = await axios.post('http://localhost:5000/api/create_tool', { name, description });
        res.send(response.data);
    } catch (error) {
        console.error('Error creating tool:', error);
        res.status(500).send({ error: error.message });
    }
});

// Route to serve the tool execution page
app.get('/tool/:name', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'tool.html'));
});

// Route to interact with the Python API to execute a tool
app.post('/execute_tool/:name', async (req, res) => {
    try {
        const toolName = req.params.name;
        const params = req.body.params;
        console.log(`Executing tool: ${toolName} with params:`, params);
        const response = await axios.post('http://localhost:5000/api/use_tool', { tool_name: toolName, params });
        if (response.headers['content-type'].includes('application/json')) {
            res.send(response.data);
        } else {
            console.error('Unexpected response format:', response.data);
            res.status(500).send({ error: 'Unexpected response format' });
        }
    } catch (error) {
        console.error('Error executing tool:', error);
        res.status(500).send({ error: error.message });
    }
});

// Route to fetch tool parameters
app.get('/tool_parameters/:name', async (req, res) => {
    try {
        const toolName = req.params.name;
        const response = await axios.get(`http://localhost:5000/api/tool_parameters/${toolName}`);
        res.send(response.data);
    } catch (error) {
        console.error('Error fetching tool parameters:', error);
        res.status(500).send({ error: error.message });
    }
});

app.listen(port, () => {
    console.log(`Node.js app listening at http://localhost:${port}`);
});
