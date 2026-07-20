import { SectionTitle } from "@/components/common/SectionTitle";
import { HOW_IT_WORKS } from "@/lib/mock-data";

/**
 * Step-by-step timeline. Numbering is meaningful here since the steps
 * are a real, ordered onboarding flow (not decorative 01/02/03 markers).
 */
export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t border-border bg-surface py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle
          eyebrow="How It Works"
          title="From first conversation to real confidence"
        />

        <ol className="relative mx-auto flex w-full max-w-3xl flex-col gap-10 sm:gap-12">
          <div
            aria-hidden="true"
            className="absolute bottom-6 left-5 top-6 hidden w-px bg-border sm:block"
          />
          {HOW_IT_WORKS.map((step) => (
            <li key={step.id} className="relative flex gap-5 sm:gap-6">
              <span className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface-elevated text-sm font-semibold text-primary shadow-sm">
                {step.index}
              </span>
              <div className="flex flex-col gap-1 pt-1.5">
                <h3 className="text-base font-semibold text-foreground">
                  {step.title}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {step.description}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
