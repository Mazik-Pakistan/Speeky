import { SectionTitle } from "@/components/common/SectionTitle";
import { TestimonialCard } from "@/components/landing/TestimonialCard";
import { TESTIMONIALS } from "@/lib/mock-data";

export function Testimonials() {
  return (
    <section id="testimonials" className="border-t border-border bg-surface py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle
          eyebrow="Testimonials"
          title="Trusted by students, job seekers, and professionals"
        />

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {TESTIMONIALS.map((testimonial) => (
            <TestimonialCard key={testimonial.id} testimonial={testimonial} />
          ))}
        </div>
      </div>
    </section>
  );
}
