import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'https://api.riaaiagent.cc';

async function handler(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const targetUrl = new URL(`/api/${path.join('/')}${req.nextUrl.search}`, BACKEND_URL);

  const headers = new Headers(req.headers);
  headers.delete('host');

  try {
    const hasBody = !['GET', 'HEAD'].includes(req.method);
    const body = hasBody ? await req.arrayBuffer() : undefined;

    const response = await fetch(targetUrl.toString(), {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
    });

    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      const k = key.toLowerCase();
      if (k !== 'content-encoding' && k !== 'content-length') {
        responseHeaders.append(key, value);
      }
    });

    if (typeof (response.headers as any).getSetCookie === 'function') {
      const cookies = (response.headers as any).getSetCookie();
      if (cookies.length > 0) {
        responseHeaders.delete('set-cookie');
        for (const cookie of cookies) {
          responseHeaders.append('set-cookie', cookie);
        }
      }
    }

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: 'Cannot reach the RIA backend server', details: err?.message || String(err) },
      { status: 502 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;

