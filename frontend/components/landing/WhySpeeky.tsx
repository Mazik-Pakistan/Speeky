import { Check, X } from "lucide-react";
import { SectionTitle } from "@/components/common/SectionTitle";
import { COMPARISON_POINTS } from "@/lib/mock-data";

/**
 * Explains the core philosophy: confidence over grammar. Contrasts
 * traditional English learning with AI conversation coaching using
 * a simple two-column comparison.
 */
export function WhySpeeky() {
  return (
    <section id="why-speeky" className="border-t border-border bg-surface py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle
          eyebrow="Why Speeky"
          title="Confidence matters more than grammar"
          description="Most people preparing for interviews and workplace conversations already know the grammar. What holds them back is speaking up, staying fluent under pressure, and sounding confident in the moment."
        />

        <div className="mx-auto grid w-full max-w-4xl overflow-hidden rounded-2xl border border-border bg-surface-elevated shadow-sm sm:grid-cols-2">
          <div className="flex flex-col gap-5 border-b border-border p-8 sm:border-b-0 sm:border-r">
            <span className="text-sm font-medium text-muted-foreground">
              Traditional English Learning
            </span>
            <ul className="flex flex-col gap-4">
              {COMPARISON_POINTS.map((point) => (
                <li key={point.id} className="flex items-start gap-3 text-sm text-muted-foreground">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
                  {point.traditional}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-col gap-5 p-8">
            <span className="text-sm font-medium text-primary">
              Speeky AI Coaching
            </span>
            <ul className="flex flex-col gap-4">
              {COMPARISON_POINTS.map((point) => (
                <li key={point.id} className="flex items-start gap-3 text-sm text-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                  {point.speeky}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
