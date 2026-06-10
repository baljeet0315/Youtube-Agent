import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

// Attach Clerk token to every request
api.interceptors.request.use(async (config) => {
  try {
    const { getToken } = await import("@clerk/nextjs/client" as any);
    const token = await getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  } catch {}
  return config;
});

export default api;

// ── Job types ──────────────────────────────────────────────────

export interface CreateJobParams {
  topic: string;
  style: string;
  narration_style?: string;
  voice_id?: string;
  duration: number;
  platform: string[];
  privacy: string;
  tags?: string[];
}

export interface Job {
  id: string;
  topic: string;
  style: string;
  narration_style?: string;
  duration: number;
  platform: string[];
  privacy: string;
  status: string;
  progress: number;
  current_step?: string;
  error_message?: string;
  script?: any;
  videos?: Video[];
  created_at: string;
}

export interface Video {
  id: string;
  title?: string;
  description?: string;
  tags?: string[];
  video_url?: string;
  audio_url?: string;
  youtube_url?: string;
  instagram_url?: string;
  youtube_status?: string;
  created_at: string;
}

// ── API calls ──────────────────────────────────────────────────

export const createJob = (params: CreateJobParams) =>
  api.post("/jobs", params).then((r) => r.data);

export const getJob = (id: string) =>
  api.get(`/jobs/${id}`).then((r) => r.data);

export const getJobs = () =>
  api.get("/jobs").then((r) => r.data);

export const approveJob = (id: string, platforms: string[]) =>
  api.post(`/jobs/${id}/approve`, { platforms }).then((r) => r.data);

export const cancelJob = (id: string) =>
  api.post(`/jobs/${id}/cancel`).then((r) => r.data);

export const getMe = () =>
  api.get("/users/me").then((r) => r.data);

export const getLogs = () =>
  api.get("/users/me/logs").then((r) => r.data);
