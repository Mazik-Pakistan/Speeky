/**
 * Learning-goal selection (US-08, US-10). The backend User model has no
 * `goal` field or endpoint yet, so this is stored client-side per user.
 *
 * TODO(backend): add a `goal` column to the User model + accept it in
 * SignupSchema / UpdateProfileSchema, then replace this localStorage shim
 * with real GET/PATCH /api/users/me calls.
 */

export type LearningGoal =
  | "improve_english"
  | "job_interviews"
  | "workplace_communication"
  | "public_speaking";

export interface LearningGoalOption {
  id: LearningGoal;
  label: string;
  description: string;
}

export const LEARNING_GOALS: LearningGoalOption[] = [
  {
    id: "improve_english",
    label: "Improve English",
    description: "Build general fluency and everyday conversation confidence.",
  },
  {
    id: "job_interviews",
    label: "Job Interviews",
    description: "Prepare for behavioral and technical interview questions.",
  },
  {
    id: "workplace_communication",
    label: "Workplace Communication",
    description: "Practice meetings, emails, and professional conversations.",
  },
  {
    id: "public_speaking",
    label: "Public Speaking",
    description: "Build confidence presenting and speaking to groups.",
  },
];

export const GOAL_DASHBOARD_COPY: Record<
  LearningGoal,
  { subtitle: string; preferredCategory?: "Business" | "Social" | "Travel" }
> = {
  improve_english: {
    subtitle: "You've reached 85% fluency overall. Ready for today's challenge?",
  },
  job_interviews: {
    subtitle:
      "You've reached 85% fluency in interview scenarios. Ready to practice?",
    preferredCategory: "Business",
  },
  workplace_communication: {
    subtitle:
      "You've reached 85% fluency in workplace scenarios. Ready for today's meeting practice?",
    preferredCategory: "Business",
  },
  public_speaking: {
    subtitle:
      "You've reached 85% fluency in presentation scenarios. Ready to build confidence on stage?",
  },
};

const DEFAULT_GOAL: LearningGoal = "improve_english";
const storageKey = (userId: string) => `speeky:goal:${userId}`;

// E-03 (Goal Selection Abandonment): defaults to "Improve English" instead
// of leaving the user in an unset state.
export function getLearningGoal(userId: string): LearningGoal {
  if (typeof window === "undefined") return DEFAULT_GOAL;
  const value = window.localStorage.getItem(storageKey(userId));
  const match = LEARNING_GOALS.find((goal) => goal.id === value);
  return match?.id ?? DEFAULT_GOAL;
}

export function setLearningGoal(userId: string, goal: LearningGoal) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(userId), goal);
}
