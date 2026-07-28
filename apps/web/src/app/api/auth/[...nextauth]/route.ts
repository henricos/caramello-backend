/**
 * Internal Auth.js routes (`/api/auth/*`) — signin, callback, session, signout
 * and so on. The whole implementation lives in `src/auth.ts`; this file
 * re-exports the handlers, re-adding the app base path that Next strips from
 * the URL before route handlers run: Auth.js is configured with the PREFIXED
 * `basePath` (see `src/auth.ts`), so the request URL it parses must carry the
 * prefix too.
 */
import { NextRequest } from "next/server";

import { appBasePath, handlers } from "@/auth";

type AuthHandler = (req: NextRequest) => Promise<Response>;

function withBasePath(handler: AuthHandler): AuthHandler {
  return (req: NextRequest): Promise<Response> => {
    if (!appBasePath) {
      return handler(req);
    }
    const url = new URL(req.url);
    if (!url.pathname.startsWith(`${appBasePath}/`)) {
      url.pathname = `${appBasePath}${url.pathname}`;
    }
    return handler(new NextRequest(url, req));
  };
}

export const GET = withBasePath(handlers.GET as AuthHandler);
export const POST = withBasePath(handlers.POST as AuthHandler);
