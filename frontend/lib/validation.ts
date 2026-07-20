/**
 * Mirrors Backend (clone_backend/backend/schemas/auth_schemas.py) validation
 * rules exactly, so the frontend rejects bad input before hitting the API.
 */

const ALLOWED_EMAIL_DOMAINS = ["gmail.com", "outlook.com"];

export function isAllowedEmailDomain(email: string): boolean {
  const lower = email.trim().toLowerCase();
  return ALLOWED_EMAIL_DOMAINS.some((domain) => lower.endsWith(`@${domain}`));
}

export const EMAIL_DOMAIN_ERROR = "Only Gmail and Outlook email addresses are allowed.";

const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$/;

export function isValidPassword(password: string): boolean {
  return PASSWORD_PATTERN.test(password);
}

export const PASSWORD_RULE_ERROR =
  "Password must be 8+ characters with an uppercase letter, lowercase letter, digit, and special character (@$!%*?&).";

const NAME_PATTERN = /^[a-zA-Z0-9 _-]+$/;

export function isValidName(name: string): boolean {
  const trimmed = name.trim();
  return trimmed.length >= 3 && trimmed.length <= 100 && NAME_PATTERN.test(trimmed);
}

export const NAME_RULE_ERROR =
  "Name must be 3-100 characters (letters, numbers, spaces, _ or - only).";
