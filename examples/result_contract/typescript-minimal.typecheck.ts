// Compile-time checks for the minimal TypeScript producer.

import {
  qzxFailure,
  qzxSuccess,
  type QzxFailure,
  type QzxResult,
  type QzxSuccess,
} from "./typescript-minimal.js";

const success: QzxSuccess<{ item_id: string }> = qzxSuccess("Item loaded.", {
  item_id: "item-42",
});

const failure: QzxFailure<{ item_id: string }> = qzxFailure(
  "The requested item was not found.",
  "item_not_found",
  { item_id: "missing-42" },
);

const summarize = (result: QzxResult<{ item_id: string }>): string =>
  result.success ? result.item_id : `${result.error_code}:${result.item_id}`;

void summarize(success);
void summarize(failure);

// @ts-expect-error Successful evidence cannot define a failure field.
qzxSuccess("Contradictory success.", { error_code: "unexpected_error" });

// @ts-expect-error Domain evidence cannot override the explicit outcome.
qzxFailure("Contradictory failure.", "operation_failed", { success: true });

// @ts-expect-error The explicit message cannot be shadowed by evidence.
qzxSuccess("Canonical message.", { message: "Contradictory message." });

const contradictory: QzxSuccess = {
  success: true,
  message: "Contradictory result.",
  // @ts-expect-error Successful result types cannot carry failure identifiers.
  error_code: "unexpected_error",
};
void contradictory;
