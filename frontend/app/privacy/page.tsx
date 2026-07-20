import type { Metadata } from "next";
import { LegalDocument } from "@/components/common/LegalDocument";
import {
  PRIVACY_SECTIONS,
  PRIVACY_EFFECTIVE_DATE,
  PRIVACY_VERSION,
} from "@/lib/privacy-content";

export const metadata: Metadata = {
  title: "Privacy Policy — Speeky",
  description: "Speeky's Privacy Policy.",
};

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Privacy Policy"
      version={PRIVACY_VERSION}
      effectiveDate={PRIVACY_EFFECTIVE_DATE}
      sections={PRIVACY_SECTIONS}
      backHref="/"
      backLabel="Back to Home"
    />
  );
}
