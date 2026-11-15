const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Same-origin proxy so the browser never needs CORS or the backend URL.
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

  // Keep English-language users on English provisions; only drop the language
  // filter when the question itself is written in Devanagari (Hindi).
  const isHindi = /[\u0900-\u097F]/.test(question);

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/v1/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        query: question.trim(),
        top_k: 5,
        // All ingested sources are still review_status "needs_review"; the UI labels that.
        include_unverified: true,
        filters: isHindi ? { language: "hi" } : { language: "en" },
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    return Response.json(
      { detail: "Corpus service is unreachable. Check that the backend container is running." },
      { status: 503 },
    );
  }

  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    return Response.json(
      { detail: typeof detail === "string" ? detail : "Retrieval failed." },
      { status: response.status },
    );
  }

  return Response.json(data);
}
