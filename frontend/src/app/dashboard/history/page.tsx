"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";

const LEVEL_COLOR: Record<string, string> = {
  info: "bg-gray-100 text-gray-600",
  warning: "bg-yellow-50 text-yellow-700",
  error: "bg-red-50 text-red-600",
};

export default function HistoryPage() {
  const { getToken } = useAuth();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await getToken();
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/me/logs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setLogs(await res.json());
      setLoading(false);
    })();
  }, []);

  if (loading) return <div className="flex justify-center h-64 items-center"><div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-900 border-t-transparent" /></div>;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Activity history</h1>
        <p className="text-sm text-gray-400 mt-1">Everything that's happened on your account</p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50">
        {logs.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-12">No activity yet.</p>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="flex items-start gap-4 px-5 py-4">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 ${LEVEL_COLOR[log.level] || LEVEL_COLOR.info}`}>
                {log.action.replace(/_/g, " ")}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-700 truncate">{log.message || "—"}</p>
              </div>
              <p className="text-xs text-gray-400 flex-shrink-0">
                {new Date(log.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
