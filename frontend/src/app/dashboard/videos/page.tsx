"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { Youtube, Clock, CheckCircle, XCircle, Loader } from "lucide-react";
import clsx from "clsx";

const STATUS_COLOR: Record<string, string> = {
  done: "text-green-600 bg-green-50",
  failed: "text-red-600 bg-red-50",
  preview_ready: "text-blue-600 bg-blue-50",
  processing: "text-yellow-600 bg-yellow-50",
  pending: "text-gray-500 bg-gray-100",
};

const STATUS_LABEL: Record<string, string> = {
  done: "Done",
  failed: "Failed",
  preview_ready: "Awaiting approval",
  processing: "Processing",
  pending: "Queued",
  uploading: "Uploading",
  cancelled: "Cancelled",
};

export default function VideosPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setJobs(await res.json());
      setLoading(false);
    })();
  }, []);

  if (loading) return <div className="flex justify-center h-64 items-center"><div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-900 border-t-transparent" /></div>;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">My videos</h1>
        <p className="text-sm text-gray-400 mt-1">{jobs.length} videos total</p>
      </div>

      {jobs.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
          <p className="text-gray-400 text-sm">No videos yet. Create your first one!</p>
          <button
            onClick={() => router.push("/dashboard")}
            className="mt-4 text-sm bg-gray-900 text-white px-5 py-2.5 rounded-xl hover:bg-gray-800 transition"
          >
            Create a video
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <button
              key={job.id}
              onClick={() => router.push(`/dashboard/jobs/${job.id}`)}
              className="w-full bg-white rounded-2xl border border-gray-100 p-5 text-left hover:border-gray-200 transition flex items-center gap-4"
            >
              <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center flex-shrink-0">
                <Youtube size={18} className="text-gray-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 text-sm truncate">
                  {job.script?.title || job.topic}
                </p>
                <p className="text-xs text-gray-400 mt-0.5 truncate">{job.topic}</p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className={clsx("text-xs px-2.5 py-1 rounded-full font-medium", STATUS_COLOR[job.status] || "text-gray-500 bg-gray-100")}>
                  {STATUS_LABEL[job.status] || job.status}
                </span>
                <span className="text-xs text-gray-400">
                  {new Date(job.created_at).toLocaleDateString()}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
