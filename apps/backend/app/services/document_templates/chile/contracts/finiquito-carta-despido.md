# CARTA DE DESPIDO + FINIQUITO

> **Categoría:** laboral
> **Marco legal:** arts. 159, 160, 161, 162, 163, 168, 171 y 172 del Código del Trabajo; Ley 19.728 (Seguro de Cesantía).
> **Solemnidad:** Carta (art. 162) por escrito, entregada con constancia de recepción. Finiquito ratificado ante ministro de fe (art. 177).
> **Ministro de fe:** Notario / Inspector del Trabajo.

---

## PARTE 1: CARTA DE DESPIDO (art. 162 del Código del Trabajo)

### IDENTIFICACIÓN DEL EMPLEADOR

- **Razón social:** {{empleador_razon_social}}
- **RUT:** {{empleador_rut}}
- **Giro:** {{empleador_giro}}
- **Domicilio:** {{empleador_domicilio}}
- **Representante legal:** {{empleador_representante}}, RUT {{empleador_representante_rut}}

### IDENTIFICACIÓN DEL TRABAJADOR

- **Nombre:** {{trabajador_nombre}}
- **RUT:** {{trabajador_rut}}
- **Cargo:** {{trabajador_cargo}}
- **Fecha de ingreso:** {{trabajador_ingreso}}
- **Domicilio:** {{trabajador_domicilio}}

### COMUNICACIÓN DEL DESPIDO

Por medio de la presente, y en cumplimiento de lo dispuesto en el artículo 162 del Código del Trabajo, comunicamos a usted la decisión de poner término a su contrato de trabajo a partir del día {{trabajador_egreso}}.

### CAUSAL INVOCADA

{{#if causal_art159_4}}
El empleador invoca la causal del **artículo 159 N°4 del Código del Trabajo**, esto es, las necesidades de la empresa. Los hechos que la fundamentan son: {{causal_159_4_hechos}}.
{{/if}}

{{#if causal_art161}}
El empleador invoca la causal de **desahucio del artículo 161 del Código del Trabajo}}.
{{/if}}

{{#if causal_art160_7}}
El empleador invoca la causal del **artículo 160 N°7 del Código del Trabajo**, esto es, incumplimiento grave de las obligaciones del contrato. Los hechos que la fundamentan son: {{causal_160_7_hechos}}.
{{/if}}

{{#if causal_art163_bis}}
El empleador invoca la causal del **artículo 163 bis del Código del Trabajo**, por requerimientos de carácter estructural y no atribuibles al trabajador. Los hechos que la fundamentan son: {{causal_163_bis_hechos}}.
{{/if}}

### AVISO Y FINIQUITO

**AVISO PREVIO (art. 162 inc. 1°):**

{{#if se_dio_aviso}}
Se cumple con el aviso previo de 30 días, por lo que esta comunicación se entrega con fecha {{fecha_aviso}}, surtiendo efecto el {{trabajador_egreso}}.
{{/if}}

{{#if no_se_dio_aviso}}
No se da el aviso previo de 30 días, por lo que se pagará **indemnización sustitutiva del aviso previo** equivalente a un mes de la última remuneración, conforme al art. 162 inc. 2° del Código del Trabajo.
{{/if}}

**A VUELTAS O INDEMNIZACIONES:**

{{#if indemnizacion_anios_servicio}}
- Indemnización por años de servicio (art. 163): 1 mes por año o fracción superior a 6 meses, con tope de 11 años y tope remuneracional de 90 UFM.
{{/if}}

{{#if indemnizacion_sustitutiva_aviso}}
- Indemnización sustitutiva del aviso previo (art. 162 inc. 2°): 1 mes de remuneración.
{{/if}}

{{#if recargo_30}}
- Recargo del 30% (art. 168): procede por no pago oportuno de las indemnizaciones en el plazo legal.
{{/if}}

{{#if recargo_50}}
- Recargo del 50% (art. 171): procede cuando el despido es atribuible a incumplimiento grave del empleador.
{{/if}}

{{#if recargo_80}}
- Recargo del 80% (art. 162 inc. 7°): procede cuando el empleador invoca erróneamente la causal del art. 159 N°4.
{{/if}}

### FORMA DE PAGO

- **Las indemnizaciones legales y voluntarias se pagarán mediante:** {{pago_modalidad}}.
- **A partir del:** {{pago_fecha}}.
- **Lugar de pago:** {{pago_lugar}}.

### ACTO DE FIRMA

El(la) trabajador(a) puede firmar la carta de despido como constancia de recepción, o dejar expresa constancia de su negativa a firmar. La negativa a firmar no afecta la validez del despido.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{empleador_representante}}
RUN: {{empleador_representante_rut}}
**EMPLEADOR**

_________________________
{{trabajador_nombre}}
RUN: {{trabajador_rut}}
**TRABAJADOR — RECIBÍ CONFORME (o RECHAZO FIRMAR)**

Si firma en rechazo: _________________________

---

## PARTE 2: FINIQUITO (art. 177 del Código del Trabajo)

### ENCABEZADO

**FINIQUITO LABORAL** celebrado entre **{{empleador_razon_social}}** (RUT {{empleador_rut}}), en adelante "el empleador", y **{{trabajador_nombre}}** (RUT {{trabajador_rut}}), en adelante "el trabajador", con fecha **{{fecha}}**, en la ciudad de **{{ciudad}}**.

### DESGLOSE DE HABERES

| Concepto | Monto |
|----------|-------|
| Remuneraciones pendientes del mes en curso | ${{remuneracion_mes_monto}} |
| Mes de aviso (sustituto) | ${{mes_aviso_monto}} |
| Indemnización por años de servicio | ${{anios_servicio_monto}} |
| Recargo art. 168 / 171 / 162 (indicar %) | ${{recargo_monto}} |
| Vacaciones proporcionales | ${{feriado_monto}} |
| Bonos adeudados | ${{bonos_monto}} |
| **TOTAL HABERES** | **${{total_haberes}}** |
| Descuentos legales (AFP, salud, AFC, etc.) | ${{total_descuentos}} |
| **LÍQUIDO A PAGAR** | **${{total_liquido}}** |

### DECLARACIÓN DEL TRABAJADOR

El(la) trabajador(a) declara recibir del(la) empleador(a) la suma de **${{total_liquido}}** ({{liquido_pal}}), declarando que nada se le adeuda por concepto de remuneraciones, horas extras, comisiones, bonos, vacaciones, indemnizaciones u otros, por el período comprendido entre el {{trabajador_ingreso}} y el {{trabajador_egreso}}.

{{#if reserva_de_acciones}}
Se reserva expresamente el derecho a demandar por concepto de {{accion_reservada}}.
{{/if}}

### DECLARACIÓN DEL EMPLEADOR

El(la) empleador(a) declara haber pagado la totalidad de las remuneraciones y prestaciones adeudadas, conforme al art. 177 del Código del Trabajo.

### RATIFICACIÓN ANTE MINISTRO DE FE

El(la) ministro(a) de fe que suscribe declara que ambas partes ratifican el contenido y firma del presente finiquito, y que las firmas fueron puestas en su presencia.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{empleador_representante}}
RUN: {{empleador_representante_rut}}
**EMPLEADOR**

_________________________
{{trabajador_nombre}}
RUN: {{trabajador_rut}}
**TRABAJADOR**

_________________________
**{{ministro_fe_cargo}}: {{ministro_fe_nombre}}**
RUN: {{ministro_fe_rut}}
**MINISTRO DE FE QUE RATIFICA**

---

> ## VARIABLES
>
> ### PARTE 1 (Carta de despido)
> - `empleador_razon_social`, `empleador_rut`, `empleador_giro`, `empleador_domicilio`, `empleador_representante`, `empleador_representante_rut` (todos requeridos)
> - `trabajador_nombre`, `trabajador_rut`, `trabajador_cargo`, `trabajador_ingreso`, `trabajador_domicilio`, `trabajador_egreso` (todos requeridos)
> - `causal_art159_4`, `causal_159_4_hechos`, `causal_art161`, `causal_art160_7`, `causal_160_7_hechos`, `causal_art163_bis`, `causal_163_bis_hechos` (uno de los 4 requerido)
> - `se_dio_aviso`, `no_se_dio_aviso`, `fecha_aviso` (uno de los dos requerido)
> - `indemnizacion_anios_servicio`, `indemnizacion_sustitutiva_aviso`, `recargo_30`, `recargo_50`, `recargo_80` (opcionales, marcar los aplicables)
> - `pago_modalidad`, `pago_fecha`, `pago_lugar` (todos requeridos)
>
> ### PARTE 2 (Finiquito)
> - `remuneracion_mes_monto`, `mes_aviso_monto`, `anios_servicio_monto`, `recargo_monto`, `feriado_monto`, `bonos_monto`, `total_haberes`, `total_descuentos`, `total_liquido`, `liquido_pal` (todos requeridos)
> - `reserva_de_acciones`, `accion_reservada` (opcionales)
> - `ministro_fe_cargo`, `ministro_fe_nombre`, `ministro_fe_rut` (todos requeridos)
> - `ciudad`, `fecha` (requeridos)
