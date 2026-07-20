import { SectionTitle } from "@/components/common/SectionTitle";
import { StatsCard } from "@/components/landing/StatsCard";
import { PROGRESS_STATS } from "@/lib/mock-data";

export function ProgressAnalytics() {
  return (
    <section className="py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle
          eyebrow="Progress & Analytics"
          title="Growth you can actually see"
          description="Every session updates your dashboard, so progress feels measurable instead of assumed. This is illustrative sample data."
        />

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
          {PROGRESS_STATS.map((stat) => (
            <StatsCard key={stat.id} stat={stat} />
          ))}
        </div>
      </div>
    </section>
  );
}
