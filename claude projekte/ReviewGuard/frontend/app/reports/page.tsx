"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api";
import { Download, FileText } from "lucide-react";

export default function ReportsPage() {
  const [format, setFormat] = useState<"pdf" | "csv" | "json">("pdf");
  const [minRisk, setMinRisk] = useState(0);
  const [lastReport, setLastReport] = useState<{ id: string; format: string } | null>(null);

  const { data: reports } = useQuery({
    queryKey: ["reports"],
    queryFn: () => reportsApi.list().then((r) => r.data),
  });

  const generateMutation = useMutation({
    mutationFn: () => reportsApi.generate({ format, min_risk_score: minRisk || undefined }),
    onSuccess: (res) => setLastReport({ id: res.data.report_id, format }),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-brand mb-6">Berichte</h1>

      <div className="bg-white rounded-xl shadow-sm p-6 mb-6 max-w-lg">
        <h2 className="font-semibold mb-4">Neuen Bericht erstellen</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Format</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={format}
              onChange={(e) => setFormat(e.target.value as typeof format)}
            >
              <option value="pdf">PDF (Druckbar)</option>
              <option value="csv">CSV (Excel)</option>
              <option value="json">JSON (Export)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Mindest-Risikoscore: {Math.round(minRisk * 100)}%
            </label>
            <input
              type="range" min={0} max={1} step={0.05}
              value={minRisk}
              onChange={(e) => setMinRisk(Number(e.target.value))}
              className="w-full"
            />
            <p className="text-xs text-gray-400 mt-1">
              0% = alle Bewertungen; höher = nur risikoreiche
            </p>
          </div>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="w-full bg-brand text-white rounded-lg py-2 hover:bg-brand-light disabled:opacity-50"
          >
            {generateMutation.isPending ? "Erstelle Bericht…" : "Bericht erstellen"}
          </button>

          {lastReport && (
            <a
              href={reportsApi.downloadUrl(lastReport.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-indigo-600 hover:underline"
            >
              <Download className="w-4 h-4" />
              Letzten Bericht herunterladen (.{lastReport.format})
            </a>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold mb-4">Bisherige Berichte</h2>
        {reports && reports.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2 pr-4">Erstellt am</th>
                <th className="pb-2 pr-4">Format</th>
                <th className="pb-2">Download</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{new Date(r.created_at).toLocaleString("de-DE")}</td>
                  <td className="py-2 pr-4 uppercase font-mono text-xs">{r.format}</td>
                  <td className="py-2">
                    <a
                      href={reportsApi.downloadUrl(r.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:underline flex items-center gap-1"
                    >
                      <Download className="w-3 h-3" /> Herunterladen
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-gray-400">Noch keine Berichte erstellt.</p>
        )}
      </div>
    </div>
  );
}
