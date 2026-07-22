"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  ClipboardList,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  attemptSkipAssessment,
  confirmSkipAssessment,
  getResultsSummary,
  startAssessment,
  submitAssessmentResponse,
  type AssessmentSummary,
  type SkipAttemptResult,
} from "@/lib/assessment";
import { useAssessmentAccess } from "@/contexts/AssessmentContext";

type Step =
  | { name: "loading" }
  | { name: "already-assessed" }
  | { name: "intro" }
  | { name: "skip-confirm"; result: SkipAttemptResult }
  | {
      name: "question";
      assessmentId: string;
      questionIndex: number;
      totalQuestions: number;
      question: string;
    }
  | { name: "results"; summary: AssessmentSummary };

export default function AssessmentPage() {
  const router = useRouter();
  const { access, isLoading: accessLoading, refresh } = useAssessmentAccess();
  console.log(access);
  const [step, setStep] = React.useState<Step>({ name: "loading" });
  const [answer, setAnswer] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Decide the initial step exactly once. refresh() (called after finishing
  // the assessment) toggles accessLoading true->false again, which would
  // otherwise re-run this and clobber the "results" step with
  // "already-assessed" right after the user finishes — see hasInitialized.
  const hasInitialized = React.useRef(false);
  React.useEffect(() => {
    if (accessLoading || hasInitialized.current) return;
    hasInitialized.current = true;
    if (
      access?.assessment_status === "COMPLETED" ||
      access?.assessment_status === "PLATEAUED"
    ) {
      setStep({ name: "already-assessed" });
    } else {
      setStep({ name: "intro" });
    }
  }, [accessLoading, access]);

  async function handleStart() {
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await startAssessment();
      setStep({
        name: "question",
        assessmentId: result.assessment_id,
        questionIndex: result.question_index,
        totalQuestions: result.total_questions,
        question: result.current_question,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSkipRequest() {
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await attemptSkipAssessment();
      setStep({ name: "skip-confirm", result });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmSkip() {
    setError(null);
    setIsSubmitting(true);
    try {
      await confirmSkipAssessment();
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmitAnswer() {
    if (step.name !== "question" || !answer.trim()) return;
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await submitAssessmentResponse(step.assessmentId, {
        text_data: answer.trim(),
      });
      setAnswer("");
      if (result.status === "completed") {
        const summary = await getResultsSummary(step.assessmentId);
        await refresh();
        setStep({ name: "results", summary });
      } else {
        setStep({
          ...step,
          questionIndex: result.question_index,
          question: result.next_question ?? "",
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (step.name === "loading") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <span
          className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    );
  }

  if (step.name === "already-assessed") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl border border-border bg-surface-elevated p-8 text-center shadow-sm">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary">
          <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
        </span>
        <h1 className="font-serif text-2xl font-semibold text-foreground">
          You&apos;ve already completed your baseline assessment
        </h1>
        <p className="text-sm text-muted-foreground">
          Head to your Profile to see your results or request a re-assessment.
        </p>
        <Button href="/dashboard/profile" size="sm">
          Go to Profile
        </Button>
      </div>
    );
  }

  if (step.name === "intro") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-5 rounded-2xl border border-border bg-surface-elevated p-8 text-center shadow-sm">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary">
          <ClipboardList className="h-6 w-6" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="font-serif text-2xl font-semibold text-foreground">
            Baseline Communication Assessment
          </h1>
          <p className="text-sm text-muted-foreground">
            A short, five-question check-in sets your starting confidence score
            and personalizes AI Conversation Practice, Interview Coach, and
            Scenario-Based Learning for you. It takes about 5 minutes.
          </p>
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <div className="flex flex-col items-center gap-3">
          <Button size="lg" loading={isSubmitting} onClick={handleStart}>
            Start Assessment
          </Button>
          <button
            type="button"
            onClick={handleSkipRequest}
            disabled={isSubmitting}
            className="text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            Skip for now
          </button>
        </div>
      </div>
    );
  }

  if (step.name === "skip-confirm") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-5 rounded-2xl border border-warning/30 bg-warning/10 p-8 text-center shadow-sm">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-warning/20 text-warning">
          <TriangleAlert className="h-6 w-6" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="font-serif text-xl font-semibold text-foreground">
            Skip the baseline assessment?
          </h1>
          <p className="text-sm text-foreground">{step.result.message}</p>
        </div>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <div className="flex flex-col items-center gap-3 sm:flex-row">
          <Button size="md" onClick={() => setStep({ name: "intro" })}>
            Return to Assessment
          </Button>
          {step.result.can_skip ? (
            <Button
              size="md"
              variant="outline"
              loading={isSubmitting}
              onClick={handleConfirmSkip}
            >
              Skip Anyway
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  if (step.name === "question") {
    const progress = Math.round(
      (step.questionIndex / step.totalQuestions) * 100,
    );
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-6">
        <div>
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>
              Question {step.questionIndex + 1} of {step.totalQuestions}
            </span>
            <span>{progress}%</span>
          </div>
          <div className="mt-2 h-1.5 w-full rounded-full bg-muted">
            <div
              className="h-1.5 rounded-full bg-primary transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm sm:p-8">
          <p className="font-serif text-lg leading-relaxed text-foreground">
            {step.question}
          </p>
          <div className="mt-6">
            <Textarea
              label="Your answer"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              rows={5}
              placeholder="Type your response here..."
            />
          </div>
          {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
          <Button
            size="lg"
            className="mt-4"
            loading={isSubmitting}
            disabled={!answer.trim()}
            onClick={handleSubmitAnswer}
          >
            Continue
          </Button>
        </div>
      </div>
    );
  }

  // step.name === "results"
  const { summary } = step;
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="animate-fade-up rounded-2xl border border-border bg-gradient-to-br from-primary to-primary-hover p-8 text-center text-primary-foreground shadow-sm">
        <Sparkles
          className="mx-auto h-6 w-6 animate-fade-in"
          aria-hidden="true"
        />
        <h1 className="mt-3 font-serif text-2xl font-semibold">
          {summary.positive_framing.title}
        </h1>
        <p className="mt-2 text-sm text-primary-foreground/85">
          {summary.positive_framing.subtitle}
        </p>
        <p className="mx-auto mt-4 max-w-md text-3xl font-bold tracking-tight">
          {summary.confidence_score.display}
        </p>
        <p className="mt-1 text-sm text-primary-foreground/85">
          {summary.confidence_score.message}
        </p>
      </div>

      <div
        className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
        style={{ animationDelay: "120ms" }}
      >
        <h2 className="font-serif text-lg font-semibold text-foreground">
          Skill Breakdown
        </h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Object.values(summary.skill_breakdown).map((skill) => (
            <div
              key={skill.label}
              className="rounded-xl border border-border bg-surface p-4"
            >
              <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
                <span>{skill.label}</span>
                <span className="text-foreground">{skill.display}</span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {skill.description}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          {summary.positive_framing.highlight}
        </p>
      </div>

      <div
        className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
        style={{ animationDelay: "220ms" }}
      >
        <h2 className="font-serif text-lg font-semibold text-foreground">
          Next Steps
        </h2>
        <ul className="mt-3 flex flex-col gap-2">
          {summary.next_steps.map((step_, i) => (
            <li
              key={i}
              className="flex items-start gap-2.5 text-sm text-muted-foreground"
            >
              <CheckCircle2
                className="mt-0.5 h-4 w-4 shrink-0 text-success"
                aria-hidden="true"
              />
              {step_}
            </li>
          ))}
        </ul>
      </div>

      <Button href="/dashboard" size="lg" className="self-center">
        Go to Dashboard
      </Button>
    </div>
  );
}
