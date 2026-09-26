"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles, Youtube, X, Play, Square, SlidersHorizontal, Search,
  ChevronDown, ChevronUp, Wand2, FileText, Mic2, Image as ImageIcon, Lock,
} from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import clsx from "clsx";

// ── Static options ─────────────────────────────────────────────────────────

const STYLES = ["Educational", "Motivational", "Storytelling", "News", "Philosophical"];

// Mirrors NARRATION_PRESETS in script_generator.py (keys must match)
const NARRATION_PRESETS = [
  { key: "documentary", label: "Documentary", desc: "Calm, precise, observational" },
  { key: "storyteller", label: "Storyteller", desc: "Warm, builds tension, pays off" },
  { key: "energetic", label: "Energetic host", desc: "Fast, punchy, direct" },
  { key: "philosopher", label: "Philosopher", desc: "Unhurried, ends on a question" },
  { key: "news", label: "News explainer", desc: "Fact first, plain language" },
];

const PRIVACIES = [
  { value: "private", label: "Private", desc: "Only you can see it on YouTube" },
  { value: "unlisted", label: "Unlisted", desc: "Anyone with the link" },
  { value: "public", label: "Public", desc: "Everyone" },
];

// Must match script_generator.py: 2.5 words/s, 60 s max → 150 words
const WORDS_PER_SECOND = 2.5;
const MAX_SECONDS = 60;
const MAX_WORDS = MAX_SECONDS * WORDS_PER_SECOND;

type Voice = {
  voice_id: string; name: string; category?: string; accent?: string; language?: string;
  gender?: string; age?: string; use_case?: string; description?: string; preview_url?: string;
};
type TtsModel = { id: string; label: string; notes: string };
type VoiceSettings = { stability: number; similarity_boost: number; style: number; speed: number };

const DEFAULT_SETTINGS: VoiceSettings = { stability: 0.45, similarity_boost: 0.75, style: 0.25, speed: 1.0 };

const FALLBACK_VOICES: Voice[] = [
  { voice_id: "pNInz6obpgDQGcFmaJgB", name: "Adam", accent: "american", gender: "male", description: "deep", category: "premade" },
  { voice_id: "onwK4e9ZLuTAKqWW03F9", name: "Daniel", accent: "british", gender: "male", description: "calm", category: "premade" },
  { voice_id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", accent: "american", gender: "female", description: "warm", category: "premade" },
];

// ── Page ───────────────────────────────────────────────────────────────────

export default function CreatePage() {
  const router = useRouter();
  const { getToken } = useAuth();

  // Core
  const [inputMode, setInputMode] = useState<"idea" | "text">("idea");
  const [topic, setTopic] = useState("");
  const [sourceText, setSourceText] = useState("");

  // Voice
  const [voices, setVoices] = useState<Voice[]>(FALLBACK_VOICES);
  const [models, setModels] = useState<TtsModel[]>([]);
  const [voiceId, setVoiceId] = useState(FALLBACK_VOICES[0].voice_id);
  const [customVoice, setCustomVoice] = useState("");
  const [voiceSearch, setVoiceSearch] = useState("");
  const [ttsModel, setTtsModel] = useState("");
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [playing, setPlaying] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // More options (defaults are good; most users never open this)
  const [showMore, setShowMore] = useState(false);
  const [narrationStyle, setNarrationStyle] = useState("");
  const [style, setStyle] = useState("Educational");
  const [duration, setDuration] = useState(45);
  const [visualMode, setVisualMode] = useState<"ai_images" | "stock">("ai_images");
  const [privacy, setPrivacy] = useState("private");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [showTuning, setShowTuning] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load voices + user defaults
  useEffect(() => {
    (async () => {
      try {
        const token = await getToken({ template: "Youtube-agent-emailID" });
        const h = { Authorization: `Bearer ${token}` };
        const [vr, ur] = await Promise.all([
          fetch(`${process.env.NEXT_PUBLIC_API_URL}/voices`, { headers: h }),
          fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/me`, { headers: h }),
        ]);
        if (vr.ok) {
          const data = await vr.json();
          if (data.voices?.length) setVoices(data.voices);
          setModels(data.models || []);
          setTtsModel(data.default_model || "");
        }
        if (ur.ok) {
          const me = await ur.json();
          if (me.default_voice_id) setVoiceId(me.default_voice_id);
          if (me.default_style) setStyle(me.default_style.charAt(0).toUpperCase() + me.default_style.slice(1));
          if (me.default_duration) setDuration(me.default_duration);
          if (me.default_visual_mode) setVisualMode(me.default_visual_mode);
        }
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredVoices = useMemo(() => {
    const q = voiceSearch.trim().toLowerCase();
    if (!q) return voices;
    return voices.filter((v) =>
      [v.name, v.accent, v.gender, v.age, v.use_case, v.description, v.category]
        .filter(Boolean).join(" ").toLowerCase().includes(q));
  }, [voices, voiceSearch]);

  const togglePreview = (v: Voice) => {
    if (!v.preview_url) return;
    if (playing === v.voice_id) { audioRef.current?.pause(); setPlaying(""); return; }
    if (!audioRef.current) audioRef.current = new Audio();
    audioRef.current.src = v.preview_url;
    audioRef.current.onended = () => setPlaying("");
    audioRef.current.play().catch(() => {});
    setPlaying(v.voice_id);
  };

  const effectiveVoiceId = customVoice.trim() || voiceId;
  const selectedVoice = voices.find((v) => v.voice_id === voiceId);

  const sourceWords = sourceText.trim() ? sourceText.trim().split(/\s+/).length : 0;
  const sourceSeconds = Math.round(sourceWords / WORDS_PER_SECOND);
  const sourceTooLong = sourceWords > MAX_WORDS;

  const addTag = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === "Enter" || e.key === ",") && tagInput.trim()) {
      e.preventDefault();
      const tag = tagInput.trim().replace(/^#/, "");
      if (!tags.includes(tag)) setTags([...tags, tag]);
      setTagInput("");
    }
  };

  const canSubmit = inputMode === "idea" ? topic.trim().length > 0 : sourceText.trim().length > 0 && !sourceTooLong;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) {
      setError(inputMode === "idea" ? "Tell me what the video is about." :
        sourceTooLong ? `That's about ${sourceSeconds}s — Shorts max is ${MAX_SECONDS}s. Trim about ${sourceWords - MAX_WORDS} words.` :
        "Paste the text you want narrated.");
      return;
    }
    setLoading(true); setError("");
    try {
      const token = await getToken({ template: "Youtube-agent-emailID" });
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          input_mode: inputMode,
          topic: topic.trim(),
          source_text: inputMode === "text" ? sourceText.trim() : undefined,
          language: "en",
          style: style.toLowerCase(),
          narration_style: narrationStyle.trim(),
          voice_id: effectiveVoiceId,
          tts_model: ttsModel || undefined,
          voice_settings: voiceSettings,
          visual_mode: visualMode,
          duration,
          platform: ["youtube"],
          privacy,
          tags,
        }),
      });
      if (!res.ok) {
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

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900">Make a Short</h1>
        <p className="text-gray-500 text-sm mt-1">Tell it your idea. You'll approve the script before anything renders.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* ── 1. Idea ─────────────────────────────────────────── */}
        <Card step={1} icon={inputMode === "idea" ? Wand2 : FileText} title={inputMode === "idea" ? "What's it about?" : "Your words, spoken as written"}>
          <div className="flex rounded-xl bg-gray-100 p-1 mb-4">
            {([
              { key: "idea", label: "I have an idea", Icon: Wand2 },
              { key: "text", label: "I have the text", Icon: FileText },
            ] as const).map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => { setInputMode(m.key); setError(""); }}
                className={clsx(
                  "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm transition",
                  inputMode === m.key ? "bg-white text-gray-900 shadow-sm font-medium" : "text-gray-500 hover:text-gray-800"
                )}
              >
                <m.Icon size={15} /> {m.label}
              </button>
            ))}
          </div>

          {inputMode === "idea" ? (
            <textarea
              rows={3}
              autoFocus
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder='e.g. "why sports matter for kids" or "the strange history of the paperclip"'
              className="w-full border border-gray-200 rounded-xl px-4 py-3 text-base sm:text-sm resize-none outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 transition placeholder:text-gray-400"
            />
          ) : (
            <>
              <textarea
                rows={6}
                autoFocus
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Paste a paragraph, a passage from your story, a quote…"
                className={clsx(
                  "w-full border rounded-xl px-4 py-3 text-base sm:text-sm resize-y outline-none transition focus:ring-2 placeholder:text-gray-400",
                  sourceTooLong ? "border-red-300 focus:ring-red-100" : "border-gray-200 focus:border-brand-500 focus:ring-brand-100"
                )}
              />
              <div className={clsx("flex justify-between text-xs mt-1.5", sourceTooLong ? "text-red-500" : "text-gray-400")}>
                <span>{sourceWords} words · about {sourceSeconds}s</span>
                {sourceTooLong ? <span className="font-medium">Too long — trim {sourceWords - MAX_WORDS} words</span> : <span>max {MAX_WORDS} words</span>}
              </div>
            </>
          )}
        </Card>

        {/* ── 2. Voice ────────────────────────────────────────── */}
        <Card step={2} icon={Mic2} title="Who's narrating?"
              aside={selectedVoice && !customVoice ? <span className="text-xs text-gray-400">{selectedVoice.name}</span> : undefined}>
          {voices.length > 6 && (
            <div className="relative mb-3">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={voiceSearch}
                onChange={(e) => setVoiceSearch(e.target.value)}
                placeholder="Search voices"
                className="w-full border border-gray-200 rounded-xl pl-9 pr-4 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
          )}

          <div className={clsx("grid grid-cols-1 sm:grid-cols-2 gap-2", filteredVoices.length > 8 && "max-h-80 overflow-y-auto pr-1")}>
            {filteredVoices.length === 0 && (
              <p className="text-sm text-gray-400 py-2 col-span-2">No match. Add voices to “My Voices” in ElevenLabs and they’ll appear here.</p>
            )}
            {filteredVoices.map((v) => {
              const active = !customVoice.trim() && voiceId === v.voice_id;
              const meta = [v.gender, v.accent, v.description || v.use_case].filter(Boolean).join(" · ");
              return (
                <div
                  key={v.voice_id}
                  role="button"
                  onClick={() => { setVoiceId(v.voice_id); setCustomVoice(""); }}
                  className={clsx(
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition cursor-pointer",
                    active ? "border-brand-400 bg-brand-50 ring-2 ring-brand-100" : "border-gray-200 hover:border-gray-300 bg-white"
                  )}
                >
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); togglePreview(v); }}
                    disabled={!v.preview_url}
                    aria-label="Preview voice"
                    className={clsx("w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition",
                      v.preview_url ? "bg-gray-900 text-white hover:bg-gray-700 active:scale-95" : "bg-gray-100 text-gray-300")}
                  >
                    {playing === v.voice_id ? <Square size={12} /> : <Play size={12} className="ml-0.5" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={clsx("text-sm font-medium truncate", active ? "text-brand-700" : "text-gray-900")}>{v.name}</p>
                    <p className="text-xs text-gray-400 truncate capitalize">{meta || "—"}</p>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-gray-400 mt-3">Tap ▶ to hear a sample. Want more? Add voices to “My Voices” in ElevenLabs.</p>
        </Card>

        {/* ── More options ────────────────────────────────────── */}
        <button
          type="button"
          onClick={() => setShowMore(!showMore)}
          className="w-full flex items-center justify-between px-5 py-3.5 rounded-2xl border border-dashed border-gray-200 text-sm text-gray-500 hover:text-gray-800 hover:border-gray-300 transition bg-white/60"
        >
          <span className="flex items-center gap-2"><SlidersHorizontal size={15} /> More options</span>
          <span className="flex items-center gap-2 text-xs text-gray-400">
            {!showMore && <span className="hidden sm:inline">{style} · {duration}s · {visualMode === "ai_images" ? "AI images" : "Stock footage"} · {privacy}</span>}
            {showMore ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </span>
        </button>

        {showMore && (
          <div className="space-y-4">
            <Card icon={Sparkles} title="Tone">
              <label className="field-label">Content style</label>
              <Chips options={STYLES.map((s) => ({ key: s, label: s }))} value={style} onChange={setStyle} />

              <label className="field-label mt-4">Narration voice style</label>
              <Chips
                options={NARRATION_PRESETS.map((p) => ({ key: p.key, label: p.label, title: p.desc }))}
                value={narrationStyle}
                onChange={(k) => setNarrationStyle(narrationStyle === k ? "" : k)}
              />
              <input
                type="text"
                value={narrationStyle}
                onChange={(e) => setNarrationStyle(e.target.value)}
                placeholder='…or describe one: "tired detective", "excited science teacher"'
                className="mt-2 w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
              {inputMode === "text" && <p className="text-xs text-gray-400 mt-1.5">In text mode this only shapes the title and description.</p>}
            </Card>

            <Card icon={ImageIcon} title="Video">
              <label className="field-label">Visuals</label>
              <div className="grid grid-cols-2 gap-2">
                {([
                  { key: "ai_images", label: "AI images", desc: "Generated to match the script" },
                  { key: "stock", label: "Stock footage", desc: "Pexels clips by keyword" },
                ] as const).map((m) => (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => setVisualMode(m.key)}
                    className={clsx("text-left px-4 py-3 rounded-xl border transition",
                      visualMode === m.key ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:border-gray-300")}
                  >
                    <p className={clsx("text-sm font-medium", visualMode === m.key ? "text-brand-700" : "text-gray-800")}>{m.label}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{m.desc}</p>
                  </button>
                ))}
              </div>

              {inputMode === "idea" && (
                <>
                  <label className="field-label mt-4">Length — {duration}s</label>
                  <input type="range" min={15} max={60} step={5} value={duration}
                         onChange={(e) => setDuration(Number(e.target.value))} className="w-full accent-brand-500" />
                  <div className="flex justify-between text-xs text-gray-400 mt-1"><span>15s</span><span>60s</span></div>
                </>
              )}

              <label className="field-label mt-4">Tags</label>
              <div className="border border-gray-200 rounded-xl px-3 py-2 flex flex-wrap gap-2 min-h-[44px] focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100 transition">
                {tags.map((tag) => (
                  <span key={tag} className="flex items-center gap-1 bg-gray-100 text-gray-700 text-xs px-2.5 py-1 rounded-full">
                    #{tag}
                    <button type="button" onClick={() => setTags(tags.filter((t) => t !== tag))} className="hover:text-red-500"><X size={11} /></button>
                  </span>
                ))}
                <input
                  type="text" value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)} onKeyDown={addTag}
                  placeholder={tags.length === 0 ? "Optional — type and press Enter" : ""}
                  className="text-sm outline-none flex-1 min-w-[140px] bg-transparent"
                />
              </div>
            </Card>

            <Card icon={Youtube} title="Publishing">
              <label className="field-label">Who can see it on YouTube</label>
              <div className="space-y-2">
                {PRIVACIES.map((p) => (
                  <button
                    key={p.value} type="button" onClick={() => setPrivacy(p.value)}
                    className={clsx("w-full flex items-center justify-between px-4 py-3 rounded-xl border text-left text-sm transition",
                      privacy === p.value ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:border-gray-300")}
                  >
                    <span>
                      <span className={clsx("font-medium", privacy === p.value ? "text-brand-700" : "text-gray-800")}>{p.label}</span>
                      <span className="text-gray-400 ml-2 text-xs">{p.desc}</span>
                    </span>
                    {p.value === "private" && <Lock size={13} className="text-gray-300" />}
                  </button>
                ))}
              </div>
            </Card>

            <Card icon={Mic2} title="Voice fine-tuning">
              <label className="field-label">Paste any ElevenLabs voice ID</label>
              <input
                type="text" value={customVoice} onChange={(e) => setCustomVoice(e.target.value)}
                placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
                className={clsx("w-full border rounded-xl px-4 py-2.5 text-sm font-mono outline-none focus:ring-2",
                  customVoice.trim() ? "border-brand-400 bg-brand-50 focus:ring-brand-100" : "border-gray-200 focus:border-brand-500 focus:ring-brand-100")}
              />
              <button type="button" onClick={() => setShowTuning(!showTuning)} className="mt-4 text-sm text-gray-600 hover:text-gray-900 flex items-center gap-2">
                {showTuning ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Delivery sliders
              </button>
              {showTuning && (
                <div className="mt-3 space-y-4">
                  {models.length > 0 && (
                    <div>
                      <label className="field-label">Speech model</label>
                      <Chips options={models.map((m) => ({ key: m.id, label: m.label, title: m.notes }))} value={ttsModel} onChange={setTtsModel} />
                    </div>
                  )}
                  {([
                    { key: "stability", label: "Stability", lo: "Expressive", hi: "Steady" },
                    { key: "similarity_boost", label: "Clarity", lo: "Softer", hi: "Crisper" },
                    { key: "style", label: "Style", lo: "Neutral", hi: "Dramatic" },
                  ] as const).map((s) => (
                    <Slider key={s.key} label={s.label} lo={s.lo} hi={s.hi} min={0} max={1} step={0.05}
                            value={voiceSettings[s.key]} fmt={(v) => `${Math.round(v * 100)}%`}
                            onChange={(v) => setVoiceSettings({ ...voiceSettings, [s.key]: v })} />
                  ))}
                  <Slider label="Pace" lo="Slower" hi="Faster" min={0.7} max={1.2} step={0.05}
                          value={voiceSettings.speed} fmt={(v) => `${v.toFixed(2)}×`}
                          onChange={(v) => setVoiceSettings({ ...voiceSettings, speed: v })} />
                  <button type="button" onClick={() => setVoiceSettings(DEFAULT_SETTINGS)} className="text-xs text-gray-400 hover:text-gray-600 underline">Reset</button>
                </div>
              )}
            </Card>
          </div>
        )}

        {error && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-xl px-4 py-3">{error}</p>
        )}

        {/* ── Submit ──────────────────────────────────────────── */}
        <button
          type="submit"
          disabled={loading || !canSubmit}
          className="w-full flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 active:scale-[0.99] text-white py-4 rounded-2xl font-medium text-base transition disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-gray-900/10"
        >
          {loading ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> : <Sparkles size={18} />}
          {loading ? "Writing your script…" : "Write my script"}
        </button>
        <p className="text-xs text-gray-400 text-center">Takes about 20 seconds. Nothing is rendered until you approve it.</p>
      </form>
    </div>
  );
}

// ── Small building blocks ──────────────────────────────────────────────────

function Card({ step, icon: Icon, title, aside, children }: {
  step?: number; icon: any; title: string; aside?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          {step ? (
            <span className="w-6 h-6 rounded-full bg-gray-900 text-white text-xs font-semibold flex items-center justify-center">{step}</span>
          ) : (
            <Icon size={16} className="text-gray-400" />
          )}
          <p className="text-sm font-semibold text-gray-900">{title}</p>
        </div>
        {aside}
      </div>
      {children}
    </div>
  );
}

function Chips({ options, value, onChange }: {
  options: { key: string; label: string; title?: string }[]; value: string; onChange: (k: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.key} type="button" title={o.title} onClick={() => onChange(o.key)}
          className={clsx("px-3 py-1.5 rounded-full text-sm border transition",
            value === o.key ? "bg-brand-50 text-brand-700 border-brand-300 font-medium" : "border-gray-200 text-gray-600 hover:border-gray-300")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Slider({ label, lo, hi, min, max, step, value, fmt, onChange }: {
  label: string; lo: string; hi: string; min: number; max: number; step: number;
  value: number; fmt: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="font-medium text-gray-600">{label}</span>
        <span className="text-gray-400">{fmt(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
             onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-brand-500" />
      <div className="flex justify-between text-[11px] text-gray-400"><span>{lo}</span><span>{hi}</span></div>
    </div>
  );
}
