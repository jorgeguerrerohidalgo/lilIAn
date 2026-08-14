# lilIAn Frontend

> Next.js 14 (App Router) + TypeScript + Tailwind CSS.

Interfaz web de lilIAn. Implementa los flujos de autenticacion, gestion de casos (matters), carga de documentos, visualizacion de analisis con citaciones navegables y busqueda de precedentes.

---

## Tabla de Contenidos

- [Overview](#overview)
- [Stack](#stack)
- [Setup Local](#setup-local)
- [Variables de Entorno](#variables-de-entorno)
- [Comandos](#comandos)
- [Build y Deploy](#build-y-deploy)
- [Estructura de Directorios](#estructura-de-directorios)
- [Accesibilidad (WCAG 2.1 AA)](#accesibilidad-wcag-21-aa)
- [Testing](#testing)
- [Documentacion Tecnica](#documentacion-tecnica)

---

## Overview

- **App Router** de Next.js 14 con React Server Components para data fetching sensible y Client Components para interactividad
- Cliente HTTP centralizado en `lib/api.ts` que inyecta el JWT y maneja refresh
- Modelos compartidos con el backend via tipos exportados en `lib/types/`
- Theming con Tailwind, sin dependencias de UI opinionadas (no shadcn, no MUI): los componentes viven en `components/ui/`
- Cumplimiento WCAG 2.1 AA verificado con auditorias manuales y `eslint-plugin-jsx-a11y`

---

## Stack

| Componente        | Tecnologia                  | Version  |
|-------------------|-----------------------------|----------|
| Framework         | Next.js (App Router)        | 14.2.x   |
| Lenguaje          | TypeScript (strict)         | 5.5.x    |
| UI runtime        | React                       | 18.3.x   |
| Estilos           | Tailwind CSS + PostCSS      | 3.4.x    |
| Iconos            | lucide-react                | 0.400.x  |
| Forms             | react-hook-form + zod       | 7.52 / 3.23 |
| HTTP              | axios                       | 1.7.x    |
| Cookies           | js-cookie                   | 3.0.x    |
| Utilidades        | clsx, tailwind-merge        | 2.x      |
| Lint              | ESLint + eslint-config-next | 8.57.x   |

---

## Setup Local

### Pre-requisitos

- Node.js 20+
- npm 10+ (o pnpm/yarn equivalente)
- Backend de lilIAn corriendo (local o staging)

### Pasos

```bash
# Instalar dependencias
npm install

# Variables de entorno
cp .env.example .env.local
# Editar .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Servidor de desarrollo
npm run dev
```

Abrir http://localhost:3000.

---

## Variables de Entorno

Todas las variables expuestas al cliente deben llevar prefijo `NEXT_PUBLIC_`.

| Variable            | Descripcion                                       |
|---------------------|---------------------------------------------------|
| `NEXT_PUBLIC_API_URL` | URL base del backend (sin slash final)         |

Nada de secretos en el frontend: el backend nunca expone `SUPABASE_SERVICE_KEY` ni claves LLM. El frontend solo consume la API publica con el JWT del usuario.

---

## Comandos

```bash
npm run dev      # servidor de desarrollo (puerto 3000)
npm run build    # build de produccion
npm run start    # servir build local
npm run lint     # ESLint (next/core-web-vitals + a11y)
```

---

## Build y Deploy

### Build local

```bash
npm run build
npm run start
```

El build genera un bundle optimizado y corre los type-checks de TypeScript. Cualquier error TS falla el build.

### Deploy (Vercel — recomendado)

1. Conectar el repositorio a Vercel
2. Configurar `NEXT_PUBLIC_API_URL` con la URL del backend en produccion
3. Deploy automatico en cada push a `main`

Variables de entorno por entorno (Production / Preview / Development) se configuran en el dashboard de Vercel.

### Deploy alternativo

Next.js es portable a cualquier plataforma Node 20+ (Render, Fly, Railway). Configurar:

- Build command: `npm run build`
- Start command: `npm run start`
- Healthcheck: `GET /` debe responder 200

---

## Estructura de Directorios

```
apps/frontend/
├── app/                              # App Router
│   ├── layout.tsx                    # root layout, providers globales
│   ├── page.tsx                      # landing / redirect a /dashboard
│   ├── auth/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── dashboard/
│   │   ├── page.tsx                  # panel principal
│   │   └── clients/                  # gestion de clientes
│   ├── matters/
│   │   ├── page.tsx                  # listado
│   │   ├── new/page.tsx              # alta de caso
│   │   └── [id]/                     # detalle, analisis, documentos
│   ├── documents/                    # carga y gestion documental
│   └── precedents/                   # busqueda de precedentes
├── components/
│   ├── ui/                           # primitives (Button, Input, Modal, ...)
│   ├── layout/                       # nav, header, sidebar
│   ├── chat/                         # chat legal
│   └── matters/                      # vistas y forms especificas de casos
│       ├── matter-card.tsx
│       ├── matter-form.tsx
│       └── document-analysis-view.tsx
├── lib/
│   ├── api.ts                        # cliente HTTP (axios + JWT)
│   ├── auth.ts                       # helpers de sesion
│   ├── hooks/                        # usePoll, useReducedMotion, etc
│   ├── types/                        # tipos compartidos con backend
│   └── utils.ts                      # cn(), formaters
├── public/                           # assets estaticos
├── next.config.js
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json                     # strict: true
├── package.json
└── .env.example
```

---

## Accesibilidad (WCAG 2.1 AA)

lilIAn apunta a WCAG 2.1 AA en todas las pantallas. El trabajo se hace por sprint (S5 cubrio auditoria completa) y se mantiene via lint + revision manual.

### Patrones establecidos

- **Skip to content**: enlace visible al recibir foco, salta la nav repetida
- **Navegacion**: `aria-current="page"` en item activo, `aria-label` en iconos
- **Regiones**: `<header>`, `<main>`, `<nav>`, `<aside>`, `<footer>` semanticos
- **Formularios**: `<fieldset>` + `<legend>` para grupos, `htmlFor` explicito en labels
- **Botones de submit**: `aria-busy` mientras la peticion esta en vuelo
- **Modales**: focus trap, cierre con `Esc`, devolucion de foco al disparador
- **Estados de carga**: spinners con `role="status"` y texto descriptivo
- **Mensajes de error/exito**: `role="alert"` y `aria-live="polite"`
- **SVGs decorativos**: `aria-hidden="true"` (cubierto por sprint 5)
- **Tablas y charts**: caption, scope, navegacion por teclado en visualizaciones
- **Disclosure / acordion**: `aria-expanded` y `aria-controls` sincronizados
- **Tablists**: flechas izquierda/derecha navegan tabs, `aria-selected` refleja estado
- **Reduced motion**: `useReducedMotion` para animaciones no esenciales

### Contraste

- Texto principal sobre fondo blanco: ratio >= 7:1
- Texto UI y placeholders: >= 4.5:1
- Estados focus visibles con outline custom (no solo color)

### Auditoria

- Manual: navegacion solo teclado, screen reader (NVDA / VoiceOver), zoom al 200%
- Lint: `eslint-plugin-jsx-a11y` activado via `eslint-config-next`

Cualquier nuevo componente debe pasar el checklist antes de merge:

- [ ] Foco visible y orden logico del tab
- [ ] Contraste suficiente en todos los estados
- [ ] Roles ARIA solo cuando el HTML semantico no alcanza
- [ ] Mensajes de error anunciados por screen reader
- [ ] Sin trampas de foco (modales devuelven foco al cerrar)
- [ ] Animaciones respetan `prefers-reduced-motion`

---

## Testing

```bash
npm run lint              # ESLint + a11y
npm run build             # type-check + production build
```

### Testing recomendado (Sprint 8+)

- **Unit**: Vitest + Testing Library para componentes puros (hooks, formaters, primitives)
- **Integration**: Testing Library sobre rutas server-rendered con mocks de API
- **E2E**: Playwright sobre flujos criticos (login, alta de caso, carga de documento, revision)
- **Visual regression**: Playwright screenshots a 320 / 768 / 1024 / 1440

Cobertura objetivo: 80% en `lib/` y `components/ui/`.

---

## Documentacion Tecnica

- Arquitectura general: [../../docs/architecture.md](../../docs/architecture.md)
- OpenAPI del backend consumido: [../../docs/openapi.md](../../docs/openapi.md)
- Deploy: [../../DEPLOYMENT.md](../../DEPLOYMENT.md)

---

## Volver

[README raiz](../../README.md)