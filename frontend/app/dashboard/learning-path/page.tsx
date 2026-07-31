"use client";

import * as React from "react";
import {
  Map,
  CheckCircle2,
  Lock,
  Trophy,
  RotateCcw,
  Play,
  Star,
  ChevronRight,
  AlertTriangle,
  Info,
  Sparkles,
  Award,
  ArrowRight,
  RefreshCw,
  Download,
  Share2,
  ShieldAlert,
  BookOpen,
  Zap,
  Clock,
  Target,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  getRecommendation,
  switchPath,
  evaluateMilestone,
  resetPath,
  pauseModule,
  resumeModule,
  checkModuleAccess,
  checkPathCompletion,
  getCertification,
  getModuleSessionHref,
  type RecommendationResponse,
  type LearningPath,
  type LPModule,
  type PauseResumeResponse,
  type PathCompletionCheckResponse,
  type PathSummaryResponse,
  type ModuleAccessResponse,
} from "@/lib/learningPath";

// ── Utility helpers ───────────────────────────────────────────────────────────
function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  { id: "path",        label: "My Path",       icon: Map },
  { id: "milestones",  label: "Milestones",    icon: Trophy },
  { id: "completion",  label: "Completion",    icon: Award },
] as const;
type TabId = (typeof TABS)[number]["id"];

// ── Reusable UI atoms ─────────────────────────────────────────────────────────
function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm",
        className
      )}
    >
      {children}
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.FC<{ className?: string }>;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-3 mb-6">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <h2 className="font-serif text-lg font-semibold text-foreground">{title}</h2>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({
  children,
  variant,
}: {
  children: React.ReactNode;
  variant: "success" | "warn" | "info" | "neutral" | "danger";
}) {
  const cls = {
    success: "bg-success/10 text-success border-success/20",
    warn: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
    info: "bg-primary/10 text-primary border-primary/20",
    neutral: "bg-muted text-muted-foreground border-border",
    danger: "bg-danger/10 text-danger border-danger/20",
  }[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        cls
      )}
    >
      {children}
    </span>
  );
}

function ProgressBar({
  value,
  max,
  className,
}: {
  value: number;
  max: number;
  className?: string;
}) {
  const pct = Math.min(100, Math.round((value / Math.max(max, 1)) * 100));
  return (
    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500",
          className || "bg-primary"
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function Spinner() {
  return (
    <span className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent text-primary inline-block" />
  );
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm">
      <AlertTriangle className="h-4 w-4 text-danger shrink-0 mt-0.5" />
      <span className="text-danger">{message}</span>
    </div>
  );
}

function SuccessAlert({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-success/30 bg-success/10 p-4 text-sm">
      <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
      <span className="text-success">{message}</span>
    </div>
  );
}

// ── Confetti component (pure CSS, no external library) ────────────────────────
const CONFETTI_COLORS = [
  "bg-primary", "bg-accent", "bg-amber-400", "bg-success",
  "bg-violet-500", "bg-pink-400",
];

function Confetti() {
  const pieces = React.useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => ({
        id: i,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        left: `${Math.random() * 100}%`,
        delay: `${Math.random() * 1.2}s`,
        size: Math.random() > 0.5 ? "h-2 w-1.5" : "h-1.5 w-1",
        rotate: `${Math.floor(Math.random() * 360)}deg`,
        duration: `${0.8 + Math.random() * 1.0}s`,
      })),
    []
  );

  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl"
      aria-hidden="true"
    >
      {pieces.map((p) => (
        <div
          key={p.id}
          className={cn(
            "absolute top-0 rounded-sm opacity-0 animate-fade-up",
            p.color,
            p.size
          )}
          style={{
            left: p.left,
            animationDelay: p.delay,
            animationDuration: p.duration,
            transform: `rotate(${p.rotate})`,
          }}
        />
      ))}
    </div>
  );
}



// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 1 & 2 — Path Recommendation + Switching ("My Path" tab)
// ═══════════════════════════════════════════════════════════════════════════════
function PathTab() {
  const { user } = useAuth();
  const router = useRouter();
  const [rec, setRec] = React.useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Switch state
  const [switchModalOpen, setSwitchModalOpen] = React.useState(false);
  const [pendingPath, setPendingPath] = React.useState<LearningPath | null>(null);
  const [switching, setSwitching] = React.useState(false);
  const [switchMsg, setSwitchMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);
  const [accepted, setAccepted] = React.useState(false);

  // Module access & completion state
  const [moduleAccess, setModuleAccess] = React.useState<Record<string, ModuleAccessResponse>>({});
  const [completedModuleIds, setCompletedModuleIds] = React.useState<string[]>([]);

  // Paused-session banner state
  const [pausedSession, setPausedSession] = React.useState<
    (PauseResumeResponse & { _pathId: string; _module: LPModule }) | null
  >(null);
  const [pauseChecked, setPauseChecked] = React.useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getRecommendation();
      setRec(data);
      // Check access for each module in the recommended path
      const path = data.available_paths.find(
        (p) => p.path_id === data.recommended_path_id
      );
      if (path?.modules) {
        loadModuleAccess(path.path_id, path.modules);
        // Also fetch which modules are already completed
        try {
          const completion = await checkPathCompletion(data.recommended_path_id);
          const incomplete = new Set(completion.incomplete_module_ids);
          const allIds = path.modules.map((m) => m.module_id);
          setCompletedModuleIds(allIds.filter((id) => !incomplete.has(id)));
        } catch {
          // Non-fatal: completed state just won't show
        }
        // Silently scan for any paused session on this path's modules
        checkForPausedSession(path.path_id, path.modules);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load recommendation.");
    } finally {
      setLoading(false);
    }
  }

  async function checkForPausedSession(pathId: string, modules: LPModule[]) {
    const sorted = [...modules].sort((a, b) => a.sequence_order - b.sequence_order);
    for (const mod of sorted) {
      try {
        const r = await resumeModule({ path_id: pathId, module_id: mod.module_id });
        if (r.success && r.resumed) {
          setPausedSession({ ...r, _pathId: pathId, _module: mod });
          break;
        }
      } catch {
        // Non-fatal — no paused session for this module
      }
    }
    setPauseChecked(true);
  }

  async function loadModuleAccess(path_id: string, modules: LPModule[]) {
    const results: Record<string, ModuleAccessResponse> = {};
    for (const mod of modules) {
      try {
        const access = await checkModuleAccess(path_id, mod.module_id);
        results[mod.module_id] = access;
      } catch {
        // Non-fatal: keep as unknown
      }
    }
    setModuleAccess(results);
  }

  React.useEffect(() => {
    load();
  }, []);

  // Accept recommendation
  async function handleAccept() {
    if (!rec) return;
    setSwitching(true);
    setSwitchMsg(null);
    try {
      const r = await switchPath({
        target_path_id: rec.recommended_path_id,
        confirm: true,
        request_id: `accept_${Date.now()}`,
      });
      setSwitchMsg({ type: "success", text: r.message });
      setAccepted(true);
    } catch (e) {
      setSwitchMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to accept path.",
      });
    } finally {
      setSwitching(false);
    }
  }

  // Initiate switch (shows confirmation modal)
  function handlePickPath(path: LearningPath) {
    setPendingPath(path);
    setSwitchModalOpen(true);
  }

  // Confirmed switch
  async function handleConfirmSwitch() {
    if (!pendingPath) return;
    setSwitching(true);
    setSwitchMsg(null);
    try {
      const r = await switchPath({
        target_path_id: pendingPath.path_id,
        confirm: true,
        request_id: `switch_${Date.now()}`,
      });
      setSwitchMsg({ type: "success", text: r.message });
      setSwitchModalOpen(false);
      setAccepted(true);
      await load();
    } catch (e) {
      setSwitchMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to switch path.",
      });
    } finally {
      setSwitching(false);
    }
  }


  if (loading)
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  if (error) return <ErrorAlert message={error} />;
  if (!rec) return null;

  const activePath = rec.available_paths.find(
    (p) => p.path_id === rec.recommended_path_id
  );
  const sortedModules = activePath
    ? [...activePath.modules].sort((a, b) => a.sequence_order - b.sequence_order)
    : [];

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Map}
        title="Your Learning Path"
        subtitle="A personalized path recommended based on your baseline assessment."
      />

      {/* Resume banner — shown automatically when a paused session exists for a module on this path */}
      {pauseChecked && pausedSession?.resumed && (
        <div className="animate-fade-up rounded-2xl border-2 border-primary/40 bg-primary/10 p-5 shadow-sm">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <Play className="h-5 w-5" />
            </span>
            <div className="flex-1">
              <div className="flex items-center justify-between gap-2 mb-1">
                <p className="font-serif font-semibold text-base text-foreground">
                  Resume Interview — {pausedSession._module.title}
                </p>
                <span className="rounded-full bg-primary/15 px-2.5 py-0.5 text-xs font-semibold text-primary">
                  Question {pausedSession.question_index + 1}
                </span>
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                {pausedSession.message}
              </p>
              {pausedSession.conversation_context && pausedSession.conversation_context.length > 0 && (
                <div className="mb-3 rounded-xl border border-border bg-surface p-3 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground block mb-1">Restored context:</span>
                  <span className="italic">
                    "{pausedSession.conversation_context[pausedSession.conversation_context.length - 1]?.content}"
                  </span>
                </div>
              )}
              {pausedSession.was_interrupted && (
                <div className="mb-3 flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  Your previous session was interrupted mid-processing. Please repeat your last input.
                </div>
              )}
              <div className="flex items-center gap-2 mt-2">
                <Button
                  size="sm"
                  onClick={() =>
                    router.push(getModuleSessionHref(pausedSession._pathId, pausedSession._module))
                  }
                >
                  <Play className="h-3.5 w-3.5" /> Continue Now
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recommendation card */}
      <Card
        className={cn(
          "relative border-primary/30 bg-primary/5",
          rec.is_fallback && "border-amber-400/30 bg-amber-400/5"
        )}
      >
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
            <BookOpen className="h-6 w-6" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h3 className="font-serif text-lg font-semibold text-foreground">
                {rec.path_title}
              </h3>
              <StatusBadge variant={rec.is_fallback ? "warn" : "info"}>
                {rec.is_fallback ? "Default Path" : "AI Recommended"}
              </StatusBadge>
              <StatusBadge variant="neutral">{rec.learning_level}</StatusBadge>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-3">
              {rec.reasoning}
            </p>
            {rec.confidence_score > 0 && (
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs text-muted-foreground">Confidence score:</span>
                <span className="text-xs font-semibold text-primary">
                  {rec.confidence_score.toFixed(1)}
                </span>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={handleAccept}
                loading={switching}
                disabled={accepted}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {accepted ? "Path Accepted" : "Accept Recommendation"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => document.getElementById("lp-path-chooser")?.scrollIntoView({ behavior: "smooth" })}
              >
                Choose a different path
              </Button>
            </div>
          </div>
        </div>
        {rec.is_fallback && (
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs">
            <Info className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
            <span className="text-amber-700 dark:text-amber-400">
              Recommendation engine timed out — showing curated default path. You can always choose a different one below.
            </span>
          </div>
        )}
      </Card>

      {switchMsg && (
        switchMsg.type === "success"
          ? <SuccessAlert message={switchMsg.text} />
          : <ErrorAlert message={switchMsg.text} />
      )}



      {/* Module list for active path */}
      {activePath && sortedModules.length > 0 && (
        <Card>
          <h3 className="font-semibold text-sm text-foreground mb-4 flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            Modules in "{activePath.title}"
            <StatusBadge variant={activePath.strict_sequential ? "info" : "success"}>
              {activePath.strict_sequential ? "Sequential" : "Free Explore"}
            </StatusBadge>
          </h3>
          <div className="flex flex-col gap-3">
            {sortedModules.map((mod, idx) => {
              const access = moduleAccess[mod.module_id];
              const isAccessible = access?.accessible ?? true;
              const isCompleted = completedModuleIds.includes(mod.module_id);

              return (
                <div
                  key={mod.module_id}
                  className={cn(
                    "relative flex items-center gap-3 rounded-xl border p-4 transition-all duration-300",
                    isCompleted && "border-success/30 bg-success/5",
                    isAccessible && !isCompleted && "border-border bg-surface",
                    !isAccessible && !isCompleted && "border-border bg-muted opacity-60"
                  )}
                >

                  {/* Step indicator */}
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                      isCompleted
                        ? "bg-success/15 text-success"
                        : isAccessible
                        ? "bg-primary/15 text-primary"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {isCompleted ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : isAccessible ? (
                      <span>{idx + 1}</span>
                    ) : (
                      <Lock className="h-3.5 w-3.5" />
                    )}
                  </span>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm text-foreground">
                        {mod.title}
                      </span>
                      {isCompleted && (
                        <StatusBadge variant="success">
                          <CheckCircle2 className="h-3 w-3" /> Completed
                        </StatusBadge>
                      )}
                    </div>
                    {!isAccessible && access?.reason && (
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                        {access.reason}
                      </p>
                    )}
                    {!isAccessible && access?.current_score !== null && access?.current_score !== undefined && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Your score: {access.current_score.toFixed(0)} — need {access.required_score}+ to unlock.{" "}
                        <span className="text-primary font-medium">
                          Retry the previous module to improve!
                        </span>
                      </p>
                    )}
                    {mod.prerequisites.length > 0 && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Requires: {mod.prerequisites.join(", ")}
                      </p>
                    )}
                    {isAccessible && !isCompleted && (
                      <p className="text-xs text-primary/70 mt-0.5 flex items-center gap-1">
                        <ChevronRight className="h-3 w-3" />
                        Launches Workplace English Coach practice session
                      </p>
                    )}
                  </div>

                  {isCompleted ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        router.push(getModuleSessionHref(activePath.path_id, mod))
                      }
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Practice Again
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant={isAccessible ? "primary" : "outline"}
                      disabled={!isAccessible}
                      onClick={() => {
                        if (isAccessible) {
                          router.push(getModuleSessionHref(activePath.path_id, mod));
                        }
                      }}
                    >
                      {isAccessible ? (
                        <>
                          <Play className="h-3.5 w-3.5" /> Start Lesson
                        </>
                      ) : (
                        <>
                          <Lock className="h-3.5 w-3.5" /> Locked
                        </>
                      )}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Path chooser */}
      <div id="lp-path-chooser">
        <h3 className="font-semibold text-sm text-foreground mb-3">
          All Available Paths
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {rec.available_paths
            .filter((p) => p.is_published && !p.is_deprecated)
            .map((path) => (
              <Card
                key={path.path_id}
                className={cn(
                  "flex flex-col gap-3 cursor-pointer transition-all hover:border-primary/40 hover:shadow-md",
                  path.path_id === rec.recommended_path_id && "border-primary/40 bg-primary/5"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-sm text-foreground">{path.title}</span>
                  {path.path_id === rec.recommended_path_id && (
                    <StatusBadge variant="info">Recommended</StatusBadge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">{path.description}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge variant="neutral">{path.learning_level}</StatusBadge>
                  <StatusBadge variant="neutral">{path.modules.length} modules</StatusBadge>
                </div>
                <Button
                  size="sm"
                  variant={path.path_id === rec.recommended_path_id ? "secondary" : "outline"}
                  onClick={() => handlePickPath(path)}
                  disabled={path.path_id === rec.recommended_path_id && accepted}
                >
                  {path.path_id === rec.recommended_path_id && accepted
                    ? "Active Path"
                    : "Select This Path"}
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </Card>
            ))}
        </div>
      </div>

      {/* Reset path */}
      <ResetPathSection user={user} rec={rec} />

      {/* Confirmation modal for path switching */}
      <Modal
        open={switchModalOpen}
        onClose={() => {
          setSwitchModalOpen(false);
          setPendingPath(null);
          setSwitchMsg(null);
        }}
        title="Switch Learning Path?"
        description={
          pendingPath?.is_enterprise_assigned
            ? "⚠️ This path has incomplete assessment requirements."
            : undefined
        }
      >
        <div className="flex flex-col gap-4">
          {pendingPath && (
            <div className="rounded-xl border border-border bg-surface p-4">
              <p className="font-semibold text-sm text-foreground">{pendingPath.title}</p>
              <p className="text-xs text-muted-foreground mt-1">{pendingPath.description}</p>
              <div className="flex gap-2 mt-2 flex-wrap">
                <StatusBadge variant="neutral">{pendingPath.learning_level}</StatusBadge>
                <StatusBadge variant="neutral">{pendingPath.modules.length} modules</StatusBadge>
              </div>
            </div>
          )}
          <div className="flex items-start gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs">
            <Info className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
            <span className="text-amber-700 dark:text-amber-400">
              Your progress on your current path will be auto-saved and preserved. You can switch back at any time.
            </span>
          </div>
          {switchMsg && (
            switchMsg.type === "error"
              ? <ErrorAlert message={switchMsg.text} />
              : <SuccessAlert message={switchMsg.text} />
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSwitchModalOpen(false);
                setPendingPath(null);
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleConfirmSwitch}
              loading={switching}
            >
              Yes, Switch Path
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ── Reset path section (Piece 4) ──────────────────────────────────────────────
function ResetPathSection({
  user,
  rec,
}: {
  user: ReturnType<typeof useAuth>["user"];
  rec: RecommendationResponse | null;
}) {
  const [resetModalOpen, setResetModalOpen] = React.useState(false);
  const [resetting, setResetting] = React.useState(false);
  const [resetMsg, setResetMsg] = React.useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  if (!rec) return null;

  async function handleConfirmReset() {
    setResetting(true);
    setResetMsg(null);
    try {
      const r = await resetPath({
        path_id: rec!.recommended_path_id,
        confirm: true,
      });
      setResetMsg({ type: "success", text: r.message });
      setResetModalOpen(false);
    } catch (e) {
      setResetMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to reset path.",
      });
    } finally {
      setResetting(false);
    }
  }

  return (
    <>
      <Card className="border-danger/20">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-danger/10 text-danger">
            <ShieldAlert className="h-5 w-5" />
          </span>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-sm text-foreground mb-1">
              Reset This Path
            </h3>
            <p className="text-xs text-muted-foreground mb-3">
              This is a <strong>destructive action</strong>. All your progress on this path will be reset to zero. Your prior progress will be archived, but your active progress will be permanently cleared. If you have an active session in progress, finish or end it first.
            </p>
            {resetMsg && (
              resetMsg.type === "success"
                ? <SuccessAlert message={resetMsg.text} />
                : <ErrorAlert message={resetMsg.text} />
            )}
            <Button
              variant="danger"
              size="sm"
              onClick={() => setResetModalOpen(true)}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset Path from Scratch
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        open={resetModalOpen}
        onClose={() => {
          setResetModalOpen(false);
          setResetMsg(null);
        }}
        title="⚠️ Reset Learning Path?"
        description="This cannot be easily undone. Read carefully before confirming."
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-danger/30 bg-danger/10 p-4">
            <p className="text-sm font-semibold text-danger mb-1">
              You are about to permanently reset your active progress.
            </p>
            <ul className="text-xs text-danger/80 list-disc ml-4 space-y-1 mt-2">
              <li>All module completions and scores on this path will be cleared.</li>
              <li>Your prior progress will be archived (you can view it later, but cannot restore it).</li>
              <li>If you have an active paused session, the reset will be blocked — end your session first.</li>
              <li>Enterprise-assigned paths cannot be reset without admin authorization.</li>
            </ul>
          </div>
          {resetMsg && (
            resetMsg.type === "error"
              ? <ErrorAlert message={resetMsg.text} />
              : <SuccessAlert message={resetMsg.text} />
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setResetModalOpen(false);
                setResetMsg(null);
              }}
            >
              Cancel — Keep My Progress
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleConfirmReset}
              loading={resetting}
            >
              Yes, Reset Everything
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 3 — Milestones tab (extends Progress Dashboard badges)
// ═══════════════════════════════════════════════════════════════════════════════
function MilestonesTab() {
  const [msg, setMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);
  const [acting, setActing] = React.useState(false);

  async function handleEvalDemo() {
    setActing(true);
    setMsg(null);
    try {
      const r = await evaluateMilestone({
        path_id: "beginner-path",
        module_id: "mod_b1",
        score: 92,
      });
      setMsg({
        type: r.awarded_badges.length > 0 ? "success" : "info" as any,
        text:
          r.awarded_badges.length > 0
            ? `🏅 New badge${r.awarded_badges.length > 1 ? "s" : ""} awarded: ${r.awarded_badges.join(", ")}! ${r.message}`
            : r.message,
      });
    } catch (e) {
      setMsg({ type: "error", text: e instanceof ApiError ? e.message : "Failed." });
    } finally {
      setActing(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Trophy}
        title="Milestones & Achievements"
        subtitle="Badges earned through your learning path are displayed on your Progress Dashboard."
      />

      {/* Cross-link to the existing Progress Dashboard badges tab */}
      <Card className="border-amber-400/30 bg-amber-400/5">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-400/20 text-amber-500">
            <Award className="h-5 w-5" />
          </span>
          <div className="flex-1">
            <h3 className="font-semibold text-sm text-foreground mb-1">
              Your Full Badge Catalog
            </h3>
            <p className="text-xs text-muted-foreground mb-3">
              All badges earned through learning path milestones (and your streak/confidence milestones) are unified in your Progress Dashboard. No duplicates — one badge system.
            </p>
            <Button size="sm" variant="outline" href="/dashboard/progress">
              <Trophy className="h-3.5 w-3.5" />
              View All Badges on Progress Dashboard
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Learning Path-specific milestone triggers */}
      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-4 flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" />
          Path Milestone Badges
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              id: "lp_first_module",
              title: "First Step on the Path",
              desc: "Complete your first module in any learning path.",
              icon: "🥇",
            },
            {
              id: "lp_path_halfway",
              title: "Halfway There",
              desc: "Complete at least 2 modules in the same path.",
              icon: "⚡",
            },
            {
              id: "lp_master_score",
              title: "Master Score",
              desc: "Score 90+ on any module.",
              icon: "🌟",
            },
          ].map((badge) => (
            <div
              key={badge.id}
              className="flex flex-col items-center gap-2 rounded-xl border border-border bg-surface p-4 text-center"
            >
              <span className="text-3xl">{badge.icon}</span>
              <span className="font-semibold text-xs text-foreground">{badge.title}</span>
              <span className="text-xs text-muted-foreground">{badge.desc}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Manual milestone evaluation trigger */}
      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-1 flex items-center gap-2">
          <Star className="h-4 w-4 text-amber-500" />
          Evaluate Milestones Now
        </h3>
        <p className="text-xs text-muted-foreground mb-4">
          Milestones are evaluated automatically when you complete a module. You can also trigger an evaluation manually — duplicate events are safely ignored (no badge will be awarded twice).
        </p>
        {msg && (
          msg.type === "success"
            ? <SuccessAlert message={msg.text} />
            : <ErrorAlert message={msg.text} />
        )}
        <div className="mt-3">
          <Button size="sm" onClick={handleEvalDemo} loading={acting}>
            <Sparkles className="h-3.5 w-3.5" />
            Evaluate Current Module Milestones
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 8 — Path Completion & Certification tab
// ═══════════════════════════════════════════════════════════════════════════════
function CompletionTab() {
  const [pathId, setPathId] = React.useState("beginner-path");
  const [check, setCheck] = React.useState<PathCompletionCheckResponse | null>(null);
  const [cert, setCert] = React.useState<PathSummaryResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [certLoading, setCertLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  async function handleCheck() {
    setLoading(true);
    setError(null);
    setCert(null);
    setCheck(null);
    try {
      const r = await checkPathCompletion(pathId);
      setCheck(r);
      if (r.is_complete && r.summary) {
        setCert(r.summary as PathSummaryResponse);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to check completion.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGetCert() {
    setCertLoading(true);
    setError(null);
    try {
      const r = await getCertification(pathId);
      setCert(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load certification.");
    } finally {
      setCertLoading(false);
    }
  }

  function handleCopyLink() {
    if (!cert) return;
    navigator.clipboard.writeText(cert.shareable_card_data.certificate_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleSaveText() {
    if (!cert) return;
    const content = [
      `Certificate: ${cert.shareable_card_data.title}`,
      `Level: ${cert.shareable_card_data.level}`,
      `Practice Time: ${fmtSeconds(cert.total_practice_time_seconds)}`,
      `Avg Confidence: ${cert.average_confidence_score.toFixed(1)}/100`,
      `Vocabulary Mastered: ${cert.total_vocabulary_mastered} words`,
      `Certificate URL: ${cert.shareable_card_data.certificate_url}`,
      `Certificate ID: ${cert.certificate_id}`,
    ].join("\n");
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `speeky-certificate-${cert.certificate_id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Award}
        title="Path Completion & Certification"
        subtitle="Verify 100% completion and generate your shareable achievement summary."
      />

      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-4">
          Check Completion Status
        </h3>
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="Path ID (e.g. beginner-path)"
            value={pathId}
            onChange={(e) => setPathId(e.target.value)}
            className="h-9 flex-1 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <Button size="sm" onClick={handleCheck} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5" />
            Check
          </Button>
        </div>
        {error && <ErrorAlert message={error} />}

        {check && !check.is_complete && (
          <div className="flex flex-col gap-3">
            <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm">
              <Info className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-amber-700 dark:text-amber-400">
                  Not complete yet — {check.completed_modules_count}/{check.total_modules_count} modules done.
                </p>
                {check.incomplete_module_ids.length > 0 && (
                  <p className="text-xs text-amber-600 dark:text-amber-400/80 mt-1">
                    Still incomplete: <strong>{check.incomplete_module_ids.join(", ")}</strong>
                  </p>
                )}
              </div>
            </div>
            <ProgressBar
              value={check.completed_modules_count}
              max={check.total_modules_count}
            />
            <p className="text-xs text-muted-foreground text-right">
              {check.completed_modules_count}/{check.total_modules_count} modules completed
            </p>
          </div>
        )}
      </Card>

      {/* Celebration & summary card — shown on full completion */}
      {cert && (
        <div className="relative animate-fade-up">
          {/* Confetti burst */}
          <div className="relative overflow-hidden rounded-2xl border-2 border-amber-400/50 bg-gradient-to-br from-amber-400/10 via-primary/10 to-success/10 p-6">
            <Confetti />
            <div className="relative z-10 flex flex-col items-center text-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-400/20 text-amber-500">
                <Trophy className="h-8 w-8" />
              </div>
              <div>
                <h2 className="font-serif text-2xl font-bold text-foreground mb-1">
                  Path Complete! 🎉
                </h2>
                <p className="text-sm text-muted-foreground">
                  {cert.path_title}
                </p>
                {check?.is_grandfathered && (
                  <StatusBadge variant="info">
                    Grandfathered — completed original path
                  </StatusBadge>
                )}
              </div>

              {/* Summary card data */}
              <div className="w-full grid grid-cols-3 gap-3 mt-2">
                {[
                  {
                    label: "Practice Time",
                    value: fmtSeconds(cert.total_practice_time_seconds),
                    icon: Clock,
                  },
                  {
                    label: "Avg Confidence",
                    value: `${cert.average_confidence_score.toFixed(1)}/100`,
                    icon: Star,
                  },
                  {
                    label: "Vocabulary",
                    value: `${cert.total_vocabulary_mastered} words`,
                    icon: BookOpen,
                  },
                ].map(({ label, value, icon: Icon }) => (
                  <div
                    key={label}
                    className="flex flex-col items-center gap-1.5 rounded-xl border border-amber-400/20 bg-surface-elevated p-3"
                  >
                    <Icon className="h-4 w-4 text-amber-500" />
                    <span className="font-bold text-lg font-serif text-foreground">{value}</span>
                    <span className="text-xs text-muted-foreground">{label}</span>
                  </div>
                ))}
              </div>

              <div className="w-full rounded-xl border border-border bg-surface p-3 text-left">
                <p className="text-xs text-muted-foreground mb-1">Certificate ID</p>
                <p className="font-mono text-xs text-foreground font-semibold">
                  {cert.certificate_id}
                </p>
              </div>

              {/* Share actions */}
              <div className="flex flex-wrap gap-2 justify-center">
                <Button size="sm" variant="outline" onClick={handleCopyLink}>
                  <Share2 className="h-3.5 w-3.5" />
                  {copied ? "Link Copied!" : "Copy Share Link"}
                </Button>
                <Button size="sm" variant="outline" onClick={handleSaveText}>
                  <Download className="h-3.5 w-3.5" />
                  Save as Text
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Share your achievement on LinkedIn or with your team. Use the link or save the text summary — no platform share required.
              </p>
            </div>
          </div>
        </div>
      )}

      {check?.is_complete && !cert && (
        <div className="flex justify-center">
          <Button onClick={handleGetCert} loading={certLoading}>
            <Award className="h-4 w-4" />
            Generate My Certificate
          </Button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Page
// ═══════════════════════════════════════════════════════════════════════════════
export default function LearningPathPage() {
  const [activeTab, setActiveTab] = React.useState<TabId>("path");

  const TAB_CONTENT: Record<TabId, React.ReactNode> = {
    path:       <PathTab />,
    milestones: <MilestonesTab />,
    completion: <CompletionTab />,
  };


  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Page header */}
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Learning Path
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Follow a structured, AI-recommended path through modules — unlock new levels as you progress.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1.5 rounded-2xl border border-border bg-surface-elevated p-1.5 shadow-sm">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium transition-all",
              activeTab === id
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      <div>{TAB_CONTENT[activeTab]}</div>
    </div>
  );
}
