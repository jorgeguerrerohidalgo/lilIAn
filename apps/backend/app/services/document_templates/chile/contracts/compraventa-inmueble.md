# CONTRATO DE COMPRAVENTA DE INMUEBLE

> **Categoría:** compraventas
> **Marco legal:** arts. 1793 a 1876 del Código Civil; DFL 2 de 1959 (vivienda), Ley 18.101 (cuando se financia por arriendo).
> **Solemnidad:** Escritura pública ante notario (art. 1801 del Código Civil). Inscripción en el Conservador de Bienes Raíces (art. 686 del Código Civil).
> **Ministro de fe:** Notario Público.

---

## VENDEDOR

- **Nombre:** {{vendedor_nombre}}
- **RUT:** {{vendedor_rut}}
- **Estado civil:** {{vendedor_estado_civil}}
- **Domicilio:** {{vendedor_domicilio}}

## COMPRADOR

- **Nombre:** {{comprador_nombre}}
- **RUT:** {{comprador_rut}}
- **Estado civil:** {{comprador_estado_civil}}
- **Domicilio:** {{comprador_domicilio}}

{{#if conyuge_comprador_nombre}}
- **Cónyuge:** {{conyuge_comprador_nombre}}, RUT {{conyuge_comprador_rut}}
- **Régimen matrimonial:** {{conyuge_comprador_regimen}}
{{/if}}

## INMUEBLE

- **Tipo:** {{inmueble_tipo}}
- **Ubicación:** {{inmueble_direccion}}
- **Comuna:** {{inmueble_comuna}}
- **Ciudad:** {{inmueble_ciudad}}
- **Rol de avalúo fiscal:** {{inmueble_rol}}
- **Fojas:** {{inmueble_fojas}}
- **Número:** {{inmueble_numero}}
- **Año de inscripción:** {{inmueble_anio_inscripcion}}
- **Conservador:** Conservador de Bienes Raíces de {{inmueble_conservador}}
- **Deslindes:**
  - Norte: {{inmueble_deslinde_norte}}
  - Sur: {{inmueble_deslinde_sur}}
  - Oriente: {{inmueble_deslinde_oriente}}
  - Poniente: {{inmueble_deslinde_poniente}}
- **Servidumbres activas o pasivas:** {{inmueble_servidumbres}}
- **Hipotecas o gravámenes:** {{inmueble_gravamenes}}

## PRECIO Y FORMA DE PAGO

- **Precio total:** UF {{precio_uf}} ({{precio_pal}})
- **Forma de pago:**
  - {{pago_detalle}}

{{#if pie_pago}}
- **Pago al contado:** {{pie_pago}}
{{/if}}

{{#if saldo_financiamiento}}
- **Saldo financiado:** {{saldo_financiamiento}}
- **Institución financiera:** {{banco_nombre}}
- **Tasa:** {{banco_tasa}}
- **Plazo:** {{banco_plazo}}
- **Banco asume la promesa de hipoteca:** {{banco_promesa_hipoteca}}
{{/if}}

## ESTADO DEL INMUEBLE

El(la) vendedor(a) declara que el inmueble se encuentra:
- Libre de ocupantes y litigios.
- Al día en contribuciones, gastos comunes y servicios básicos.
- En condiciones de ser habitado inmediatamente.
- No afectado por planes reguladores pendientes que limiten su uso.

## SANEAMIENTO

El(la) vendedor(a) se obliga al saneamiento conforme a los arts. 1837 a 1857 del Código Civil, respondiendo por evicción y vicios redhibitorios.

## ENTREGA Y TRADICIÓN

La tradición del inmueble se realiza conforme al art. 686 del Código Civil, mediante la inscripción en el Conservador de Bienes Raíces, la que se practicará una vez protocolizada la presente escritura.

## DECLARACIONES ESPECIALES

{{#if declaracion_copropiedad}}
- El inmueble forma parte de un condominio sujeto a la Ley 21.442 (Copropiedad Inmobiliaria), administración a cargo de {{copropiedad_administrador}}.
- Gastos comunes al día: {{copropiedad_gastos_estado}}.
{{/if}}

{{#if declaracion_vivienda_social}}
- El inmueble se encuentra afecto a las normas del MINVU según DFL 2 de 1959; no podrá ser arrendado por menos del arriendo mínimo legal.
{{/if}}

## CLÁUSULAS PENALES

- Mora automática: se aplicará el interés máximo convencional del art. 6 de la Ley 18.010 sobre operaciones de crédito de dinero, sin perjuicio de la resolución del contrato.
- Cláusula penal compensatoria: 10% del precio por incumplimiento grave.

## IMPUESTOS Y GASTOS

- **Impuesto territorial:** al día al {{fecha_pago_contribuciones}}.
- **Contribuciones:** serán de cargo del comprador a partir de la fecha de tradición.
- **Gastos notariales y de inscripción:** {{gastos_notariales}}.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{vendedor_nombre}}
RUN: {{vendedor_rut}}
**VENDEDOR**

_________________________
{{comprador_nombre}}
RUN: {{comprador_rut}}
**COMPRADOR**

{{#if conyuge_comprador_nombre}}
_________________________
{{conyuge_comprador_nombre}}
RUN: {{conyuge_comprador_rut}}
**CÓNYUGE — CONFORME**
{{/if}}

---

> ## VARIABLES
>
> - `vendedor_nombre`, `vendedor_rut`, `vendedor_estado_civil`, `vendedor_domicilio` (todos requeridos)
> - `comprador_nombre`, `comprador_rut`, `comprador_estado_civil`, `comprador_domicilio` (todos requeridos)
> - `conyuge_comprador_nombre`, `conyuge_comprador_rut`, `conyuge_comprador_regimen` (opcionales, completar cuando aplique)
> - `inmueble_tipo`, `inmueble_direccion`, `inmueble_comuna`, `inmueble_ciudad`, `inmueble_rol`, `inmueble_fojas`, `inmueble_numero`, `inmueble_anio_inscripcion`, `inmueble_conservador`, `inmueble_deslinde_norte`, `inmueble_deslinde_sur`, `inmueble_deslinde_oriente`, `inmueble_deslinde_poniente`, `inmueble_servidumbres`, `inmueble_gravamenes` (todos requeridos)
> - `precio_uf`, `precio_pal`, `pago_detalle` (requeridos)
> - `pie_pago`, `saldo_financiamiento`, `banco_nombre`, `banco_tasa`, `banco_plazo`, `banco_promesa_hipoteca` (opcionales)
> - `declaracion_copropiedad`, `copropiedad_administrador`, `copropiedad_gastos_estado`, `declaracion_vivienda_social`, `fecha_pago_contribuciones`, `gastos_notariales` (opcionales)
> - `ciudad`, `fecha` (requeridos)
