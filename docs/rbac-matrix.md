# Matriz RBAC - Lilian

## Definición de Roles

| Rol | Descripción |
|-----|-------------|
| PLATFORM_ADMIN | Administrador global de la plataforma Lilian. Acceso multi-tenant a todas las organizaciones para soporte, mantenimiento y operaciones internas. |
| OWNER | Propietario de la organización. Acceso total dentro de su organización, incluyendo facturación, configuración crítica y eliminación. |
| ADMIN | Administrador de la organización. Gestiona usuarios, configuración y recursos, sin acceso a facturación ni eliminación de la organización. |
| LAWYER | Abogado. Gestiona matters, clientes, documentos y plantillas dentro de su organización. |
| COMPANY_USER | Usuario corporativo. Accede a los matters en los que está asignado, con permisos limitados sobre clientes y documentos. |
| CLIENT | Cliente final. Solo ve sus propios matters y documentos asociados. Sin acceso a recursos administrativos. |
| VIEWER | Lector. Acceso de solo lectura sobre los recursos a los que se le haya concedido visibilidad explícita. |

## Matriz de Permisos (Rol × Recurso × Acción)

Notación: `C` = create, `R` = read, `U` = update, `D` = delete, `A` = admin, `-` = sin acceso, `R*` = lectura restringida al propio contexto (ver notas).

| Recurso      | PLATFORM_ADMIN | OWNER        | ADMIN        | LAWYER       | COMPANY_USER | CLIENT       | VIEWER |
|--------------|----------------|--------------|--------------|--------------|--------------|--------------|--------|
| organizations | CRUD A         | CRUD A       | R U          | R            | R*           | R*           | -      |
| matters       | CRUD A         | CRUD A       | CRUD         | CRUD         | R U (asign.) | R* (propios) | R*     |
| clients       | CRUD A         | CRUD A       | CRUD         | CRUD         | R            | R* (propio)  | R*     |
| documents     | CRUD A         | CRUD A       | CRUD         | CRUD         | R            | R* (propios) | R*     |
| templates     | CRUD A         | CRUD A       | CRUD         | CRUD         | R            | -            | R*     |
| precedents    | CRUD A         | CRUD A       | R            | R            | R            | -            | R*     |
| users         | CRUD A         | CRUD A       | CRUD         | R            | R (auto)     | R (auto)     | R (auto) |
| audit_logs    | R A            | R            | R            | -            | -            | -            | -      |

## Acciones Disponibles

| Acción | Descripción |
|--------|-------------|
| create | Crear nuevos registros del recurso |
| read   | Consultar registros del recurso |
| update | Modificar registros existentes |
| delete | Eliminar registros del recurso |
| admin  | Operaciones administrativas especiales (transferencia de propiedad, configuración de tenant, acceso cross-tenant) |

## Notas y Restricciones de Contexto

### Aislamiento multi-tenant
- **PLATFORM_ADMIN** es el único rol con acceso cross-tenant. Todos los demás operan exclusivamente dentro de su `organization_id`.
- Toda consulta debe filtrar por `organization_id` excepto para `PLATFORM_ADMIN`.

### Restricciones por recurso

- **organizations**
  - `OWNER` puede eliminar (soft-delete) la organización.
  - `ADMIN` actualiza datos de la organización pero no puede eliminarla ni cambiar al `OWNER`.
  - `LAWYER`, `COMPANY_USER` y `CLIENT` solo leen los datos básicos visibles en su interfaz.

- **matters**
  - `LAWYER` es el responsable natural de crear y gestionar matters.
  - `COMPANY_USER` solo ve y actualiza los matters en los que está asignado como colaborador.
  - `CLIENT` solo ve los matters donde figura como cliente asociado.
  - `VIEWER` solo lectura sobre matters explícitamente compartidos.

- **clients**
  - `COMPANY_USER` no puede crear ni eliminar clientes; solo lectura.
  - `CLIENT` solo ve su propio registro.

- **documents**
  - La acción `delete` la realiza el propietario del documento o un `ADMIN`/`OWNER`.
  - `CLIENT` solo ve documentos vinculados a sus propios matters.

- **templates**
  - `LAWYER` puede crear plantillas reutilizables para la organización.
  - `COMPANY_USER` solo lectura (al usar plantillas en la creación de documentos).
  - `CLIENT` y `VIEWER` no acceden salvo que se comparta explícitamente.

- **precedents**
  - Lectura transversal para roles internos (precedentes son base de conocimiento compartida).
  - `CLIENT` no accede. `VIEWER` solo lectura restringida.

- **users**
  - `ADMIN` no puede asignar ni revocar el rol de `OWNER`.
  - `COMPANY_USER`, `CLIENT` y `VIEWER` solo leen su propio perfil.

- **audit_logs**
  - Solo `PLATFORM_ADMIN` (admin), `OWNER` y `ADMIN` pueden consultarlos.
  - Los registros de auditoría son inmutables: nadie puede crear, actualizar ni eliminar.

### Convenciones

- `R*` indica lectura restringida al contexto del usuario (propios matters, documentos propios, etc.).
- `R (auto)` indica que el usuario solo puede leer su propio registro de usuario.
- `-` indica denegación explícita.
- La intersección de permisos se aplica con AND lógico: si una fila deniega una acción, se deniega aunque otra condición la permita.
