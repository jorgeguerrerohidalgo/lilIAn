# CONSTITUCIÓN DE SOCIEDAD POR ACCIONES (SpA)

> **Categoría:** sociedades
> **Marco legal:** Ley 18.046 (aplicable supletoriamente vía art. 425 del Código de Comercio); DFL 1 de 1982 (Ley de Impuesto a las Ventas y Servicios — efectos jurídicos); Ley 21.000 (Conservador de Empresas y Sociedades).
> **Solemnidad:** Escritura pública ante notario. Inscripción en el Conservador de Empresas y Sociedades. Publicación de extracto en el Diario Oficial.
> **Ministro de fe:** Notario Público.

---

## SOCIOS FUNDADORES

### Socio 1

- **Nombre / Razón social:** {{socio1_nombre}}
- **RUT:** {{socio1_rut}}
- **Domicilio:** {{socio1_domicilio}}
- **Nacionalidad:** {{socio1_nacionalidad}}

{{#if socio2_nombre}}
### Socio 2

- **Nombre / Razón social:** {{socio2_nombre}}
- **RUT:** {{socio2_rut}}
- **Domicilio:** {{socio2_domicilio}}
- **Nacionalidad:** {{socio2_nacionalidad}}
{{/if}}

{{#if socio3_nombre}}
### Socio 3

- **Nombre / Razón social:** {{socio3_nombre}}
- **RUT:** {{socio3_rut}}
- **Domicilio:** {{socio3_domicilio}}
- **Nacionalidad:** {{socio3_nacionalidad}}
{{/if}}

## ELEMENTOS ESENCIALES DE LA SOCIEDAD

### Razón social

La sociedad se denominará **"{{sociedad_razon}}"**, debiendo utilizar siempre este nombre seguido de la expresión **"SpA"** (Sociedad por Acciones).

### Objeto social

La sociedad tendrá por objeto la realización de las siguientes actividades:

> {{sociedad_objeto}}

### Duración

La duración de la sociedad será de **{{sociedad_duracion}}** desde la fecha de constitución, prorrogable según lo que acuerde la junta de accionistas con el quórum del art. 67 N°10 de la Ley 18.046.

### Domicilio

El domicilio legal de la sociedad será la ciudad de **{{sociedad_domicilio}}**, sin perjuicio de las sucursales que los accionistas acuerden establecer.

### Capital

- **Capital inicial:** ${{sociedad_capital}} (CLP).
- **Número de acciones:** {{sociedad_acciones_totales}} acciones nominativas, sin valor nominal.
- **Distribución:**

| Socio | N° acciones | Porcentaje | Monto suscrito ($) |
|-------|-------------|------------|---------------------|
| {{socio1_nombre}} | {{socio1_acciones}} | {{socio1_porcentaje}}% | {{socio1_monto}} |
{{#if socio2_nombre}}
| {{socio2_nombre}} | {{socio2_acciones}} | {{socio2_porcentaje}}% | {{socio2_monto}} |
{{/if}}
{{#if socio3_nombre}}
| {{socio3_nombre}} | {{socio3_acciones}} | {{socio3_porcentaje}}% | {{socio3_monto}} |
{{/if}}

- **Plazo para integrar:** {{sociedad_plazo_integrar}}.
- **Aportes no dinerarios:** {{sociedad_aportes_no_dinerarios}}.

### Tipo de acciones

Todas las acciones serán de una misma serie, denominadas **"Acciones ordinarias"**, confiriendo los mismos derechos económicos y políticos. {{#if acciones_preferentes}} Se crean además las siguientes series preferentes: {{acciones_preferentes_detalle}}.{{/if}}

## ADMINISTRACIÓN

### Directorio

{{#if directorio_individual}}
La sociedad será administrada por un **Director de Sociedad** único, sin directorio, conforme al art. 35 de la Ley 18.046.
{{/if}}

{{#if directorio}}
La sociedad será administrada por un **Directorio** compuesto por **{{directorio_numero}}** directores titulares y sus respectivos suplentes, elegidos por la junta ordinaria de accionistas por un período de {{directorio_periodo}} años.
{{/if}}

- **Presidente:** {{sociedad_presidente}}
- **Gerente general:** {{sociedad_gerente_general}}
- **Atribuciones del directorio:** las señaladas en el art. 39 de la Ley 18.046.

### Facultades del gerente general

El gerente general tendrá la representación judicial y extrajudicial de la sociedad, con las facultades del artículo 41 de la Ley 18.046, especialmente:

1. Representar a la sociedad en juicio y fuera de él.
2. Celebrar toda clase de actos y contratos.
3. Abrir y cerrar cuentas corrientes bancarias.
4. Girar, endosar, protestar y cancelar cheques y letras de cambio.
5. Contratar y desvincular trabajadores, firmar finiquitos.

## ESTADOS FINANCIEROS Y UTILIDADES

- **Ejercicio comercial:** del 1 de enero al 31 de diciembre de cada año.
- **Utilidades:** se distribuirán conforme al art. 78 de la Ley 18.046, salvo acuerdo en contrario de la unanimidad de las acciones emitidas.
- **Política de dividendos:** {{sociedad_politica_dividendos}}.

## REPARTO DE UTILIDADES

Las utilidades líquidas se repartirán entre los socios a prorrata de sus acciones, salvo pacto en contrario. No se permitirá el reparto de dividendos provisorios sin la aprobación del directorio.

## PACTOS ACCIONARIOS (estatutarios)

### Derecho a tanto (derecho de preferencia)

En caso de venta de acciones, los demás accionistas tendrán derecho a adquirirlas preferentemente en proporción a sus participaciones, a igualdad de condiciones.

### Drag-along (venta conjunta forzada)

Si un accionista que represente al menos {{drag_along_porcentaje}}% del capital acepta una oferta de un tercero por la totalidad de las acciones, los demás accionistas estarán obligados a vender sus acciones en las mismas condiciones.

### Tag-along (venta conjunta)

Si un accionista mayoritario vende sus acciones, los minoritarios tendrán derecho a vender las suyas en las mismas condiciones (tag-along).

### Pacto de no competencia

{{#if pacto_no_competencia}}
Los socios no podrán, durante la vigencia de la sociedad y hasta {{pacto_no_competencia_anos}} años después de su retiro, participar en actividades que compitan con la sociedad, en la zona geográfica de {{pacto_no_competencia_zona}}.
{{/if}}

## DISOLUCIÓN

La sociedad se disolverá por las causales del art. 103 de la Ley 18.046, en especial:

1. Vencimiento del plazo de duración.
2. Acuerdo de la junta de accionistas con quórum del 75% de las acciones emitidas con derecho a voto.
3. Inherencia del pleno de la sociedad a una sola persona por más de 10 días.
4. Las demás causales del art. 103.

## NOTARIO Y PROTOCOLIZACIÓN

La presente escritura pública se protocoliza en el Registro del Notario que suscribe y, conjuntamente con el extracto respectivo, se inscribe en el Conservador de Empresas y Sociedades con jurisdicción en el domicilio de la sociedad.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{socio1_nombre}}
RUN: {{socio1_rut}}
**SOCIO FUNDADOR 1**

{{#if socio2_nombre}}
_________________________
{{socio2_nombre}}
RUN: {{socio2_rut}}
**SOCIO FUNDADOR 2**
{{/if}}

{{#if socio3_nombre}}
_________________________
{{socio3_nombre}}
RUN: {{socio3_rut}}
**SOCIO FUNDADOR 3**
{{/if}}

_________________________
{{sociedad_gerente_general}}
RUN: {{sociedad_gerente_rut}}
**GERENTE GENERAL DESIGNADO**

_________________________
**Notario Público**
**MINISTRO DE FE**

---

> ## VARIABLES
>
> - `socio1_nombre`, `socio1_rut`, `socio1_domicilio`, `socio1_nacionalidad` (requeridos)
> - `socio2_nombre`, `socio2_rut`, `socio2_domicilio`, `socio2_nacionalidad` (opcionales)
> - `socio3_nombre`, `socio3_rut`, `socio3_domicilio`, `socio3_nacionalidad` (opcionales)
> - `sociedad_razon`, `sociedad_objeto`, `sociedad_duracion`, `sociedad_domicilio`, `sociedad_capital`, `sociedad_acciones_totales`, `sociedad_plazo_integrar`, `sociedad_aportes_no_dinerarios` (todos requeridos)
> - `socio1_acciones`, `socio1_porcentaje`, `socio1_monto` (requeridos)
> - `socio2_acciones`, `socio2_porcentaje`, `socio2_monto` (opcionales)
> - `socio3_acciones`, `socio3_porcentaje`, `socio3_monto` (opcionales)
> - `directorio_individual`, `directorio`, `directorio_numero`, `directorio_periodo` (uno de los dos requerido)
> - `sociedad_presidente`, `sociedad_gerente_general`, `sociedad_gerente_rut` (requeridos)
> - `sociedad_politica_dividendos` (requerido)
> - `drag_along_porcentaje`, `pacto_no_competencia`, `pacto_no_competencia_anos`, `pacto_no_competencia_zona` (opcionales)
> - `ciudad`, `fecha` (requeridos)
