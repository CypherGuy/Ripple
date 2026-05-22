import { NextResponse } from "next/server";

const ORCHESTRATOR_URL =
  process.env.ORCHESTRATOR_URL ??
  "https://ripple-orchestrator-mctjeick3a-nw.a.run.app";

export async function POST() {
  const secret = process.env.ADMIN_SECRET ?? "";
  try {
    const r = await fetch(`${ORCHESTRATOR_URL}/admin/close-mrs`, {
      method: "POST",
      headers: { "X-Admin-Secret": secret },
    });
    const data = await r.json();
    return NextResponse.json(data, { status: r.status });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
