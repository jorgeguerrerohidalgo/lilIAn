# FINIQUITO LABORAL

> **Categoría:** laboral
> **Marco legal:** arts. 162, 163, 168, 169, 171, 172 y 177 del Código del Trabajo; Ley 19.728 (Seguro de Cesantía); Ley 17.322 (cobranza previsional).
> **Solemnidad:** Ratificación ante ministro de fe (art. 177 Código del Trabajo) — Notario, Inspector del Trabajo o persona capacitada.
> **Ministro de fe:** Notario / Inspector del Trabajo.

---

## DATOS DEL TRABAJADOR

- **Nombre:** {{trabajador_nombre}}
- **RUT:** {{trabajador_rut}}
- **Estado civil:** {{trabajador_estado_civil}}
- **Nacionalidad:** {{trabajador_nacionalidad}}
- **Domicilio:** {{trabajador_domicilio}}
- **Cargo o función:** {{trabajador_cargo}}
- **Fecha de ingreso:** {{trabajador_ingreso}}
- **Fecha de egreso:** {{trabajador_egreso}}

## DATOS DEL EMPLEADOR

- **Razón social:** {{empleador_razon_social}}
- **RUT:** {{empleador_rut}}
- **Giro:** {{empleador_giro}}
- **Domicilio:** {{empleador_domicilio}}
- **Representante legal:** {{empleador_representante}}, RUT {{empleador_representante_rut}}

## CAUSAL DE TÉRMINO DEL CONTRATO

{{#if causal_art159}}
- **Causal:** art. 159 N°{{causal_159_numero}} del Código del Trabajo ({{causal_159_desc}}).
{{/if}}

{{#if causal_art160}}
- **Causal:** art. 160 N°{{causal_160_numero}} del Código del Trabajo ({{causal_160_desc}}).
{{/if}}

{{#if causal_art161}}
- **Desahucio del empleador:** art. 161 del Código del Trabajo.
{{/if}}

{{#if causal_art171}}
- **Autodespido:** art. 171 del Código del Trabajo, por incumplimiento grave del empleador.
{{/if}}

## DETALLE DE HABERES

### Remuneraciones pendientes

| Concepto | Cálculo | Monto |
|----------|---------|-------|
| Remuneraciones del mes en curso | {{remuneracion_mes_detalle}} | ${{remuneracion_mes_monto}} |
| Horas extras impagas | {{horas_extras_detalle}} | ${{horas_extras_monto}} |
| Comisiones adeudadas | {{comisiones_detalle}} | ${{comisiones_monto}} |
| Bonos adeudados | {{bonos_detalle}} | ${{bonos_monto}} |

### Indemnizaciones

| Concepto | Base legal | Cálculo | Monto |
|----------|-----------|---------|-------|
| Mes de aviso (sustituto) | art. 162 inc. 2 | {{mes_aviso_calculo}} | ${{mes_aviso_monto}} |
| Años de servicio | art. 163 | {{anios_servicio_calculo}} | ${{anios_servicio_monto}} |
| Recargo del art. 168 | 30% / 50% / 80% | {{recargo_calculo}} | ${{recargo_monto}} |
| Vacaciones proporcionales | art. 73 | {{feriado_calculo}} | ${{feriado_monto}} |

### Cotizaciones previsionales

| Concepto | Estado |
|---------|--------|
| AFP | {{estado_afp}} |
| FONASA / ISAPRE | {{estado_salud}} |
| Seguro de Cesantía (AFC) | {{estado_afc}} |
| Mutualidad / Accidentes del trabajo | {{estado_mutualidad}} |

### Totales

- **Total haberes:** ${{total_haberes}}
- **Total descuentos legales:** ${{total_descuentos}}
- **Líquido a pagar:** ${{total_liquido}}

## FORMA Y OPORTUNIDAD DEL PAGO

- **Modalidad:** {{pago_modalidad}} ({{pago_instrumento}}).
- **A disposición del trabajador desde:** {{pago_fecha}}.
- **Moneda:** pesos chilenos (CLP).

## DECLARACIÓN DEL TRABAJADOR

El(la) trabajador(a) declara recibir, a su entera conformidad, el monto líquido indicado en el presente instrumento, declarando que nada se le adeuda por concepto de remuneraciones, horas extras, comisiones, bonos, vacaciones, indemnizaciones u otros, por el período comprendido entre el {{trabajador_ingreso}} y el {{trabajador_egreso}}.

{{#if reserva_de_acciones}}
- **Reserva de acciones:** el(la) trabajador(a) se reserva expresamente el derecho a deducir las acciones que estime pertinentes por concepto de {{accion_reservada}}.
{{/if}}

{{#if finiquito_pago_inmediato}}
- **Pago inmediato:** este pago tiene el carácter de indemnizatorio y se realiza en este acto, sin perjuicio de las acciones de nulidad del despido del artículo 168 del Código del Trabajo.
{{/if}}

## DECLARACIÓN DEL EMPLEADOR

El(la) empleador(a) declara haber puesto a disposición del(la) trabajador(a) la totalidad de las remuneraciones y prestaciones adeudadas, en los términos del artículo 177 del Código del Trabajo.

## FIRMAS Y RATIFICACIÓN

Las partes firman en presencia del ministro de fe que ratifica, en conformidad al art. 177 del Código del Trabajo.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{trabajador_nombre}}
RUN: {{trabajador_rut}}
**TRABAJADOR**

_________________________
{{empleador_representante}}
RUN: {{empleador_representante_rut}}
**EMPLEADOR**

_________________________
**{{ministro_fe_cargo}}: {{ministro_fe_nombre}}**
RUN: {{ministro_fe_rut}}
**MINISTRO DE FE QUE RATIFICA**

---

> ## VARIABLES
>
> `trabajador_nombre`, `trabajador_rut`, `trabajador_estado_civil`, `trabajador_nacionalidad`, `trabajador_domicilio`, `trabajador_cargo`, `trabajador_ingreso`, `trabajador_egreso` (todos requeridos)
>
> `empleador_razon_social`, `empleador_rut`, `empleador_giro`, `empleador_domicilio`, `empleador_representante`, `empleador_representante_rut` (todos requeridos)
>
> `causal_art159`, `causal_159_numero`, `causal_159_desc`, `causal_art160`, `causal_160_numero`, `causal_160_desc`, `causal_art161`, `causal_art171`, `causal_171_desc` (uno de los 4 grupos requerido)
>
> `remuneracion_mes_detalle`, `horas_extras_detalle`, `comisiones_detalle`, `bonos_detalle`, `mes_aviso_calculo`, `anios_servicio_calculo`, `recargo_calculo`, `feriado_calculo` (todos opcionales, completar según corresponda)
>
> `estado_afp`, `estado_salud`, `estado_afc`, `estado_mutualidad` (todos requeridos)
>
> `pago_modalidad`, `pago_instrumento`, `pago_fecha` (todos requeridos)
>
> `reserva_de_acciones`, `accion_reservada`, `finiquito_pago_inmediato` (todos opcionales)
>
> `ministro_fe_cargo`, `ministro_fe_nombre`, `ministro_fe_rut` (todos requeridos)
>
> `ciudad`, `fecha` (requeridos)
