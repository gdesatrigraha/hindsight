import { NextRequest, NextResponse } from "next/server";
import { localizeApiErrorPayload } from "@/lib/i18n/api-errors";
import { sdk, lowLevelClient } from "@/lib/hindsight-client";
import { respondWithSdk } from "@/lib/sdk-response";

type RetainItem = {
  content: string;
  observation_scopes?: "per_tag" | "combined" | "all_combinations" | "shared" | string[][];
  observation_scopes_param?: { tag_key_whitelist?: string[] };
  [key: string]: unknown;
};

export async function POST(request: NextRequest) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      localizeApiErrorPayload(request, {
        error: "Invalid JSON body",
        errorKey: "api.errors.auth.invalidRequestBody",
      }),
      { status: 400 }
    );
  }
  const bankId = body.bank_id || body.agent_id;

  if (!bankId) {
    return NextResponse.json(
      localizeApiErrorPayload(request, {
        error: "bank_id is required",
        errorKey: "api.errors.validation.bankIdRequired",
      }),
      { status: 400 }
    );
  }

  const { items, observation_scopes, observation_scopes_param } = body;

  // The async endpoint uses the generated SDK directly, so mirror the synchronous proxy's
  // top-level defaults here. Nullish coalescing preserves explicit empty lists and lets item-level
  // settings take precedence without duplicating observation-scope generation in the proxy.
  const mappedItems =
    observation_scopes !== undefined || observation_scopes_param !== undefined
      ? items?.map((item: RetainItem) => ({
          ...item,
          observation_scopes: item.observation_scopes ?? observation_scopes,
          observation_scopes_param: item.observation_scopes_param ?? observation_scopes_param,
        }))
      : items;

  const response = await sdk.retainMemories({
    client: lowLevelClient,
    path: { bank_id: bankId },
    body: { items: mappedItems, async: true },
  });
  return respondWithSdk(response, "Failed to batch retain async", { request });
}
