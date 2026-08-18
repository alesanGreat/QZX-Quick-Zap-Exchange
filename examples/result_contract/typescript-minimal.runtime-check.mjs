// Runtime checks for JavaScript callers that do not have TypeScript's guards.

const { qzxFailure, qzxSuccess } = await import("./typescript-minimal.ts");

const invalidCalls = [
  () => qzxSuccess("   ", {}),
  () => qzxSuccess("Contradictory.", { error_code: "unexpected_error" }),
  () => qzxFailure("Failed.", "Bad-Code", {}),
  () => qzxFailure("Failed.", "operation_failed", {}, "  "),
];

let rejected = 0;
for (const call of invalidCalls) {
  try {
    call();
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    rejected += 1;
  }
}

if (rejected !== invalidCalls.length) {
  throw new Error(`Expected ${invalidCalls.length} rejections; received ${rejected}.`);
}

console.log(`Rejected ${rejected} invalid untyped producer calls.`);
