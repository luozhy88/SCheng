export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/save") return handleSave(request, env, url);
    return env.ASSETS.fetch(request);
  },
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json;charset=UTF-8", ...CORS },
  });

async function handleSave(request, env, url) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

  const key = url.searchParams.get("key") || "";
  if (!/^[A-Za-z0-9_-]{2,64}$/.test(key)) return json({ error: "invalid key" }, 400);

  if (request.method === "GET") {
    const row = await env.DB.prepare(
      "SELECT data, updated_at FROM saves WHERE key = ?"
    ).bind(key).first();
    if (!row) return json({ error: "not found" }, 404);
    return json({ data: JSON.parse(row.data), updatedAt: row.updated_at });
  }

  if (request.method === "POST") {
    const body = await request.json().catch(() => null);
    if (!body || body.data === undefined || body.data === null) {
      return json({ error: "invalid body" }, 400);
    }
    const data = JSON.stringify(body.data);
    if (data.length > 200000) return json({ error: "too large" }, 413);
    const ts = Number.isInteger(body.updatedAt) && body.updatedAt > 0 ? body.updatedAt : Date.now();
    await env.DB.prepare(
      `INSERT INTO saves (key, data, updated_at) VALUES (?, ?, ?)
       ON CONFLICT(key) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at`
    ).bind(key, data, ts).run();
    return json({ ok: true, updatedAt: ts });
  }

  return json({ error: "method not allowed" }, 405);
}
