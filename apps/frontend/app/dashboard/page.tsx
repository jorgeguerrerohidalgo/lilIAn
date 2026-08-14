"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";
import { StatCard } from "@/components/ui";
import { Badge } from "@/components/ui";
import { MatterStatusBadge, UrgencyBadge } from "@/components/ui";
import type { MatterStatus, UrgencyLevel } from "@/components/ui";
import { getApiUrl } from "@/lib/api";


const API_URL = getApiUrl();

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  status: string;
  urgency: string;
  created_at: string;
}

const matterTypeLabels: Record<string, string> = {
  contract_review: "Revisión de contrato",
  lease: "Arriendo",
  labor: "Laboral",
  company: "Empresas",
  data_protection: "Protección de datos",
  consumer: "Consumidor",
  family: "Familia",
  debt: "Deudas",
  other: "Otro",
};

// Icons
function PlusIcon() {
  return (
    <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function BriefcaseIcon({ className = "w-12 h-12" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-2 4.166a2.25 2.25 0 01-2.155 2.154H7.911a2.25 2.25 0 01-2.154-2.155l.917-4.166m-1.173-2.833V3.75a2.25 2.25 0 012.25-2.25h9.75a2.25 2.25 0 012.25 2.25v1.833m-1.173-2.833l-1.173 2.833m1.173 2.833v8.25M18 18H6a2.25 2.25 0 01-2.25-2.25V6.75A2.25 2.25 0 013.75 4.5h16.5A2.25 2.25 0 0122.5 6.75v8.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6" />
    </svg>
  );
}

function DocumentIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <svg aria-hidden="true" className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg aria-hidden="true" className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.496c.866-2.297 2.792-3.503 4.303-3.496l1.5-.001c1.5 0 3.104.523 4.303 2.496M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

export default function DashboardPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    fetch(`${API_URL}/api/v1/matters`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setMatters(data || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const totalMatters = matters.length;
  const inProgress = matters.filter(
    (m) => m.status === "processing" || m.status === "in_progress"
  ).length;
  const readyForReview = matters.filter((m) => m.status === "analysis_ready").length;
  const urgent = matters.filter(
    (m) => m.urgency === "high" || m.urgency === "urgent"
  ).length;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-semibold text-foreground tracking-tight">
            Mis casos
          </h1>
          <p className="text-secondary mt-1">
            Gestiona tus casos legales y documentos
          </p>
        </div>
        <Link href="/matters/new">
          <Button variant="primary" size="lg">
            <PlusIcon />
            Nuevo caso
          </Button>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total casos"
          value={totalMatters}
          icon={<BriefcaseIcon className="w-8 h-8" />}
        />
        <StatCard
          label="En proceso"
          value={inProgress}
          icon={<DocumentIcon className="w-8 h-8" />}
        />
        <StatCard
          label="Listos para revisión"
          value={readyForReview}
          icon={<CheckCircleIcon />}
        />
        <StatCard
          label="Urgentes"
          value={urgent}
          icon={<AlertIcon />}
        />
      </div>

      {/* Cases List */}
      <Card padding="none" elevated>
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-heading font-semibold text-lg text-foreground">Casos recientes</h2>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin" />
          </div>
        ) : matters.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4 text-secondary">
              <BriefcaseIcon className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-medium text-foreground mb-2">
              No tienes casos aún
            </h3>
            <p className="text-secondary mb-6 max-w-sm mx-auto">
              Comienza creando tu primer caso legal para gestionar documentos y análisis
            </p>
            <Link href="/matters/new">
              <Button variant="primary">
                <PlusIcon />
                Crear primer caso
              </Button>
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {matters.map((matter) => (
              <Link
                key={matter.id}
                href={`/matters/${matter.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-muted/50 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-medium text-foreground truncate group-hover:text-primary transition-colors">
                      {matter.title}
                    </h3>
                    <MatterStatusBadge status={matter.status as MatterStatus} />
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-secondary">
                      {matterTypeLabels[matter.matter_type] || matter.matter_type}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-400">
                      {new Date(matter.created_at).toLocaleDateString("es-CL", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                    {(matter.urgency === "high" || matter.urgency === "urgent") && (
                      <>
                        <span className="text-slate-300">•</span>
                        <UrgencyBadge level={matter.urgency as UrgencyLevel} />
                      </>
                    )}
                  </div>
                </div>
                <div className="text-slate-400 group-hover:text-primary transition-colors">
                  <ChevronRightIcon />
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
