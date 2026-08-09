// QZX Result Contract v1 — minimal TypeScript producer example.
// No QZX runtime dependency is required. Validate emitted JSON against the
// canonical schema before making a compatibility claim.

type DomainEvidence = Record<string, unknown>;

type QzxSuccess<T extends DomainEvidence = DomainEvidence> = T & {
  success: true;
  message: string;
};

type QzxFailure<T extends DomainEvidence = DomainEvidence> = T & {
  success: false;
  message: string;
  error_code: string;
  error?: string;
};

type QzxResult<T extends DomainEvidence = DomainEvidence> =
  | QzxSuccess<T>
  | QzxFailure<T>;

export function qzxSuccess<T extends DomainEvidence>(
  message: string,
  evidence: T,
): QzxSuccess<T> {
  return { ...evidence, success: true, message };
}

export function qzxFailure<T extends DomainEvidence>(
  message: string,
  errorCode: string,
  evidence: T,
  error?: string,
): QzxFailure<T> {
  return {
    ...evidence,
    success: false,
    message,
    error_code: errorCode,
    ...(error === undefined ? {} : { error }),
  };
}

// Existing domain evidence remains intact; QZX adds a small stable envelope.
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
