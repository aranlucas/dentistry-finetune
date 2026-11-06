import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { api, type Report } from "@/api";

const comparison = {
  cases: [],
  loss: [],
  original_loss: [],
  reproduction: true,
  available_outputs: { base_rag: 0, adapter_rag: 0 },
  original_available_outputs: { base_rag: 0, adapter_rag: 0 },
  demo_model_available: false,
  demo_adapter_available: false,
};

function readComparison(report: Report | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...comparison, report }))),
  );

  return new QueryClient().fetchQuery(api.comparison());
}

afterEach(() => vi.unstubAllGlobals());

describe("pending local comparison responses", () => {
  it("accepts an explicitly missing report", async () => {
    expect(await readComparison(null)).toMatchObject({ report: null });
  });

  it("preserves unknown rates and training before any answer is saved", async () => {
    const tally = { count: 0, total: 0, rate: null };

    const metrics = { n: 0, json_valid: tally, schema_valid: tally, semantic_exact: tally };

    const condition = { metrics, abstention_cases: metrics };

    const report = {
      training: null,
      conditions: { retrieval: condition, base_rag: condition, adapter_rag: condition },
    };

    expect(await readComparison(report)).toMatchObject({ report });
  });
});
