# Glosario

Términos legales y técnicos usados en lilIAn. Cuando un término tiene un
significado específico dentro de este código, se indica de forma explícita.

Índice: [Dominio legal](#dominio-legal) | [IA y RAG](#ia-y-rag) |
[Arquitectura y multi-tenancy](#arquitectura-y-multi-tenancy) |
[Procesamiento de documentos](#procesamiento-de-documentos) |
[Análisis y salidas](#análisis-y-salidas) |
[Infraestructura](#infraestructura) | [Testing](#testing)

---

## Dominio legal

### Matter (caso legal)

La unidad central de trabajo. Un asunto legal concreto, con principio y fin,
perteneciente a un cliente.

Un matter tiene tipo (`MatterType`), área legal derivada, abogado asignado,
urgencia y estado. De él cuelgan documentos, notas, análisis, sesiones de chat y
alertas de plazo.

Tabla: `matters`. Modelo: `app/models/matter.py`.

Se traduce como "caso" en la interfaz en español, pero en el código siempre es
`matter`. No mezclar ambos nombres dentro del mismo archivo.

### Client

La persona física o jurídica representada. Existe con independencia de cualquier
asunto concreto y persiste entre encargos. Un cliente tiene cero o más matters.

Tabla: `clients`.

Cuidado con la ambigüedad: `CLIENT` es también un rol RBAC, el del usuario final
que accede a la plataforma para ver sus propios casos. Un registro en `clients`
y un usuario con rol `CLIENT` son cosas distintas.

### Matter type

Clasificación del asunto. Determina el prompt del sistema usado en el análisis y
el área legal aplicable.

Valores (`MatterType`, `app/models/matter.py`):

| Valor | Significado |
|-------|-------------|
| `contract_review` | Revisión de contratos |
| `lease` | Arrendamiento |
| `labor` | Laboral |
| `company` | Societario |
| `data_protection` | Protección de datos |
| `consumer` | Consumo |
| `family` | Familia |
| `debt` | Cobranza |
| `other` | Otros |

### Matter status

Estado del caso en su ciclo de vida (`MatterStatus`):

| Estado | Significado |
|--------|-------------|
| `new` | Creado, sin procesar |
| `processing` | Documentos en procesamiento |
| `analysis_ready` | Análisis disponible |
| `pending_human_review` | Requiere aprobación de un abogado |
| `missing_information` | Falta documentación para continuar |
| `contact_client` | Requiere gestión con el cliente |
| `in_progress` | En trabajo activo |
| `closed` | Cerrado |
| `archived` | Archivado |

`pending_human_review` no es decorativo: bloquea el uso del análisis para
decisiones automáticas hasta que alguien con permiso lo apruebe.

### Legal area

Área del derecho que determina qué cuerpo normativo se usa como contexto en el
análisis.

Valores (`LegalArea`, `app/models/legal_area.py`): `labor`, `civil`, `consumer`,
`family`, `commerce`, `penal`, `other`.

Se infiere automáticamente desde el `matter_type` mediante
`get_legal_area_from_matter_type()`, y desde un código de ley mediante
`get_legal_area_from_law_code()`.

Ejemplo de mapeo: `contract_review`, `lease`, `debt` y `data_protection` mapean
todos a `civil`. Varios tipos de caso comparten área legal.

### Precedent

Precedente judicial: una resolución previa usada como contexto para el análisis.
El sistema los indexa y recupera por similitud semántica, de forma que un
análisis puede apoyarse en cómo se resolvió un caso parecido.

Tabla: `precedents`. Servicio: `app/services/precedent_rag.py`. Analítica sobre
ellos: `app/services/precedent_analytics.py`.

Los precedentes son conocimiento compartido dentro de la organización: los roles
internos tienen lectura transversal sobre ellos.

### Legal source

Fuente normativa indexada: un código o una ley. Ejemplos usados en el sistema:
`codigo_trabajo`, `codigo_civil`, `codigo_comercio`, `codigo_penal`,
`ley_proteccion_consumidor` (19.496), `ley_tribunales_familia` (19.968).

Tablas: `legal_sources` y `legal_source_versions`. La segunda existe porque las
leyes se modifican: un análisis hecho hace un año se apoyó en una versión
concreta del texto, y eso debe poder auditarse.

### Deadline alert

Alerta sobre un plazo procesal o contractual próximo, generada a partir del
análisis de los documentos del caso.

Tabla: `deadline_alerts`. Generación: `app/services/deadline_generator.py`.

En materia legal un plazo incumplido puede ser irrecuperable, de ahí que esto
sea una entidad de primer nivel y no un campo más del análisis.

### Clause

Cláusula contractual. El análisis las identifica, las clasifica y puede
compararlas contra plantillas de referencia para detectar desviaciones respecto
de lo esperado.

Servicios: `app/services/clause_comparator.py`,
`app/services/clause_templates.py`.

### Normative conflict

Contradicción detectada entre lo que dice un documento y lo que exige la
legislación aplicable. Por ejemplo, una cláusula que fija una jornada superior
al máximo legal.

Se calcula con `detect_normative_conflicts()` en `app/services/analysis.py` y
devuelve conflictos y observaciones. Las observaciones son señalamientos de
menor gravedad que no llegan a ser contradicción.

---

## IA y RAG

### RAG (Retrieval Augmented Generation)

Técnica que consiste en recuperar fragmentos relevantes de una base de
conocimiento y añadirlos al prompt antes de llamar al modelo, en lugar de
confiar en el conocimiento interno del modelo.

En lilIAn el contexto recuperado combina tres fuentes: los documentos del caso,
la legislación del área legal correspondiente y precedentes judiciales
similares.

La razón de usar RAG en un producto legal es la verificabilidad. Un modelo puede
inventar una norma; un fragmento recuperado de un corpus indexado se puede citar
y comprobar.

Servicios: `app/services/rag.py`, `app/services/precedent_rag.py`.

### Document chunk

Fragmento de documento indexado de forma independiente. Un documento se divide
en chunks porque un contrato completo no cabe en el contexto del modelo, y
porque recuperar el fragmento exacto es más preciso que pasar el documento
entero.

En este proyecto: aproximadamente 1000 caracteres por chunk, con solapamiento
entre chunks consecutivos y un mínimo de 200 caracteres. El corte busca límites
de frase para no partir ideas por la mitad.

Cada chunk conserva su página de origen, lo que permite construir citas
precisas.

Tabla: `document_chunks`, con `organization_id` y `matter_id` para el
aislamiento. Servicio: `app/services/chunker.py`.

### Overlap (solapamiento)

Caracteres compartidos entre dos chunks consecutivos. Sin solapamiento, una idea
que cae justo en el límite entre dos fragmentos se pierde para la búsqueda. Con
solapamiento aparece completa en al menos uno de los dos.

Coste: duplicación parcial de texto, y por tanto más almacenamiento y más
embeddings.

### Embedding

Representación vectorial del significado de un texto. Dos textos con significado
parecido producen vectores cercanos en el espacio, lo que permite buscar por
sentido y no por coincidencia literal de palabras.

Se almacenan en pgvector, la extensión de PostgreSQL para vectores. Modelo por
defecto: `text-embedding-3-small` de OpenAI, configurable vía
`EMBEDDING_PROVIDER` y `EMBEDDING_MODEL`.

Punto crítico: si cambias de modelo de embeddings, los vectores antiguos dejan de
ser comparables con los nuevos. Hay que reindexar todo el corpus.

Servicio: `app/services/embeddings.py`.

### Hybrid search

Combinación de búsqueda vectorial (semántica) y búsqueda por palabras clave
(léxica).

Cada una falla donde la otra acierta. La vectorial encuentra "terminación del
contrato" al buscar "despido", pero puede fallar con un identificador exacto
como "artículo 161". La léxica es infalible con términos exactos y ciega ante
sinónimos. En materia legal ambos casos son frecuentes, así que se combinan.

### Top-k

Número de fragmentos que se recuperan y se pasan al modelo. Un valor bajo puede
omitir contexto necesario; uno alto encarece la llamada, ralentiza la respuesta
y añade ruido que puede empeorar la calidad.

### Context window

Cantidad máxima de tokens que un modelo puede procesar en una llamada, sumando
prompt y respuesta. Todo el diseño de chunking y de top-k existe precisamente
por este límite.

### Token

Unidad mínima de texto para un modelo, aproximadamente 4 caracteres en español.
Es la unidad de facturación de los proveedores de LLM y el principal coste
variable de la plataforma.

### Prompt injection

Intento de manipular el comportamiento del modelo mediante instrucciones
insertadas en el contenido que procesa. En lilIAn el vector de ataque es un
documento subido que contiene texto como "ignora las instrucciones anteriores".

El sistema detecta patrones conocidos en `app/services/analysis.py`:
`ignore previous instructions`, `ignore above instructions`,
`disregard the system prompt`, `you are now`, `new instructions:` y marcadores de
plantilla de chat como `<|im_start|>`.

Detectarlo no descarta el análisis: lo marca con `requires_human_review` y anota
el motivo en `warnings`.

### System prompt

Instrucción base que define el rol y las restricciones del modelo. En lilIAn
varía según el `matter_type`: analizar un contrato de arrendamiento y una
demanda laboral requieren enfoques distintos.

### Structured output

Salida del modelo forzada a cumplir un esquema, en este caso un modelo Pydantic.
Permite trabajar con datos tipados en lugar de parsear texto libre.

Nunca se confía ciegamente: la salida se valida antes de persistirse.

### Hallucination

Afirmación generada por el modelo que suena plausible pero no está respaldada
por el contexto proporcionado. En un producto legal es el riesgo principal.

Mitigación en lilIAn: citas obligatorias que enlazan cada afirmación a su
fragmento origen, y bandera de revisión humana cuando la confianza es baja. Si
una afirmación no tiene cita, hay que desconfiar de ella.

---

## Arquitectura y multi-tenancy

### Organization (tenant)

Unidad de aislamiento. Cada estudio o departamento legal es una organización.
Todas las tablas de negocio llevan `organization_id`, y toda consulta se filtra
por el tenant del usuario autenticado.

Tabla: `organizations`. Pertenencia: `organization_members`, que asocia usuario,
organización y rol.

### Tenant isolation

Garantía de que los datos de una organización nunca son accesibles desde otra.
Se implementa en tres capas:

1. Filtrado por `organization_id` en la capa de aplicación
2. Row-Level Security en PostgreSQL como defensa en profundidad
3. Tests automatizados que intentan explícitamente el acceso cruzado
   (`test_isolation.py`, `test_s2_isolation_full.py`)

La regla operativa: ninguna query sin filtro de organización.

### RLS (Row-Level Security)

Mecanismo de PostgreSQL que aplica políticas de acceso a nivel de fila dentro de
la propia base de datos. Aquí funciona como red de seguridad: si un bug de
aplicación omitiera un filtro, la base de datos sigue bloqueando el acceso.

### RBAC (Role-Based Access Control)

Control de acceso basado en roles. Los siete roles del sistema:

| Rol | Alcance |
|-----|---------|
| `PLATFORM_ADMIN` | Global, multi-tenant. Soporte y operaciones internas |
| `OWNER` | Total dentro de su organización, incluida facturación |
| `ADMIN` | Gestión de usuarios y recursos, sin facturación ni borrado de la organización |
| `LAWYER` | Casos, clientes, documentos y plantillas de su organización |
| `COMPANY_USER` | Solo los casos donde está asignado |
| `CLIENT` | Solo sus propios casos y documentos |
| `VIEWER` | Solo lectura sobre lo que se le comparta explícitamente |

Matriz completa por recurso y acción: [rbac-matrix.md](rbac-matrix.md).

### Tenant context

Estructura que transporta la organización activa a lo largo de una petición, de
forma que servicios y repositorios puedan aplicar el filtro sin recibirlo
manualmente en cada llamada.

Implementación: `app/api/deps/`.

### Audit log

Registro inmutable de operaciones sensibles: quién, qué, cuándo y en qué
organización.

Tabla: `audit_logs`. Servicio: `app/services/audit.py`. Solo `OWNER`, `ADMIN` y
`PLATFORM_ADMIN` pueden leerlo.

### JWT (JSON Web Token)

Token firmado que transporta la identidad del usuario. En lilIAn viaja en una
cookie httpOnly, no accesible desde JavaScript, lo que limita el impacto de un
XSS.

Configuración: `JWT_SECRET` (mínimo 32 caracteres), `JWT_ISSUER`,
`JWT_AUDIENCE`.

### Token blacklist

Lista de tokens revocados almacenada en Redis. Un JWT es válido hasta su
expiración por naturaleza, así que revocar una sesión requiere una lista
explícita.

Diseñada como fail-open: si Redis cae, el sistema registra el error pero no
bloquea a todos los usuarios. Implementación: `app/core/token_blacklist.py`.

### Rate limiting

Límite de peticiones por unidad de tiempo. Configurado vía
`RATE_LIMIT_PER_MINUTE` (60 por defecto) y `RATE_LIMIT_AUTH_PER_MINUTE` (10).
Los endpoints de registro y login tienen límite propio para dificultar ataques de
fuerza bruta y creación masiva de cuentas.

Implementación: slowapi, `app/core/rate_limit.py`.

### CORS

Mecanismo del navegador que controla qué orígenes pueden llamar a la API. En
producción el wildcard `*` está bloqueado deliberadamente: es incompatible con
el envío de credenciales en cookies.

Configuración: `ALLOWED_ORIGINS`.

---

## Procesamiento de documentos

### Document

Archivo subido a un caso: PDF o DOCX. Se almacena en storage privado y se
registra en la tabla `documents` con su estado de procesamiento.

### Document processing pipeline

Secuencia que convierte un archivo en conocimiento consultable:

1. Subida y almacenamiento
2. Encolado del trabajo en Redis
3. Extracción de texto (PyMuPDF para PDF, python-docx para DOCX)
4. Deduplicación por hash de contenido
5. Chunking con solapamiento
6. Generación de embeddings
7. Persistencia en `document_chunks`

Implementación: `app/services/document_processor.py` y el worker en
`workers/document_processor/`.

### Worker

Proceso separado del backend que consume trabajos de la cola de Redis. Existe
porque procesar un documento tarda demasiado para hacerlo dentro de una petición
HTTP.

Consecuencia operativa habitual: si despliegas el backend sin el worker, los
documentos se suben pero nunca se procesan.

### Queue (RQ)

Cola de trabajos sobre Redis. Cola por defecto: `default`. Inspección:
`redis-cli LLEN rq:queue:default`.

### Deduplication

Detección de documentos idénticos por hash de contenido, para no reprocesar ni
volver a pagar embeddings del mismo texto. Test:
`tests/unit/test_document_processor_dedup.py`.

### Storage provider

Abstracción sobre el almacenamiento de archivos, con dos implementaciones:
Supabase Storage (producción) y filesystem local (desarrollo). Se selecciona con
`STORAGE_PROVIDER`.

Implementación: `app/services/storage.py`.

### Signed URL

URL temporal que da acceso a un archivo privado sin exponer credenciales. El
backend la genera tras verificar permisos. Expira por diseño, así que el
frontend debe pedirla en cada carga y no cachearla.

---

## Análisis y salidas

### Document analysis

Resultado estructurado del análisis de un documento: cláusulas identificadas,
riesgos, obligaciones y plazos.

Tabla: `document_analyses`, relación 1:1 con el documento.

### Analysis report

Informe consolidado a nivel de caso, que agrega los hallazgos de todos sus
documentos y añade los conflictos normativos detectados.

Tabla: `analysis_reports`. Los riesgos individuales cuelgan de él en
`risk_items`.

### Citation

Enlace entre una afirmación generada por la IA y el fragmento concreto del
documento que la respalda, incluyendo la página.

Es el mecanismo central de verificabilidad del producto: permite al abogado
saltar al texto original y comprobar la afirmación en segundos. Componente
frontend: `components/citation-link.tsx`.

### Risk item

Riesgo concreto detectado en el análisis, con su descripción, gravedad y
referencia al fragmento que lo origina.

Tabla: `risk_items`, asociada a un `analysis_report`.

### Risk score

Puntuación que cuantifica la gravedad de un riesgo o el nivel de riesgo agregado
de un caso, para permitir priorización.

Es una estimación asistida por IA, no una calificación jurídica. Sirve para
ordenar la revisión, no para decidir por el abogado.

### Validation summary

Resultado de `_validate_llm_output()`. Siempre incluye dos campos:

- `requires_human_review`: booleano que indica si el análisis puede usarse de
  forma automática
- `warnings`: lista de motivos concretos

Las comprobaciones incluyen forma de la respuesta (máximo 8000 caracteres por
campo de texto, máximo 200 elementos por lista, profundidad máxima de 8 niveles)
y detección de patrones de inyección de prompt.

### requires_human_review

Bandera booleana que bloquea el uso de un análisis para decisiones automáticas
hasta que un usuario con permiso lo apruebe explícitamente en el workflow de
revisión.

Se activa cuando la validación detecta salida sospechosa, cuando el tipo de caso
lo exige por política, o manualmente.

### Review workflow

Proceso por el cual un abogado revisa, aprueba o rechaza un análisis generado
por IA. Modelo: `app/models/review.py`. Endpoint:
`app/api/endpoints/review.py`.

Es la garantía de que la IA no toma decisiones sin supervisión humana.

### Evidence bundle

Conjunto estructurado de evidencia que respalda un análisis: los fragmentos
recuperados, las normas aplicadas y los precedentes considerados. Permite
reconstruir a posteriori en qué se basó una conclusión.

Servicio: `app/services/evidence.py`.

### Golden dataset

Conjunto de casos legales de referencia con resultado esperado conocido, usado
para detectar regresiones de calidad cuando cambia un prompt, un modelo o el
corpus normativo.

Ubicación: `apps/backend/tests/fixtures/legal_cases/`. Test:
`tests/test_golden_dataset.py`.

Un cambio de prompt puede mejorar un caso y romper otros tres. Sin dataset
golden, eso no se detecta hasta que lo reporta un usuario.

---

## Infraestructura

### pgvector

Extensión de PostgreSQL que añade el tipo `vector` y operadores de similitud.
Permite hacer búsqueda semántica dentro de la misma base de datos, sin necesidad
de una base vectorial separada.

Requiere `CREATE EXTENSION IF NOT EXISTS vector;`.

### Supabase

Plataforma que en este proyecto aporta PostgreSQL gestionado con pgvector y
almacenamiento de archivos.

Dos claves con propósitos distintos: `SUPABASE_ANON_KEY` para acceso limitado y
`SUPABASE_SERVICE_ROLE_KEY` para el backend, que ignora RLS. La service role key
nunca debe llegar al frontend ni a una variable `NEXT_PUBLIC_*`.

### Alembic

Herramienta de migraciones de esquema para SQLAlchemy. La tabla
`alembic_version` registra la revisión aplicada. Comandos habituales:
`alembic upgrade head`, `alembic history`, `alembic stamp`.

### Polling

Consultar el estado periódicamente hasta que cambie. Se usa para seguir el
procesamiento de documentos.

En el frontend se hace con el hook `usePoll` (`lib/hooks/use-poll.ts`), que
limpia el intervalo al desmontar el componente. Configuración por defecto para
documentos: 5 segundos entre intentos, máximo 60 intentos, es decir 5 minutos.

### Health check

Endpoint `GET /health`, que devuelve `{"status": "healthy"}`. Lo usan Railway y
Docker Compose para decidir si una instancia está viva.

### Ruff

Linter y formateador de Python usado en el proyecto. Configuración en
`pyproject.toml`: línea de 100 caracteres, target py312.

---

## Testing

### AAA (Arrange, Act, Assert)

Estructura estándar de un test: preparar el estado, ejecutar la acción bajo
prueba, verificar el resultado. Un test con esas tres partes visibles se lee sin
esfuerzo.

### Fixture

Estado preparado y reutilizable para tests. Los principales están en
`apps/backend/tests/conftest.py`:

- `db`: sesión SQLite en memoria, con tablas creadas al entrar y borradas al
  salir
- `client`: `TestClient` de FastAPI con `get_db` sobrescrito al motor de test

### Marker

Etiqueta que clasifica un test. Los definidos en `pyproject.toml`:

- `unit`: sin base de datos ni red
- `integration`: usa el motor SQLite de test
- `slow`: tarda más de 5 segundos

Uso: `pytest -m unit`.

### Coverage

Porcentaje de código ejecutado por los tests. El umbral actual en configuración
es 60 por ciento (`fail_under`), con objetivo de 80 por ciento.

Advertencia habitual: la cobertura mide qué líneas se ejecutan, no si las
aserciones son correctas. Un 100 por cien de cobertura con aserciones triviales
no garantiza nada.

### Isolation test

Test que verifica que un usuario de una organización no puede acceder a datos de
otra. Es la categoría de test más crítica del proyecto, porque el fallo que
previene es una fuga de datos de clientes entre estudios.

Archivos: `tests/test_isolation.py`, `tests/test_s2_isolation_full.py`.

### E2E (end-to-end)

Test que ejercita el sistema completo a través de la interfaz real, como lo haría
un usuario. Configuración: `apps/frontend/playwright.config.ts`. Tests:
`tests/e2e/`.
