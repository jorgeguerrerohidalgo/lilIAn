import Link from "next/link";
import { Button } from "@/components/ui";
import { Card } from "@/components/ui";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-soft to-cream">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <header className="flex items-center justify-between mb-16">
          <Link href="/" className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-lg">
              <span className="text-3xl font-heading font-bold text-white">L</span>
            </div>
            <div>
              <h1 className="text-2xl font-heading font-bold text-ink tracking-tight">
                lil<span className="text-coral">I</span>An
              </h1>
              <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI v2</p>
            </div>
          </Link>
          <nav className="flex gap-3">
            <Link href="/auth/login">
              <Button variant="ghost">Iniciar sesión</Button>
            </Link>
            <Link href="/auth/register">
              <Button variant="primary">Registrarse</Button>
            </Link>
          </nav>
        </header>

        <section className="py-20 text-center">
          <h2 className="text-4xl md:text-5xl font-heading font-bold text-ink mb-6 tracking-tight">
            Revisor legal inteligente de documentos
          </h2>
          <p className="text-xl text-ink/60 mb-8 max-w-2xl mx-auto">
            Analiza contratos, detecta riesgos y prepárate para decisiones legales
            con el apoyo de inteligencia artificial especializada en derecho chileno.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/auth/register">
              <Button variant="primary" size="lg">
                Comenzar gratis
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="secondary" size="lg">
                Ya tengo cuenta
              </Button>
            </Link>
          </div>
        </section>

        <section className="py-16 grid md:grid-cols-3 gap-6">
          <Card className="text-center p-6">
            <div className="w-12 h-12 bg-blue-pale rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.25a2.25 2.25 0 00-2.25-2.25H5a2.25 2.25 0 00-2.25 2.25v10.5a2.25 2.25 0 002.25 2.25h14.5a2.25 2.25 0 002.25-2.25v-2.25" />
              </svg>
            </div>
            <h3 className="text-xl font-heading font-bold text-ink mb-2">Análisis documental</h3>
            <p className="text-ink/60">Sube contratos y documentos para recibir un análisis preliminar estructurado.</p>
          </Card>

          <Card className="text-center p-6">
            <div className="w-12 h-12 bg-amber-pale rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-amber" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-xl font-heading font-bold text-ink mb-2">Detección de riesgos</h3>
            <p className="text-ink/60">Identifica cláusulas riesgosas y recibe recomendaciones preliminares.</p>
          </Card>

          <Card className="text-center p-6">
            <div className="w-12 h-12 bg-green-pale rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-xl font-heading font-bold text-ink mb-2">Consulta contextual</h3>
            <p className="text-ink/60">Pregunta sobre tus documentos y recibe respuestas basadas en su contenido.</p>
          </Card>
        </section>

        <section className="py-16 text-center">
          <Card className="bg-ink text-white p-8">
            <p className="text-lg font-medium">
              Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.
            </p>
          </Card>
        </section>

        <footer className="py-8 text-center text-ink/40 text-sm">
          <p>lilIAn - Plataforma legaltech chilena asistida por IA</p>
        </footer>
      </div>
    </main>
  );
}
