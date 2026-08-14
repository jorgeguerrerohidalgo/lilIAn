# Preguntas frecuentes (FAQ)

Respuestas a las preguntas más habituales sobre lilIAn. Para problemas técnicos
concretos, consulta [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## ¿Qué es lilIAn?

lilIAn es una plataforma de asistencia legal con inteligencia artificial
orientada a estudios jurídicos y departamentos legales. Centraliza el trabajo
documental de un caso y aporta análisis asistido por IA sobre esos documentos.

Lo que hace:

- **Análisis documental.** Sube contratos, demandas o escritos y obtén un
  análisis estructurado: cláusulas relevantes, riesgos detectados, obligaciones
  y plazos.
- **RAG sobre legislación y precedentes.** Las respuestas se apoyan en
  legislación chilena indexada y en precedentes judiciales, con citas
  navegables al fragmento de origen.
- **Chat contextual.** Preguntas en lenguaje natural sobre los documentos de un
  caso concreto, no sobre conocimiento genérico.
- **Workflow de revisión humana.** Todo análisis que el sistema considera de
  baja confianza queda bloqueado hasta que un abogado lo aprueba.
- **Gestión de casos y clientes.** Casos, documentos, notas, historial de
  estados y alertas de plazos.

Lo que no es: lilIAn no sustituye el criterio profesional de un abogado. Es una
herramienta de apoyo. Toda salida de la IA está pensada para ser revisada.

---

## ¿Qué áreas legales soporta?

El sistema clasifica cada caso en un área legal (`LegalArea`), que determina qué
cuerpo normativo se usa como contexto en el análisis:

| Área | Valor interno | Cobertura normativa principal |
|------|---------------|-------------------------------|
| Laboral | `labor` | Código del Trabajo, Estatuto de Seguridad Social |
| Civil | `civil` | Código Civil, Código de Aguas |
| Consumo | `consumer` | Ley 19.496 de Protección al Consumidor |
| Familia | `family` | Ley 19.968 de Tribunales de Familia, Ley 16.618, Ley 19.585 |
| Comercial | `commerce` | Código de Comercio, Ley de Bancos, Ley de Quiebras |
| Penal | `penal` | Código Penal, Código de Procedimiento Penal |
| Otras | `other` | Código Orgánico de Tribunales, Estatuto Administrativo |

El área se infiere automáticamente desde el tipo de caso (`MatterType`), que
puede ser: revisión de contratos, arrendamiento, laboral, societario,
protección de datos, consumo, familia, cobranza u otro.

La cobertura normativa es chilena. Aplicar lilIAn a otra jurisdicción requiere
indexar el corpus legal correspondiente.

---

## ¿Cómo se garantiza la privacidad de los documentos?

La privacidad se aborda en varias capas, no en una sola.

**Aislamiento multi-tenant.** Cada organización es un tenant. Todas las tablas
que contienen datos de negocio llevan `organization_id`, y toda consulta se
filtra por el tenant del usuario autenticado. Existen tests dedicados de
aislamiento (`test_isolation.py`, `test_s2_isolation_full.py`) que verifican que
un usuario de una organización no puede leer datos de otra.

**Row-Level Security.** PostgreSQL aplica RLS como defensa en profundidad: si un
bug en la aplicación omitiera un filtro, la base de datos sigue bloqueando el
acceso cruzado.

**RBAC granular.** Siete roles (`PLATFORM_ADMIN`, `OWNER`, `ADMIN`, `LAWYER`,
`COMPANY_USER`, `CLIENT`, `VIEWER`) con permisos definidos por recurso y acción.
El detalle está en [rbac-matrix.md](rbac-matrix.md). Un cliente final solo ve
sus propios casos y documentos.

**Storage privado.** El bucket de documentos no es público. El acceso se hace
mediante URLs firmadas temporales generadas por el backend tras verificar
permisos.

**Autenticación.** JWT en cookies httpOnly, no accesibles desde JavaScript, lo
que reduce el impacto de un XSS. Los tokens revocados entran en una blacklist en
Redis.

**Auditoría.** Los accesos y operaciones sensibles se registran en `audit_logs`,
con organización, usuario y acción.

**Procesamiento por terceros.** El análisis se realiza mediante proveedores de
LLM externos (Anthropic, OpenAI o MiniMax según configuración). Esto implica que
el texto de los documentos se envía al proveedor configurado. Es un punto que
debe evaluarse explícitamente en el acuerdo de tratamiento de datos con cada
cliente. Ver la pregunta sobre uso sin conexión más abajo.

---

## ¿Puedo usar lilIAn sin conexión a internet?

Depende de qué funcionalidad se considere imprescindible.

**Lo que sí funciona en una red aislada:**

- Base de datos PostgreSQL con pgvector
- Redis y el worker de procesamiento
- Storage en filesystem local (`STORAGE_PROVIDER=local`)
- Extracción de texto de PDF y DOCX (PyMuPDF y python-docx corren en local)
- Chunking y toda la gestión de casos, clientes y documentos

**Lo que no funciona sin conexión con la configuración por defecto:**

- Análisis con LLM: requiere llamada a la API del proveedor
- Generación de embeddings: por defecto usa la API de OpenAI
- Búsqueda semántica sobre documentos nuevos, porque depende de los embeddings

**Vía para un despliegue aislado.** La capa de LLM es una interfaz abstracta
(`app/services/llm.py`) que ya soporta varios proveedores. Apuntarla a un modelo
autoalojado con endpoint compatible es viable, y lo mismo aplica al proveedor de
embeddings. Esto no está soportado como configuración estándar hoy, y exige
validar la calidad del análisis con el modelo local antes de usarlo en
producción: un modelo pequeño puede degradar significativamente la precisión
jurídica.

---

## ¿Cuál es la diferencia entre un caso y un cliente?

Son entidades distintas con una relación uno a muchos.

**Cliente (`clients`)**: la persona física o jurídica a la que representas.
Existe de forma independiente de cualquier asunto concreto y persiste en el
tiempo. Contiene datos de contacto e identificación. Un cliente puede tener
cero, uno o muchos casos.

**Caso (`matters`)**: un asunto legal concreto con principio y fin. Pertenece a
un cliente, tiene un tipo (`MatterType`), un área legal derivada, un abogado
asignado, un nivel de urgencia y un estado que evoluciona a lo largo del ciclo
de vida:

`new` → `processing` → `analysis_ready` → `pending_human_review` →
`missing_information` / `contact_client` → `in_progress` → `closed` → `archived`

Los documentos, notas, análisis, sesiones de chat y alertas de plazo cuelgan del
caso, no del cliente. Esto importa por dos razones prácticas: el aislamiento del
contexto de IA se hace a nivel de caso (el chat de un caso no ve documentos de
otro), y los permisos se evalúan a nivel de caso (un `COMPANY_USER` solo accede
a los casos donde está asignado).

Regla mental: si al terminar el trabajo la entidad deja de tener actividad, es
un caso. Si sigue existiendo para futuros encargos, es un cliente.

---

## ¿Cómo funciona el análisis con IA?

El flujo completo, desde que subes un documento hasta que ves el resultado:

**1. Subida y almacenamiento.** El documento se guarda en storage privado y se
registra en `documents` con estado inicial.

**2. Procesamiento asíncrono.** Se encola un trabajo en Redis. El worker extrae
el texto (PyMuPDF para PDF, python-docx para DOCX), lo normaliza y detecta
duplicados por hash para no reprocesar lo mismo dos veces.

**3. Chunking.** El texto se divide en fragmentos de aproximadamente 1000
caracteres con solapamiento, cortando por límites de frase cuando es posible
para no partir ideas por la mitad. Cada chunk conserva su página de origen, lo
que permite citar con precisión más adelante.

**4. Embeddings.** Cada chunk se convierte en un vector y se guarda en
`document_chunks` con pgvector, junto a su `organization_id` y `matter_id`.

**5. Recuperación de contexto (RAG).** Al pedir un análisis, el sistema reúne:
el texto de los documentos del caso, los artículos de legislación chilena
relevantes al área legal detectada y los precedentes judiciales similares.

**6. Llamada al LLM.** Se construye un prompt específico según el tipo de caso y
se solicita una salida estructurada validada contra un esquema Pydantic.

**7. Validación de la salida.** Antes de persistir nada, `_validate_llm_output()`
verifica la forma de la respuesta (longitudes, número de elementos, profundidad
de anidamiento) y busca patrones de inyección de prompt. Si algo resulta
sospechoso, el análisis se marca con `requires_human_review = true` y se anota
el motivo en `warnings`.

**8. Detección de conflictos normativos.** Se compara el contenido del documento
con la legislación aplicable y se emiten conflictos y observaciones.

**9. Citas.** Cada afirmación relevante se enlaza al chunk que la respalda, de
forma que el abogado puede saltar al texto original y verificarla.

**10. Revisión humana.** Si el análisis requiere revisión, no puede usarse para
decisiones automáticas hasta que un usuario con permiso lo apruebe.

El punto 10 es deliberado: el diseño asume que la IA puede equivocarse y sitúa
el control en el profesional.

---

## ¿Qué pasa si la IA se equivoca?

Se equivocará. Un modelo de lenguaje puede omitir una cláusula, malinterpretar
una redacción ambigua o citar una norma que no aplica. El sistema está diseñado
partiendo de esa premisa, no de la contraria.

**Mitigaciones implementadas:**

- **Citas verificables.** Cada conclusión enlaza al fragmento del documento que
  la sustenta. Si no hay cita, hay que desconfiar.
- **Bandera de revisión humana.** Las salidas de baja confianza se marcan
  automáticamente y quedan bloqueadas para uso automático.
- **Validación estructural.** Respuestas malformadas o sospechosas de inyección
  se detectan antes de persistirse.
- **Dataset golden.** Existe un conjunto de casos legales de referencia
  (`tests/fixtures/legal_cases/`) usado para detectar regresiones de calidad
  cuando cambia un prompt o un modelo.
- **Trazabilidad.** El análisis queda registrado con su versión y su origen, lo
  que permite auditar a posteriori qué se generó y cuándo.

**Responsabilidad.** El análisis de lilIAn no constituye asesoría legal. La
responsabilidad profesional sobre el trabajo entregado al cliente final es
siempre del abogado, que debe revisar el contenido antes de usarlo. La
plataforma es un acelerador de trabajo, no un sustituto de la diligencia
profesional.

**Si detectas un error sistemático** (no un fallo puntual sino un patrón: por
ejemplo, que siempre se omite un tipo de cláusula), repórtalo. Ese tipo de fallo
suele corregirse ajustando el prompt o el corpus normativo, y el caso concreto
puede incorporarse al dataset golden para evitar la regresión.

---

## ¿Cuánto cuesta?

El modelo de precios comercial se define por organización mediante suscripción.
El esquema soporta planes (`plans`), suscripciones (`subscriptions`) y eventos
de uso (`usage_events`) para medición y facturación.

Para consultas comerciales concretas, contacta con el equipo. Este documento no
es una lista de precios.

**Costes de infraestructura para un despliegue propio.** Si vas a autoalojar,
los componentes con coste son:

| Componente | Servicio típico |
|------------|-----------------|
| Base de datos y storage | Supabase |
| Redis | Upstash o equivalente |
| Backend | Railway |
| Frontend | Vercel |
| LLM | Anthropic, OpenAI o MiniMax, por tokens |
| Embeddings | OpenAI, por tokens |

El coste variable dominante en uso real es el de LLM, y escala con el volumen y
el tamaño de los documentos analizados, no con el número de usuarios. Un
contrato largo consume muchos más tokens que diez consultas de chat.

---

## ¿Cómo migro mis datos?

**Importación hacia lilIAn.** No existe hoy un importador genérico de un clic.
La vía soportada es la API REST: crear organizaciones, clientes, casos y subir
documentos programáticamente. Los documentos se procesan por el mismo pipeline
que los subidos manualmente, de forma que quedan indexados y disponibles para
búsqueda y análisis.

Consideraciones prácticas al migrar:

- Migra clientes antes que casos: los casos referencian al cliente.
- Los documentos deben subirse tras crear el caso al que pertenecen.
- El procesamiento es asíncrono. Una migración grande satura la cola si se
  lanza toda de golpe; conviene aplicar throttling.
- La generación de embeddings tiene coste por token. Estima antes de migrar un
  archivo histórico completo.

**Exportación desde lilIAn.** Tus datos son tuyos. Vías disponibles:

- API REST para extraer casos, clientes, documentos y análisis en JSON
- Descarga de los documentos originales desde storage
- Exportación de análisis en formatos legibles vía el generador de documentos

Recomendación operativa: si estás evaluando la plataforma, valida el camino de
salida antes de migrar todo el histórico. Es más barato descubrir una limitación
con cien casos que con diez mil.

---

## ¿Tienen SOC 2 / ISO 27001?

lilIAn no cuenta actualmente con certificación SOC 2 Tipo II ni ISO 27001.

Es importante distinguir entre controles técnicos implementados y certificación
formal auditada por un tercero. La plataforma implementa varios controles que
esos marcos exigen:

- Autenticación con JWT en cookies httpOnly y blacklist de tokens revocados
- Control de acceso basado en roles documentado en una matriz explícita
- Aislamiento multi-tenant verificado por tests automatizados
- Row-Level Security en base de datos como defensa en profundidad
- Registro de auditoría de operaciones sensibles
- Gestión de secretos mediante variables de entorno, documentada en
  [SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md)
- Rate limiting en endpoints de autenticación
- CORS restrictivo con wildcard bloqueado en producción
- Cifrado en tránsito por HTTPS y en reposo mediante el proveedor de base de
  datos

Lo que falta para una certificación no es principalmente técnico, sino de
proceso: evidencia auditada de forma continua, políticas formales de seguridad,
gestión documentada de proveedores, plan de respuesta a incidentes probado y un
periodo de observación del auditor.

**Para clientes con requisitos de cumplimiento estrictos.** Si tu organización
exige certificación como condición contractual, plantéalo antes de la
implantación. Un despliegue autoalojado dentro de tu propia infraestructura
certificada puede ser una alternativa viable, ya que hereda parte de tus
controles existentes.

Para la política de reporte de vulnerabilidades, consulta `SECURITY.md`.

---

## Ver también

- [GLOSSARY.md](GLOSSARY.md) - definiciones de términos legales y técnicos
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - resolución de problemas
- [architecture.md](architecture.md) - arquitectura del sistema
- [rbac-matrix.md](rbac-matrix.md) - matriz de permisos por rol
- [schema.md](schema.md) - modelo de datos
