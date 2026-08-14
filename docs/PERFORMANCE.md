# Notas de performance

Objetivos de latencia, estrategia de caché, decisiones tomadas y cómo medir.

Regla previa a cualquier optimización: mide primero. La intuición sobre dónde
está el cuello de botella acierta con menos frecuencia de lo que parece, y una
optimización sin medición previa suele añadir complejidad sin mejorar nada.

---

## 1. Latencias objetivo por endpoint

Objetivos expresados en percentil 95 (p95), no en media. La media oculta
precisamente los casos que el usuario percibe como lentos.

### Operaciones síncronas

| Endpoint | Objetivo p95 | Notas |
|----------|--------------|-------|
| `GET /health` | < 50 ms | Sin acceso a base de datos |
| `POST /api/v1/auth/login` | < 400 ms | Dominado por bcrypt, ver más abajo |
| `GET /api/v1/matters` | < 300 ms | Listado paginado |
| `GET /api/v1/matters/{id}` | < 250 ms | Con relaciones precargadas |
| `POST /api/v1/matters` | < 300 ms | Escritura simple |
| `GET /api/v1/clients` | < 250 ms | Listado paginado |
| `GET /api/v1/documents?matter_id=` | < 300 ms | Listado por caso |
| `POST /api/v1/documents` | < 2 s | Subida, sin incluir procesamiento |
| `GET /api/v1/documents/{id}/status` | < 100 ms | Consultado en bucle por polling |

El endpoint de estado tiene el objetivo más estricto de los listados porque se
llama cada 5 segundos por cada documento en procesamiento. Una latencia alta ahí
se multiplica por el número de documentos activos.

`login` es deliberadamente lento: bcrypt está diseñado para serlo. Reducir el
factor de coste para ganar latencia debilita la protección contra fuerza bruta y
no debe hacerse.

### Operaciones asíncronas

Estas no son peticiones HTTP con respuesta inmediata. El objetivo se mide desde
el encolado hasta la finalización.

| Operación | Objetivo p95 | Notas |
|-----------|--------------|-------|
| Procesamiento de documento | < 60 s para 50 páginas | Extracción, chunking y embeddings |
| Análisis de caso | < 90 s | Dominado por la latencia del LLM |
| Búsqueda semántica | < 800 ms | Consulta pgvector más embedding de la query |
| Chat con contexto RAG | < 5 s primer token | Recuperación más generación |

### Presupuesto de un análisis típico

Desglose aproximado de dónde se va el tiempo en un análisis de contrato de 30
páginas:

| Fase | Tiempo aproximado | Porcentaje |
|------|-------------------|------------|
| Extracción de texto | 2 s | 3 % |
| Chunking | 0,2 s | menos del 1 % |
| Generación de embeddings | 8 s | 11 % |
| Recuperación RAG | 1 s | 1 % |
| Llamada al LLM | 55 s | 78 % |
| Validación y persistencia | 4 s | 6 % |

Conclusión operativa: optimizar el chunking no cambia nada perceptible. El 78
por ciento está en la llamada al LLM, y ahí las palancas reales son reducir el
tamaño del prompt, elegir un modelo más rápido o paralelizar cuando el trabajo
es divisible.

---

## 2. Estrategia de caché

### Qué se cachea hoy

**Métricas.** `app/core/metrics.py` cachea los valores agregados durante 60
segundos. Sin ello, cada scrape recalcularía agregaciones sobre toda la base.

**Blacklist de tokens.** Redis, con TTL alineado a la expiración natural del
JWT. No tiene sentido guardar un token revocado más allá del momento en que
habría caducado por sí mismo.

**Deduplicación de documentos.** Hash de contenido persistido, que evita
reprocesar y re-embeber un archivo idéntico ya subido.

### Qué merece cachearse y aún no se cachea

**Contexto legal por área.** Los artículos del Código del Trabajo no cambian
entre peticiones. Recuperarlos en cada análisis es trabajo repetido. Es la
oportunidad de caché con mejor relación beneficio/coste pendiente: TTL largo, de
horas o días, con invalidación explícita al actualizar una fuente legal.

**Embeddings de consultas frecuentes.** Si varios usuarios preguntan lo mismo,
el vector de la consulta es idéntico. Caché con clave por hash de la consulta
normalizada.

**Listados paginados.** TTL corto, de 30 a 60 segundos, con invalidación al
escribir en el recurso. Beneficio moderado; conviene medir antes de añadir la
complejidad de invalidación.

### Qué no debe cachearse nunca

- Resultados de análisis: son específicos del caso y del momento
- Cualquier dato sin la clave de organización incluida en la clave de caché
- URLs firmadas de storage: expiran por diseño y una URL cacheada da un error
  confuso al usuario
- Respuestas que dependen del rol del usuario, salvo que el rol forme parte de
  la clave

### Regla de oro del cacheo multi-tenant

**Toda clave de caché incluye `organization_id`.** Sin excepción.

```python
# Correcto
key = f"legal_context:{organization_id}:{legal_area}:v1"

# Incorrecto: sirve datos de una organización a otra
key = f"legal_context:{legal_area}"
```

Un error de aislamiento en la capa de caché es tan grave como uno en la capa de
base de datos, y bastante más difícil de detectar porque solo aparece bajo
concurrencia.

Incluye también una versión (`:v1`) en la clave. Cambiar el formato de lo
cacheado sin cambiar la clave produce fallos de deserialización en producción
que son molestos de diagnosticar.

### Invalidación

Dos estrategias, según el dato:

- **TTL** para datos que toleran estar algo desactualizados (contexto legal,
  métricas). Es simple y no puede quedar inconsistente de forma permanente.
- **Invalidación explícita al escribir** para datos que deben reflejar cambios
  de inmediato. Más correcto y más frágil: cada nueva ruta de escritura debe
  acordarse de invalidar.

Cuando dudes, usa TTL. Una caché con TTL corto que a veces sirve datos de hace
30 segundos es mejor que una caché con invalidación explícita que a veces sirve
datos de hace tres días porque alguien olvidó un `delete`.

---

## 3. Polling frente a WebSocket

**Decisión: polling.** El seguimiento del procesamiento de documentos se hace
con polling HTTP mediante el hook `usePoll`
(`apps/frontend/lib/hooks/use-poll.ts`).

Configuración actual (`MATTER_DOCUMENT_POLL`):

```ts
intervalMs: 5_000,     // 5 segundos entre intentos
maxAttempts: 60,       // 5 minutos de techo
```

### Por qué polling

**Duración del trabajo.** El procesamiento tarda decenas de segundos. Con un
intervalo de 5 segundos, el usuario percibe el cambio de estado casi
inmediatamente. La latencia adicional frente a un push es irrelevante a esa
escala.

**Sin estado en el servidor.** WebSocket exige conexiones persistentes, lo que
complica el escalado horizontal: con varias réplicas hay que enrutar el mensaje
a la réplica correcta o introducir un bus de mensajes. El polling funciona con
cualquier balanceador sin configuración adicional.

**Compatibilidad con la plataforma.** Railway y Vercel soportan WebSocket, pero
con matices de timeout y de facturación por conexión abierta. El polling usa el
mismo camino HTTP ya probado.

**Coste de implementación.** El endpoint de estado ya existía. WebSocket habría
supuesto gestión de conexiones, reconexión, heartbeat y autenticación del canal.

**Volumen bajo.** Un usuario procesa unos pocos documentos a la vez. El coste
agregado del polling es despreciable a la escala actual.

### Cuándo revisar la decisión

Reconsiderar WebSocket o SSE si se cumple alguna de estas condiciones:

- Se necesita latencia por debajo del segundo en una notificación
- Aparecen funciones colaborativas en tiempo real, como varios abogados editando
  el mismo caso
- El endpoint de estado pasa a representar una fracción significativa del tráfico
- Se implementa streaming de la respuesta del chat, donde SSE es la opción
  natural y más simple que WebSocket

### Reglas de implementación del polling

- Usa siempre `usePoll`. Nunca `setInterval` dentro de un handler de eventos: el
  intervalo sobrevive al desmontaje del componente y produce fugas.
- Todo poll tiene `maxAttempts`. Un bucle sin techo golpea el servidor de forma
  indefinida si el estado nunca cambia.
- El endpoint consultado debe ser barato. `/status` devuelve el mínimo
  imprescindible, no el objeto completo.
- Considera detener el polling cuando la pestaña no está visible
  (`document.visibilityState`).

---

## 4. Patrones de consulta a base de datos

### El problema N+1

Es la causa número uno de lentitud en listados. Al cargar 50 casos y acceder a
`matter.client.name` en cada uno, SQLAlchemy emite 51 consultas: una para los
casos y una por cada cliente.

```python
# Mal: 1 + N consultas
matters = db.query(Matter).filter(Matter.organization_id == org_id).all()
for m in matters:
    print(m.client.name)      # una query por iteración

# Bien: 1 consulta con JOIN
from sqlalchemy.orm import joinedload

matters = (
    db.query(Matter)
    .options(joinedload(Matter.client))
    .filter(Matter.organization_id == org_id)
    .all()
)
```

`joinedload` para relaciones uno a uno y muchos a uno. `selectinload` para uno a
muchos, ya que un JOIN sobre una colección multiplica filas innecesariamente.

### Paginación obligatoria

Ningún listado devuelve resultados sin límite. Una organización con diez mil
documentos convierte un endpoint sin `LIMIT` en un incidente de producción.

```python
query.offset(skip).limit(min(limit, MAX_PAGE_SIZE)).all()
```

Aplica un techo al `limit` recibido del cliente. Un parámetro `?limit=1000000`
no debe poder tumbar el servicio.

Para paginación profunda, `OFFSET` degrada porque la base de datos debe recorrer
y descartar todas las filas anteriores. Con miles de páginas, la paginación por
cursor sobre una columna indexada es la alternativa correcta.

### Índices

Todas las tablas de negocio filtran por `organization_id`, así que esa columna
debe estar indexada en todas ellas. Ya lo están las columnas usadas en filtros
frecuentes: `document_chunks.legal_area`, `law_chunks.legal_area`.

Índices compuestos útiles cuando el patrón de filtrado lo justifica:

```sql
CREATE INDEX idx_matters_org_status ON matters (organization_id, status);
CREATE INDEX idx_documents_matter ON documents (matter_id, created_at DESC);
```

El orden de las columnas importa: PostgreSQL puede usar un índice
`(organization_id, status)` para filtrar solo por `organization_id`, pero no para
filtrar solo por `status`. Pon primero la columna más selectiva y más usada.

Los índices no son gratis: ralentizan las escrituras y ocupan espacio. Añade uno
cuando un `EXPLAIN ANALYZE` demuestre que hace falta, no por precaución.

### Búsqueda vectorial

Las consultas sobre pgvector son las más caras del sistema. Consideraciones:

- Un índice `ivfflat` o `hnsw` sobre la columna de embeddings evita el escaneo
  secuencial. Sin índice, la búsqueda compara contra todos los vectores de la
  tabla.
- Filtra por `organization_id` y `matter_id` **antes** de la comparación
  vectorial. Reducir el conjunto candidato es la optimización más efectiva.
- Limita el número de resultados. Recuperar 100 chunks cuando el prompt solo
  admite 10 es trabajo desperdiciado en la base de datos y en la red.

### Pool de conexiones

Cada réplica del backend y cada worker mantienen su propio pool. Con varias
réplicas es fácil agotar el límite de conexiones del plan de base de datos.

Para Supabase, usa el connection pooler en modo transaction (puerto 6543) en
lugar de la conexión directa (5432) para el backend. Mantén `pool_size`
conservador y dimensiona pensando en el número total de procesos, no en uno
solo.

### Transacciones

Mantenlas cortas. Una transacción abierta durante una llamada al LLM retiene la
conexión durante decenas de segundos y bloquea filas mientras tanto. El patrón
correcto es: leer datos, cerrar la transacción, llamar al LLM, abrir una nueva
transacción para escribir el resultado.

---

## 5. Latencia del LLM

Es el componente dominante del tiempo total. Merece atención específica.

### Factores que la determinan

**Tokens de entrada.** Un prompt mayor implica más tiempo de procesamiento. El
contexto RAG es la parte más voluminosa y la más fácil de recortar.

**Tokens de salida.** Se generan secuencialmente, así que una respuesta larga
tarda proporcionalmente más. Limitar `max_tokens` a lo realmente necesario tiene
efecto directo.

**Modelo elegido.** Los modelos más capaces son más lentos. No todas las tareas
necesitan el mismo: clasificar un documento admite un modelo rápido, analizar un
contrato complejo no.

**Cola del proveedor.** En horas punta la latencia sube por causas ajenas. Esto
no se optimiza, se absorbe con reintentos y con expectativas realistas en la UI.

### Palancas disponibles

**Recortar el contexto.** Antes de aumentar top-k por si acaso, mide si los
fragmentos adicionales cambian el resultado. Suele haber un punto a partir del
cual añadir contexto no mejora la calidad y sí empeora la latencia y el coste.

**Elegir el modelo por tarea.** Clasificación de documentos, extracción de
metadatos y detección de idioma pueden usar un modelo pequeño. El análisis
jurídico de fondo justifica el modelo grande.

**Paralelizar lo divisible.** Analizar cinco documentos independientes en
paralelo divide el tiempo total. Respeta el rate limit del proveedor: la
concurrencia excesiva produce 429 y acaba siendo más lenta por los reintentos.

**Streaming en el chat.** El tiempo hasta el primer token es lo que el usuario
percibe como capacidad de respuesta. Con streaming, una respuesta de 20 segundos
se siente mucho más rápida que sin él, aunque el total sea idéntico.

**Caché de contexto legal.** Ver la sección de caché. Elimina trabajo repetido
antes de la llamada.

### Reintentos

`app/services/retry_utils.py` implementa reintentos con backoff. Dos cuidados:

- Backoff exponencial con jitter. Sin jitter, todos los clientes reintentan a la
  vez tras un incidente y reproducen el pico que causó el fallo.
- Techo de reintentos. Tres suelen bastar. Reintentar indefinidamente ante un
  error permanente, como una API key inválida, desperdicia tiempo y dinero.

### Coste

La latencia y el coste están correlacionados: ambos escalan con los tokens.
Optimizar el tamaño del prompt mejora las dos métricas a la vez, lo que la
convierte en la optimización con mejor retorno del sistema.

---

## 6. Tamaño del bundle en frontend

### Presupuesto

| Tipo de página | JS (gzip) | CSS |
|----------------|-----------|-----|
| Landing y login | < 150 kB | < 30 kB |
| Páginas de aplicación | < 300 kB | < 50 kB |

### Situación actual

Las dependencias de producción son deliberadamente contenidas: `next`, `react`,
`react-hook-form`, `zod`, `axios`, `js-cookie`, `lucide-react`, `clsx` y
`tailwind-merge`. No hay librería de componentes pesada ni framework de
animación.

Puntos de atención:

- **lucide-react.** Importa iconos de forma individual
  (`import { FileText } from "lucide-react"`), nunca el paquete completo. El
  tree-shaking depende de ello.
- **axios.** Añade unos 15 kB gzip. Es asumible por la centralización de
  interceptores en `lib/api.ts`, que aporta manejo uniforme de errores y
  credenciales.
- **Tailwind.** Purga las clases no usadas en build. El CSS resultante escala
  con la variedad de clases empleadas, no con el tamaño del framework.

### Medir

```bash
cd apps/frontend
npm run build          # Next imprime el tamaño por ruta
```

La salida del build muestra First Load JS por ruta. Es la métrica a vigilar: una
ruta que se dispara respecto al resto suele delatar un import pesado añadido sin
querer.

Para analizar en detalle, `@next/bundle-analyzer` da el desglose por módulo.

### Reglas

- Antes de añadir una dependencia, comprueba su peso en bundlephobia y valora si
  el problema se resuelve con 30 líneas propias.
- Componentes pesados que no se ven en la carga inicial (visores, editores,
  gráficos) van con `next/dynamic`.
- Aprovecha los Server Components: el código que corre solo en servidor no llega
  al bundle del cliente.
- Imágenes con `width` y `height` explícitos para evitar layout shift.
  `loading="lazy"` salvo la imagen principal.

### Core Web Vitals

| Métrica | Objetivo |
|---------|----------|
| LCP | < 2,5 s |
| INP | < 200 ms |
| CLS | < 0,1 |
| FCP | < 1,5 s |

---

## 7. Cómo medir

### Principio

Mide antes de optimizar y vuelve a medir después. Una optimización que no se
verifica es una hipótesis con código añadido.

### Backend: perfilado de Python

Para saber dónde se va el tiempo dentro de una función:

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
resultado = funcion_bajo_analisis(args)
profiler.disable()

stats = pstats.Stats(profiler).sort_stats("cumulative")
stats.print_stats(25)
```

Ordena por `cumulative` para encontrar el camino caliente, y por `tottime` para
encontrar la función que consume tiempo por sí misma.

Para un desglose línea a línea, `line_profiler` con el decorador `@profile`.

### Backend: medir un endpoint

```bash
# Latencia de una petición
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/v1/matters

# Carga sostenida
ab -n 200 -c 10 http://localhost:8000/health
```

Contenido de `curl-format.txt`:

```
time_namelookup:  %{time_namelookup}\n
time_connect:     %{time_connect}\n
time_starttransfer: %{time_starttransfer}\n
time_total:       %{time_total}\n
```

`time_starttransfer` menos `time_connect` aproxima el tiempo de proceso en
servidor, separado de la latencia de red.

### Base de datos: consultas lentas

Registra el SQL emitido durante el desarrollo:

```python
import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
```

Es la forma más rápida de detectar un N+1: verás la misma consulta repetida con
distintos parámetros.

Para analizar una consulta concreta:

```sql
EXPLAIN ANALYZE
SELECT * FROM matters WHERE organization_id = 1 AND status = 'in_progress';
```

Qué buscar en el plan:

- `Seq Scan` sobre una tabla grande indica índice faltante
- Diferencia grande entre filas estimadas y reales sugiere estadísticas
  desactualizadas; ejecuta `ANALYZE`
- `Nested Loop` con muchas iteraciones suele mejorar con un índice adecuado

En Supabase, el dashboard incluye una vista de consultas lentas basada en
`pg_stat_statements`, que es el punto de partida más eficiente en producción.

### Métricas de aplicación

El backend expone métricas en `/metrics`, con caché de 60 segundos. Es la vía
para observar tendencias en producción sin instrumentación adicional.

### Redis

```bash
redis-cli -u "$REDIS_URL" INFO stats       # hits y misses
redis-cli -u "$REDIS_URL" INFO memory
redis-cli -u "$REDIS_URL" LLEN rq:queue:default
```

Una cola que crece de forma sostenida indica que los workers no dan abasto:
o hay que escalarlos o el trabajo tarda más de lo previsto.

Un ratio de aciertos de caché bajo indica que la clave o el TTL están mal
elegidos, y que la caché está añadiendo latencia sin aportar beneficio.

### Frontend

- **Lighthouse.** DevTools, pestaña Lighthouse. Ejecuta en modo incógnito: las
  extensiones distorsionan la medición.
- **React DevTools Profiler.** Identifica re-renders innecesarios.
- **Pestaña Network.** Ordena por tamaño y por duración. Busca peticiones en
  cascada que podrían ser paralelas.
- **Performance.** Grabación de una interacción concreta para ver dónde se
  bloquea el hilo principal.

### Trazado de extremo a extremo

El sistema no tiene trazado distribuido instrumentado. Para seguir una operación
que atraviesa backend, cola y worker, propaga un identificador de correlación
por los logs de las tres partes. Si el volumen de incidentes de latencia lo
justifica, OpenTelemetry sobre FastAPI es el siguiente paso natural.

### Antipatrones de medición

- Medir en la primera ejecución. Los cachés fríos, la compilación JIT y la
  conexión inicial distorsionan. Descarta las primeras iteraciones.
- Medir en local y extrapolar a producción. La latencia de red hacia la base de
  datos cambia por completo el perfil.
- Optimizar la media. Los usuarios recuerdan el p95, no el promedio.
- Medir una sola vez. La variabilidad entre ejecuciones puede superar la mejora
  que crees haber conseguido.

---

## 8. Checklist de performance en revisión de código

Al revisar un PR que toca rutas de datos:

- [ ] Las consultas nuevas filtran por `organization_id`
- [ ] Los listados tienen paginación con techo de `limit`
- [ ] Las relaciones accedidas en bucle usan `joinedload` o `selectinload`
- [ ] Las claves de caché incluyen `organization_id` y versión
- [ ] Las transacciones no envuelven llamadas a servicios externos
- [ ] Los polls usan `usePoll` y tienen `maxAttempts`
- [ ] Los imports pesados en frontend son dinámicos si no son críticos
- [ ] Los iconos se importan de forma individual
- [ ] Las llamadas al LLM tienen `max_tokens` acotado

---

## Ver también

- [architecture.md](architecture.md) - flujos completos del sistema
- [schema.md](schema.md) - modelo de datos e índices
- [TESTING.md](TESTING.md) - estrategia de tests
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - diagnóstico de problemas
- [GLOSSARY.md](GLOSSARY.md) - terminología técnica
