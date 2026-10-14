/**
 * RIA Collection Agent - Cloudflare Worker Edge Gateway
 *
 * Proxies /api/* requests to GCP VM 1 (Gunicorn) with SSL termination,
 * CORS handling, and session cookie forwarding.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Handle CORS Preflight Requests (OPTIONS)
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": request.headers.get("Origin") || "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, Cookie, X-Requested-With",
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Max-Age": "86400",
        },
      });
    }

    // 2. Health check route directly at the edge
    if (url.pathname === "/edge-health") {
      return new Response(JSON.stringify({ edge: "ok", worker: "ria-collection-agent" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // 3. Resolve Backend Host (VM 1)
    const backendHost = env.BACKEND_HOST || "http://127.0.0.1:5001";
    const targetUrl = new URL(url.pathname + url.search, backendHost);

    // 4. Forward headers and pass client IP & secure proto
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
    headers.set("X-Forwarded-Proto", "https");
    headers.set("X-Real-IP", request.headers.get("CF-Connecting-IP") || "");

    try {
      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: headers,
        body: ["GET", "HEAD"].includes(request.method) ? null : request.body,
        redirect: "follow",
      });

      // 5. Build response with CORS and Cookies preserved
      const responseHeaders = new Headers(response.headers);
      if (request.headers.get("Origin")) {
        responseHeaders.set("Access-Control-Allow-Origin", request.headers.get("Origin"));
        responseHeaders.set("Access-Control-Allow-Credentials", "true");
      }

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders,
      });
    } catch (err) {
      return new Response(
        JSON.stringify({
          error: "Backend service temporarily unreachable",
          details: err.message,
          target: targetUrl.origin,
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
  },
};
