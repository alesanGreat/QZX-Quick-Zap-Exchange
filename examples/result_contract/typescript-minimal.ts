// QZX Result Contract v1 — minimal TypeScript producer example.
// No QZX runtime dependency is required. Validate emitted JSON against the
// canonical schema before making a compatibility claim.

export type QzxMeta = Record<string, unknown> & {
  schema_version?: 1;
  command?: string;
  duration_ms?: number;
  command_maturity?: Record<string, unknown>;
};

export type DomainEvidence = Record<string, unknown> & {
  details?: Record<string, unknown>;
  warnings?: string[];
  meta?: QzxMeta;
};

export type QzxOutcomeField =
  | "success"
  | "message"
  | "error"
  | "error_code";

type WithoutQzxOutcomeFields<T extends DomainEvidence> = T & {
  [K in Extract<keyof T, QzxOutcomeField>]: never;
};

export type QzxSuccess<T extends DomainEvidence = DomainEvidence> = Omit<
  T,
  QzxOutcomeField
> & {
  success: true;
  message: string;
  error?: never;
  error_code?: never;
};

export type QzxFailure<T extends DomainEvidence = DomainEvidence> = Omit<
  T,
  QzxOutcomeField
> & {
  success: false;
  message: string;
  error_code: string;
  error?: string;
};

export type QzxResult<T extends DomainEvidence = DomainEvidence> =
  | QzxSuccess<T>
  | QzxFailure<T>;

const QZX_OUTCOME_FIELDS: ReadonlySet<QzxOutcomeField> = new Set([
  "success",
  "message",
  "error",
  "error_code",
]);

const ERROR_CODE_PATTERN = /^[a-z][a-z0-9_]*$/u;

function requireNonBlank(value: string, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new TypeError(`${field} must be a non-empty string.`);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireDomainEvidence(evidence: DomainEvidence): void {
  if (!isRecord(evidence)) {
    throw new TypeError("evidence must be an object.");
  }
  for (const field of QZX_OUTCOME_FIELDS) {
    if (Object.hasOwn(evidence, field)) {
      throw new TypeError(
        `evidence must not redefine the QZX outcome field ${JSON.stringify(field)}.`,
      );
    }
  }
}

export function qzxSuccess<T extends DomainEvidence>(
  message: string,
  evidence: WithoutQzxOutcomeFields<T>,
): QzxSuccess<T> {
  requireDomainEvidence(evidence);
  return {
    ...evidence,
    success: true,
    message: requireNonBlank(message, "message"),
  };
}

export function qzxFailure<T extends DomainEvidence>(
  message: string,
  errorCode: string,
  evidence: WithoutQzxOutcomeFields<T>,
  error?: string,
): QzxFailure<T> {
  requireDomainEvidence(evidence);
  const checkedMessage = requireNonBlank(message, "message");
  if (typeof errorCode !== "string" || !ERROR_CODE_PATTERN.test(errorCode)) {
    throw new TypeError("errorCode must use lower_snake_case.");
  }
  const checkedError =
    error === undefined ? undefined : requireNonBlank(error, "error");
  return {
    ...evidence,
    success: false,
    message: checkedMessage,
    error_code: errorCode,
    ...(checkedError === undefined ? {} : { error: checkedError }),
  };
}

// Existing domain evidence remains intact; QZX adds a small stable envelope.
const success: QzxResult<{ item_id: string; value: number }> = qzxSuccess(
  "Item loaded.",
  {
    item_id: "item-42",
    value: 7,
    warnings: ["Cached data may be stale."],
    meta: { schema_version: 1, duration_ms: 2.5 },
  },
);

const failure: QzxResult<{ item_id: string }> = qzxFailure(
  "The requested item was not found.",
  "item_not_found",
  {
    item_id: "missing-42",
    details: { attempted_source: "cache" },
  },
);

console.log(JSON.stringify(success));
console.log(JSON.stringify(failure));
