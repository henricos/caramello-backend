/**
 * Public health probe (`GET /health` under the base path), used by the compose
 * healthcheck and by external uptime monitoring.
 *
 * It deliberately checks NOTHING beyond "this server answers": the web has no
 * state of its own — no database, no queue, no cache. Database and provider
 * health belong to the api's own `/health`, and probing the api from here would
 * only make one service's outage look like two.
 */
export function GET(): Response {
  return Response.json({ status: "ok" });
}
