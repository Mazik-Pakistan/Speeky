"use client";

import * as React from "react";
import {
  Settings,
  Plus,
  Trash2,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  GripVertical,
  AlertTriangle,
  CheckCircle2,
  Info,
  Save,
  Globe,
  ShieldAlert,
  UserCheck,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import {
  adminSavePath,
  adminPublishPath,
  adminDeleteModule,
  adminAcquireLock,
  manualUnlockOverride,
  type AdminLockResponse,
} from "@/lib/learningPath";

// ── Utility helpers ───────────────────────────────────────────────────────────
function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

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

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  { id: "builder",  label: "Path Builder",    icon: Settings },
  { id: "lock",     label: "Locking",         icon: Lock },
  { id: "override", label: "User Overrides",  icon: UserCheck },
] as const;
type TabId = (typeof TABS)[number]["id"];

// ── Module editor type ────────────────────────────────────────────────────────
interface DraftModule {
  module_id: string;
  title: string;
  sequence_order: number;
  prerequisites: string;
  passing_score: number;
  content: string;
  expanded: boolean;
}

function genId() {
  return `mod_${Math.random().toString(36).slice(2, 9)}`;
}

function defaultModule(order: number): DraftModule {
  return {
    module_id: genId(),
    title: "",
    sequence_order: order,
    prerequisites: "",
    passing_score: 70,
    content: "",
    expanded: true,
  };
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 5 — Admin Authoring & Publishing (Path Builder tab)
// ═══════════════════════════════════════════════════════════════════════════════
function PathBuilderTab({ adminId }: { adminId: string }) {
  // Path-level fields
  const [pathId, setPathId] = React.useState(`path_${Date.now()}`);
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [level, setLevel] = React.useState("Beginner");
  const [strictSequential, setStrictSequential] = React.useState(true);
  const [isEnterprise, setIsEnterprise] = React.useState(false);

  // Module list
  const [modules, setModules] = React.useState<DraftModule[]>([defaultModule(1)]);

  // Action state
  const [saving, setSaving] = React.useState(false);
  const [publishing, setPublishing] = React.useState(false);
  const [savedPathId, setSavedPathId] = React.useState<string | null>(null);
  const [publishModalOpen, setPublishModalOpen] = React.useState(false);
  const [deleteModalModule, setDeleteModalModule] = React.useState<DraftModule | null>(null);
  const [msg, setMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);

  function addModule() {
    setModules((prev) => [
      ...prev,
      defaultModule(prev.length + 1),
    ]);
  }

  function removeModuleDraft(id: string) {
    setModules((prev) => {
      const remaining = prev.filter((m) => m.module_id !== id);
      return remaining.map((m, i) => ({ ...m, sequence_order: i + 1 }));
    });
  }

  function updateModule(id: string, field: keyof DraftModule, value: unknown) {
    setModules((prev) =>
      prev.map((m) => (m.module_id === id ? { ...m, [field]: value } : m))
    );
  }

  function toggleExpand(id: string) {
    setModules((prev) =>
      prev.map((m) => (m.module_id === id ? { ...m, expanded: !m.expanded } : m))
    );
  }

  // Move module up/down
  function moveModule(id: string, dir: "up" | "down") {
    setModules((prev) => {
      const idx = prev.findIndex((m) => m.module_id === id);
      if (idx < 0) return prev;
      const next = [...prev];
      const swapIdx = dir === "up" ? idx - 1 : idx + 1;
      if (swapIdx < 0 || swapIdx >= next.length) return prev;
      [next[idx], next[swapIdx]] = [next[swapIdx], next[idx]];
      return next.map((m, i) => ({ ...m, sequence_order: i + 1 }));
    });
  }

  // Check for circular dependency: if mod A lists mod B as prerequisite and
  // mod B lists mod A, that's invalid.
  function hasCircularDep(): boolean {
    const prereqMap: Record<string, string[]> = {};
    for (const m of modules) {
      prereqMap[m.module_id] = m.prerequisites
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    for (const [id, prereqs] of Object.entries(prereqMap)) {
      for (const prereq of prereqs) {
        if (prereqMap[prereq]?.includes(id)) return true;
      }
    }
    return false;
  }

  async function handleSave() {
    if (!title.trim()) {
      setMsg({ type: "error", text: "Path title is required." });
      return;
    }
    if (modules.some((m) => !m.title.trim())) {
      setMsg({ type: "error", text: "All modules must have a title." });
      return;
    }
    if (hasCircularDep()) {
      setMsg({ type: "error", text: "Circular dependency detected in module prerequisites. Check your prerequisite lists." });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const r = await adminSavePath({
        path_id: pathId,
        title,
        description,
        learning_level: level,
        is_published: false,
        strict_sequential: strictSequential,
        is_enterprise_assigned: isEnterprise,
        modules: modules.map((m) => ({
          module_id: m.module_id,
          title: m.title,
          sequence_order: m.sequence_order,
          prerequisites: m.prerequisites
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          passing_score: m.passing_score,
          content: m.content,
          content_version: 1,
        })),
      });
      setSavedPathId(r.path_id);
      setPathId(r.path_id);
      setMsg({ type: "success", text: r.message });
    } catch (e) {
      setMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to save path.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!savedPathId) {
      setMsg({ type: "error", text: "Save the path first before publishing." });
      return;
    }
    if (modules.length === 0) {
      setMsg({ type: "error", text: "Cannot publish a path with no modules." });
      return;
    }
    setPublishing(true);
    setMsg(null);
    try {
      const r = await adminPublishPath(savedPathId);
      setMsg({ type: "success", text: r.message });
      setPublishModalOpen(false);
    } catch (e) {
      setMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to publish path.",
      });
    } finally {
      setPublishing(false);
    }
  }

  async function handleDeleteModule(mod: DraftModule) {
    // Try deleting from backend (non-fatal if it doesn't exist yet)
    try {
      await adminDeleteModule(mod.module_id);
    } catch {
      // Module may be draft-only (not yet saved) — silently continue
    }
    removeModuleDraft(mod.module_id);
    setDeleteModalModule(null);
    setMsg({ type: "success", text: `Module "${mod.title || mod.module_id}" removed.` });
  }

  const circularDepError = hasCircularDep();

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Settings}
        title="Path Builder"
        subtitle="Create and sequence a learning path. Add modules, set prerequisites, and publish when ready."
      />

      {/* Path-level settings */}
      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-4">Path Settings</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <label className="text-xs text-muted-foreground mb-1 block">Path Title *</label>
            <input
              type="text"
              placeholder="e.g. Business Communication Mastery"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs text-muted-foreground mb-1 block">Description</label>
            <textarea
              rows={2}
              placeholder="Describe what learners will achieve..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Learning Level</label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {["Beginner", "Intermediate", "Advanced", "Expert"].map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Path ID (auto-generated)</label>
            <input
              type="text"
              value={pathId}
              onChange={(e) => setPathId(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-muted px-3 text-xs text-muted-foreground focus:outline-none"
            />
          </div>
        </div>

        {/* Toggles */}
        <div className="mt-4 flex flex-col gap-3">
          {/* Strict Sequential toggle */}
          <div className="flex items-center justify-between rounded-xl border border-border bg-surface p-3">
            <div>
              <p className="text-sm font-medium text-foreground">Strict Sequential Mode</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Learners must complete each module in order. Disabling allows free exploration of any module at any time.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={strictSequential}
              onClick={() => setStrictSequential((v) => !v)}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30",
                strictSequential ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none block h-5 w-5 rounded-full bg-white shadow transition-transform",
                  strictSequential ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>

          {/* Enterprise toggle */}
          <div className="flex items-center justify-between rounded-xl border border-border bg-surface p-3">
            <div>
              <p className="text-sm font-medium text-foreground">Enterprise Assignment</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Mark this path as required for enterprise users. They cannot reset or abandon it without admin approval.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={isEnterprise}
              onClick={() => setIsEnterprise((v) => !v)}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30",
                isEnterprise ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none block h-5 w-5 rounded-full bg-white shadow transition-transform",
                  isEnterprise ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>
        </div>
      </Card>

      {/* Module list */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm text-foreground">
            Modules ({modules.length})
          </h3>
          <Button size="sm" variant="outline" onClick={addModule}>
            <Plus className="h-3.5 w-3.5" />
            Add Module
          </Button>
        </div>

        {circularDepError && (
          <div className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 p-3 text-xs">
            <AlertTriangle className="h-3.5 w-3.5 text-danger shrink-0 mt-0.5" />
            <span className="text-danger">
              <strong>Circular dependency detected!</strong> Module A requires Module B and Module B requires Module A. This path cannot be saved until resolved.
            </span>
          </div>
        )}

        {modules.map((mod, idx) => (
          <Card key={mod.module_id} className="p-4">
            {/* Module header */}
            <div className="flex items-center gap-3 mb-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary text-xs font-bold">
                {mod.sequence_order}
              </span>
              <div className="flex-1 min-w-0">
                <input
                  type="text"
                  placeholder={`Module ${mod.sequence_order} title`}
                  value={mod.title}
                  onChange={(e) => updateModule(mod.module_id, "title", e.target.value)}
                  className="h-8 w-full rounded-lg border border-input bg-surface px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => moveModule(mod.module_id, "up")}
                  disabled={idx === 0}
                  title="Move up"
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-surface hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronUp className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => moveModule(mod.module_id, "down")}
                  disabled={idx === modules.length - 1}
                  title="Move down"
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-surface hover:text-foreground disabled:opacity-30 transition-colors"
                >
                  <ChevronDown className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => toggleExpand(mod.module_id)}
                  title={mod.expanded ? "Collapse" : "Expand"}
                  className="rounded-lg p-1.5 text-muted-foreground hover:bg-surface hover:text-foreground transition-colors"
                >
                  <GripVertical className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setDeleteModalModule(mod)}
                  title="Remove module"
                  className="rounded-lg p-1.5 text-danger hover:bg-danger/10 transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Expanded module fields */}
            {mod.expanded && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">
                    Prerequisites (comma-separated module IDs)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. mod_abc123, mod_def456"
                    value={mod.prerequisites}
                    onChange={(e) => updateModule(mod.module_id, "prerequisites", e.target.value)}
                    className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">
                    Passing Score (0–100)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={mod.passing_score}
                    onChange={(e) =>
                      updateModule(mod.module_id, "passing_score", Number(e.target.value))
                    }
                    className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs text-muted-foreground mb-1 block">Content</label>
                  <textarea
                    rows={3}
                    placeholder="Module content, learning objectives, or instructions..."
                    value={mod.content}
                    onChange={(e) => updateModule(mod.module_id, "content", e.target.value)}
                    className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
                  />
                </div>
                <div className="sm:col-span-2">
                  <p className="text-xs text-muted-foreground font-mono">
                    Module ID: <span className="text-foreground">{mod.module_id}</span>
                    {" "}— use this ID as a prerequisite in other modules.
                  </p>
                </div>
              </div>
            )}
          </Card>
        ))}

        {modules.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
            <Plus className="h-8 w-8 opacity-30" />
            <p className="text-sm">No modules yet. Add your first module to get started.</p>
          </div>
        )}
      </div>

      {msg && (
        msg.type === "success"
          ? <SuccessAlert message={msg.text} />
          : <ErrorAlert message={msg.text} />
      )}

      {/* Action bar */}
      <div className="flex flex-wrap justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleSave}
          loading={saving}
          disabled={circularDepError}
        >
          <Save className="h-3.5 w-3.5" />
          Save Draft
        </Button>
        <Button
          size="sm"
          onClick={() => {
            if (!savedPathId) {
              setMsg({ type: "error", text: "Save the path first before publishing." });
              return;
            }
            if (modules.length === 0) {
              setMsg({ type: "error", text: "Cannot publish a path with no modules." });
              return;
            }
            setPublishModalOpen(true);
          }}
          disabled={!savedPathId || modules.length === 0}
        >
          <Globe className="h-3.5 w-3.5" />
          Publish Path
        </Button>
      </div>

      {/* Publish confirmation modal */}
      <Modal
        open={publishModalOpen}
        onClose={() => setPublishModalOpen(false)}
        title="Publish Learning Path?"
        description="Once published, learners can be recommended or switch to this path."
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="font-semibold text-sm text-foreground">{title || pathId}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {modules.length} module{modules.length !== 1 ? "s" : ""} · {level} · {strictSequential ? "Sequential" : "Free Explore"}
            </p>
          </div>
          <div className="flex items-start gap-2 rounded-xl border border-info/30 bg-info/10 p-3 text-xs text-info">
            <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            Learners will be able to see and switch to this path immediately after publishing.
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setPublishModalOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={handlePublish} loading={publishing}>
              <Globe className="h-3.5 w-3.5" />
              Confirm Publish
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete module confirmation modal */}
      <Modal
        open={deleteModalModule !== null}
        onClose={() => setDeleteModalModule(null)}
        title="Remove Module?"
        description="This cannot be undone. The module will be deleted from the path."
      >
        {deleteModalModule && (
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-danger/30 bg-danger/10 p-4">
              <p className="text-sm text-danger font-semibold">
                "{deleteModalModule.title || deleteModalModule.module_id}"
              </p>
              <p className="text-xs text-danger/80 mt-1">
                Any modules that list this one as a prerequisite will need to be updated.
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setDeleteModalModule(null)}>
                Cancel
              </Button>
              <Button variant="danger" size="sm" onClick={() => handleDeleteModule(deleteModalModule)}>
                <Trash2 className="h-3.5 w-3.5" />
                Delete Module
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 5 (cont.) — Admin Lock tab
// ═══════════════════════════════════════════════════════════════════════════════
function AdminLockTab({ adminId }: { adminId: string }) {
  const [lockPathId, setLockPathId] = React.useState("");
  const [locking, setLocking] = React.useState(false);
  const [lockResult, setLockResult] = React.useState<AdminLockResponse | null>(null);
  const [lockError, setLockError] = React.useState<string | null>(null);

  async function handleAcquireLock() {
    if (!lockPathId.trim()) {
      setLockError("Path ID is required.");
      return;
    }
    setLocking(true);
    setLockError(null);
    setLockResult(null);
    try {
      const r = await adminAcquireLock({ path_id: lockPathId, admin_id: adminId });
      setLockResult(r);
    } catch (e) {
      setLockError(e instanceof ApiError ? e.message : "Failed to acquire lock.");
    } finally {
      setLocking(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Lock}
        title="Admin Editing Lock"
        subtitle="Acquire a path-level edit lock so two admins cannot overwrite each other's changes simultaneously."
      />

      {/* Lock status display */}
      {lockResult && (
        <div
          className={cn(
            "flex items-start gap-3 rounded-xl border p-4 text-sm",
            lockResult.success
              ? "border-success/30 bg-success/10"
              : "border-amber-400/30 bg-amber-400/10"
          )}
        >
          {lockResult.success ? (
            <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          )}
          <div>
            <p
              className={cn(
                "font-medium",
                lockResult.success ? "text-success" : "text-amber-700 dark:text-amber-400"
              )}
            >
              {lockResult.message}
            </p>
            {lockResult.locked_by && (
              <p className="text-xs text-muted-foreground mt-1">
                Currently locked by: <strong>{lockResult.locked_by}</strong>
              </p>
            )}
          </div>
        </div>
      )}

      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-1 flex items-center gap-2">
          <Lock className="h-4 w-4 text-primary" />
          Acquire Edit Lock
        </h3>
        <p className="text-xs text-muted-foreground mb-4">
          Locks expire automatically after 15 minutes of inactivity. If another admin holds the lock, you'll see who locked it.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Path ID to lock"
            value={lockPathId}
            onChange={(e) => setLockPathId(e.target.value)}
            className="h-9 flex-1 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <Button size="sm" onClick={handleAcquireLock} loading={locking}>
            <Lock className="h-3.5 w-3.5" />
            Acquire Lock
          </Button>
        </div>
        {lockError && <div className="mt-3"><ErrorAlert message={lockError} /></div>}
      </Card>

      {/* Sequential locking explanation */}
      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-3 flex items-center gap-2">
          <Unlock className="h-4 w-4 text-primary" />
          Module Sequential Locking
        </h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Sequential locking is controlled by the <strong>Strict Sequential Mode</strong> toggle on each path (in the Path Builder tab). When enabled, a learner cannot access Module N+1 until they pass Module N at or above the required passing score.
        </p>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            {
              mode: "Sequential",
              icon: Lock,
              desc: "Learners must complete each module in order. Good for structured skill building.",
              variant: "info" as const,
            },
            {
              mode: "Free Explore",
              icon: Unlock,
              desc: "Learners can tackle any module freely. Good for reference paths and advanced users.",
              variant: "success" as const,
            },
          ].map(({ mode, icon: Icon, desc, variant }) => (
            <div
              key={mode}
              className="flex items-start gap-3 rounded-xl border border-border bg-surface p-3"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="h-4 w-4" />
              </span>
              <div>
                <p className="font-semibold text-xs text-foreground">{mode}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PIECE 7 (admin side) — Manual Unlock Override tab
// ═══════════════════════════════════════════════════════════════════════════════
function UserOverrideTab() {
  const [targetUserId, setTargetUserId] = React.useState("");
  const [overridePathId, setOverridePathId] = React.useState("");
  const [unlockAll, setUnlockAll] = React.useState(false);
  const [moduleIds, setModuleIds] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [msg, setMsg] = React.useState<{ type: "success" | "error"; text: string } | null>(null);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    setMsg(null);
    try {
      const r = await manualUnlockOverride({
        target_user_id: targetUserId,
        path_id: overridePathId,
        unlock_all: unlockAll,
        module_ids: unlockAll
          ? undefined
          : moduleIds
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
      });
      setMsg({ type: "success", text: r.message });
      setConfirmOpen(false);
    } catch (e) {
      setMsg({
        type: "error",
        text: e instanceof ApiError ? e.message : "Failed to apply override.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    targetUserId.trim() &&
    overridePathId.trim() &&
    (unlockAll || moduleIds.trim());

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={UserCheck}
        title="Manual Unlock Override"
        subtitle="Grant a specific enterprise user access to locked modules — bypassing their prerequisite chain."
      />

      <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-xs">
        <ShieldAlert className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
        <span className="text-amber-700 dark:text-amber-400">
          <strong>Admin action.</strong> This bypasses the normal sequential unlock flow. Use this only for enterprise users who have an external reason to skip prerequisites (e.g., proven prior experience, cohort policy exceptions).
        </span>
      </div>

      <Card>
        <h3 className="font-semibold text-sm text-foreground mb-4 flex items-center gap-2">
          <UserCheck className="h-4 w-4 text-primary" />
          Override Settings
        </h3>
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Target User ID</label>
            <input
              type="text"
              placeholder="e.g. user_abc123"
              value={targetUserId}
              onChange={(e) => setTargetUserId(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Path ID</label>
            <input
              type="text"
              placeholder="e.g. enterprise-path-001"
              value={overridePathId}
              onChange={(e) => setOverridePathId(e.target.value)}
              className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {/* Unlock all toggle */}
          <div className="flex items-center justify-between rounded-xl border border-border bg-surface p-3">
            <div>
              <p className="text-sm font-medium text-foreground">Unlock All Modules</p>
              <p className="text-xs text-muted-foreground">
                Grants this user access to every module in the path regardless of their score.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={unlockAll}
              onClick={() => setUnlockAll((v) => !v)}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30",
                unlockAll ? "bg-primary" : "bg-muted"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none block h-5 w-5 rounded-full bg-white shadow transition-transform",
                  unlockAll ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>

          {!unlockAll && (
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Specific Module IDs to Unlock (comma-separated)
              </label>
              <input
                type="text"
                placeholder="e.g. mod_abc123, mod_def456"
                value={moduleIds}
                onChange={(e) => setModuleIds(e.target.value)}
                className="h-9 w-full rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          )}
        </div>

        {msg && (
          <div className="mt-4">
            {msg.type === "success" ? (
              <SuccessAlert message={msg.text} />
            ) : (
              <ErrorAlert message={msg.text} />
            )}
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <Button
            variant="danger"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={!canSubmit}
          >
            <Unlock className="h-3.5 w-3.5" />
            Apply Override
          </Button>
        </div>
      </Card>

      {/* Confirmation modal */}
      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm Manual Override"
        description="This grants a user access to locked modules, bypassing prerequisites."
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-border bg-surface p-4 text-xs space-y-1.5">
            <p><span className="text-muted-foreground">User:</span> <strong>{targetUserId}</strong></p>
            <p><span className="text-muted-foreground">Path:</span> <strong>{overridePathId}</strong></p>
            <p>
              <span className="text-muted-foreground">Scope:</span>{" "}
              <strong>{unlockAll ? "All modules" : moduleIds}</strong>
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" size="sm" onClick={handleSubmit} loading={submitting}>
              Confirm Override
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Admin Page — role-gated
// ═══════════════════════════════════════════════════════════════════════════════
export default function LearningPathAdminPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = React.useState<TabId>("builder");

  React.useEffect(() => {
    if (!isLoading && user && user.role !== "ADMIN") {
      router.replace("/dashboard");
    }
  }, [isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user || user.role !== "ADMIN") return null;

  const TAB_CONTENT: Record<TabId, React.ReactNode> = {
    builder:  <PathBuilderTab adminId={user.id} />,
    lock:     <AdminLockTab adminId={user.id} />,
    override: <UserOverrideTab />,
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
              Learning Path Admin
            </h1>
            <StatusBadge variant="danger">Admin Only</StatusBadge>
          </div>
          <p className="text-sm text-muted-foreground">
            Create and publish learning paths, manage sequential locking, and apply enterprise user overrides.
          </p>
        </div>
        <Button variant="outline" size="sm" href="/dashboard/learning-path">
          <Eye className="h-3.5 w-3.5" />
          Learner View
        </Button>
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
