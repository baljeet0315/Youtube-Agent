"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
  CheckCircle, XCircle, Youtube, ExternalLink, ThumbsUp, RotateCcw,
  Sparkles, Clapperboard, Music, Pencil, Save, MessageSquare, Film, ChevronDown, ChevronUp,
} from "lucide-react";
import clsx from "clsx";

const STATUS_STEPS = [
  { key: "pending", label: "Queued" },
  { key: "scripting", label: "Script" },
  { key: "script_ready", label: "Review" },
  { key: "rendering", label: "Render" },
  { key: "preview_ready", label: "Preview" },
  { key: "uploading", label: "Upload" },
  { key: "done", label: "Done" },
];
// Old jobs may still carry "processing"; treat it as rendering for the stepper.
const STATUS_ALIAS: Record<string, string> = { processing: "rendering" };

const MOODS = ["calm", "mysterious", "tense", "uplifting", "energetic", "none"];
const MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "static"];
const WORDS_PER_SECOND = 2.5;
const MAX_WORDS = 150;

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"" | "approve" | "render" | "save" | "regen">("");
  const [error, setError] = useState("");

  // Script review draft (local edits before saving)
  const [draft, setDraft] = useState<any>(null);
  const [dirty, setDirty] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showScenes, setShowScenes] = useState(false);
  const draftForScript = useRef<string>("");

  const api = async (path: string, init: RequestInit = {}) => {
    const token = await getToken({ template: "Youtube-agent-emailID" });
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(init.headers || {}) },
    });
    if (!res.ok) {
      let msg = await res.text();
      try { msg = JSON.parse(msg).detail || msg; } catch {}
      throw new Error(msg);
    }
    return res.json();
  };

  const fetchJob = async () => {
    try {
      const data = await api(`/jobs/${id}`);
      setJob(data);
      // Re-seed the draft whenever a *new* script arrives (not on every poll)
      const sig = JSON.stringify(data.script || {});
      if (data.status === "script_ready" && sig !== draftForScript.current) {
        draftForScript.current = sig;
        setDraft(JSON.parse(sig));
        setDirty(false);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJob();
    const interval = setInterval(() => {
      const s = job?.status;
      if (s && ["done", "failed", "preview_ready", "cancelled", "script_ready"].includes(s)) {
        clearInterval(interval);
        return;
      }
      fetchJob();
    }, 4000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);

  const run = async (kind: typeof busy, fn: () => Promise<any>) => {
    setBusy(kind); setError("");
    try { await fn(); await fetchJob(); }
    catch (e: any) { setError(e.message || "Something went wrong"); }
    finally { setBusy(""); }
  };

  const saveEdits = async () => {
    const edits: any = {
      title: draft.title, description: draft.description, tags: draft.tags,
      music_mood: draft.music_mood,
      scenes: draft.scenes.map((s: any) => ({ id: s.id, visual_prompt: s.visual_prompt, caption: s.caption, motion: s.motion })),
    };
    if (job.script?.input_mode !== "text") edits.narration = draft.narration;
    const r = await api(`/jobs/${id}/script`, { method: "PATCH", body: JSON.stringify(edits) });
    draftForScript.current = JSON.stringify(r.script);
    setDraft(r.script); setDirty(false);
  };

  const handleRender = () => run("render", async () => {
    if (dirty) await saveEdits();
    await api(`/jobs/${id}/render`, { method: "POST" });
  });

  const handleRegenerate = () => run("regen", async () => {
    await api(`/jobs/${id}/regenerate`, { method: "POST", body: JSON.stringify({ feedback }) });
    setFeedback("");
  });

  const handleApprove = () => run("approve", async () => {
    await api(`/jobs/${id}/approve`, { method: "POST", body: JSON.stringify({ platforms: job.platform }) });
  });

  const setField = (k: string, v: any) => { setDraft({ ...draft, [k]: v }); setDirty(true); };
  const setScene = (sid: number, k: string, v: any) => {
    setDraft({ ...draft, scenes: draft.scenes.map((s: any) => (s.id === sid ? { ...s, [k]: v } : s)) });
    setDirty(true);
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-900 border-t-transparent" /></div>;
  if (!job) return <p className="text-gray-500">Job not found.</p>;

  const status = STATUS_ALIAS[job.status] || job.status;
  const video = job.videos?.[0];
  const isFailed = status === "failed";
  const isDone = status === "done";
  const isScriptReady = status === "script_ready" && draft;
  const isPreviewReady = status === "preview_ready";
  const isWorking = ["pending", "scripting", "rendering", "uploading"].includes(status);
  const currentStepIndex = STATUS_STEPS.findIndex((s) => s.key === status);
  const textMode = job.script?.input_mode === "text";
  const words = draft?.narration ? draft.narration.trim().split(/\s+/).length : 0;
  const tooLong = words > MAX_WORDS;

  return (
    <div>
      <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-400 hover:text-gray-600 mb-6 flex items-center gap-1">
        ← Back to create
      </button>

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 truncate">{job.script?.title || job.topic}</h1>
        <p className="text-sm text-gray-400 mt-0.5 truncate">{job.topic}</p>
      </div>

      {/* Progress steps */}
      {!isFailed && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6 mb-5">
          <div className="flex items-center justify-between mb-4 overflow-x-auto">
            {STATUS_STEPS.map((step, i) => (
              <div key={step.key} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div className={clsx(
                    "w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all",
                    i < currentStepIndex || isDone ? "bg-gray-900 text-white"
                      : i === currentStepIndex ? (isWorking ? "bg-brand-500 text-white animate-pulse" : "bg-brand-500 text-white")
                      : "bg-gray-100 text-gray-400"
                  )}>
                    {i < currentStepIndex || isDone ? <CheckCircle size={14} /> : i + 1}
                  </div>
                  <p className="text-[11px] text-gray-400 mt-1.5 text-center w-14">{step.label}</p>
                </div>
                {i < STATUS_STEPS.length - 1 && (
                  <div className={clsx("h-0.5 w-5 mx-0.5 mb-4 transition-all", i < currentStepIndex || isDone ? "bg-gray-900" : "bg-gray-100")} />
                )}
              </div>
            ))}
          </div>

          {isWorking && (
            <div>
              <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                <span>{job.current_step || "Working..."}</span>
                <span>{job.progress}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-gray-900 rounded-full transition-all duration-500" style={{ width: `${job.progress}%` }} />
              </div>
            </div>
          )}

          {isDone && (
            <p className="text-sm text-green-600 font-medium flex items-center gap-2">
              <CheckCircle size={16} /> Video generated and uploaded successfully
            </p>
          )}
        </div>
      )}

      {/* Error state */}
      {(isFailed || error) && (
        <div className="bg-red-50 border border-red-100 rounded-2xl p-5 mb-5">
          <div className="flex items-center gap-2 mb-1">
            <XCircle size={18} className="text-red-500" />
            <p className="font-medium text-red-700">{isFailed ? "Something failed" : "Error"}</p>
          </div>
          <p className="text-sm text-red-500">{error || job.error_message}</p>
          {isFailed && job.script && (
            <div className="flex gap-3 mt-4">
              <button onClick={handleRender} className="text-sm text-red-700 flex items-center gap-1 hover:underline">
                <RotateCcw size={13} /> Retry render with this script
              </button>
              <button onClick={() => router.push("/dashboard")} className="text-sm text-red-500 hover:underline">New job</button>
            </div>
          )}
          {isFailed && !job.script && (
            <button onClick={() => router.push("/dashboard")} className="mt-4 text-sm text-red-600 flex items-center gap-1 hover:underline">
              <RotateCcw size={13} /> Try again with a new job
            </button>
          )}
        </div>
      )}

      {/* ── Script Review ─────────────────────────────────────── */}
      {isScriptReady && (
        <div className="space-y-5 mb-5">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <Pencil size={14} className="text-gray-400" /> Here's your script
              </p>
              <span className="text-xs text-gray-400">
                ~{Math.round(words / WORDS_PER_SECOND)}s
                {job.regeneration_count > 0 && ` · rewrite ${job.regeneration_count}`}
              </span>
            </div>
            <p className="text-xs text-gray-400 -mt-2 mb-4">Read it aloud in your head. Edit anything directly, or tell it what to change below.</p>

            <label className="field-label">Title</label>
            <input
              value={draft.title || ""}
              onChange={(e) => setField("title", e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 mb-4"
            />

            <label className="field-label">
              Narration {textMode && <span className="text-gray-300 font-normal normal-case tracking-normal">(your text — locked)</span>}
            </label>
            <textarea
              rows={8}
              value={draft.narration || ""}
              readOnly={textMode}
              onChange={(e) => setField("narration", e.target.value)}
              className={clsx(
                "w-full border rounded-xl px-4 py-3 text-sm leading-relaxed resize-y outline-none focus:ring-2",
                textMode ? "bg-gray-50 border-gray-100 text-gray-600"
                  : tooLong ? "border-red-300 focus:ring-red-100"
                  : "border-gray-200 focus:border-brand-500 focus:ring-brand-100"
              )}
            />
            {tooLong && <p className="text-xs text-red-500 mt-1">Over {MAX_WORDS} words — too long for a Short.</p>}
          </div>

          {/* Feedback → regenerate (primary way to change things) */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-6">
            <p className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
              <MessageSquare size={14} className="text-gray-400" /> Want it different?
            </p>
            <p className="text-xs text-gray-400 mb-3">Say it like you'd tell a writer. It'll rewrite in about 20 seconds.</p>
            <textarea
              rows={2}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={textMode
                ? '"make the visuals darker", "shorter scenes", "different title"'
                : '"too formal — make it punchier", "open with the statistic", "aim it at parents"'}
              className="w-full border border-gray-200 rounded-xl px-4 py-3 text-base sm:text-sm resize-y outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            <button
              onClick={handleRegenerate}
              disabled={!!busy || feedback.trim().length < 3}
              className="mt-3 flex items-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-800 px-4 py-2.5 rounded-xl text-sm font-medium transition disabled:opacity-40"
            >
              {busy === "regen" ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-gray-800 border-t-transparent" /> : <Sparkles size={15} />}
              Rewrite it
            </button>
            {job.feedback_history?.length > 0 && (
              <div className="mt-4 space-y-1">
                {job.feedback_history.map((h: any, i: number) => (
                  <p key={i} className="text-xs text-gray-400">↳ {h.feedback}</p>
                ))}
              </div>
            )}
          </div>

          {/* Scenes + mood (advanced, collapsed) */}
          <button
            type="button"
            onClick={() => setShowScenes(!showScenes)}
            className="w-full flex items-center justify-between px-5 py-3.5 rounded-2xl border border-dashed border-gray-200 text-sm text-gray-500 hover:text-gray-800 hover:border-gray-300 transition bg-white/60"
          >
            <span className="flex items-center gap-2"><Clapperboard size={15} /> Scenes & visuals ({draft.scenes.length} scenes · {draft.music_mood} music)</span>
            {showScenes ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showScenes && (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
              <div>
                <label className="field-label flex items-center gap-1"><Music size={12} /> Music mood</label>
                <div className="flex flex-wrap gap-1.5">
                  {MOODS.map((m) => (
                    <button key={m} type="button" onClick={() => setField("music_mood", m)}
                      className={clsx("px-2.5 py-1 rounded-full text-xs border transition",
                        draft.music_mood === m ? "bg-brand-50 text-brand-600 border-brand-200 font-medium" : "border-gray-200 text-gray-500 hover:border-gray-300")}>
                      {m}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="field-label">Visual style</label>
                <p className="text-xs text-gray-500 leading-relaxed">{draft.style_guide?.visual_style}</p>
                {draft.style_guide?.subject_consistency && (
                  <p className="text-xs text-gray-400 mt-1">Recurring subject: {draft.style_guide.subject_consistency}</p>
                )}
              </div>
            </div>
            <div className="space-y-4">
              {draft.scenes.map((s: any) => (
                <div key={s.id} className="border border-gray-100 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="text-xs font-medium text-gray-400">Scene {s.id} · ~{s.duration_hint}s</span>
                    <select
                      value={s.motion}
                      onChange={(e) => setScene(s.id, "motion", e.target.value)}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 outline-none"
                    >
                      {MOTIONS.map((m) => <option key={m} value={m}>{m.replace("_", " ")}</option>)}
                    </select>
                  </div>
                  {s.narration_excerpt && (
                    <p className={clsx("text-sm italic mb-2", s.excerpt_verified === false ? "text-amber-600" : "text-gray-700")}>
                      "{s.narration_excerpt}"
                    </p>
                  )}
                  <label className="text-[11px] uppercase tracking-wider text-gray-400">Visual</label>
                  <textarea
                    rows={2}
                    value={s.visual_prompt || ""}
                    onChange={(e) => setScene(s.id, "visual_prompt", e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-y outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 mt-1"
                  />
                  <div className="flex items-center gap-2 mt-2">
                    <label className="text-[11px] uppercase tracking-wider text-gray-400 shrink-0">Caption</label>
                    <input
                      value={s.caption || ""}
                      placeholder="none"
                      onChange={(e) => setScene(s.id, "caption", e.target.value || null)}
                      className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-brand-500"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 pt-1">
            {dirty && (
              <button
                onClick={() => run("save", saveEdits)}
                disabled={!!busy || tooLong}
                className="flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-800 py-4 px-5 rounded-2xl font-medium text-sm transition disabled:opacity-50"
              >
                {busy === "save" ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-gray-800 border-t-transparent" /> : <Save size={16} />}
                Save edits
              </button>
            )}
            <button
              onClick={handleRender}
              disabled={!!busy || tooLong}
              className="flex-1 flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 active:scale-[0.99] text-white py-4 rounded-2xl font-medium text-base transition disabled:opacity-60 shadow-lg shadow-gray-900/10"
            >
              {busy === "render" ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> : <Film size={18} />}
              {dirty ? "Save & make the video" : "Looks good — make the video"}
            </button>
          </div>
          <p className="text-xs text-gray-400 text-center">Takes 2–3 minutes. You'll preview it before it goes to YouTube.</p>
        </div>
      )}

      {/* Preview */}
      {(isPreviewReady || isDone) && video?.video_url && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6 mb-5">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-4">Preview</p>
          <video
            key={video.video_url}
            src={video.video_url}
            controls
            className="w-full rounded-xl bg-black max-h-[500px]"
            style={{ aspectRatio: "9/16", maxWidth: "280px", margin: "0 auto", display: "block" }}
          />
          {video.title && (
            <div className="mt-4 space-y-1">
              <p className="font-medium text-gray-900">{video.title}</p>
              <p className="text-sm text-gray-500 line-clamp-2">{video.description}</p>
              {video.tags && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {video.tags.map((tag: string) => (
                    <span key={tag} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">#{tag}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Approve / re-render */}
      {isPreviewReady && (
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleRender}
            disabled={!!busy}
            className="flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-800 py-3.5 px-5 rounded-xl font-medium text-sm transition disabled:opacity-50"
            title="Render again with the same script"
          >
            <RotateCcw size={15} /> Re-render
          </button>
          <button
            onClick={handleApprove}
            disabled={!!busy}
            className="flex-1 flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 text-white py-3.5 rounded-xl font-medium text-sm transition disabled:opacity-60"
          >
            {busy === "approve" ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> : <ThumbsUp size={16} />}
            {busy === "approve" ? "Uploading…" : "Looks good — post to YouTube"}
          </button>
        </div>
      )}

      {/* YouTube link */}
      {isDone && video?.youtube_url && (
        <a href={video.youtube_url} target="_blank" rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-700 py-3.5 rounded-xl font-medium text-sm transition mt-4">
          <Youtube size={16} className="text-red-500" /> View on YouTube <ExternalLink size={13} className="text-gray-400" />
        </a>
      )}
    </div>
  );
}
