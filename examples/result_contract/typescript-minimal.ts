// QZX Result Contract v1 — minimal TypeScript producer module.
// No QZX runtime dependency is required. Validate emitted JSON against the
// canonical schema before making a compatibility claim.

export type DomainEvidence = Record<string, unknown>;

type ReservedOutcomeField = "success" | "message" | "error" | "error_code";
type SafeEvidence<T extends DomainEvidence> = T &
  Partial<Record<ReservedOutcomeField, never>>;

export type QzxSuccess<T extends DomainEvidence = DomainEvidence> = Omit<
  T,
  ReservedOutcomeField
> & {
  success: true;
  message: string;
  error?: never;
  error_code?: never;
};

export type QzxFailure<T extends DomainEvidence = DomainEvidence> = Omit<
  T,
  ReservedOutcomeField
> & {
  success: false;
  message: string;
  error_code: string;
  error?: string;
};

export type QzxResult<T extends DomainEvidence = DomainEvidence> =
  | QzxSuccess<T>
  | QzxFailure<T>;

const RESERVED_OUTCOME_FIELDS: readonly ReservedOutcomeField[] = [
  "success",
  "message",
  "error",
  "error_code",
];
const ERROR_CODE_PATTERN = /^[a-z][a-z0-9_]*$/;

function requireNonBlank(field: string, value: string): void {
  if (typeof value !== "string" || !/\S/.test(value)) {
    throw new TypeError(`${field} must be a non-empty string.`);
  }
}

function requireSafeEvidence(evidence: DomainEvidence): void {
  for (const field of RESERVED_OUTCOME_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(evidence, field)) {
      throw new TypeError(
        `Domain evidence must not redefine the QZX outcome field '${field}'.`,
      );
    }
  }
}

export function qzxSuccess<T extends DomainEvidence>(
  message: string,
  evidence: SafeEvidence<T>,
): QzxSuccess<T> {
  requireNonBlank("message", message);
  requireSafeEvidence(evidence);
  return { ...evidence, success: true, message };
}

export function qzxFailure<T extends DomainEvidence>(
  message: string,
  errorCode: string,
  evidence: SafeEvidence<T>,
  error?: string,
): QzxFailure<T> {
  requireNonBlank("message", message);
  if (!ERROR_CODE_PATTERN.test(errorCode)) {
    throw new TypeError(
      "errorCode must match ^[a-z][a-z0-9_]*$.",
    );
  }
  if (error !== undefined) {
    requireNonBlank("error", error);
  }
  requireSafeEvidence(evidence);
  return {
    ...evidence,
    success: false,
    message,
    error_code: errorCode,
    ...(error === undefined ? {} : { error }),
  };
}
