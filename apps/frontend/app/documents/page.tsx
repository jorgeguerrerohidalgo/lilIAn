"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui";
import { Button } from "@/components/ui";
import { EmptyState } from "@/components/ui";

interface DocumentRow {
  id: number;
  matter_id: number;
  matter_title: string;
  original_filename: string;
  status: string;
  file_size: number | null;
  mime_type: string | null;
  created_at: string;
  processed_at: string | null;
}

interface Matter {
  id: number;
  title: string;
}

function formatBytes(b: number | null): string {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function DocumentIcon({ className = "w-7 h-7" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
    </svg>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);

  useEffect(() => {
    void loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      // Aggregating documents across matters: the backend doesn't expose
      // a flat /documents endpoint yet, so we fan out per matter and
      // flatten. With realistic numbers (≤ 100 matters/tenant) this is
      // fast enough; once volume grows we'll add a proper index endpoint.
      const mattersRes = await fetch("/api/v1/matters");
      if (!mattersRes.ok) {
        setRows([]);
        return;
      }
      const matters: Matter[] = await mattersRes.json();
      const out: DocumentRow[] = [];
      await Promise.all(
        matters.map(async (m) => {
          const res = await fetch(`/api/v1/documents/matters/${m.id}/documents`);
          if (!res.ok) return;
          const docs = await res.json();
          for (const d of docs) {
            out.push({
              id: d.id,
              matter_id: m.id,
              matter_title: m.title,
              original_filename: d.original_filename,
              status: d.status,
              file_size: d.file_size ?? null,
              mime_type: d.mime_type ?? null,
              created_at: d.created_at,
              processed_at: d.processed_at ?? null,
            });
          }
        }),
      );
      // Sort by creation time, newest first.
      out.sort((a, b) => b.created_at.localeCompare(a.created_at));
      setRows(out);
    } finally {
      setLoading(false);
    }
  }

  const handleSeedSample = async () => {
    setSeeding(true);
    setSeedError(null);
    try {
      const res = await fetch("/api/v1/matters/sample-contract", {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          data.detail || "No pudimos crear el contrato de ejemplo",
        );
      }
      const data = await res.json();
      router.push(`/matters/${data.matter_id}`);
    } catch (err: unknown) {
      const message = err instanceof Error
        ? err.message
        : "No pudimos crear el contrato de ejemplo";
      setSeedError(message);
      setSeeding(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-heading font-bold text-ink tracking-tight">
          Documentos
        </h1>
        <p className="text-ink/60 mt-1">
          Todos los archivos que has subido, agrupados por caso.
        </p>
      </div>

      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-4 border-border border-t-coral rounded-full animate-spin" />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<DocumentIcon />}
            title="Aún no has subido documentos"
            description="Los archivos se adjuntan a un caso y aparecen aquí. También puedes probar con un contrato de ejemplo pre-cargado."
            action={
              <Button
                type="button"
                variant="primary"
                size="lg"
                loading={seeding}
                disabled={seeding}
                onClick={handleSeedSample}
              >
                {seeding ? "Creando…" : "Probar con un contrato de ejemplo"}
              </Button>
            }
            secondary={
              <Link href="/matters/new">
                <Button variant="outline" className="w-full">
                  Crear un caso para subir archivos
                </Button>
              </Link>
            }
          />
        ) : (
          <div className="divide-y divide-border">
            {rows.map((d) => (
              <Link
                key={d.id}
                href={`/matters/${d.matter_id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-soft transition-colors group"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-soft flex items-center justify-center text-ink/40">
                    <DocumentIcon className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-ink truncate group-hover:text-coral transition-colors">
                      {d.original_filename}
                    </p>
                    <p className="text-xs text-ink/50 truncate">
                      {d.matter_title} · {formatBytes(d.file_size)} ·{" "}
                      {new Date(d.created_at).toLocaleDateString("es-CL", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-xs font-semibold uppercase tracking-wider px-3 py-1 rounded-full ${
                    d.status === "analyzed" || d.status === "processed"
                      ? "bg-emerald-50 text-emerald-700"
                      : d.status === "failed"
                        ? "bg-coral/10 text-coral-dark"
                        : "bg-amber-50 text-amber-800"
                  }`}
                >
                  {d.status === "analyzed"
                    ? "Analizado"
                    : d.status === "processed"
                      ? "Procesado"
                      : d.status === "failed"
                        ? "Falló"
                        : "En proceso"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </Card>

      {seedError && (
        <p
          role="alert"
          aria-live="assertive"
          className="text-sm text-coral-dark"
        >
          {seedError}
        </p>
      )}
    </div>
  );
}
