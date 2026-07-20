import { SectionTitle } from "@/components/common/SectionTitle";
import { FeatureCard } from "@/components/landing/FeatureCard";
import { CORE_FEATURES } from "@/lib/mock-data";

export function CoreFeatures() {
  return (
    <section id="features" className="py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle
          eyebrow="Core Features"
          title="Everything you need to communicate with confidence"
          description="Speeky combines conversation practice, interview coaching, and workplace scenarios into one AI-powered coach."
        />

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {CORE_FEATURES.map((feature) => (
            <FeatureCard key={feature.id} feature={feature} />
          ))}
        </div>
      </div>
    </section>
  );
}
