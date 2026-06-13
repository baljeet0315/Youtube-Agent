"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { Save } from "lucide-react";

const VOICES = [
  { id: "pNInz6obpgDQGcFmaJgB", name: "Adam — Deep · Neutral · Male" },
  { id: "onwK4e9ZLuTAKqWW03F9", name: "Daniel — British · Calm · Male" },
  { id: "EXAVITQu4vr4xnSDxMaL", name: "Bella — Warm · Conversational · Female" },
  { id: "VR6AewLTigWG4xSOukaG", name: "Arnold — Strong · Authoritative · Male" },
];

export default function SettingsPage() {
  const { getToken } = useAuth();
  const [user, setUser] = useState<any>(null);
  const [voiceId, setVoiceId] = useState("");
  const [style, setStyle] = useState("educational");
  const [duration, setDuration] = useState(45);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
        setVoiceId(data.default_voice_id || VOICES[0].id);
        setStyle(data.default_style || "educational");
        setDuration(data.default_duration || 45);
      }
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ default_voice_id: voiceId, default_style: style, default_duration: duration }),
    });
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!user) return <div className="flex justify-center h-64 items-center"><div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-900 border-t-transparent" /></div>;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-400 mt-1">Your default preferences for new videos</p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-6 space-y-6">
        <div>
          <label className="block text-xs font-medium uppercase tracking-widest text-gray-400 mb-3">Default voice</label>
          <select
            value={voiceId}
            onChange={(e) => setVoiceId(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none"
          >
            {VOICES.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-widest text-gray-400 mb-3">Default style</label>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none"
          >
            {["educational", "motivational", "storytelling", "news", "philosophical"].map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium uppercase tracking-widest text-gray-400 mb-3">Default duration — {duration}s</label>
          <input
            type="range" min={15} max={60} step={5}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="w-full accent-gray-900"
          />
        </div>

        <div className="pt-2">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-3">Connected accounts</p>
          <div className="flex items-center justify-between py-3 border border-gray-100 rounded-xl px-4">
            <div>
              <p className="text-sm font-medium text-gray-800">YouTube</p>
              <p className="text-xs text-gray-400">{user.has_youtube ? "Connected" : "Not connected"}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${user.has_youtube ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-500"}`}>
                {user.has_youtube ? "Active" : "Not set up"}
              </span>
              {!user.has_youtube && (
                <button
                  onClick={async () => {
                    const token = await getToken();
                    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/youtube/url`, {
                      headers: { Authorization: `Bearer ${token}` },
                    });
                    if (res.ok) {
                      const { url } = await res.json();
                      window.location.href = url;
                    }
                  }}
                  className="text-xs px-3 py-1 bg-red-600 text-white rounded-full font-medium hover:bg-red-700 transition"
                >
                  Connect
                </button>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-gray-900 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800 transition disabled:opacity-60"
        >
          <Save size={14} />
          {saved ? "Saved!" : saving ? "Saving..." : "Save preferences"}
        </button>
      </div>
    </div>
  );
}
