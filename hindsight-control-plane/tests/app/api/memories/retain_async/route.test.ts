import type { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

type RetainMemoriesArg = {
  body: { items: Array<Record<string, unknown>>; async: boolean };
};

const { retainMemories } = vi.hoisted(() => ({
  retainMemories: vi.fn<(arg: RetainMemoriesArg) => Promise<unknown>>(),
}));

vi.mock("@/lib/hindsight-client", () => ({
  sdk: { retainMemories },
  lowLevelClient: {},
}));

vi.mock("@/lib/sdk-response", () => ({
  respondWithSdk: vi.fn(() => new Response(null, { status: 200 })),
}));

vi.mock("@/lib/i18n/api-errors", () => ({
  localizeApiErrorPayload: (_request: NextRequest, payload: unknown) => payload,
}));

import { POST } from "@/app/api/memories/retain_async/route";

describe("POST /api/memories/retain_async", () => {
  beforeEach(() => {
    retainMemories.mockReset();
    retainMemories.mockResolvedValue({ data: { message: "queued" }, error: undefined });
  });

  it("maps top-level observation settings into items, including an empty whitelist", async () => {
    const request = new Request("http://localhost/api/memories/retain_async", {
      method: "POST",
      body: JSON.stringify({
        bank_id: "bank-1",
        items: [{ content: "fact" }],
        observation_scopes: "combined",
        observation_scopes_param: { tag_key_whitelist: [] },
      }),
      headers: { "content-type": "application/json" },
    });

    await POST(request as unknown as NextRequest);

    expect(retainMemories.mock.calls[0][0].body).toEqual({
      items: [
        {
          content: "fact",
          observation_scopes: "combined",
          observation_scopes_param: { tag_key_whitelist: [] },
        },
      ],
      async: true,
    });
  });

  it("keeps item-level observation settings over top-level defaults", async () => {
    const request = new Request("http://localhost/api/memories/retain_async", {
      method: "POST",
      body: JSON.stringify({
        bank_id: "bank-1",
        items: [
          {
            content: "fact",
            observation_scopes: "per_tag",
            observation_scopes_param: { tag_key_whitelist: ["user"] },
          },
        ],
        observation_scopes: "combined",
        observation_scopes_param: { tag_key_whitelist: ["project"] },
      }),
      headers: { "content-type": "application/json" },
    });

    await POST(request as unknown as NextRequest);

    expect(retainMemories.mock.calls[0][0].body.items).toEqual([
      {
        content: "fact",
        observation_scopes: "per_tag",
        observation_scopes_param: { tag_key_whitelist: ["user"] },
      },
    ]);
  });
});
