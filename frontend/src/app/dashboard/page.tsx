"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Mic, Youtube, Instagram, ChevronRight, X } from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import clsx from "clsx";

const STYLES = ["Educational", "Motivational", "Storytelling", "News", "Philosophical"];

const VOICES = [
  { id: "pNInz6obpgDQGcFmaJgB", name: "Adam", desc: "Deep · Neutral · Male" },
  { id: "onwK4e9ZLuTAKqWW03F9", name: "Daniel", desc: "British · Calm · Male" },
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", desc: "Warm · Conversational · Female" },
  { id: "VR6AewLTigWG4xSOukaG", name: "Arnold", desc: "Strong · Authoritative · Male" },
];

const PRIVACIES = [
  { value: "private", label: "Private", desc: "Review before publishing" },
  { value: "unlisted", label: "Unlisted", desc: "Only people with the link" },
  { value: "public", label: "Public", desc: "Visible to everyone" },
];

// Mirrors NARRATION_PRESETS in script_generator.py (keys must match)
const NARRATION_PRESETS = [
  { key: "documentary", label: "Documentary", desc: "Calm, precise, observational" },
  { key: "storyteller", label: "Storyteller", desc: "Warm, builds tension, pays off" },
  { key: "energetic", label: "Energetic host", desc: "Fast, punchy, direct" },
  { key: "philosopher", label: "Philosopher", desc: "Unhurried, ends on a question" },
  { key: "news", label: "News explainer", desc: "Fact first, plain language" },
];

// Must match script_generator.py: 2.5 words/s, 60 s max → 150 words
const WORDS_PER_SECOND = 2.5;
const MAX_SECONDS = 60;
const MAX_WORDS = MAX_SECONDS * WORDS_PER_SECOND;

export default function CreatePage() {
  const router = useRouter();
  const { getToken } = useAuth();

  const [inputMode, setInputMode] = useState<"idea" | "text">("idea");
  const [topic, setTopic] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [narrationStyle, setNarrationStyle] = useState("");
  const [style, setStyle] = useState("Educational");
  const [voiceId, setVoiceId] = useState(VOICES[0].id);
  const [visualMode, setVisualMode] = useState<"ai_images" | "stock">("ai_images");
  const [duration, setDuration] = useState(45);
  const [platforms, setPlatforms] = useState<string[]>(["youtube"]);
  const [privacy, setPrivacy] = useState("private");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const addTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === "Enter" || e.key === ",") && tagInput.trim()) {
      e.preventDefault();
      const tag = tagInput.trim().replace(/^#/, "");
      if (!tags.includes(tag)) setTags([...tags, tag]);
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => setTags(tags.filter((t) => t !== tag));

  const togglePlatform = (p: string) => {
    setPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  // Live length check for pasted text
  const sourceWords = sourceText.trim() ? sourceText.trim().split(/\s+/).length : 0;
  const sourceSeconds = Math.round(sourceWords / WORDS_PER_SECOND);
  const sourceTooLong = sourceWords > MAX_WORDS;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inputMode === "idea" && !topic.trim()) { setError("Please enter a topic."); return; }
    if (inputMode === "text") {
      if (!sourceText.trim()) { setError("Paste the text you want narrated."); return; }
      if (sourceTooLong) {
        setError(`That's about ${sourceSeconds}s at speaking pace — Shorts max is ${MAX_SECONDS}s. Trim to roughly ${MAX_WORDS} words (you're ${sourceWords - MAX_WORDS} over).`);
        return;
      }
    }
    if (platforms.length === 0) { setError("Select at least one platform."); return; }

    setLoading(true);
    setError("");

    try {
      const token = await getToken({ template: "Youtube-agent-emailID" });
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          input_mode: inputMode,
          topic: topic.trim(),
          source_text: inputMode === "text" ? sourceText.trim() : undefined,
          style: style.toLowerCase(),
          narration_style: narrationStyle.trim(),
          voice_id: voiceId,
          visual_mode: visualMode,
          duration,
          platform: platforms,
          privacy,
          tags,
        }),
      });

      if (!res.ok) {
        // FastAPI returns {"detail": "..."} — surface the message, not raw JSON
        let msg = await res.text();
        try { msg = JSON.parse(msg).detail || msg; } catch {}
        throw new Error(msg);
      }
      const data = await res.json();
      router.push(`/dashboard/jobs/${data.job_id}`);
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Create a video</h1>
        <p className="text-gray-400 text-sm mt-1">Ask for a script, review it, then render</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Input */}
        <Section title="Your idea">
          {/* Mode toggle */}
          <div className="inline-flex rounded-xl border border-gray-200 p-1 mb-4 bg-gray-50">
            {([
              { key: "idea", label: "Give me an idea" },
              { key: "text", label: "Use my own text" },
            ] as const).map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => { setInputMode(m.key); setError(""); }}
                className={clsx(
                  "px-4 py-1.5 rounded-lg text-sm transition",
                  inputMode === m.key
                    ? "bg-white text-gray-900 shadow-sm font-medium"
                    : "text-gray-500 hover:text-gray-700"
                )}
              >
                {m.label}
              </button>
            ))}
          </div>

          {inputMode === "idea" ? (
            <>
              <label className="field-label">What do you want?</label>
              <textarea
                rows={3}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder='Just ask — e.g. "create me a script for why sports is important for a child"'
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 outline-none transition"
              />
            </>
          ) : (
            <>
              <label className="field-label">Your narration (used word for word)</label>
              <textarea
                rows={7}
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Paste a paragraph, a passage from your story, a quote... It will be spoken exactly as written."
                className={clsx(
                  "w-full border rounded-xl px-4 py-3 text-sm resize-y outline-none transition focus:ring-2",
                  sourceTooLong
                    ? "border-red-300 focus:border-red-400 focus:ring-red-100"
                    : "border-gray-200 focus:border-brand-500 focus:ring-brand-100"
                )}
              />
              <div className={clsx("flex justify-between text-xs mt-1.5", sourceTooLong ? "text-red-500" : "text-gray-400")}>
                <span>
                  {sourceWords} / {MAX_WORDS} words · ~{sourceSeconds}s
                </span>
                {sourceTooLong && (
                  <span className="font-medium">
                    Too long for a Short — trim {sourceWords - MAX_WORDS} words
                  </span>
                )}
              </div>
              <label className="field-label mt-4">Title hint <span className="text-gray-300 font-normal normal-case tracking-normal">(optional)</span></label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="What is this about? Helps with the title and visuals."
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition"
              />
            </>
          )}

          <label className="field-label mt-4">Narration style</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {NARRATION_PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                title={p.desc}
                onClick={() => setNarrationStyle(narrationStyle === p.key ? "" : p.key)}
                className={clsx(
                  "px-3 py-1.5 rounded-full text-sm border transition",
                  narrationStyle === p.key
                    ? "bg-brand-50 text-brand-600 border-brand-200 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={narrationStyle}
            onChange={(e) => setNarrationStyle(e.target.value)}
            placeholder='…or describe one: "tired detective", "excited science teacher", "whispered bedtime story"'
            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition"
          />
          <p className="text-xs text-gray-400 mt-1.5">
            {inputMode === "text"
              ? "In text mode this only shapes the title and description — your words are never changed."
              : "Pick a preset or describe any voice. Leave empty for Documentary."}
          </p>

          <label className="field-label mt-4">Content style</label>
          <div className="flex flex-wrap gap-2">
            {STYLES.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setStyle(s)}
                className={clsx(
                  "px-3 py-1.5 rounded-full text-sm border transition",
                  style === s
                    ? "bg-brand-50 text-brand-600 border-brand-200 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                )}
              >
                {s}
              </button>
            ))}
          </div>

          <label className="field-label mt-4">Tags</label>
          <div className="border border-gray-200 rounded-xl px-4 py-2.5 flex flex-wrap gap-2 min-h-[44px] focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100 transition">
            {tags.map((tag) => (
              <span key={tag} className="flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2.5 py-1 rounded-full">
                #{tag}
                <button type="button" onClick={() => removeTag(tag)} className="hover:text-red-500">
                  <X size={11} />
                </button>
              </span>
            ))}
            <input
              type="text"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={addTag}
              placeholder={tags.length === 0 ? "Type a tag and press Enter..." : ""}
              className="text-sm outline-none flex-1 min-w-[120px] bg-transparent"
            />
          </div>
          <p className="text-xs text-gray-400 mt-1.5">Press Enter or comma to add a tag</p>
        </Section>

        {/* Voice */}
        <Section title="Voice">
          <div className="space-y-2">
            {VOICES.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setVoiceId(v.id)}
                className={clsx(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition",
                  voiceId === v.id
                    ? "border-brand-300 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                )}
              >
                <Mic size={16} className={voiceId === v.id ? "text-brand-500" : "text-gray-400"} />
                <div className="flex-1">
                  <p className={clsx("text-sm font-medium", voiceId === v.id ? "text-brand-700" : "text-gray-800")}>{v.name}</p>
                  <p className="text-xs text-gray-400">{v.desc}</p>
                </div>
                {voiceId === v.id && <div className="w-2 h-2 rounded-full bg-brand-500" />}
              </button>
            ))}
          </div>
        </Section>

        {/* Settings */}
        <Section title="Video settings">
          <label className="field-label">Visuals</label>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {([
              { key: "ai_images", label: "AI images", desc: "Generated per scene, animated. Matches the script." },
              { key: "stock", label: "Stock footage", desc: "Pexels clips by keyword. Free, generic." },
            ] as const).map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setVisualMode(m.key)}
                className={clsx(
                  "text-left px-4 py-3 rounded-xl border transition",
                  visualMode === m.key ? "border-brand-300 bg-brand-50" : "border-gray-200 hover:border-gray-300"
                )}
              >
                <p className={clsx("text-sm font-medium", visualMode === m.key ? "text-brand-700" : "text-gray-800")}>{m.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{m.desc}</p>
              </button>
            ))}
          </div>

          {inputMode === "idea" ? (
            <>
              <label className="field-label">Duration — {duration}s</label>
              <input
                type="range"
                min={15} max={60} step={5}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="w-full accent-brand-500"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>15s</span><span>60s</span>
              </div>
            </>
          ) : (
            <>
              <label className="field-label">Duration</label>
              <p className="text-sm text-gray-600">
                ~{sourceSeconds || 0}s — set by your text length
              </p>
            </>
          )}

          <label className="field-label mt-4">Publish to</label>
          <div className="flex gap-3">
            {[
              { key: "youtube", label: "YouTube", Icon: Youtube },
              { key: "instagram", label: "Instagram", Icon: Instagram },
            ].map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => togglePlatform(key)}
                className={clsx(
                  "flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm transition",
                  platforms.includes(key)
                    ? "border-brand-300 bg-brand-50 text-brand-700 font-medium"
                    : "border-gray-200 text-gray-500 hover:border-gray-300"
                )}
              >
                <Icon size={16} /> {label}
              </button>
            ))}
          </div>

          <label className="field-label mt-4">Privacy</label>
          <div className="space-y-2">
            {PRIVACIES.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setPrivacy(p.value)}
                className={clsx(
                  "w-full flex items-center justify-between px-4 py-3 rounded-xl border text-left transition text-sm",
                  privacy === p.value
                    ? "border-brand-300 bg-brand-50"
                    : "border-gray-200 hover:border-gray-300"
                )}
              >
                <div>
                  <span className={clsx("font-medium", privacy === p.value ? "text-brand-700" : "text-gray-800")}>{p.label}</span>
                  <span className="text-gray-400 ml-2 text-xs">{p.desc}</span>
                </div>
                {privacy === p.value && <div className="w-2 h-2 rounded-full bg-brand-500" />}
              </button>
            ))}
          </div>
        </Section>

        {error && (
          <p className="text-red-500 text-sm bg-red-50 border border-red-100 rounded-xl px-4 py-3">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 text-white py-3.5 rounded-xl font-medium text-sm transition disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
          ) : (
            <Sparkles size={16} />
          )}
          {loading ? "Starting..." : "Create script"}
        </button>
        <p className="text-xs text-gray-400 text-center -mt-2">
          You'll review the script before any video is rendered.
        </p>
      </form>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6">
      <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-4">{title}</p>
      {children}
    </div>
  );
}
