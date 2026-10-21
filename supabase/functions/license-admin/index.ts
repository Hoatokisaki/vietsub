import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function reply(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function digestHwid(value: string) {
  const normalized = value.trim().toLowerCase();
  if (!normalized || normalized.length > 512) throw new Error("HWID khong hop le.");
  const bytes = new TextEncoder().encode(normalized);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405);

  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const allowedIds = (Deno.env.get("LICENSE_ADMIN_USER_IDS") ?? "")
    .split(",").map((value) => value.trim()).filter(Boolean);
  if (!url || !serviceKey || allowedIds.length === 0) {
    return reply({ error: "admin_not_configured" }, 503);
  }

  const authorization = request.headers.get("Authorization") ?? "";
  const token = authorization.match(/^Bearer\s+(.+)$/i)?.[1];
  const publicKey = request.headers.get("apikey") ?? "";
  if (!token || !publicKey) return reply({ error: "authentication_required" }, 401);

  try {
    // Verify the access token against Supabase Auth before checking the admin allowlist.
    const auth = createClient(url, publicKey, { auth: { persistSession: false } });
    const { data: authData, error: authError } = await auth.auth.getUser(token);
    const userId = authData.user?.id ?? "";
    if (authError || !userId || !allowedIds.includes(userId)) {
      return reply({ error: "admin_access_denied" }, 403);
    }

    const body = await request.json();
    const action = String(body.action ?? "");
    const db = createClient(url, serviceKey, { auth: { persistSession: false } });

    if (action === "list") {
      const { data, error } = await db.from("license_entitlements")
        .select("product_id,hwid_sha256,hwid_hint,holder_name,active,expires_at,created_at,updated_at")
        .eq("product_id", "luaVietsup")
        .order("created_at", { ascending: false })
        .limit(500);
      if (error) throw error;
      return reply({ licenses: data ?? [] });
    }

    if (action === "grant") {
      const hwid = String(body.hwid ?? "").trim();
      const label = String(body.label ?? "").trim();
      const days = Number(body.expiry_days ?? 0);
      if (!hwid || hwid.length > 512) return reply({ error: "invalid_hwid" }, 400);
      if (label.length > 120) return reply({ error: "label_too_long" }, 400);
      if (!Number.isInteger(days) || days < 0 || days > 36500) return reply({ error: "invalid_expiry" }, 400);
      const hash = await digestHwid(hwid);
      const expiresAt = days === 0 ? null : new Date(Date.now() + days * 86400000).toISOString();
      const row = {
        product_id: "luaVietsup",
        hwid_sha256: hash,
        hwid_hint: hwid.slice(-8),
        holder_name: label,
        active: true,
        expires_at: expiresAt,
        updated_at: new Date().toISOString(),
      };
      const { error } = await db.from("license_entitlements").upsert(row, {
        onConflict: "product_id,hwid_sha256",
      });
      if (error) throw error;
      return reply({ ok: true, hwid_sha256: hash });
    }

    if (action === "revoke") {
      const hash = String(body.hwid_sha256 ?? "").toLowerCase();
      if (!/^[0-9a-f]{64}$/.test(hash)) return reply({ error: "invalid_hwid_hash" }, 400);
      const { data, error } = await db.from("license_entitlements")
        .update({ active: false, updated_at: new Date().toISOString() })
        .eq("product_id", "luaVietsup")
        .eq("hwid_sha256", hash)
        .select("hwid_sha256");
      if (error) throw error;
      return reply({ ok: true, found: Boolean(data?.length) });
    }

    return reply({ error: "unsupported_action" }, 400);
  } catch (error) {
    console.error("license-admin failed", error);
    return reply({ error: "admin_request_failed" }, 500);
  }
});
