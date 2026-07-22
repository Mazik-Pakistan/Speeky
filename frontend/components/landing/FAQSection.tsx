import { SectionTitle } from "@/components/common/SectionTitle";
import { Accordion } from "@/components/ui/accordion";
import { FAQ_ITEMS } from "@/lib/mock-data";

export function FAQSection() {
  const items = FAQ_ITEMS.map((item) => ({
    id: item.id,
    trigger: item.question,
    content: item.answer,
  }));

  return (
    <section id="faq" className="py-24">
      <div className="container flex flex-col gap-14">
        <SectionTitle eyebrow="FAQ" title="Common questions" />

        <div className="mx-auto w-full max-w-2xl">
          <Accordion items={items} />
        </div>
      </div>
    </section>
  );
}
