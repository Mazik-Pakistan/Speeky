"use client";

import * as React from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { TERMS_SECTIONS, TERMS_EFFECTIVE_DATE, TERMS_VERSION } from "@/lib/terms-content";
import { PRIVACY_SECTIONS, PRIVACY_EFFECTIVE_DATE, PRIVACY_VERSION } from "@/lib/privacy-content";

interface LegalModalProps {
  open: boolean;
  onClose: () => void;
  type: "terms" | "privacy" | null;
}

export function LegalModal({ open, onClose, type }: LegalModalProps) {
  if (!type) return null;

  const isTerms = type === "terms";
  const title = isTerms ? "Terms and Conditions" : "Privacy Policy";
  const version = isTerms ? TERMS_VERSION : PRIVACY_VERSION;
  const date = isTerms ? TERMS_EFFECTIVE_DATE : PRIVACY_EFFECTIVE_DATE;
  const sections = isTerms ? TERMS_SECTIONS : PRIVACY_SECTIONS;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      hideCloseButton
      // Hide the scrollbar while keeping it scrollable
      className="max-h-[85vh] max-w-2xl overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
    >
      <div className="mt-2 flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-primary">{version}</span>
          <p className="text-xs text-muted-foreground">Effective Date: {date}</p>
        </div>

        <div className="flex flex-col gap-6">
          {sections.map((section) => (
            <section key={section.id} className="flex flex-col gap-2">
              {section.title && (
                <h3 className="font-serif text-lg font-semibold text-foreground">
                  {section.title}
                </h3>
              )}
              {section.paragraphs?.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-muted-foreground">
                  {p}
                </p>
              ))}
              {section.bullets && (
                <ul className="flex flex-col gap-1 pl-1">
                  {section.bullets.map((b, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground"
                    >
                      <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
                      {b}
                    </li>
                  ))}
                </ul>
              )}
              {section.closingParagraphs?.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-muted-foreground">
                  {p}
                </p>
              ))}
            </section>
          ))}
        </div>

        <div className="sticky bottom-0 mt-4 border-t border-border bg-surface-elevated pb-2 pt-4">
          <Button type="button" onClick={onClose} className="w-full">
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}