import type { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { retainBatch } = vi.hoisted(() => ({
  retainBatch: vi.fn(),
}));

vi.mock("@/lib/hindsight-client", () => ({
  hindsightClient: { retainBatch },
}));

vi.mock("@/lib/i18n/api-errors", () => ({
  localizeApiErrorPayload: (_request: NextRequest, payload: unknown) => payload,
}));

import { POST } from "@/app/api/memories/retain/route";

describe("POST /api/memories/retain", () => {
  beforeEach(() => {
    retainBatch.mockReset();
    retainBatch.mockResolvedValue({ success: true });
  });

  it("maps a top-level observation strategy into items", async () => {
    const request = new Request("http://localhost/api/memories/retain", {
      method: "POST",
      body: JSON.stringify({
        bank_id: "bank-1",
        items: [{ content: "fact" }],
        observation_scopes: "combined",
      }),
      headers: { "content-type": "application/json" },
    });

    await POST(request as unknown as NextRequest);

    expect(retainBatch).toHaveBeenCalledWith(
      "bank-1",
      [
        {
          content: "fact",
          observation_scopes: "combined",
        },
      ],
      { documentId: undefined, documentTags: undefined }
    );
  });

  it("keeps item-level observation settings over top-level defaults", async () => {
    const request = new Request("http://localhost/api/memories/retain", {
      method: "POST",
      body: JSON.stringify({
        bank_id: "bank-1",
        items: [
          {
            content: "fact",
            observation_scopes: "per_tag",
          },
        ],
        observation_scopes: "combined",
      }),
      headers: { "content-type": "application/json" },
    });

    await POST(request as unknown as NextRequest);

    expect(retainBatch.mock.calls[0][1]).toEqual([
      {
        content: "fact",
        observation_scopes: "per_tag",
      },
    ]);
  });
});
