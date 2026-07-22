import type { Metadata } from "next";
import { LegalDocument } from "@/components/common/LegalDocument";
import {
  TERMS_SECTIONS,
  TERMS_EFFECTIVE_DATE,
  TERMS_VERSION,
} from "@/lib/terms-content";

export const metadata: Metadata = {
  title: "Terms & Conditions — Speeky",
  description: "Speeky's Terms and Conditions.",
};

export default function TermsPage() {
  return (
    <LegalDocument
      title="Terms and Conditions"
      version={TERMS_VERSION}
      effectiveDate={TERMS_EFFECTIVE_DATE}
      sections={TERMS_SECTIONS}
      backHref="/signup"
      backLabel="Back to Sign Up"
    />
  );
}
