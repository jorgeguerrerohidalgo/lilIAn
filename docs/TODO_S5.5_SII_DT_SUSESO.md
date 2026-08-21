# S5.5 — SII / DT / SUSESO integrations (DEFERRED)

## Status

**Deferred to a future sprint.** Esta tarea es XL (multi-semana) según
el plan de Sprint 5. Se documenta acá el alcance aproximado para que un
próximo sprint pueda retomarlo sin rediscover.

## Por qué no se hizo en S5

1. **Acceso a la API del SII**, la DT y SUSESO requiere convenios
   formales (la mayoría son SOAP/XML sobre HTTPS con certificados
   cliente). No es un HTTP JSON simple; ningún endpoint está
   públicamente accesible.
2. **OAuth / Clave Única**: el SII usa Clave Única del Estado para
   autenticar a personas naturales; las empresas acceden vía
   certificado digital e-firma. Necesitamos infraestructura de firma
   en servidor.
3. **Rate limits y operaciones batch**: la DT (Dirección del Trabajo)
   y SUSESO exponen servicios SOAP con reglamentación de frecuencia
   y ventanas de mantenimiento.
4. **Realtime data**: las fiscalizaciones DT, los certificados de
   cotizaciones SUSESO y los F22 del SII cambian mensualmente. Sin
   un cache bien diseñado, las latencias degradan la UX.

## Lo que se necesitaría

### SII (Servicio de Impuestos Internos)

- **Endpoint:** `https://www.sii.cl/cgi_rnc/vista/rnc_rfc.htm` (público,
  sólo RUT válidos) + servicios autenticados para F22, F29, F30,
  facturación electrónica, situación tributaria.
- **Auth:** Clave Única (OAuth 2.0 ChileAtiende) o e-firma (cert
  cliente).
- **Casos de uso:**
  - Validar RUT y razón social al crear un cliente.
  - Verificar inicio de actividades y régimen tributario.
  - Consultar boletas de honorarios electrónicas para clientes
    abogados.
  - Descargar F22 anual para revisión por un tributarista.
- **Riesgos:** costo de implementar OAuth, mantenimiento de claves,
  PII en logs.

### DT (Dirección del Trabajo)

- **Endpoint:** portal público de la DT + servicios autenticados.
  Sin API REST pública; la mayoría de la información se entrega vía
  "Portal Trabajador" con RUT + clave.
- **Casos de uso:**
  - Verificar dictámenes vigentes.
  - Consultar jurisprudencia administrativa.
  - Generar certificado de cotizaciones para finiquitos.
- **Riesgos:** dependencia del scraping si no hay API formal.

### SUSESO (Superintendencia de Seguridad Social)

- **Endpoint:** SOAP complejo. Mutualidades (ACHS, Mutual de Seguridad,
  IST) tienen sistemas propietarios.
- **Casos de uso:**
  - Verificar si un trabajador tiene accidente laboral vigente.
  - Consultar días de licencia médica.
  - Cobertura de prestaciones adicionales.
- **Riesgos:** integración multi-mutualidad, LATAM-wide.

## Tareas del próximo sprint

- [ ] Diagnóstico: revisar si existen API públicas o sandbox del SII.
- [ ] Diseñar capa de abstracción ``app/services/integrations/cl/``
  con clientes por organismo.
- [ ] MVP: solo validar RUT y razón social contra el SII (servicio
  público sin auth).
- [ ] UI: incorporar "Datos del cliente" pre-llenados desde SII en
  la creación de clientes.
- [ ] Caching: Redis con TTL de 24h para RUTs consultados.
- [ ] Logs: redacción estricta de RUTs y nombres en logs.

## Estimación

- 2-3 sprints para el MVP con SII + DT.
- 1 sprint adicional para SUSESO y mutualidades.

## Como afecta al producto

- Mientras tanto, los datos tributarios y laborales del cliente los
  ingresa el abogado a mano.
- Esta brecha no bloquea el launch: la mayoría de los flujos no
  requieren integración con estos organismos.
