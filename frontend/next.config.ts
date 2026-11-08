import type { NextConfig } from "next";

// The Flask API (backend/server.py). The browser only talks to this Next.js app,
// which forwards /api/* there, so the sign-in cookie stays on one origin.
const BACKEND_URL = process.env.BACKEND_URL || "https://api.riaaiagent.cc";

const nextConfig: NextConfig = {
  /* API routes are handled natively by src/app/api/[...path]/route.ts */
};

export default nextConfig;
