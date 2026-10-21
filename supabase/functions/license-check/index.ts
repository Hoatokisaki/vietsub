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

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return reply({ error: "method_not_allowed" }, 405);

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return reply({ error: "invalid_json" }, 400);
  }
  const product = String(body.product ?? "");
  const digest = String(body.hwid_sha256 ?? "").toLowerCase();
  if (product !== "luaVietsup" || !/^[0-9a-f]{64}$/.test(digest)) {
    return reply({ error: "invalid_request" }, 400);
  }

  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceKey) return reply({ error: "server_not_configured" }, 503);

  try {
    const db = createClient(url, serviceKey, { auth: { persistSession: false } });
    const { data, error } = await db
      .from("license_entitlements")
      .select("active, expires_at")
      .eq("product_id", product)
      .eq("hwid_sha256", digest)
      .maybeSingle();
    if (error) throw error;
    const expiry = data?.expires_at ? new Date(data.expires_at) : null;
    const premium = Boolean(data?.active) && (!expiry || expiry.getTime() > Date.now());
    return reply({
      premium,
      expires_at: premium ? data?.expires_at ?? null : null,
      message: premium ? "Premium da duoc xac nhan." : "Thiet bi chua duoc cap quyen Premium.",
    });
  } catch (error) {
    console.error("license-check failed", error);
    return reply({ error: "license_check_unavailable" }, 503);
  }
});
