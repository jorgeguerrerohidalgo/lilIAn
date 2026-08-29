import Link from "next/link";
import { Button } from "@/components/ui";

// Public landing / pricing / agents header. Kept in sync across every
// marketing surface — extracting prevents the duplicate-but-slightly-different
// header that otherwise drifts between routes (already happened on
// `/pricing` once).
export function MarketingHeader() {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 mb-12 md:mb-16">
      <Link href="/" className="flex items-center gap-3 sm:gap-4 min-w-0">
        <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-xl bg-gradient-to-br from-ink to-blue flex items-center justify-center shadow-lg shrink-0">
          <span className="text-2xl sm:text-3xl font-heading font-bold text-white">L</span>
        </div>
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-heading font-bold text-ink tracking-tight">
            lil<span className="text-coral">I</span>An
          </h1>
          <p className="text-[10px] font-bold uppercase tracking-widest text-ink/40">Legal AI v2</p>
        </div>
      </Link>
      <nav className="flex items-center gap-2 sm:gap-3">
        <Link href="/auth/login">
          <Button variant="ghost" size="sm" className="px-3 sm:px-4">
            <span className="hidden sm:inline">Iniciar sesión</span>
            <span className="sm:hidden">Entrar</span>
          </Button>
        </Link>
        <Link href="/auth/register">
          <Button variant="primary" size="sm" className="px-3 sm:px-4 whitespace-nowrap">
            Registrarse
          </Button>
        </Link>
      </nav>
    </header>
  );
}
