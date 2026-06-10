"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { CheckCircle, XCircle, Clock, Youtube, ExternalLink, ThumbsUp, RotateCcw } from "lucide-react";
import clsx from "clsx";

const STATUS_STEPS = [
  { key: "pending", label: "Queued" },
  { key: "processing", label: "Generating" },
  { key: "preview_ready", label: "Preview ready" },
  { key: "uploading", label: "Uploading" },
  { key: "done", label: "Done" },
];

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [job, setJob] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  const fetchJob = async () => {
    const token = await getToken();
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setJob(await res.json());
    setLoading(false);
  };

  useEffect(() => {
    fetchJob();
    // Poll every 4 seconds while processing
    const interval = setInterval(() => {
      if (job?.status && ["done", "failed", "preview_ready", "cancelled"].includes(job.status)) {
        clearInterval(interval);
        return;
      }
      fetchJob();
    }, 4000);
    return () => clearInterval(interval);
  }, [job?.status]);

  const handleApprove = async () => {
    setApproving(true);
    const token = await getToken();
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ platforms: job.platform }),
    });
    await fetchJob();
    setApproving(false);
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-900 border-t-transparent" /></div>;
  if (!job) return <p className="text-gray-500">Job not found.</p>;

  const video = job.videos?.[0];
  const isFailed = job.status === "failed";
  const isDone = job.status === "done";
  const isPreviewReady = job.status === "preview_ready";
  const isProcessing = ["pending", "processing"].includes(job.status);

  const currentStepIndex = STATUS_STEPS.findIndex((s) => s.key === job.status);

  return (
    <div>
      <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-400 hover:text-gray-600 mb-6 flex items-center gap-1">
        ← Back to create
      </button>

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900 truncate">{job.script?.title || job.topic}</h1>
        <p className="text-sm text-gray-400 mt-0.5">{job.topic}</p>
      </div>

      {/* Progress steps */}
      {!isFailed && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6 mb-5">
          <div className="flex items-center justify-between mb-4">
            {STATUS_STEPS.map((step, i) => (
              <div key={step.key} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div className={clsx(
                    "w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all",
                    i < currentStepIndex || isDone
                      ? "bg-gray-900 text-white"
                      : i === currentStepIndex
                        ? "bg-brand-500 text-white animate-pulse"
                        : "bg-gray-100 text-gray-400"
                  )}>
                    {i < currentStepIndex || isDone ? <CheckCircle size={14} /> : i + 1}
                  </div>
                  <p className="text-xs text-gray-400 mt-1.5 text-center w-16">{step.label}</p>
                </div>
                {i < STATUS_STEPS.length - 1 && (
                  <div className={clsx("h-0.5 w-8 mx-1 mb-4 transition-all", i < currentStepIndex || isDone ? "bg-gray-900" : "bg-gray-100")} />
                )}
              </div>
            ))}
          </div>

          {isProcessing && (
            <div>
              <div className="flex justify-between text-xs text-gray-400 mb-1.5">
                <span>{job.current_step || "Processing..."}</span>
                <span>{job.progress}%</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gray-900 rounded-full transition-all duration-500"
                  style={{ width: `${job.progress}%` }}
                />
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
      {isFailed && (
        <div className="bg-red-50 border border-red-100 rounded-2xl p-6 mb-5">
          <div className="flex items-center gap-2 mb-2">
            <XCircle size={18} className="text-red-500" />
            <p className="font-medium text-red-700">Generation failed</p>
          </div>
          <p className="text-sm text-red-500">{job.error_message}</p>
          <button onClick={() => router.push("/dashboard")} className="mt-4 text-sm text-red-600 flex items-center gap-1 hover:underline">
            <RotateCcw size={13} /> Try again with a new job
          </button>
        </div>
      )}

      {/* Preview */}
      {(isPreviewReady || isDone) && video?.video_url && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6 mb-5">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-4">Preview</p>
          <video
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

      {/* Approve button */}
      {isPreviewReady && (
        <button
          onClick={handleApprove}
          disabled={approving}
          className="w-full flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 text-white py-3.5 rounded-xl font-medium text-sm transition disabled:opacity-60"
        >
          {approving ? <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> : <ThumbsUp size={16} />}
          {approving ? "Uploading..." : `Approve and upload to ${job.platform?.join(" + ")}`}
        </button>
      )}

      {/* YouTube link */}
      {isDone && video?.youtube_url && (
        <a
          href={video.youtube_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-700 py-3.5 rounded-xl font-medium text-sm transition mt-4"
        >
          <Youtube size={16} className="text-red-500" />
          View on YouTube
          <ExternalLink size={13} className="text-gray-400" />
        </a>
      )}
    </div>
  );
}
