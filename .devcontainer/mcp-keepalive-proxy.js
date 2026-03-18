// MCP Keepalive Proxy
// Sits between Claude Code and a remote MCP server to prevent session timeouts.
// Reads config from environment variables:
//   MCP_REMOTE_URL    - the remote MCP server URL (required)
//   MCP_AUTH_HEADER   - Authorization header value (optional)
//   MCP_KEEPALIVE_SEC - keepalive interval in seconds (default: 30)
//   MCP_PROXY_PORT    - local proxy port (default: 9847)

const http = require("http");
const https = require("https");

const REMOTE_URL = process.env.MCP_REMOTE_URL;
if (!REMOTE_URL) {
  console.error("[proxy] MCP_REMOTE_URL is required");
  process.exit(1);
}

const AUTH_HEADER = process.env.MCP_AUTH_HEADER || "";
const KEEPALIVE_INTERVAL = (parseInt(process.env.MCP_KEEPALIVE_SEC, 10) || 30) * 1000;
const PORT = parseInt(process.env.MCP_PROXY_PORT, 10) || 9847;

let upstreamSessionId = null;
let localSessionId = "local-" + Date.now();
let keepaliveTimer = null;
let initPromise = null;

function remotePost(body, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(REMOTE_URL);
    const proto = url.protocol === "https:" ? https : http;
    const reqHeaders = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      ...extraHeaders,
    };
    if (AUTH_HEADER) reqHeaders.Authorization = AUTH_HEADER;

    const req = proto.request(
      { hostname: url.hostname, port: url.port, path: url.pathname, method: "POST", headers: reqHeaders },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () =>
          resolve({ statusCode: res.statusCode, headers: res.headers, body: data })
        );
      }
    );
    req.on("error", reject);
    req.write(typeof body === "string" ? body : JSON.stringify(body));
    req.end();
  });
}

async function initUpstream() {
  if (initPromise) return initPromise;
  initPromise = (async () => {
    try {
      const body = {
        jsonrpc: "2.0",
        method: "initialize",
        params: {
          protocolVersion: "2025-03-26",
          capabilities: {},
          clientInfo: { name: "mcp-proxy", version: "1.0" },
        },
        id: "init-" + Date.now(),
      };
      const res = await remotePost(body);
      if (res.headers["mcp-session-id"]) {
        upstreamSessionId = res.headers["mcp-session-id"];
        console.log(`[proxy] Upstream session: ${upstreamSessionId}`);
        await remotePost(
          { jsonrpc: "2.0", method: "notifications/initialized" },
          { "mcp-session-id": upstreamSessionId }
        );
      }
      startKeepalive();
      return res;
    } finally {
      initPromise = null;
    }
  })();
  return initPromise;
}

function startKeepalive() {
  if (keepaliveTimer) clearInterval(keepaliveTimer);
  keepaliveTimer = setInterval(async () => {
    if (!upstreamSessionId) return;
    try {
      const res = await remotePost(
        { jsonrpc: "2.0", method: "tools/list", id: "ka-" + Date.now() },
        { "mcp-session-id": upstreamSessionId }
      );
      if (res.statusCode !== 200 || res.body.includes('"code":32001')) {
        console.log(`[proxy] Keepalive: session expired, reinit...`);
        upstreamSessionId = null;
        await initUpstream();
      } else {
        console.log(`[proxy] Keepalive OK @ ${new Date().toISOString()}`);
      }
    } catch (e) {
      console.log(`[proxy] Keepalive error: ${e.message}, reinit...`);
      upstreamSessionId = null;
      await initUpstream();
    }
  }, KEEPALIVE_INTERVAL);
}

async function forwardRequest(body) {
  if (!upstreamSessionId) await initUpstream();

  let res = await remotePost(body, { "mcp-session-id": upstreamSessionId });

  if (res.body.includes('"code":32001') || res.body.includes("Session not found")) {
    console.log("[proxy] Session expired on request, reinit...");
    upstreamSessionId = null;
    await initUpstream();
    res = await remotePost(body, { "mcp-session-id": upstreamSessionId });
  }

  return res;
}

const server = http.createServer(async (req, res) => {
  if (req.method === "DELETE") {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method === "GET") {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "Mcp-Session-Id": localSessionId,
    });
    const interval = setInterval(() => res.write(": ping\n\n"), 15000);
    req.on("close", () => clearInterval(interval));
    return;
  }

  let body = "";
  req.on("data", (chunk) => (body += chunk));
  req.on("end", async () => {
    try {
      let parsed;
      try { parsed = JSON.parse(body); } catch (_) { parsed = null; }

      console.log(`[proxy] << ${parsed?.method || "unknown"} (id: ${parsed?.id || "none"})`);

      if (parsed && parsed.method === "initialize") {
        await initUpstream();
        const initResponse = {
          result: {
            protocolVersion: "2024-11-05",
            capabilities: { logging: {}, tools: { listChanged: true } },
            serverInfo: { name: "mcp-keepalive-proxy", version: "1.0.0" },
          },
          id: parsed.id,
          jsonrpc: "2.0",
        };
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache,no-store",
          "Mcp-Session-Id": localSessionId,
        });
        res.end(`event: message\ndata: ${JSON.stringify(initResponse)}\n\n`);
        return;
      }

      if (parsed && parsed.method === "notifications/initialized") {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Mcp-Session-Id": localSessionId,
        });
        res.end();
        return;
      }

      const remote = await forwardRequest(body);

      const respHeaders = {
        "Content-Type": remote.headers["content-type"] || "text/event-stream",
        "Cache-Control": "no-cache,no-store",
        "Mcp-Session-Id": localSessionId,
      };

      console.log(`[proxy] >> ${remote.statusCode} (${remote.body.length} bytes)`);
      res.writeHead(remote.statusCode, respHeaders);
      res.end(remote.body);
    } catch (e) {
      console.error("[proxy] Error:", e.message);
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Mcp-Session-Id": localSessionId,
      });
      res.end(
        `event: message\ndata: ${JSON.stringify({
          jsonrpc: "2.0",
          error: { code: -32000, message: e.message },
          id: null,
        })}\n\n`
      );
    }
  });
});

server.listen(PORT, "127.0.0.1", async () => {
  console.log(`[proxy] MCP keepalive proxy on http://127.0.0.1:${PORT}`);
  console.log(`[proxy] Proxying to ${REMOTE_URL}`);
  console.log(`[proxy] Keepalive every ${KEEPALIVE_INTERVAL / 1000}s`);
  await initUpstream();
});
