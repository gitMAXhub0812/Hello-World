"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewsApi, classifyApi, Review, Classification } from "@/lib/api";
import { Plus, RefreshCw, Trash2, ChevronDown } from "lucide-react";

const DRAFT_TYPE_LABELS = {
  platform_report: "Plattform-Meldung",
  owner_response: "Antwort-Entwurf",
  legal_notice: "Anwalt-Vorlage",
} as const;

function RiskBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.65 ? "bg-red-500" : score >= 0.35 ? "bg-amber-400" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold w-8 text-right">{pct}%</span>
    </div>
  );
}

function AddReviewModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    platform: "jameda",
    reviewer_name: "",
    rating: 1,
    content: "",
    url: "",
  });

  const mutation = useMutation({
    mutationFn: () => reviewsApi.create(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["reviews"] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-lg">
        <h2 className="text-xl font-bold mb-6">Bewertung hinzufügen</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Plattform</label>
            <select
              className="w-full border rounded-lg px-3 py-2"
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
            >
              <option value="jameda">Jameda</option>
              <option value="google">Google</option>
              <option value="manual">Manuell / Screenshot</option>
              <option value="other">Sonstige</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Rezensent (optional)</label>
            <input
              className="w-full border rounded-lg px-3 py-2"
              value={form.reviewer_name}
              onChange={(e) => setForm({ ...form, reviewer_name: e.target.value })}
              placeholder="Anonym"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Sternebewertung</label>
            <input
              type="number" min={1} max={5}
              className="w-full border rounded-lg px-3 py-2"
              value={form.rating}
              onChange={(e) => setForm({ ...form, rating: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Bewertungstext *</label>
            <textarea
              rows={5}
              className="w-full border rounded-lg px-3 py-2"
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="Vollständigen Bewertungstext einfügen..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">URL (optional)</label>
            <input
              className="w-full border rounded-lg px-3 py-2"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="https://..."
            />
          </div>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border rounded-lg px-4 py-2 hover:bg-gray-50">
            Abbrechen
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.content || mutation.isPending}
            className="flex-1 bg-brand text-white rounded-lg px-4 py-2 hover:bg-brand-light disabled:opacity-50"
          >
            {mutation.isPending ? "Wird gespeichert…" : "Speichern & Analysieren"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ReviewRow({ review }: { review: Review }) {
  const [expanded, setExpanded] = useState(false);
  const [cls, setCls] = useState<Classification | null>(null);
  const [draftType, setDraftType] = useState<keyof typeof DRAFT_TYPE_LABELS>("platform_report");
  const [draft, setDraft] = useState<string | null>(null);
  const [loadingCls, setLoadingCls] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const qc = useQueryClient();

  const handleExpand = async () => {
    setExpanded((v) => !v);
    if (!cls && review.is_processed) {
      setLoadingCls(true);
      try {
        const res = await classifyApi.get(review.id);
        setCls(res.data);
      } catch { /* not yet classified */ }
      setLoadingCls(false);
    }
  };

  const handleReclassify = async () => {
    setLoadingCls(true);
    const res = await classifyApi.classify(review.id);
    setCls(res.data);
    qc.invalidateQueries({ queryKey: ["reviews"] });
    setLoadingCls(false);
  };

  const handleDraft = async () => {
    setLoadingDraft(true);
    const res = await classifyApi.createDraft(review.id, draftType);
    setDraft(res.data.content);
    setLoadingDraft(false);
  };

  const deleteMutation = useMutation({
    mutationFn: () => reviewsApi.delete(review.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });

  const riskColor = cls
    ? cls.overall_risk_score >= 0.65 ? "border-l-red-500"
    : cls.overall_risk_score >= 0.35 ? "border-l-amber-400"
    : "border-l-green-500"
    : "border-l-gray-200";

  return (
    <div className={`bg-white rounded-xl shadow-sm border-l-4 ${riskColor} mb-3`}>
      <div
        className="flex items-center gap-4 p-4 cursor-pointer hover:bg-gray-50 rounded-xl"
        onClick={handleExpand}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold px-2 py-0.5 bg-brand/10 text-brand rounded-full capitalize">
              {review.platform}
            </span>
            {review.reviewer_name && (
              <span className="text-xs text-gray-500">{review.reviewer_name}</span>
            )}
            {review.rating && (
              <span className="text-xs text-amber-500">{"★".repeat(review.rating)}</span>
            )}
          </div>
          <p className="text-sm text-gray-700 truncate">{review.content}</p>
        </div>
        {cls && <RiskBar score={cls.overall_risk_score} />}
        {!review.is_processed && (
          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">Ausstehend</span>
        )}
        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t pt-4 space-y-4">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{review.content}</p>

          {review.url && (
            <a href={review.url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline">
              Original öffnen ↗
            </a>
          )}

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={handleReclassify}
              disabled={loadingCls}
              className="flex items-center gap-1 text-xs px-3 py-1.5 bg-brand text-white rounded-lg hover:bg-brand-light"
            >
              <RefreshCw className="w-3 h-3" /> {loadingCls ? "Analysiere…" : "KI-Analyse"}
            </button>
            <button
              onClick={() => deleteMutation.mutate()}
              className="flex items-center gap-1 text-xs px-3 py-1.5 bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
            >
              <Trash2 className="w-3 h-3" /> Löschen
            </button>
          </div>

          {loadingCls && <p className="text-xs text-gray-400">Analyse läuft…</p>}

          {cls && (
            <div className="bg-gray-50 rounded-lg p-4 space-y-3">
              <div className="flex flex-wrap gap-2">
                {cls.is_insult && <span className="badge-red">Beleidigung {Math.round((cls.insult_confidence ?? 0)*100)}%</span>}
                {cls.is_spam   && <span className="badge-amber">Spam {Math.round((cls.spam_confidence ?? 0)*100)}%</span>}
                {cls.is_fake   && <span className="badge-red">Fake {Math.round((cls.fake_confidence ?? 0)*100)}%</span>}
                {cls.has_false_claims && <span className="badge-red">Falschaussage {Math.round((cls.false_claims_confidence ?? 0)*100)}%</span>}
                {cls.is_toxic  && <span className="badge-red">Toxisch {Math.round((cls.toxic_confidence ?? 0)*100)}%</span>}
              </div>
              {cls.reasoning && <p className="text-xs text-gray-600">{cls.reasoning}</p>}
              {cls.flagged_phrases && cls.flagged_phrases.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1">Markierte Stellen:</p>
                  <ul className="text-xs text-red-700 list-disc list-inside">
                    {cls.flagged_phrases.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}

          {cls && (
            <div className="space-y-2">
              <p className="text-xs font-semibold">Entwurf generieren:</p>
              <div className="flex gap-2">
                <select
                  className="flex-1 text-xs border rounded-lg px-2 py-1.5"
                  value={draftType}
                  onChange={(e) => setDraftType(e.target.value as typeof draftType)}
                >
                  {Object.entries(DRAFT_TYPE_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
                <button
                  onClick={handleDraft}
                  disabled={loadingDraft}
                  className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  {loadingDraft ? "Generiere…" : "Erstellen"}
                </button>
              </div>
              {draft && (
                <textarea
                  readOnly
                  rows={8}
                  className="w-full text-xs border rounded-lg px-3 py-2 bg-white"
                  value={draft}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  const [showModal, setShowModal] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["reviews"],
    queryFn: () => reviewsApi.list().then((r) => r.data),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-brand">Bewertungen</h1>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-brand text-white px-4 py-2 rounded-lg hover:bg-brand-light"
        >
          <Plus className="w-4 h-4" /> Bewertung hinzufügen
        </button>
      </div>

      {isLoading && <p className="text-gray-400">Lade…</p>}

      {data?.items.map((r) => <ReviewRow key={r.id} review={r} />)}

      {showModal && <AddReviewModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
