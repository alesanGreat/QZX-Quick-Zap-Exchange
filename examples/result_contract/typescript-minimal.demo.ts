// Runnable demonstration for the side-effect-free TypeScript producer module.

import {
  qzxFailure,
  qzxSuccess,
  type QzxResult,
} from "./typescript-minimal.js";

const success: QzxResult<{ item_id: string; value: number }> = qzxSuccess(
  "Item loaded.",
  { item_id: "item-42", value: 7 },
);

const failure: QzxResult<{ item_id: string }> = qzxFailure(
  "The requested item was not found.",
  "item_not_found",
  { item_id: "missing-42" },
);

console.log(JSON.stringify(success));
console.log(JSON.stringify(failure));
