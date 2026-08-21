# PODER GENERAL (Notarial)

> **Categoría:** poderes
> **Marco legal:** Código Civil (arts. 2112 y siguientes), Ley 18.046 (sociedades), Ley 18.101 (arriendos cuando aplique), Ley 19.628 (datos personales).
> **Solemnidad:** Escritura pública ante notario (art. 1677 Código Civil). Inscripción en el Conservador de Bienes Raíces cuando verse sobre inmuebles.
> **Ministro de fe:** Notario Público.

---

## DATOS DEL OTORGANTE

- **Nombre completo:** {{otorgante_nombre}}
- **RUT:** {{otorgante_rut}}
- **Estado civil:** {{otorgante_estado_civil}}
- **Nacionalidad:** {{otorgante_nacionalidad}}
- **Domicilio:** {{otorgante_domicilio}}
- **Comuna:** {{otorgante_comuna}}
- **Ciudad:** {{otorgante_ciudad}}
- **Profesión u oficio:** {{otorgante_profesion}}

## DATOS DEL APODERADO

- **Nombre completo:** {{apoderado_nombre}}
- **RUT:** {{apoderado_rut}}
- **Profesión u oficio:** {{apoderado_profesion}}
- **Domicilio:** {{apoderado_domicilio}}

## FACULTADES

Por el presente instrumento, el(la) otorgante viene en conferir poder **GENERAL** al(la) apoderado(a) para que, en su nombre y representación, ejecute todas las actuaciones y celebre todos los actos y contratos que sean necesarios, en especial y sin que esta enumeración sea taxativa, los siguientes:

1. Representarlo ante toda clase de autoridades administrativas, políticas, judiciales, fiscales, municipales, y ante personas naturales o jurídicas de derecho público o privado.
2. Girar, percibir, transigir, cobrar y cancelar toda clase de documentos, sean letras, pagarés, cheques, facturas, contratos, mutuos, depósitos y cualquier otra obligación.
3. Celebrar contratos de promesa, compraventa, permuta, dación en pago, donación, arrendamiento y subarrendamiento, comodato y mutuo, sobre toda clase de bienes muebles e inmuebles.
4. Constituir, aceptar, posponer, alzar y cancelar hipotecas, prendas, fianzas, solidaridades y demás garantías reales o personales.
5. Otorgar y firmar poderes y revocarlos, delegar y reasumir el presente mandato.
6. Comparecer en juicio y fuera de él, en conformidad al artículo 6 del Código de Procedimiento Civil, en toda clase de juicios y ante cualquier tribunal.
7. Administrar bienes muebles e inmuebles, percibir y pagar rentas, suscribir contratos de trabajo y finiquitos.
8. Constituir, modificar, disolver y liquidar sociedades de cualquier clase, en especial EIRL, SpA, Ltda. y sociedades colectivas.
9. Otorgar los mandatos especiales necesarios para inscribir, renovar y tomar razón de este poder en los registros públicos.
10. Firmar los instrumentos públicos y privados que sean menester, con todas las facultades del artículo 2112 del Código Civil y del artículo 7 del Código de Procedimiento Civil.

## DURACIÓN Y REVOCACIÓN

El presente poder tendrá una vigencia de {{vigencia}} y se entenderá revocado por el(la) otorgante desde el momento en que el(la) apoderado(a) reciba comunicación escrita al efecto, sin necesidad de formalidad adicional.

## DECLARACIÓN

El(la) otorgante declara conocer el alcance del presente mandato y las responsabilidades civiles y penales que de su ejercicio pudieren derivarse, en conformidad al artículo 2402 del Código Civil (obligaciones del mandatario).

---

**En {{ciudad}}, a {{fecha}}**

**EL NOTARIO PÚBLICO QUE SUSCRIBE** certifica que el(la) otorgante, persona identificada en este instrumento, firma en su presencia y declara que es la persona que aparece individualizada, mayor de edad, y que se encuentra en pleno uso de sus facultades.

_________________________
{{otorgante_nombre}}
RUN: {{otorgante_rut}}
**OTORGANTE**

_________________________
{{apoderado_nombre}}
RUN: {{apoderado_rut}}
**APODERADO — ACEPTA EL CARGO**

_________________________
Notario Público
**MINISTRO DE FE**

---

> ## VARIABLES
>
> - `otorgante_nombre` (requerido)
> - `otorgante_rut` (requerido, formato XX.XXX.XXX-X)
> - `otorgante_estado_civil` (requerido)
> - `otorgante_nacionalidad` (requerido)
> - `otorgante_domicilio` (requerido)
> - `otorgante_comuna` (requerido)
> - `otorgante_ciudad` (requerido)
> - `otorgante_profesion` (opcional)
> - `apoderado_nombre` (requerido)
> - `apoderado_rut` (requerido)
> - `apoderado_profesion` (opcional)
> - `apoderado_domicilio` (requerido)
> - `facultades` (opcional, multilínea — se concatena con la lista estándar)
> - `vigencia` (opcional, default: "indefinida")
> - `ciudad` (requerido)
> - `fecha` (requerido, formato ISO 8601)
