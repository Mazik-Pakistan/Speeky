"use client";

import * as React from "react";
import {
  Flame, ShieldCheck, Trophy, BarChart3, FileDown,
  AlertCircle, TrendingUp, Lock, CheckCircle2, Star,
  Calendar, Clock, Zap, BookOpen, Award, Crown,
  Footprints, Sparkles, ChevronDown, ChevronUp,
  AlertTriangle, Info, RefreshCw, Send
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  getStreakInfo, activateFreeze, performMakeupDrill, logPracticeSession,
  getConfidenceBreakdown, disputeSessionScore,
  getBadgeCatalog, exportProgressReport,
  submitStreakAppeal, getHistoricalData, expandPeriodData,
  type StreakInfoResponse, type ConfidenceBreakdownResponse,
  type BadgeCatalogResponse, type ProgressReportResponse,
  type HistoricalDataResponse, type AggregatedDataPoint,
} from "@/lib/progressDashboard";

// ── Utility helpers ───────────────────────────────────────────────────────────
function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function today(): string {
  return new Date().toISOString().split("T")[0];
}

function nDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split("T")[0];
}

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  { id: "streak",     label: "Streak & Freeze",   icon: Flame },
  { id: "confidence", label: "Confidence Score",   icon: BarChart3 },
  { id: "badges",     label: "Badges",             icon: Trophy },
  { id: "report",     label: "Progress Report",    icon: FileDown },
  { id: "appeal",     label: "Streak Appeal",      icon: ShieldCheck },
  { id: "history",    label: "History",            icon: TrendingUp },
] as const;

type TabId = (typeof TABS)[number]["id"];

// ── ICON MAP for badge icons ──────────────────────────────────────────────────
const BADGE_ICONS: Record<string, React.FC<{ className?: string }>> = {
  "footsteps": ({ className }) => <Footprints className={className} />,
  "flame":     ({ className }) => <Flame className={className} />,
  "zap":       ({ className }) => <Zap className={className} />,
  "crown":     ({ className }) => <Crown className={className} />,
  "clock":     ({ className }) => <Clock className={className} />,
  "award":     ({ className }) => <Award className={className} />,
  "book-open": ({ className }) => <BookOpen className={className} />,
  "sparkles":  ({ className }) => <Sparkles className={className} />,
};

// ── Reusable UI atoms ─────────────────────────────────────────────────────────
function Card({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div onClick={onClick} className={cn("rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm", className)}>
      {children}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, subtitle }: { icon: React.FC<{ className?: string }>; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-3 mb-6">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shrink-0">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <h2 className="font-serif text-lg font-semibold text-foreground">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function StatusBadge({ children, variant }: { children: React.ReactNode; variant: "success" | "warn" | "info" | "neutral" }) {
  const cls = {
    success: "bg-success/10 text-success border-success/20",
    warn:    "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
    info:    "bg-primary/10 text-primary border-primary/20",
    neutral: "bg-muted text-muted-foreground border-border",
  }[variant];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", cls)}>
      {children}
    </span>
  );
}

function ProgressBar({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = Math.min(100, Math.round((value / Math.max(max, 1)) * 100));
  return (
    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
      <div
        className={cn("h-full rounded-full transition-all duration-500", className || "bg-primary")}
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

// ── PIECE 1: Streak & Freeze ──────────────────────────────────────────────────
function StreakTab() {
  const [streak, setStreak] = React.useState<StreakInfoResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [freezeDate, setFreezeDate] = React.useState(today());
  const [msg, setMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);
  const [acting, setActing] = React.useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try { setStreak(await getStreakInfo()); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Failed to load streak."); }
    finally { setLoading(false); }
  }

  React.useEffect(() => { load(); }, []);

  async function handleFreeze() {
    setActing(true); setMsg(null);
    try {
      const r = await activateFreeze(freezeDate);
      setMsg({ type: "success", text: r.message });
      await load();
    } catch (e) {
      setMsg({ type: "error", text: e instanceof ApiError ? e.message : "Failed." });
    } finally { setActing(false); }
  }

  async function handlePractice() {
    setActing(true); setMsg(null);
    try {
      const r = await logPracticeSession({ date: today(), duration_seconds: 600, fluency_score: 80, vocabulary_score: 75 });
      setMsg({ type: "success", text: r.message });
      await load();
    } catch (e) {
      setMsg({ type: "error", text: e instanceof ApiError ? e.message : "Failed." });
    } finally { setActing(false); }
  }

  async function handleMakeup() {
    setActing(true); setMsg(null);
    try {
      const r = await performMakeupDrill();
      setMsg({ type: "success", text: r.message });
      await load();
    } catch (e) {
      setMsg({ type: "error", text: e instanceof ApiError ? e.message : "Failed to perform makeup drill." });
    } finally { setActing(false); }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;
  if (error) return <ErrorAlert message={error} />;
  if (!streak) return null;

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={Flame} title="Streak & Freeze Tokens" subtitle="Keep your practice streak alive with freeze tokens earned at milestones." />

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Current Streak", value: `${streak.current_streak}d`, icon: Flame, color: "text-orange-500" },
          { label: "Highest Streak", value: `${streak.highest_streak}d`, icon: Star, color: "text-amber-500" },
          { label: "Freeze Tokens", value: `${streak.freeze_tokens}`, icon: ShieldCheck, color: "text-primary" },
          { label: "Active Freezes", value: `${streak.active_freezes.length}`, icon: Calendar, color: "text-accent" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="flex flex-col items-center gap-2 py-5 text-center">
            <Icon className={cn("h-6 w-6", color)} />
            <span className="text-2xl font-bold text-foreground font-serif">{value}</span>
            <span className="text-xs text-muted-foreground">{label}</span>
          </Card>
        ))}
      </div>

      {/* Streak fire visualization */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-foreground">Practice Streak</span>
          {streak.last_practice_date && (
            <StatusBadge variant="info">Last practiced: {streak.last_practice_date}</StatusBadge>
          )}
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {Array.from({ length: Math.max(7, streak.current_streak + 1) }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-8 w-8 rounded-lg flex items-center justify-center text-xs font-medium transition-all",
                i < streak.current_streak
                  ? "bg-orange-500/20 border border-orange-500/40 text-orange-500"
                  : "bg-muted border border-border text-muted-foreground"
              )}
            >
              {i < streak.current_streak ? "🔥" : i + 1}
            </div>
          ))}
        </div>
        {streak.active_freezes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {streak.active_freezes.map(d => (
              <StatusBadge key={d} variant="info">🛡 Frozen: {d}</StatusBadge>
            ))}
          </div>
        )}
      </Card>

      {/* Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" /> Activate Freeze
          </h3>
          <p className="text-xs text-muted-foreground mb-4">
            Protect your streak on a specific date. Costs 1 freeze token.
            {streak.freeze_tokens === 0 && <span className="text-amber-600 dark:text-amber-400"> (No tokens available — earn more by reaching 7-day milestones.)</span>}
          </p>
          <div className="flex gap-2">
            <input
              type="date"
              value={freezeDate}
              onChange={e => setFreezeDate(e.target.value)}
              className="h-9 flex-1 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            <Button size="sm" onClick={handleFreeze} loading={acting} disabled={streak.freeze_tokens === 0}>
              Freeze
            </Button>
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
            <Zap className="h-4 w-4 text-amber-500" /> Makeup Drill
          </h3>
          <p className="text-xs text-muted-foreground mb-4">
            One-time streak restoration per calendar month. Only available when you have zero freeze tokens.
            {streak.last_makeup_drill_month && <span> Last used: <strong>{streak.last_makeup_drill_month}</strong>.</span>}
          </p>
          <Button size="sm" variant="outline" onClick={handleMakeup} loading={acting}>
            Perform Makeup Drill
          </Button>
        </Card>
      </div>

      <Card>
        <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-success" /> Log Today&apos;s Practice
        </h3>
        <p className="text-xs text-muted-foreground mb-4">
          Manually log a practice session for today to maintain your streak.
        </p>
        <Button size="sm" onClick={handlePractice} loading={acting}>
          Log Practice for Today
        </Button>
      </Card>

      {msg && (msg.type === "success" ? <SuccessAlert message={msg.text} /> : <ErrorAlert message={msg.text} />)}
    </div>
  );
}

// ── PIECE 2: Confidence Score ─────────────────────────────────────────────────
function ConfidenceTab() {
  const [bd, setBd] = React.useState<ConfidenceBreakdownResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [disputeId, setDisputeId] = React.useState("");
  const [disputeReason, setDisputeReason] = React.useState("");
  const [disputing, setDisputing] = React.useState(false);
  const [disputeMsg, setDisputeMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);

  React.useEffect(() => {
    (async () => {
      try { setBd(await getConfidenceBreakdown()); }
      catch (e) { setError(e instanceof ApiError ? e.message : "Failed to load."); }
      finally { setLoading(false); }
    })();
  }, []);

  async function handleDispute() {
    if (!disputeId.trim() || !disputeReason.trim()) return;
    setDisputing(true); setDisputeMsg(null);
    try {
      const r = await disputeSessionScore(disputeId.trim(), disputeReason.trim());
      setDisputeMsg({ type: "success", text: r.message });
      setDisputeId(""); setDisputeReason("");
    } catch (e) {
      setDisputeMsg({ type: "error", text: e instanceof ApiError ? e.message : "Failed." });
    } finally { setDisputing(false); }
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;
  if (error) return <ErrorAlert message={error} />;
  if (!bd) return null;

  const COMPONENT_COLORS: Record<string, string> = {
    fluency: "bg-blue-500",
    vocabulary: "bg-violet-500",
    pronunciation: "bg-emerald-500",
  };

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={BarChart3} title="Confidence Score Breakdown" subtitle="Understand exactly how your confidence score is calculated." />

      {/* Score card */}
      <Card className="flex flex-col sm:flex-row items-center gap-6">
        <div className="flex flex-col items-center gap-1">
          <span className="text-5xl font-bold font-serif text-primary">{bd.current_score.toFixed(1)}</span>
          <span className="text-xs text-muted-foreground uppercase tracking-wide">Confidence Score</span>
          <StatusBadge variant={bd.insufficient_data ? "warn" : "success"}>
            {bd.session_count} session{bd.session_count !== 1 ? "s" : ""} recorded
          </StatusBadge>
        </div>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground leading-relaxed">{bd.explanation}</p>
        </div>
      </Card>

      {bd.insufficient_data && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm">
          <Info className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <span className="text-amber-700 dark:text-amber-400">Insufficient data for a full breakdown — log at least 2 practice sessions to unlock detailed analysis.</span>
        </div>
      )}

      {/* Sub-metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Object.entries(bd.components).map(([key, comp]) => (
          <Card key={key} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-foreground">{key}</span>
              <StatusBadge variant="neutral">{comp.weight}% weight</StatusBadge>
            </div>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-bold font-serif text-foreground">
                {comp.recent_average !== null ? comp.recent_average.toFixed(1) : "—"}
              </span>
              <span className="text-xs text-muted-foreground mb-0.5">/ 100</span>
            </div>
            <ProgressBar
              value={comp.recent_average ?? 0}
              max={100}
              className={COMPONENT_COLORS[key] || "bg-primary"}
            />
            <p className="text-xs text-muted-foreground">{comp.description}</p>
          </Card>
        ))}
      </div>

      {/* Dispute panel */}
      <Card>
        <h3 className="text-sm font-semibold text-foreground mb-1 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-amber-500" /> Flag a Score Dispute
        </h3>
        <p className="text-xs text-muted-foreground mb-4">
          Believe a session score was inaccurate? Flag it for review. This does not immediately change your score. Max 3 disputes per day.
        </p>
        <div className="flex flex-col gap-3">
          <input
            type="text"
            placeholder="Session ID (e.g. sess_abc123)"
            value={disputeId}
            onChange={e => setDisputeId(e.target.value)}
            className="h-9 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <textarea
            rows={3}
            placeholder="Describe why you believe this score is inaccurate..."
            value={disputeReason}
            onChange={e => setDisputeReason(e.target.value)}
            className="rounded-lg border border-input bg-surface px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
          />
          <div className="flex justify-end">
            <Button size="sm" onClick={handleDispute} loading={disputing} disabled={!disputeId.trim() || !disputeReason.trim()}>
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Submit Dispute
            </Button>
          </div>
        </div>
        {disputeMsg && (disputeMsg.type === "success" ? <SuccessAlert message={disputeMsg.text} /> : <ErrorAlert message={disputeMsg.text} />)}
      </Card>
    </div>
  );
}

// ── PIECE 3: Badges ───────────────────────────────────────────────────────────
function BadgesTab() {
  const [catalog, setCatalog] = React.useState<BadgeCatalogResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<"all" | "earned" | "locked">("all");

  React.useEffect(() => {
    (async () => {
      try { setCatalog(await getBadgeCatalog()); }
      catch (e) { setError(e instanceof ApiError ? e.message : "Failed to load badges."); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;
  if (error) return <ErrorAlert message={error} />;
  if (!catalog) return null;

  const CATEGORY_COLORS: Record<string, string> = {
    streak: "text-orange-500",
    practice_time: "text-blue-500",
    vocabulary: "text-violet-500",
    special: "text-amber-500",
  };

  const filtered = catalog.badges.filter(b =>
    filter === "all" ? true : filter === "earned" ? b.earned : !b.earned
  );

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={Trophy} title="Badge Catalog" subtitle="Earn badges by reaching milestones. Every badge is unique — no duplicates." />

      {/* Summary */}
      <Card className="flex items-center gap-6">
        <div className="flex flex-col items-center gap-1">
          <span className="text-4xl font-bold font-serif text-amber-500">{catalog.earned_count}</span>
          <span className="text-xs text-muted-foreground">Earned</span>
        </div>
        <div className="h-10 w-px bg-border" />
        <div className="flex flex-col items-center gap-1">
          <span className="text-4xl font-bold font-serif text-muted-foreground">{catalog.total_badges - catalog.earned_count}</span>
          <span className="text-xs text-muted-foreground">Locked</span>
        </div>
        <div className="flex-1 ml-4">
          <ProgressBar value={catalog.earned_count} max={catalog.total_badges} className="bg-amber-500" />
          <span className="text-xs text-muted-foreground mt-1 block">{catalog.earned_count}/{catalog.total_badges} badges earned</span>
        </div>
      </Card>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(["all", "earned", "locked"] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize",
              filter === f
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Badge grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {filtered.map(badge => {
          const IconComp = BADGE_ICONS[badge.icon] || (({ className }) => <Award className={className} />);
          return (
            <Card
              key={badge.badge_id}
              className={cn(
                "flex items-start gap-4 transition-all",
                badge.earned ? "border-amber-400/40 bg-amber-500/5" : "opacity-70"
              )}
            >
              <div className={cn(
                "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
                badge.earned ? "bg-amber-500/20 text-amber-500" : "bg-muted text-muted-foreground"
              )}>
                <IconComp className="h-6 w-6" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-foreground">{badge.title}</span>
                  {badge.earned
                    ? <StatusBadge variant="success"><CheckCircle2 className="h-3 w-3" /> Earned</StatusBadge>
                    : <StatusBadge variant="neutral"><Lock className="h-3 w-3" /> Locked</StatusBadge>
                  }
                </div>
                <span className={cn("text-xs font-medium", CATEGORY_COLORS[badge.category] || "text-muted-foreground")}>
                  {badge.category.replace("_", " ")}
                </span>
                <p className="text-xs text-muted-foreground mt-1">{badge.description}</p>
                {!badge.earned && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>{badge.requirement_text}</span>
                      <span>{badge.progress_label}</span>
                    </div>
                    <ProgressBar value={badge.current_progress} max={badge.target_requirement} />
                  </div>
                )}
                {badge.earned && badge.earned_at && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                    Earned {new Date(badge.earned_at).toLocaleDateString()}
                  </p>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── PIECE 4: Progress Report ──────────────────────────────────────────────────
function ReportTab() {
  const [startDate, setStartDate] = React.useState(nDaysAgo(30));
  const [endDate, setEndDate] = React.useState(today());
  const [report, setReport] = React.useState<ProgressReportResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleGenerate() {
    setLoading(true); setError(null); setReport(null);
    try { setReport(await exportProgressReport(startDate, endDate)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Failed to generate report."); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={FileDown} title="Progress Report Export" subtitle="Generate a structured summary for a date range — ready to share or print." />

      <Card>
        <h3 className="text-sm font-semibold text-foreground mb-4">Select Date Range</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-muted-foreground">From</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              className="h-9 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-muted-foreground">To</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              className="h-9 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>
          <div className="flex items-end">
            <Button size="sm" onClick={handleGenerate} loading={loading}>
              Generate Report
            </Button>
          </div>
        </div>
      </Card>

      {error && <ErrorAlert message={error} />}

      {report && (
        <div className="flex flex-col gap-4 animate-fade-up">
          {report.note && (
            <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm">
              <Info className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
              <span className="text-amber-700 dark:text-amber-400">{report.note}</span>
            </div>
          )}

          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Sessions", value: String(report.session_count) },
              { label: "Practice Time", value: fmtSeconds(report.total_practice_time_seconds) },
              { label: "Badges Earned", value: String(report.badges_earned.length) },
              { label: "Data Type", value: report.is_rollup ? "Monthly Rollups" : "Per-Session" },
            ].map(({ label, value }) => (
              <Card key={label} className="flex flex-col items-center gap-1 py-4 text-center">
                <span className="text-2xl font-bold font-serif text-primary">{value}</span>
                <span className="text-xs text-muted-foreground">{label}</span>
              </Card>
            ))}
          </div>

          {/* Monthly rollups */}
          {report.is_rollup && report.monthly_rollups.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold text-foreground mb-4">Monthly Summary</h3>
              <div className="space-y-3">
                {report.monthly_rollups.map(r => (
                  <div key={r.month} className="flex items-center gap-3 p-3 rounded-lg bg-muted/40">
                    <span className="text-xs font-mono font-medium text-muted-foreground w-16">{r.month}</span>
                    <div className="flex-1 grid grid-cols-3 gap-2 text-xs">
                      <div><span className="text-muted-foreground">Sessions: </span><strong>{r.sessions_count}</strong></div>
                      <div><span className="text-muted-foreground">Avg Score: </span><strong>{r.avg_confidence_score.toFixed(1)}</strong></div>
                      <div><span className="text-muted-foreground">Time: </span><strong>{fmtSeconds(r.total_practice_seconds)}</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Confidence trend */}
          {report.confidence_score_trend.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold text-foreground mb-4">Confidence Score Trend</h3>
              <div className="space-y-2">
                {report.confidence_score_trend.map(d => (
                  <div key={d.date} className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground w-24 shrink-0">{d.date}</span>
                    <ProgressBar value={d.score} max={100} className="bg-primary flex-1" />
                    <span className="text-xs font-medium text-foreground w-10 text-right">{d.score.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Badges */}
          {report.badges_earned.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold text-foreground mb-3">Badges Earned in This Period</h3>
              <div className="flex flex-wrap gap-2">
                {report.badges_earned.map(b => (
                  <StatusBadge key={b} variant="success"><Trophy className="h-3 w-3" />{b.replace(/_/g, " ")}</StatusBadge>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

// ── PIECE 5: Streak Appeal ────────────────────────────────────────────────────
function AppealTab() {
  const [date, setDate] = React.useState(nDaysAgo(3));
  const [reason, setReason] = React.useState("");
  const [hasEvidence, setHasEvidence] = React.useState(false);
  const [evidenceNote, setEvidenceNote] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<{ type: "success" | "warn" | "error"; text: string } | null>(null);

  async function handleSubmit() {
    setSubmitting(true); setResult(null);
    try {
      const r = await submitStreakAppeal({ date_of_break: date, reason, has_evidence: hasEvidence, evidence_note: evidenceNote || undefined });
      const type = r.status === "approved" ? "success" : r.status === "flagged_for_manual_review" ? "warn" : "error";
      setResult({ type, text: r.message });
    } catch (e) {
      setResult({ type: "error", text: e instanceof ApiError ? e.message : "Failed to submit appeal." });
    } finally { setSubmitting(false); }
  }

  const STATUS_ICONS = {
    success: <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />,
    warn:    <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />,
    error:   <AlertTriangle className="h-4 w-4 text-danger shrink-0 mt-0.5" />,
  };
  const STATUS_STYLES = {
    success: "border-success/30 bg-success/10 text-success",
    warn:    "border-amber-400/30 bg-amber-400/10 text-amber-700 dark:text-amber-400",
    error:   "border-danger/30 bg-danger/10 text-danger",
  };

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={ShieldCheck} title="Streak Restore Appeal" subtitle="Submit a manual appeal if your streak broke due to a confirmed platform bug." />

      <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm">
        <Info className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
        <div className="text-amber-700 dark:text-amber-400 text-xs">
          <strong>Note:</strong> This is separate from freeze tokens (automatic). Appeals are for platform bugs only and require supporting evidence to be approved. Appeals older than 14 days are rejected. Accounts submitting 5+ appeals in 30 days are flagged for manual review.
        </div>
      </div>

      <Card>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground">Date of streak break</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)}
              className="h-9 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20" />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground">Reason for appeal</label>
            <textarea rows={3} value={reason} onChange={e => setReason(e.target.value)}
              placeholder="Describe the platform bug or technical issue that caused your streak to break..."
              className="rounded-lg border border-input bg-surface px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none" />
          </div>

          <div className="flex items-center gap-3">
            <input type="checkbox" id="has-evidence" checked={hasEvidence} onChange={e => setHasEvidence(e.target.checked)}
              className="h-4 w-4 rounded border-input accent-primary" />
            <label htmlFor="has-evidence" className="text-xs text-foreground cursor-pointer">
              I have supporting evidence (screenshot, error message, etc.)
            </label>
          </div>

          {hasEvidence && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-foreground">Evidence note</label>
              <textarea rows={2} value={evidenceNote} onChange={e => setEvidenceNote(e.target.value)}
                placeholder="Describe your evidence (e.g. 'Screenshot shows 500 error at 11:54pm on the date above')..."
                className="rounded-lg border border-input bg-surface px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none" />
            </div>
          )}

          <div className="flex justify-end">
            <Button size="sm" onClick={handleSubmit} loading={submitting} disabled={!reason.trim()}>
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Submit Appeal
            </Button>
          </div>
        </div>
      </Card>

      {result && (
        <div className={cn("flex items-start gap-3 rounded-xl border p-4 text-sm", STATUS_STYLES[result.type])}>
          {STATUS_ICONS[result.type]}
          <span>{result.text}</span>
        </div>
      )}
    </div>
  );
}

// ── PIECE 6: History Chart ────────────────────────────────────────────────────
function HistoryTab() {
  const [range, setRange] = React.useState<"week" | "month" | "year" | "all_time">("month");
  const [data, setData] = React.useState<HistoricalDataResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState<string | null>(null);
  const [expandedSessions, setExpandedSessions] = React.useState<Record<string, typeof data extends null ? never[] : NonNullable<typeof data>["raw_sessions"]>>({});

  const RANGES = [
    { id: "week", label: "7 Days" },
    { id: "month", label: "30 Days" },
    { id: "year", label: "Year" },
    { id: "all_time", label: "All Time" },
  ] as const;

  async function load(r: typeof range) {
    setLoading(true); setError(null); setData(null); setExpanded(null);
    try { setData(await getHistoricalData(r)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Failed to load history."); }
    finally { setLoading(false); }
  }

  function changeRange(r: typeof range) {
    setRange(r);
    load(r);
  }

  async function handleExpand(period_label: string) {
    if (expanded === period_label) { setExpanded(null); return; }
    setExpanded(period_label);
    if (expandedSessions[period_label]) return;
    try {
      const r = await expandPeriodData(period_label);
      setExpandedSessions(prev => ({ ...prev, [period_label]: r.sessions as any }));
    } catch { /* ignore */ }
  }

  React.useEffect(() => { load("month"); }, []);

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader icon={TrendingUp} title="Practice History" subtitle="Track your progress over time. Long ranges auto-aggregate into rollups." />

      {/* Range selector */}
      <div className="flex gap-2">
        {RANGES.map(r => (
          <button key={r.id} onClick={() => changeRange(r.id)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              range === r.id ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}>
            {r.label}
          </button>
        ))}
      </div>

      {loading && <div className="flex justify-center py-12"><Spinner /></div>}
      {error && <ErrorAlert message={error} />}

      {data && (
        <div className="flex flex-col gap-4 animate-fade-up">
          <div className="flex items-center gap-2">
            <StatusBadge variant="info">
              {data.aggregation_level === "raw" ? "Per-session data" : `${data.aggregation_level === "weekly" ? "Weekly" : "Monthly"} rollups`}
            </StatusBadge>
            {data.raw_sessions !== null && <StatusBadge variant="neutral">{data.raw_sessions.length} sessions</StatusBadge>}
          </div>

          {/* Raw sessions */}
          {data.aggregation_level === "raw" && data.raw_sessions && (
            <div className="flex flex-col gap-2">
              {data.raw_sessions.length === 0 && (
                <Card className="flex flex-col items-center gap-3 py-10 text-center">
                  <BarChart3 className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No practice sessions in this period.</p>
                </Card>
              )}
              {data.raw_sessions.map(s => (
                <Card key={s.session_id} className={cn("flex items-center gap-4", s.is_outlier && "border-amber-400/40 bg-amber-500/5")}>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-muted-foreground">{s.timestamp.slice(0, 10)}</span>
                      {s.is_outlier && <StatusBadge variant="warn"><Star className="h-3 w-3" /> Outlier</StatusBadge>}
                    </div>
                    <span className="text-xs text-muted-foreground font-mono">{s.session_id}</span>
                  </div>
                  <div className="flex gap-4 ml-auto shrink-0">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="text-sm font-semibold text-foreground">{s.fluency_score.toFixed(0)}</span>
                      <span className="text-xs text-muted-foreground">Fluency</span>
                    </div>
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="text-sm font-semibold text-foreground">{s.vocabulary_score.toFixed(0)}</span>
                      <span className="text-xs text-muted-foreground">Vocab</span>
                    </div>
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="text-sm font-semibold text-foreground">{fmtSeconds(s.duration_seconds)}</span>
                      <span className="text-xs text-muted-foreground">Time</span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* Aggregated points */}
          {data.aggregated_points && (
            <div className="flex flex-col gap-2">
              {data.aggregated_points.length === 0 && (
                <Card className="flex flex-col items-center gap-3 py-10 text-center">
                  <BarChart3 className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No data available for this time range.</p>
                </Card>
              )}
              {data.aggregated_points.map((pt: AggregatedDataPoint) => (
                <div key={pt.period_label}>
                  <Card
                    className={cn(
                      "cursor-pointer transition-all",
                      pt.is_gap ? "opacity-40 border-dashed" : "",
                      expanded === pt.period_label ? "border-primary/40" : ""
                    )}
                    onClick={() => !pt.is_gap && handleExpand(pt.period_label)}
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex flex-col gap-0.5 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-semibold text-foreground">{pt.period_label}</span>
                          {pt.is_gap && <StatusBadge variant="neutral">No activity</StatusBadge>}
                          {pt.best_outlier_session && <StatusBadge variant="warn"><Star className="h-3 w-3" /> Best session preserved</StatusBadge>}
                        </div>
                        <span className="text-xs text-muted-foreground">{pt.start_date} → {pt.end_date}</span>
                      </div>
                      {!pt.is_gap && (
                        <div className="flex gap-4 ml-auto shrink-0 items-center">
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="text-sm font-semibold text-foreground">{pt.session_count}</span>
                            <span className="text-xs text-muted-foreground">Sessions</span>
                          </div>
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="text-sm font-semibold text-foreground">{pt.avg_confidence.toFixed(0)}</span>
                            <span className="text-xs text-muted-foreground">Avg Score</span>
                          </div>
                          <div className="flex flex-col items-center gap-0.5">
                            <span className="text-sm font-semibold text-foreground">{fmtSeconds(pt.total_practice_seconds)}</span>
                            <span className="text-xs text-muted-foreground">Time</span>
                          </div>
                          {expanded === pt.period_label
                            ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            : <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          }
                        </div>
                      )}
                    </div>
                  </Card>

                  {/* Expanded sessions */}
                  {expanded === pt.period_label && expandedSessions[pt.period_label] && (
                    <div className="mt-2 ml-4 flex flex-col gap-1.5 animate-fade-up">
                      {(expandedSessions[pt.period_label] as any[]).map((s: any) => (
                        <div key={s.session_id} className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3">
                          <span className="text-xs font-mono text-muted-foreground">{s.timestamp.slice(0, 10)}</span>
                          <span className="text-xs text-muted-foreground font-mono flex-1">{s.session_id}</span>
                          <span className="text-xs font-medium text-foreground">Score: {s.fluency_score.toFixed(0)}</span>
                          <span className="text-xs text-muted-foreground">{fmtSeconds(s.duration_seconds)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ProgressPage() {
  const [activeTab, setActiveTab] = React.useState<TabId>("streak");

  const TAB_CONTENT: Record<TabId, React.ReactNode> = {
    streak:     <StreakTab />,
    confidence: <ConfidenceTab />,
    badges:     <BadgesTab />,
    report:     <ReportTab />,
    appeal:     <AppealTab />,
    history:    <HistoryTab />,
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Page header */}
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Progress Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Track streaks, confidence scores, badges, and your full practice history in one place.
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
