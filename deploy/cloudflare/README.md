# Frontend Deployment on Cloudflare

This guide explains how to deploy the `ria-ui` frontend on **Cloudflare Pages** and configure the reverse proxy for backend API communication on Google Cloud.

---

## Architecture Overview

```
Customer / Operator Browser
          │
          ▼
Cloudflare Edge CDN (Pages)
 ├── Static Pages / UI Assets ──► Served from Cloudflare Edge Cache
 └── /api/* Requests          ──► Proxied to Google Cloud VM 1 (https://api.yourdomain.com/api/*)
```

Because Next.js proxies `/api/*` to `BACKEND_URL`, deploying on Cloudflare gives you:
1. **Global CDN speed** with zero server management for the frontend.
2. **DDoS protection & Free SSL** provided natively by Cloudflare.
3. **Clean Origin Cookies**: The browser sees a single origin (`yourdomain.com`), keeping session cookies (`SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE="Lax"`) secure and functioning properly.

---

## Option 1: Cloudflare Pages + Cloudflare Proxy Rule (Recommended & Simplest)

### Step 1: Connect Git Repository to Cloudflare Pages
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com) > **Workers & Pages** > **Create application** > **Pages** > **Connect to Git**.
2. Select your repository: `RIA-collection-agent-v` (or `roxigroups/RIA-collection-agent-v`).
3. Configure build settings:
   * **Framework preset**: `Next.js (Static Export / OpenNext)`
   * **Root directory**: `frontend`
   * **Build command**: `npm run build`
   * **Output directory**: `.next` (or `out` for static export)
   * **Node.js Version**: `20.x` (Set Environment Variable: `NODE_VERSION = 20`)

### Step 2: Configure Environment Variable
In Cloudflare Pages Project Settings > **Environment variables**:
* `BACKEND_URL`: `https://api.yourdomain.com` (pointing to your VM 1 public IP or DNS record).

---

## Option 2: Cloudflare Page Rule / Worker API Proxy

If hosting the frontend on `app.yourdomain.com` and backend API on `api.yourdomain.com`:

1. Under your Cloudflare DNS, create:
   * `A` record: `api.yourdomain.com` ──► Public IP of **VM 1** (Proxied via Cloudflare Orange Cloud).
   * `CNAME` record: `app.yourdomain.com` ──► Cloudflare Pages domain (`<project>.pages.dev`).

2. If using a single domain (`yourdomain.com`):
   Create a **Cloudflare Origin Rule** or **Worker Route**:
   * Match: `yourdomain.com/api/*`
   * Route to Origin: VM 1 Public IP (port 5001 or 443 with Nginx/Caddy).

---

## Production Security Notes

1. In `backend/.env`, set:
   ```env
   SESSION_COOKIE_SECURE="1"
   SESSION_COOKIE_SAMESITE="Lax"
   ```
2. Whitelist Cloudflare IP ranges in your GCP VM 1 firewall for port 443/5001 so that direct public access to your backend VM is prevented.
