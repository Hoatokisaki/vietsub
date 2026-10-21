// Edge Function: app-update
// Manages version check and download links for luaVietsup
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Current latest released version
    const latestRelease = {
      version: "2.6",
      release_date: "2026-10-21",
      title: "luaVietsup Pro v2.6",
      changelog: [
        "1. Tối ưu xuất video không âm thanh trên CPU Intel Core i5.",
        "2. Đảm bảo hỗ trợ GPU CTranslate2 CUDA 12 (cublas64_12.dll).",
        "3. Tích hợp tính năng Kiểm tra cập nhật và Update online trực tiếp.",
        "4. Quản lý bản quyền HWID từ xa độc lập.",
      ].join("\n"),
      type: "installer", // "patch" (.zip) hoặc "installer" (.exe)
      download_url: "https://your-server-or-storage.com/Setup_luaVietsup_Pro_v2.6.exe",
      size_mb: 3600,
      required: false,
    };

    return new Response(JSON.stringify(latestRelease), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 500,
    });
  }
});
