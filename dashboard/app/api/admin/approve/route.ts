import { NextRequest, NextResponse } from "next/server";

const ORCHESTRATOR_URL =
  process.env.ORCHESTRATOR_URL ??
  "https://ripple-orchestrator-mctjeick3a-nw.a.run.app";

export async function POST(req: NextRequest) {
  const secret = process.env.ADMIN_SECRET ?? "";
  try {
    const body = await req.json();
    const r = await fetch(`${ORCHESTRATOR_URL}/internal/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Secret": secret,
      },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    return NextResponse.json(data, { status: r.status });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}
