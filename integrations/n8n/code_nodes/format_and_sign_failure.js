/**
 * REBOOTX — n8n Failure Event Formatter & Exact-Byte HMAC Signer
 *
 * This code runs inside an n8n Code node downstream of an Error Trigger node.
 * It formats the error context into a strict REBOOTX FailureEvent schema and
 * calculates an exact-byte HMAC-SHA256 signature using the integration secret.
 *
 * Security & Compatibility:
 * 1. Checks for native Node.js 'crypto' module first.
 * 2. If require('crypto') is restricted by n8n sandbox (NODE_FUNCTION_ALLOW_BUILTIN unset),
 *    it falls back transparently to a zero-dependency, FIPS 180-4 compliant pure JS HMAC-SHA256.
 * 3. Never hardcodes secrets; resolves from workflow parameters, $vars, or process.env.
 * 4. Generates stable event IDs (no Date.now() / random tokens) ensuring deterministic deduplication.
 */

// --- 1. Pure JavaScript FIPS 180-4 & RFC 2104 HMAC-SHA256 Fallback ---
function hmacSha256(key, message) {
    function rightRotate(value, amount) {
        return (value >>> amount) | (value << (32 - amount));
    }
    function sha256Bytes(bytes) {
        const K = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        ];
        let H0 = 0x6a09e667, H1 = 0xbb67ae85, H2 = 0x3c6ef372, H3 = 0xa54ff53a;
        let H4 = 0x510e527f, H5 = 0x9b05688c, H6 = 0x1f83d9ab, H7 = 0x5be0cd19;

        const bitLen = bytes.length * 8;
        const newLen = (((bytes.length + 8) >> 6) + 1) << 6;
        const padded = new Uint8Array(newLen);
        padded.set(bytes);
        padded[bytes.length] = 0x80;

        const view = new DataView(padded.buffer);
        view.setUint32(newLen - 4, bitLen >>> 0);
        view.setUint32(newLen - 8, Math.floor(bitLen / 0x100000000));

        const W = new Uint32Array(64);
        for (let i = 0; i < newLen; i += 64) {
            for (let t = 0; t < 16; t++) {
                W[t] = view.getUint32(i + (t * 4));
            }
            for (let t = 16; t < 64; t++) {
                const s0 = rightRotate(W[t - 15], 7) ^ rightRotate(W[t - 15], 18) ^ (W[t - 15] >>> 3);
                const s1 = rightRotate(W[t - 2], 17) ^ rightRotate(W[t - 2], 19) ^ (W[t - 2] >>> 10);
                W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
            }
            let a = H0, b = H1, c = H2, d = H3, e = H4, f = H5, g = H6, h = H7;
            for (let t = 0; t < 64; t++) {
                const S1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
                const ch = (e & f) ^ ((~e) & g);
                const temp1 = (h + S1 + ch + K[t] + W[t]) | 0;
                const S0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
                const maj = (a & b) ^ (a & c) ^ (b & c);
                const temp2 = (S0 + maj) | 0;

                h = g; g = f; f = e; e = (d + temp1) | 0;
                d = c; c = b; b = a; a = (temp1 + temp2) | 0;
            }
            H0 = (H0 + a) | 0; H1 = (H1 + b) | 0; H2 = (H2 + c) | 0; H3 = (H3 + d) | 0;
            H4 = (H4 + e) | 0; H5 = (H5 + f) | 0; H6 = (H6 + g) | 0; H7 = (H7 + h) | 0;
        }
        const out = new Uint8Array(32);
        const outView = new DataView(out.buffer);
        outView.setUint32(0, H0); outView.setUint32(4, H1); outView.setUint32(8, H2); outView.setUint32(12, H3);
        outView.setUint32(16, H4); outView.setUint32(20, H5); outView.setUint32(24, H6); outView.setUint32(28, H7);
        return out;
    }

    const encoder = typeof TextEncoder !== 'undefined' ? new TextEncoder() : {
        encode: (s) => Uint8Array.from(unescape(encodeURIComponent(s)), c => c.charCodeAt(0))
    };
    let keyBytes = typeof key === 'string' ? encoder.encode(key) : key;
    const msgBytes = typeof message === 'string' ? encoder.encode(message) : message;

    if (keyBytes.length > 64) {
        keyBytes = sha256Bytes(keyBytes);
    }
    const kPad = new Uint8Array(64);
    kPad.set(keyBytes);

    const iPad = new Uint8Array(64);
    const oPad = new Uint8Array(64);
    for (let i = 0; i < 64; i++) {
        iPad[i] = kPad[i] ^ 0x36;
        oPad[i] = kPad[i] ^ 0x5c;
    }

    const inner = new Uint8Array(64 + msgBytes.length);
    inner.set(iPad);
    inner.set(msgBytes, 64);
    const innerHash = sha256Bytes(inner);

    const outer = new Uint8Array(64 + 32);
    outer.set(oPad);
    outer.set(innerHash, 64);
    const outerHash = sha256Bytes(outer);

    return Array.from(outerHash).map(b => b.toString(16).padStart(2, '0')).join('');
}

// --- 2. String Sanitization & Reference Validation ---
function sanitizeReference(value, fallback) {
    if (!value || typeof value !== 'string') return fallback;
    const cleaned = value.replace(/[^A-Za-z0-9_.:/-]/g, '_').slice(0, 200);
    return cleaned.length > 0 ? cleaned : fallback;
}

// --- 3. Error Normalization ---
function deriveErrorDetails(err) {
    const rawMsg = (err && (err.message || err.description || (typeof err === 'string' ? err : ''))) || 'Unknown execution error';
    const message = rawMsg.slice(0, 4000);

    let httpStatus = null;
    if (err && typeof err.statusCode === 'number' && err.statusCode >= 100 && err.statusCode <= 599) {
        httpStatus = err.statusCode;
    } else if (err && typeof err.status === 'number' && err.status >= 100 && err.status <= 599) {
        httpStatus = err.status;
    } else {
        const match = message.match(/\b(1\d\d|2\d\d|3\d\d|4\d\d|5\d\d)\b/);
        if (match) {
            httpStatus = parseInt(match[1], 10);
        }
    }

    let category = 'PROVIDER_UNAVAILABLE';
    if (httpStatus === 401 || httpStatus === 403 || /unauthorized|forbidden|auth/i.test(message)) {
        category = 'AUTHENTICATION_FAILURE';
    } else if (httpStatus === 429 || /rate limit|throttl|too many requests/i.test(message)) {
        category = 'RATE_LIMIT';
    } else if (httpStatus === 400 || httpStatus === 422 || /invalid payload|schema validation/i.test(message)) {
        category = 'INVALID_PAYLOAD';
    } else if (httpStatus === 408 || httpStatus === 504 || /timeout|timed out/i.test(message)) {
        category = 'TRANSIENT_NETWORK_FAILURE';
    } else if (/econnrefused|enotfound|network|econnreset/i.test(message)) {
        category = 'TRANSIENT_NETWORK_FAILURE';
    } else if (httpStatus === 503 || httpStatus === 502) {
        category = 'PROVIDER_UNAVAILABLE';
    }

    const res = { category, message };
    if (httpStatus !== null) {
        res.http_status = httpStatus;
    }
    return res;
}

// --- 4. Main Transformation & Signing Logic ---
function formatAndSignFailure(inputContext, config = {}) {
    const execution = (inputContext && inputContext.execution) || {};
    const workflow = (inputContext && inputContext.workflow) || {};
    const err = execution.error || inputContext.error || {};

    const rawExecId = String(execution.id || inputContext.executionId || 'manual-exec');
    const sourceExecId = sanitizeReference(rawExecId, 'unknown-exec');
    const lastNode = execution.lastNodeExecuted || inputContext.lastNodeExecuted || 'unknown-step';
    const failedStep = sanitizeReference(lastNode, 'unknown-step');

    // Stable event ID for deterministic deduplication (no random or Date.now tokens)
    const eventId = sanitizeReference(`n8n:${sourceExecId}:${failedStep}`, 'n8n:exec:step');

    // Workflow external ID: from config, or sanitized workflow name/id
    const workflowExternalId = sanitizeReference(
        config.workflowExternalId || workflow.name || 'notify-orders',
        'notify-orders'
    );

    // Operation ID: from custom context data if present, or stable execution reference
    const rawOpId = (execution.data && execution.data.operation_id) ||
                    (inputContext.operation_id) ||
                    `op-${sourceExecId}`;
    const operationId = sanitizeReference(rawOpId, `op-${sourceExecId}`);

    const errorDetails = deriveErrorDetails(err);

    // Exact ISO 8601 UTC timestamp
    const timestamp = (config.timestampOverride) || new Date().toISOString();

    // Construct the strict FailureEvent payload
    const failureEvent = {
        schema_version: '1.0',
        event_id: eventId,
        timestamp: timestamp,
        source: 'n8n',
        source_execution_id: sourceExecId,
        workflow_external_id: workflowExternalId,
        failed_step: failedStep,
        operation_id: operationId,
        error: errorDetails
    };

    const rawBody = JSON.stringify(failureEvent);

    const integrationId = config.integrationId || '00000000-0000-0000-0000-000000000000';
    const webhookSecret = config.webhookSecret || '';

    // Calculate HMAC-SHA256 signature
    let signatureHex = '';
    try {
        if (typeof require !== 'undefined') {
            const crypto = require('crypto');
            signatureHex = crypto.createHmac('sha256', webhookSecret).update(rawBody).digest('hex');
        } else {
            signatureHex = hmacSha256(webhookSecret, rawBody);
        }
    } catch (_e) {
        // Fallback to pure JavaScript HMAC if require('crypto') is blocked by n8n sandbox
        signatureHex = hmacSha256(webhookSecret, rawBody);
    }

    const baseUrl = (config.baseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '');

    return {
        endpoint: `${baseUrl}/api/v1/events/failure`,
        payload: rawBody,
        headers: {
            'Content-Type': 'application/json',
            'X-Integration-ID': integrationId,
            'X-Webhook-Signature': `sha256=${signatureHex}`
        },
        event: failureEvent
    };
}

// --- 5. n8n Execution Hook ---
// If running inside n8n Code node environment
if (typeof $input !== 'undefined' || typeof $json !== 'undefined') {
    const inputData = (typeof $input !== 'undefined' && $input.first) ? $input.first().json : (typeof $json !== 'undefined' ? $json : {});
    
    // Config resolution: check n8n workflow variables ($vars), environment ($env), or node parameters
    const getEnvOrVar = (key, fallback) => {
        try {
            if (typeof $vars !== 'undefined' && $vars && $vars[key]) return $vars[key];
        } catch (_e) {}
        try {
            if (typeof $env !== 'undefined' && $env && $env[key]) return $env[key];
        } catch (_e) {}
        try {
            if (typeof process !== 'undefined' && process.env && process.env[key]) return process.env[key];
        } catch (_e) {}
        return fallback;
    };

    const runtimeConfig = {
        baseUrl: getEnvOrVar('REBOOTX_BASE_URL', 'http://127.0.0.1:8000'),
        integrationId: getEnvOrVar('REBOOTX_INTEGRATION_ID', '00000000-0000-0000-0000-000000000000'),
        webhookSecret: getEnvOrVar('REBOOTX_WEBHOOK_SECRET', ''),
        workflowExternalId: getEnvOrVar('REBOOTX_WORKFLOW_EXTERNAL_ID', 'notify-orders')
    };

    const result = formatAndSignFailure(inputData, runtimeConfig);
    return [{ json: result }];
}

// Export for Node.js testing/benchmarking
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatAndSignFailure,
        hmacSha256,
        sanitizeReference,
        deriveErrorDetails
    };
}

