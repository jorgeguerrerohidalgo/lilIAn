# CONTRATO DE ARRIENDO DE VIVIENDA

> **Categoría:** arriendos
> **Marco legal:** Ley 18.101 (artículos 1, 2, 4, 6, 7, 12, 14); arts. 1915 a 1996 del Código Civil; Ley 19.496 cuando el arrendador es proveedor persona jurídica.
> **Solemnidad:** Escritura privada con firma del arrendatario (Ley 18.101 art. 5). Inscripción si el plazo es superior a un año.
> **Ministro de fe:** No requiere, salvo ratificación en caso de cobro judicial.

---

## ARRENDADOR

- **Nombre:** {{arrendador_nombre}}
- **RUT:** {{arrendador_rut}}
- **Domicilio:** {{arrendador_domicilio}}
- **Comuna:** {{arrendador_comuna}}
- **Ciudad:** {{arrendador_ciudad}}

## ARRENDATARIO

- **Nombre:** {{arrendatario_nombre}}
- **RUT:** {{arrendatario_rut}}
- **Estado civil:** {{arrendatario_estado_civil}}
- **Profesión u oficio:** {{arrendatario_profesion}}
- **Domicilio actual:** {{arrendatario_domicilio}}

{{#if codeudor_nombre}}
- **Codeudor:** {{codeudor_nombre}}, RUT {{codeudor_rut}}
- **Domicilio codeudor:** {{codeudor_domicilio}}
{{/if}}

## INMUEBLE

- **Tipo:** {{inmueble_tipo}}
- **Dirección:** {{inmueble_direccion}}
- **Comuna:** {{inmueble_comuna}}
- **Ciudad:** {{inmueble_ciudad}}
- **Rol de avalúo fiscal:** {{inmueble_rol}}
- **Mobiliario incluido:** {{inmueble_mobiliario}}

## CLÁUSULAS OBLIGATORIAS (Ley 18.101)

### Renta y reajustabilidad

- **Renta mensual:** UF {{renta_uf}} (${{renta_pesos}} al {{fecha_firma}})
- **Reajuste:** Trimestral según variación del IPC del período (Ley 18.101 art. 4). Excepcionalmente podrá pactarse un reajuste distinto, siempre que conste por escrito.
- **Día de pago:** entre los días {{dia_pago_minimo}} y {{dia_pago_maximo}} de cada mes.

### Garantía (art. 6 Ley 18.101)

- **Monto:** equivalente a un mes de renta (UF {{garantia_uf}}).
- **Forma de constitución:** {{garantia_forma}}.
- **Devolución:** dentro de 30 días contados desde la restitución del inmueble, descontados los daños y rentas impagas, con reajuste por IPC desde la fecha de término del arriendo.

{{#if garantia_adicional}}
- **Garantía adicional:** conforme al art. 7 de la Ley 18.101, UF {{garantia_adicional_uf}} (hasta 2 rentas para talleres, comercios o industrias).
{{/if}}

### Plazo (art. 2 Ley 18.101)

- **Duración:** {{plazo_duracion}} meses, desde el {{plazo_inicio}} hasta el {{plazo_termino}}.
- **Renovación tácita:** conforme al artículo 1951 del Código Civil, el contrato se entenderá renovado por períodos iguales si ninguna parte avisa con la anticipación legal.

### Desahucio (art. 12 Ley 18.101)

- Para vivienda: aviso previo con 60 días de anticipación por escrito a la fecha de término.
- Para comercio, taller o industria: 90 días.

### Prohibiciones del arrendatario

- Subarrendar o ceder el contrato sin autorización escrita del arrendador (art. 1946 Código Civil).
- Destinar el inmueble a un uso distinto del convenido.
- Causar molestias a los vecinos o contravenir las normas del Reglamento de Copropiedad cuando corresponda.

### Obligaciones del arrendador (art. 1927 Código Civil)

- Mantener el inmueble en condiciones de servir al uso convenido.
- Responder por los defectos que afecten la seguridad y habitabilidad.
- Pagar las contribuciones y permisos municipales que correspondan.

### Restitución (art. 14 Ley 18.101)

En caso de término del contrato, el arrendatario restituye materialmente el inmueble. Si no lo hiciera voluntariamente, el arrendador puede demandar la restitución judicial con el procedimiento del art. 14.

### Cláusula penal

- **Mora:** interés corriente del mercado (art. 795 Código de Comercio) desde el primer día de atraso.
- **Cláusula penal compensatoria:** 100% de la renta mensual para el caso de restitución tardía del inmueble.

### Comisión a la administración

{{#if comision_admin}}
- **Comisión por reestructuración de garantía:** {{comision_admin_porcentaje}}% (prohibida por el art. 6 inc. 4° de la Ley 18.101, salvo pacto expreso excluyente).
{{/if}}

## DECLARACIÓN ESPECIAL

El presente contrato se celebra en el marco de la Ley 18.101 y se interpretará de acuerdo con el principio de protección del arrendatario contenido en el art. 2 bis del mismo cuerpo legal.

---

**En {{ciudad}}, a {{fecha}}**

_________________________
{{arrendador_nombre}}
RUN: {{arrendador_rut}}
**ARRENDADOR**

_________________________
{{arrendatario_nombre}}
RUN: {{arrendatario_rut}}
**ARRENDATARIO**

{{#if codeudor_nombre}}
_________________________
{{codeudor_nombre}}
RUN: {{codeudor_rut}}
**CODEUDOR**
{{/if}}

---

> ## VARIABLES
>
> - `arrendador_nombre`, `arrendador_rut`, `arrendador_domicilio`, `arrendador_comuna`, `arrendador_ciudad` (todos requeridos)
> - `arrendatario_nombre`, `arrendatario_rut`, `arrendatario_estado_civil`, `arrendatario_profesion`, `arrendatario_domicilio` (todos requeridos)
> - `codeudor_nombre`, `codeudor_rut`, `codeudor_domicilio` (opcionales)
> - `inmueble_tipo`, `inmueble_direccion`, `inmueble_comuna`, `inmueble_ciudad`, `inmueble_rol`, `inmueble_mobiliario` (todos requeridos)
> - `renta_uf`, `renta_pesos`, `dia_pago_minimo`, `dia_pago_maximo`, `fecha_firma` (todos requeridos)
> - `garantia_uf`, `garantia_forma` (requeridos)
> - `garantia_adicional`, `garantia_adicional_uf` (opcionales)
> - `plazo_duracion`, `plazo_inicio`, `plazo_termino` (todos requeridos)
> - `comision_admin`, `comision_admin_porcentaje` (opcionales)
> - `ciudad`, `fecha` (requeridos)
