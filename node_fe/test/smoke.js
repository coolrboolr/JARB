#!/usr/bin/env node

const { request } = require('node:http');
const { request: httpsRequest } = require('node:https');
const { URL } = require('node:url');

const API_BASE = process.env.JARB_API_BASE || 'http://localhost:5000';
const toolsUrl = new URL('/api/tools', API_BASE);
const client = toolsUrl.protocol === 'https:' ? httpsRequest : request;

console.log(`[smoke] Checking catalog via ${toolsUrl.href}`);

const req = client(
    toolsUrl,
    {
        method: 'GET',
        headers: {
            Accept: 'application/json',
        },
        timeout: 5_000,
    },
    (res) => {
        const chunks = [];

        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () => {
            const body = Buffer.concat(chunks).toString('utf8');

            let payload;
            try {
                payload = JSON.parse(body);
            } catch (error) {
                console.error('[smoke] Backend did not return JSON:', error.message);
                process.exitCode = 1;
                return;
            }

            const isEnvelope =
                typeof payload === 'object' &&
                payload !== null &&
                typeof payload.success === 'boolean' &&
                Object.prototype.hasOwnProperty.call(payload, 'data') &&
                Object.prototype.hasOwnProperty.call(payload, 'error');

            if (!isEnvelope) {
                console.error('[smoke] Response is missing the {success,data,error} envelope.');
                process.exitCode = 1;
                return;
            }

            if (!payload.success) {
                console.error('[smoke] Catalog request failed:', payload.error);
                process.exitCode = 1;
                return;
            }

            const tools = Array.isArray(payload.data?.tools) ? payload.data.tools : [];
            console.log(`[smoke] Success: received ${tools.length} tool(s).`);

            const sampleTool = tools.find((tool) => Array.isArray(tool.parameters) && tool.parameters.length);
            if (sampleTool) {
                const invalidParam = sampleTool.parameters.find(
                    (param) => typeof param.required !== 'boolean' || typeof param.annotation?.type !== 'string',
                );
                if (invalidParam) {
                    console.error('[smoke] Parameter schema missing required/annotation fields.');
                    process.exitCode = 1;
                    return;
                }
                console.log(
                    `[smoke] Parameter schema OK for tool "${sampleTool.name}" (type=${sampleTool.parameters[0].annotation.type}).`,
                );
                checkRunHistory(sampleTool.name);
            } else if (tools.length) {
                console.log('[smoke] Tools present but none expose parameters to verify schema.');
            }
        });
    }
);

req.on('error', (error) => {
    console.error('[smoke] Network error:', error.message);
    process.exitCode = 1;
});

req.on('timeout', () => {
    console.error('[smoke] Request timed out.');
    req.destroy(new Error('timeout'));
});

req.end();

function checkRunHistory(toolName) {
    const runsUrl = new URL(`/api/tool_runs/${encodeURIComponent(toolName)}?limit=1`, API_BASE);
    const runsClient = runsUrl.protocol === 'https:' ? httpsRequest : request;
    const runsReq = runsClient(
        runsUrl,
        {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
            timeout: 5_000,
        },
        (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => {
                const body = Buffer.concat(chunks).toString('utf8');
                try {
                    const payload = JSON.parse(body);
                    if (!payload.success) {
                        console.warn('[smoke] Run history endpoint returned error envelope.');
                        process.exitCode = 1;
                        return;
                    }
                    if (!Array.isArray(payload.data?.runs)) {
                        console.warn('[smoke] Run history response missing runs array.');
                        process.exitCode = 1;
                        return;
                    }
                    console.log(`[smoke] Run history endpoint reachable for tool "${toolName}".`);
                } catch (error) {
                    console.error('[smoke] Run history JSON parse error:', error.message);
                    process.exitCode = 1;
                }
            });
        }
    );

    runsReq.on('error', (error) => {
        console.error('[smoke] Run history network error:', error.message);
        process.exitCode = 1;
    });

    runsReq.on('timeout', () => {
        console.error('[smoke] Run history request timed out.');
        runsReq.destroy(new Error('timeout'));
    });

    runsReq.end();
}
