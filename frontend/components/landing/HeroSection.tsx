import { ArrowRight, PlayCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TRUST_INDICATORS } from "@/lib/mock-data";

/**
 * Hero section. Communicates within seconds that Speeky is an AI
 * communication coach, not a language-learning app. The gradient here
 * is intentional per the constitution's "Gradients allowed on hero" rule.
 */
export function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[36rem] bg-[radial-gradient(60%_50%_at_50%_0%,hsl(var(--secondary))_0%,hsl(var(--background))_100%)]"
      />

      <div className="container flex flex-col items-center gap-10 py-24 text-center sm:py-32">
        <div className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-1.5 text-sm font-medium text-muted-foreground animate-fade-in">
          <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" />
          An AI communication coach, not a language course
        </div>

        <h1 className="max-w-3xl text-balance font-serif text-4xl font-semibold tracking-tight text-foreground sm:text-5xl md:text-6xl animate-fade-up">
          Speak with confidence. In interviews, meetings, and everyday life.
        </h1>

        <p className="max-w-2xl text-balance text-lg text-muted-foreground sm:text-xl animate-fade-up">
          Speeky is an AI coach that helps you practice real conversations,
          ace interviews, and communicate clearly at work &mdash; grammar isn&apos;t
          the problem, confidence is.
        </p>

        <div className="flex flex-col items-center gap-4 sm:flex-row animate-fade-up">
          <Button size="lg" className="gap-2" href="/signup">
            Get Started Free
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button size="lg" variant="outline" className="gap-2" href="#how-it-works">
            <PlayCircle className="h-4 w-4" aria-hidden="true" />
            See How It Works
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-sm text-muted-foreground">
          {TRUST_INDICATORS.map((item) => (
            <span key={item.id} className="inline-flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
              {item.label}
            </span>
          ))}
        </div>

        <div className="mt-8 w-full max-w-4xl animate-fade-up">
          <div className="overflow-hidden rounded-2xl border border-border bg-surface-elevated shadow-md">
            <div className="flex items-center gap-2 border-b border-border px-5 py-3">
              <span className="h-2.5 w-2.5 rounded-full bg-danger/60" aria-hidden="true" />
              <span className="h-2.5 w-2.5 rounded-full bg-warning/60" aria-hidden="true" />
              <span className="h-2.5 w-2.5 rounded-full bg-success/60" aria-hidden="true" />
              <span className="ml-3 text-xs text-muted-foreground">
                Speeky &mdash; AI Practice Session
              </span>
            </div>
            <div className="flex flex-col gap-4 p-6 text-left sm:p-8">
              <div className="max-w-md rounded-xl rounded-tl-sm bg-secondary px-4 py-3 text-sm text-secondary-foreground">
                Tell me about a time you handled a disagreement with a
                teammate.
              </div>
              <div className="ml-auto max-w-md rounded-xl rounded-tr-sm bg-primary px-4 py-3 text-sm text-primary-foreground">
                Sure &mdash; on my last project, a teammate and I disagreed on
                the timeline, so I suggested we walk through the risks
                together...
              </div>
              <div className="flex items-center gap-2 self-start rounded-xl border border-border bg-surface px-4 py-2 text-xs text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
                Confidence +4 &middot; Clear structure, strong example
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
