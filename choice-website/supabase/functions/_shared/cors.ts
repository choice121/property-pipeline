// Choice Properties — Shared: CORS headers
  // Used by all Edge Functions. Import this instead of redefining locally.
  // Origin is restricted to known Choice Properties domains only.
  // Wildcard (*) is intentionally avoided — it would allow any site to call
  // unauthenticated endpoints (e.g. send-inquiry) and abuse email delivery.

  const ALLOWED_ORIGINS = [
    'https://choice-properties-site.pages.dev',
    'https://apply-choice-properties.pages.dev',
  ];

  export function getCorsHeaders(req: Request): Record<string, string> {
    const origin = req.headers.get('Origin') || '';
    const allowedOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
    return {
      'Access-Control-Allow-Origin': allowedOrigin,
      'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      'Vary': 'Origin',
    };
  }

  // Legacy export — kept for backward compatibility with functions that import { cors }
  // These functions pass the headers directly in a Response; they don't make
  // per-request origin decisions. For new code, prefer getCorsHeaders(req).
  export const cors = {
    'Access-Control-Allow-Origin': 'https://choice-properties-site.pages.dev',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  };

  export const corsResponse = (req?: Request) => {
    const h = req ? getCorsHeaders(req) : cors;
    return new Response('ok', { headers: h });
  };
  