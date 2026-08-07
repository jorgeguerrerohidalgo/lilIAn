"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";
import { MatterStatusBadge, UrgencyBadge } from "@/components/ui";
import type { MatterStatus, UrgencyLevel } from "@/components/ui";
import { getApiUrl } from "../lib/api";


const API_URL = getApiUrl();

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  status: string;
  urgency: string;
  client_id: number | null;
  created_at: string;
}

interface Client {
  id: number;
  name: string;
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

function PlusIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function BriefcaseIcon({ className = "w-12 h-12" }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-2 4.166a2.25 2.25 0 01-2.155 2.154H7.911a2.25 2.25 0 01-2.154-2.155l.917-4.166m-1.173-2.833V3.75a2.25 2.25 0 012.25-2.25h9.75a2.25 2.25 0 012.25 2.25v1.833m-1.173-2.833l-1.173 2.833m1.173 2.833v8.25M18 18H6a2.25 2.25 0 01-2.25-2.25V6.75A2.25 2.25 0 013.75 4.5h16.5A2.25 2.25 0 0122.5 6.75v8.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

export default function MattersPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [clients, setClients] = useState<Record<number, Client>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/auth/login";
      return;
    }

    fetch(`${API_URL}/api/v1/matters`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then(async (data) => {
        setMatters(data);
        const clientIds = [...new Set<number>(data.filter((m: Matter) => m.client_id).map((m: Matter) => m.client_id as number))];
        const clientPromises = clientIds.map((clientId: number) =>
          fetch(`${API_URL}/api/v1/clients/${clientId}`, {
            headers: { Authorization: `Bearer ${token}` },
          }).then((res) => res.json())
        );
        const clientResults = await Promise.all(clientPromises);
        const clientMap: Record<number, Client> = {};
        clientResults.forEach((client: Client) => {
          clientMap[client.id] = client;
        });
        setClients(clientMap);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold text-ink tracking-tight">
            Casos
          </h1>
          <p className="text-ink/60 mt-1">
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

      {/* Cases List */}
      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-4 border-border border-t-coral rounded-full animate-spin" />
          </div>
        ) : matters.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <div className="w-16 h-16 bg-soft rounded-2xl flex items-center justify-center mx-auto mb-4 text-ink/30">
              <BriefcaseIcon className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-medium text-ink mb-2">
              No tienes casos aún
            </h3>
            <p className="text-ink/60 mb-6 max-w-sm mx-auto">
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
          <div className="divide-y divide-border">
            {matters.map((matter) => (
              <Link
                key={matter.id}
                href={`/matters/${matter.id}`}
                className="flex items-center justify-between px-6 py-4 hover:bg-soft transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-medium text-ink truncate group-hover:text-coral transition-colors">
                      {matter.title}
                    </h3>
                    <MatterStatusBadge status={matter.status as MatterStatus} />
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-ink/60">
                      {matterTypeLabels[matter.matter_type] || matter.matter_type}
                    </span>
                    {matter.client_id && clients[matter.client_id] && (
                      <>
                        <span className="text-ink/30">•</span>
                        <span className="text-ink/60">
                          {clients[matter.client_id].name}
                        </span>
                      </>
                    )}
                    <span className="text-ink/30">•</span>
                    <span className="text-ink/40">
                      {new Date(matter.created_at).toLocaleDateString("es-CL", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })}
                    </span>
                    {(matter.urgency === "high" || matter.urgency === "urgent") && (
                      <>
                        <span className="text-ink/30">•</span>
                        <UrgencyBadge level={matter.urgency as UrgencyLevel} />
                      </>
                    )}
                  </div>
                </div>
                <div className="text-ink/30 group-hover:text-coral transition-colors">
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
