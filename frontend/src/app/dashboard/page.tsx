"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Youtube, Instagram, X, Play, Square, SlidersHorizontal, Search } from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import clsx from "clsx";

const STYLES = ["Educational", "Motivational", "Storytelling", "News", "Philosophical"];

// Shown until /voices loads (and as fallback if it fails)
const FALLBACK_VOICES: Voice[] = [
  { voice_id: "pNInz6obpgDQGcFmaJgB", name: "Adam", accent: "american", gender: "male", description: "deep", language: "", category: "premade", preview_url: "" },
  { voice_id: "onwK4e9ZLuTAKqWW03F9", name: "Daniel", accent: "british", gender: "male", description: "calm", language: "", category: "premade", preview_url: "" },
  { voice_id: "EXAVITQu4vr4xnSDxMaL", name: "Bella", accent: "american", gender: "female", description: "warm", language: "", category: "premade", preview_url: "" },
];

type Voice = {
  voice_id: string; name: string; category?: string; accent?: string; language?: string;
  gender?: string; age?: string; use_case?: string; description?: string; preview_url?: string;
};
type TtsModel = { id: string; label: string; notes: string };
type VoiceSettings = { stability: number; similarity_boost: number; style: number; speed: number };

const DEFAULT_SETTINGS: VoiceSettings = { stability: 0.5, similarity_boost: 0.75, style: 0.3, speed: 1.0 };

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

// Mirrors LANGUAGES in script_generator.py
const LANGUAGES = [
  { code: "auto", label: "Auto (match my request)" },
  { code: "en", label: "English" },
  { code: "pa", label: "ਪੰਜਾਬੀ · Punjabi" },
  { code: "hi", label: "हिन्दी · Hindi" },
  { code: "ur", label: "اردو · Urdu" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "pt", label: "Português" },
  { code: "ar", label: "العربية · Arabic" },
  { code: "bn", label: "বাংলা · Bengali" },
  { code: "ta", label: "தமிழ் · Tamil" },
  { code: "te", label: "తెలుగు · Telugu" },
  { code: "gu", label: "ગુજરાતી · Gujarati" },
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
  const [language, setLanguage] = useState("auto");
  const [sourceText, setSourceText] = useState("");
  const [narrationStyle, setNarrationStyle] = useState("");
  const [style, setStyle] = useState("Educational");
  // Voice
  const [voices, setVoices] = useState<Voice[]>(FALLBACK_VOICES);
  const [models, setModels] = useState<TtsModel[]>([]);
  const [voiceId, setVoiceId] = useState(FALLBACK_VOICES[0].voice_id);
  const [customVoice, setCustomVoice] = useState("");
  const [voiceSearch, setVoiceSearch] = useState("");
  const [ttsModel, setTtsModel] = useState("");
  const [voiceSettings, setVoiceSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [showTuning, setShowTuning] = useState(false);
  const [playing, setPlaying] = useState<string>("");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken({ template: "Youtube-agent-emailID" });
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/voices`, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) return;
        const data = await res.json();
        if (data.voices?.length) setVoices(data.voices);
        setModels(data.models || []);
        setTtsModel(data.default_model || "");
        if (data.default_settings) setVoiceSettings({ ...DEFAULT_SETTINGS, ...data.default_settings });
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredVoices = useMemo(() => {
    const q = voiceSearch.trim().toLowerCase();
    if (!q) return voices;
    return voices.filter((v) =>
      [v.name, v.accent, v.language, v.gender, v.age, v.use_case, v.description, v.category]
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
          language: inputMode === "idea" ? language : "auto",
          style: style.toLowerCase(),
          narration_style: narrationStyle.trim(),
          voice_id: effectiveVoiceId,
          tts_model: ttsModel || undefined,
          voice_settings: voiceSettings,
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
          <div className="flex w-full sm:w-auto sm:inline-flex rounded-xl border border-gray-200 p-1 mb-4 bg-gray-50">
            {([
              { key: "idea", label: "Give me an idea" },
              { key: "text", label: "Use my own text" },
            ] as const).map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => { setInputMode(m.key); setError(""); }}
                className={clsx(
                  "flex-1 sm:flex-none px-4 py-2 rounded-lg text-sm transition whitespace-nowrap",
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
              <label className="field-label mt-4">Script language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 bg-white"
              >
                {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
              <p className="text-xs text-gray-400 mt-1.5">
                Narration, title and captions come out in this language. Pick a voice and speech model that support it (Eleven v3 for Punjabi).
              </p>
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
          {/* Search */}
          <div className="relative mb-3">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={voiceSearch}
              onChange={(e) => setVoiceSearch(e.target.value)}
              placeholder="Search voices — try “indian”, “hindi”, “female”, “calm”"
              className="w-full border border-gray-200 rounded-xl pl-9 pr-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
          </div>

          {/* Voice list */}
          <div className={clsx("space-y-1.5 overflow-y-auto pr-1", filteredVoices.length > 5 && "max-h-72")}>
            {filteredVoices.length === 0 && (
              <p className="text-sm text-gray-400 py-3">No match. Add voices to “My Voices” in ElevenLabs and they’ll show up here.</p>
            )}
            {filteredVoices.map((v) => {
              const active = !customVoice.trim() && voiceId === v.voice_id;
              const meta = [v.accent, v.language, v.gender, v.age, v.description || v.use_case].filter(Boolean).join(" · ");
              return (
                <div
                  key={v.voice_id}
                  role="button"
                  onClick={() => { setVoiceId(v.voice_id); setCustomVoice(""); }}
                  className={clsx(
                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition cursor-pointer",
                    active ? "border-brand-300 bg-brand-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                  )}
                >
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); togglePreview(v); }}
                    disabled={!v.preview_url}
                    title={v.preview_url ? "Preview" : "No preview"}
                    className={clsx("w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition",
                      v.preview_url ? "bg-gray-900 text-white hover:bg-gray-700" : "bg-gray-100 text-gray-300")}
                  >
                    {playing === v.voice_id ? <Square size={12} /> : <Play size={12} className="ml-0.5" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className={clsx("text-sm font-medium truncate", active ? "text-brand-700" : "text-gray-800")}>
                      {v.name}
                      {v.category && v.category !== "premade" && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider text-gray-400">{v.category}</span>
                      )}
                    </p>
                    <p className="text-xs text-gray-400 truncate">{meta || "—"}</p>
                  </div>
                  {active && <div className="w-2 h-2 rounded-full bg-brand-500 shrink-0" />}
                </div>
              );
            })}
          </div>

          {/* Custom ID */}
          <label className="field-label mt-4">Or paste any ElevenLabs voice ID</label>
          <input
            type="text"
            value={customVoice}
            onChange={(e) => setCustomVoice(e.target.value)}
            placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
            className={clsx("w-full border rounded-xl px-4 py-2.5 text-sm font-mono outline-none focus:ring-2",
              customVoice.trim() ? "border-brand-300 bg-brand-50 focus:ring-brand-100" : "border-gray-200 focus:border-brand-500 focus:ring-brand-100")}
          />
          <p className="text-xs text-gray-400 mt-1.5">
            For Punjabi / Hindi: open the ElevenLabs Voice Library, search the language, click “Add to My Voices” — it appears in the list above.
          </p>

          {/* Model + tuning */}
          <button
            type="button"
            onClick={() => setShowTuning(!showTuning)}
            className="mt-4 flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
          >
            <SlidersHorizontal size={14} /> {showTuning ? "Hide" : "Show"} model & delivery settings
          </button>

          {showTuning && (
            <div className="mt-3 space-y-4 border-t border-gray-100 pt-4">
              {models.length > 0 && (
                <div>
                  <label className="field-label">Speech model</label>
                  <div className="space-y-1.5">
                    {models.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setTtsModel(m.id)}
                        className={clsx("w-full text-left px-3 py-2 rounded-lg border text-sm transition",
                          ttsModel === m.id ? "border-brand-300 bg-brand-50 text-brand-700" : "border-gray-200 text-gray-700 hover:border-gray-300")}
                      >
                        <span className="font-medium">{m.label}</span>
                        <span className="text-xs text-gray-400 ml-2">{m.notes}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {([
                { key: "stability", label: "Stability", lo: "Expressive / varied", hi: "Steady / monotone" },
                { key: "similarity_boost", label: "Clarity", lo: "Softer", hi: "Crisper, closer to original" },
                { key: "style", label: "Style exaggeration", lo: "Neutral", hi: "Dramatic" },
              ] as const).map((s) => (
                <div key={s.key}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium text-gray-600">{s.label}</span>
                    <span className="text-gray-400">{Math.round(voiceSettings[s.key] * 100)}%</span>
                  </div>
                  <input
                    type="range" min={0} max={1} step={0.05}
                    value={voiceSettings[s.key]}
                    onChange={(e) => setVoiceSettings({ ...voiceSettings, [s.key]: Number(e.target.value) })}
                    className="w-full accent-brand-500"
                  />
                  <div className="flex justify-between text-[11px] text-gray-400"><span>{s.lo}</span><span>{s.hi}</span></div>
                </div>
              ))}

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-gray-600">Pace</span>
                  <span className="text-gray-400">{voiceSettings.speed.toFixed(2)}×</span>
                </div>
                <input
                  type="range" min={0.7} max={1.2} step={0.05}
                  value={voiceSettings.speed}
                  onChange={(e) => setVoiceSettings({ ...voiceSettings, speed: Number(e.target.value) })}
                  className="w-full accent-brand-500"
                />
                <div className="flex justify-between text-[11px] text-gray-400"><span>Slower</span><span>Faster</span></div>
              </div>

              <button type="button" onClick={() => setVoiceSettings(DEFAULT_SETTINGS)} className="text-xs text-gray-400 hover:text-gray-600 underline">
                Reset to defaults
              </button>
            </div>
          )}
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
