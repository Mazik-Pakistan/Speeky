import { Navbar } from "@/components/landing/Navbar";
import { LandingAuthRedirect } from "@/components/landing/LandingAuthRedirect";
import { HeroSection } from "@/components/landing/HeroSection";
import { WhySpeeky } from "@/components/landing/WhySpeeky";
import { CoreFeatures } from "@/components/landing/CoreFeatures";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { ProgressAnalytics } from "@/components/landing/ProgressAnalytics";
import { Testimonials } from "@/components/landing/Testimonials";
import { FAQSection } from "@/components/landing/FAQSection";
import { CTASection } from "@/components/landing/CTASection";
import { Footer } from "@/components/common/Footer";

export default function LandingPage() {
  return (
    <>
      <LandingAuthRedirect />
      <Navbar />
      <main>
        <HeroSection />
        <WhySpeeky />
        <CoreFeatures />
        <HowItWorks />
        <ProgressAnalytics />
        <Testimonials />
        <FAQSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
