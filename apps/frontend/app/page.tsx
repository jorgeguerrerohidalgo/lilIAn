import Link from "next/link";
import Image from "next/image";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      <div className="container mx-auto px-4 py-16">
        <header className="flex items-center justify-between mb-16">
          <div className="flex items-center gap-4">
            <Image src="/images/logo.png" alt="lilIAn Logo" width={60} height={60} priority />
            <div>
              <h1 className="text-3xl font-bold text-primary-700">lilIAn</h1>
              <p className="text-gray-600 text-sm">Plataforma legaltech chilena</p>
            </div>
          </div>
          <nav className="flex gap-4">
            <Link
              href="/auth/login"
              className="px-4 py-2 text-primary-600 hover:text-primary-700 font-medium"
            >
              Iniciar sesión
            </Link>
            <Link
              href="/auth/register"
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              Registrarse
            </Link>
          </nav>
        </header>

        <section className="py-20 text-center">
          <h2 className="text-5xl font-bold text-gray-900 mb-6">
            Revisor legal inteligente de documentos
          </h2>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Analiza contratos, detecta riesgos y prepárate para decisiones legales
            con el apoyo de inteligencia artificial especializada en derecho chileno.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/auth/register"
              className="px-8 py-4 bg-primary-600 text-white text-lg rounded-lg hover:bg-primary-700"
            >
              Comenzar gratis
            </Link>
            <Link
              href="/auth/login"
              className="px-8 py-4 border-2 border-primary-600 text-primary-600 text-lg rounded-lg hover:bg-primary-50"
            >
              Ya tengo cuenta
            </Link>
          </div>
        </section>

        <section className="py-16 grid md:grid-cols-3 gap-8">
          <div className="p-6 bg-white rounded-xl shadow-sm border">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-2">Análisis documental</h3>
            <p className="text-gray-600">Sube contratos y documentos para recibir un análisis preliminar estructurado.</p>
          </div>

          <div className="p-6 bg-white rounded-xl shadow-sm border">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-2">Detección de riesgos</h3>
            <p className="text-gray-600">Identifica cláusulas riesgosas y recibe recomendaciones preliminares.</p>
          </div>

          <div className="p-6 bg-white rounded-xl shadow-sm border">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-2">Consulta contextual</h3>
            <p className="text-gray-600">Pregunta sobre tus documentos y recibe respuestas basadas en su contenido.</p>
          </div>
        </section>

        <section className="py-16 text-center">
          <div className="bg-primary-50 rounded-2xl p-8">
            <p className="text-lg text-primary-800 font-medium">
              Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.
            </p>
          </div>
        </section>

        <footer className="py-8 text-center text-gray-500 text-sm">
          <p>lilIAn - Plataforma legaltech chilena asistida por IA</p>
        </footer>
      </div>
    </main>
  );
}
