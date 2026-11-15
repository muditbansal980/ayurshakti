const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Same-origin proxy for Gemini-powered grounded chat.
// Does NOT apply language filters so Hindi questions can retrieve English legal documents.
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ detail: "Request body must be JSON." }, { status: 400 });
  }

  const question = (body as { question?: unknown } | null)?.question;
  if (typeof question !== "string" || question.trim().length === 0) {
    return Response.json({ detail: "Provide a nonempty question." }, { status: 422 });
  }

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        question: question.trim(),
        top_k: 5,
        include_unverified: true,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
  } catch {
    return Response.json(
      { detail: "Assistant service is unreachable. Check that the backend container is running." },
      { status: 503 },
    );
  }

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    return Response.json(
      { detail: typeof detail === "string" ? detail : "Generation request failed." },
      { status: response.status },
    );
  }

  return Response.json(data);
}
