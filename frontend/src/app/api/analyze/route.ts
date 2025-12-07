import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const res = await fetch(`${apiUrl}/analyze`, {
      method: "POST",
      body: formData,
      // Important: Do not set Content-Type header manually for FormData,
      // fetch will set it with the correct boundary
    });

    if (!res.ok) {
      const errorText = await res.text();
      return NextResponse.json(
        { detail: errorText || "Backend error" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Proxy error:", error);
    return NextResponse.json(
      { detail: "Failed to connect to backend" },
      { status: 500 }
    );
  }
}

