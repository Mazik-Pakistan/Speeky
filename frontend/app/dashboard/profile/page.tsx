"use client";

import { useAuth } from "@/contexts/AuthContext";
import { ProfileInfoSection } from "@/components/dashboard/profile/ProfileInfoSection";
import { LearningGoalSection } from "@/components/dashboard/profile/LearningGoalSection";
import { AssessmentSection } from "@/components/dashboard/profile/AssessmentSection";
import { PerformanceMemorySection } from "@/components/dashboard/profile/PerformanceMemorySection";
import { PrivacyConsentSection } from "@/components/dashboard/profile/PrivacyConsentSection";
import { ConversationMemorySection } from "@/components/dashboard/profile/ConversationMemorySection";
import { CodeSwitchSection } from "@/components/dashboard/profile/CodeSwitchSection";
import { SecuritySection } from "@/components/dashboard/profile/SecuritySection";
import { DangerZoneSection } from "@/components/dashboard/profile/DangerZoneSection";

export default function ProfilePage() {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
        Profile
      </h1>

      <ProfileInfoSection />
      <LearningGoalSection />
      <AssessmentSection />
      <PerformanceMemorySection />
      <PrivacyConsentSection />
      <ConversationMemorySection />
      <CodeSwitchSection />
      <SecuritySection />
      <DangerZoneSection />
    </div>
  );
}
