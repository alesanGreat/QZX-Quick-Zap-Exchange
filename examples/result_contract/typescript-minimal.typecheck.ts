// Compile-time checks for the minimal TypeScript producer.

import {
  qzxFailure,
  qzxSuccess,
  type QzxResult,
} from "./typescript-minimal.js";

const success: QzxResult<{ item_id: string }> = qzxSuccess(
  "Item loaded.",
  {
    item_id: "item-42",
    details: { source: "cache" },
    warnings: ["Cached data may be stale."],
    meta: { schema_version: 1, duration_ms: 2.5 },
  },
);

const failure: QzxResult<{ item_id: string }> = qzxFailure(
  "The requested item was not found.",
  "item_not_found",
  { item_id: "missing-42" },
);

void success;
void failure;

// @ts-expect-error Domain evidence cannot redefine a QZX outcome field.
qzxSuccess("Contradictory success.", { error_code: "unexpected_error" });

// @ts-expect-error Domain evidence cannot override the explicit outcome.
qzxFailure("Contradictory failure.", "operation_failed", { success: true });

// @ts-expect-error Defined optional core fields retain their schema types.
qzxSuccess("Invalid details.", { details: null });
