"use client";
import { useQuery } from "@tanstack/react-query";
import { reviewsApi, classifyApi, Review, Classification } from "@/lib/api";
import { AlertTriangle, CheckCircle, Clock, Star } from "lucide-react";

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: string | number; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-6 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </div>
  );
}

function RiskBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-xs">–</span>;
  const pct = Math.round(score * 100);
  const cls =
    score >= 0.65 ? "bg-red-100 text-red-700" :
    score >= 0.35 ? "bg-amber-100 text-amber-700" :
    "bg-green-100 text-green-700";
  return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cls}`}>{pct}%</span>;
}

export default function Dashboard() {
  const { data: reviewsData } = useQuery({
    queryKey: ["reviews"],
    queryFn: () => reviewsApi.list().then((r) => r.data),
    refetchInterval: 30_000,
  });

  const reviews: Review[] = reviewsData?.items ?? [];
  const total = reviewsData?.total ?? 0;
  const processed = reviews.filter((r) => r.is_processed).length;
  const highRisk = reviews.filter((r) => !r.is_processed).length;

  const recentHighRisk = reviews
    .filter((r) => r.is_processed)
    .slice(0, 5);

  return (
    <div>
      <h1 className="text-2xl font-bold text-brand mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Bewertungen gesamt" value={total} icon={Star} color="bg-brand" />
        <StatCard label="Analysiert" value={processed} icon={CheckCircle} color="bg-green-500" />
        <StatCard label="Ausstehend" value={total - processed} icon={Clock} color="bg-amber-500" />
        <StatCard label="Nicht verarbeitet" value={highRisk} icon={AlertTriangle} color="bg-red-500" />
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-lg mb-4">Neueste Bewertungen</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2 pr-4">Plattform</th>
              <th className="pb-2 pr-4">Rezensent</th>
              <th className="pb-2 pr-4">Sterne</th>
              <th className="pb-2 pr-4">Inhalt</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {reviews.slice(0, 10).map((r) => (
              <tr key={r.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="py-2 pr-4 capitalize">{r.platform}</td>
                <td className="py-2 pr-4">{r.reviewer_name ?? "Anonym"}</td>
                <td className="py-2 pr-4">{"★".repeat(r.rating ?? 0)}</td>
                <td className="py-2 pr-4 text-gray-600 max-w-xs truncate">{r.content}</td>
                <td className="py-2">
                  {r.is_processed ? (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">Analysiert</span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">Ausstehend</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
