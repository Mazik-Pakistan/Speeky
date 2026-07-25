"use client";

import { Lock } from "lucide-react";
import { AccentProgressTracker } from "@/components/dashboard/progress/AccentProgressTracker";
import { PracticeTimeMilestones } from "@/components/dashboard/progress/PracticeTimeMilestones";
import { VocabularyGrowthTracker } from "@/components/dashboard/progress/VocabularyGrowthTracker";
import { useAssessmentAccess } from "@/contexts/AssessmentContext";

export default function ProgressPage() {
  const { access } = useAssessmentAccess();
  const isUnlocked = access?.access_level === "full_access";

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
          Progress
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Track your vocabulary growth and accent improvement over time.
        </p>
      </div>

      {!isUnlocked ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          {access?.locked_message ??
            "Complete your baseline assessment to unlock your Progress Dashboard."}
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <VocabularyGrowthTracker />
          <PracticeTimeMilestones />
          <AccentProgressTracker />
        </div>
      )}
    </div>
  );
}
