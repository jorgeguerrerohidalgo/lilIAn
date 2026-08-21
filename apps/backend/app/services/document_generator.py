"""
Document Generator Service

Generates documents from templates with context from matters/documents.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta a los templates
TEMPLATES_DIR = Path(__file__).parent / "document_templates"
# Sub-carpetas por país. S5.4 agrega ``chile/contracts/`` con plantillas
# markdown de uso notarial que se montan en la misma jerarquía.
CHILE_TEMPLATES_DIR = TEMPLATES_DIR / "chile" / "contracts"


def _load_markdown_template(md_path: Path) -> dict | None:
    """S5.4 — carga un template markdown de ``chile/contracts/`` y lo
    adapta al esquema JSON que consume ``document_generator``.

    El bloque de metadata en la cabecera del MD (líneas ``>``: ``key``)
    provee ``id``, ``category``, ``legal_area`` y ``description``. La
    lista de variables se infiere de las marcas ``{{var}}`` en el
    cuerpo, marcándolas como requeridas por defecto cuando aparecen
    en MAYÚSCULAS en una lista "VARIABLES" al pie, o como opcionales
    en los ``{{#if ...}}``.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None

    inline = _parse_blockquote_metadata(text)
    body = _strip_blockquote_metadata(text)

    base_id = md_path.stem
    template_id = inline.get("id") or base_id
    category = inline.get("category", "chile")
    description = inline.get("description", "")

    variables = _extract_variables_from_template(body)

    return {
        "id": template_id,
        "name": inline.get("name") or base_id.replace("-", " ").title(),
        "category": category,
        "description": description,
        "legal_area": inline.get("legal_area"),
        "framework": inline.get("framework"),
        "language": "es-CL",
        "format": "markdown",
        "path": str(md_path.relative_to(TEMPLATES_DIR.parent)),
        "variables": variables,
        "template": body,
    }


def _parse_blockquote_metadata(text: str) -> dict[str, str]:
    """Parsea los ``> **Clave:** valor`` al inicio del archivo."""

    meta: dict[str, str] = {}
    capture = True
    for line in text.splitlines():
        if not line.startswith(">"):
            if line.strip() == "" or line.startswith("#"):
                continue
            # Cualquier línea que no sea de metadata corta la captura.
            capture = False
            continue
        if line.strip() == ">":
            continue
        # Saltar el separador "---".
        if line.strip() == "---":
            continue
        # Extraer **Clave:** valor
        match = re.match(r"^>\s*\*\*([^*]+):\*\*\s*(.*)$", line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            meta[key] = value
    return meta


def _strip_blockquote_metadata(text: str) -> str:
    """Quita la cabecera de metadata (líneas ``>``) y deja el cuerpo."""

    out_lines: list[str] = []
    skip_header = True
    for line in text.splitlines():
        if skip_header:
            if line.strip() == "" or line.startswith(">"):
                continue
            skip_header = False
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def _extract_variables_from_template(body: str) -> list[dict]:
    """Encuentra ``{{var}}`` en el cuerpo y devuelve la lista de
    variables con un heurístico de ``required``.
    """

    used = set()
    for match in re.finditer(r"\{\{#if\s*!?(\w+)\}\}", body):
        used.add(match.group(1))
    for match in re.finditer(r"\{\{(\w+)\}\}", body):
        used.add(match.group(1))

    # Mapeo a required basándonos en una convención propia: variables
    # que aparecen en cláusulas SIN un ``{{#if}}`` cercano son
    # requeridas; las que sólo aparecen en ``{{#if}}`` son opcionales.
    used_in_conditional = set()
    for match in re.finditer(r"\{\{#if\s*!?(\w+)\}\}", body):
        used_in_conditional.add(match.group(1))

    variables = []
    for name in sorted(used):
        variables.append({
            "key": name,
            "label": name.replace("_", " ").title(),
            "required": name not in used_in_conditional,
        })
    return variables


def _load_chile_contracts() -> list[dict]:
    """S5.4 — carga todos los .md de ``chile/contracts/``."""

    if not CHILE_TEMPLATES_DIR.exists():
        return []

    templates: list[dict] = []
    for file in sorted(CHILE_TEMPLATES_DIR.glob("*.md")):
        template = _load_markdown_template(file)
        if template:
            templates.append(template)
    return templates


def get_all_templates() -> list[dict]:
    """Obtiene todos los templates disponibles."""
    templates: list[dict] = []

    if not TEMPLATES_DIR.exists():
        return templates

    for file in TEMPLATES_DIR.glob("*.json"):
        if file.name == "__init__.py":
            continue
        try:
            with open(file, encoding="utf-8") as f:
                template_data = json.load(f)
                templates.append(template_data)
        except Exception:
            continue

    # S5.4: plantillas markdown de contratos notariales chilenos.
    templates.extend(_load_chile_contracts())

    return templates


def get_template_by_id(template_id: str) -> dict | None:
    """Obtiene un template específico por su ID."""
    templates = get_all_templates()
    for template in templates:
        if template.get("id") == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> list[dict]:
    """Obtiene templates filtrados por categoría."""
    templates = get_all_templates()
    return [t for t in templates if t.get("category") == category]


def get_categories() -> list[str]:
    """Obtiene lista de categorías únicas."""
    templates = get_all_templates()
    categories = set(t.get("category", "") for t in templates)
    return sorted(list(categories))


def fill_template(template_text: str, variables: dict) -> str:
    """Reemplaza variables en el template.

    Sintaxis de variables:
    - {{variable}} - reemplaza con el valor
    - {{#if variable}}...{{/if}} - condición if
    - {{#if variable}}...{{else}}...{{/if}} - condición if/else
    - {{#if !variable}}...{{/if}} - condición if negada

    S4-13: previously this 86-line function held an if-block parser as a
    nested closure. Extract the parser into module-level helpers so the
    dispatcher becomes a clean two-step pipeline: process all if-blocks,
    then substitute remaining variables.
    """
    if_pattern = re.compile(r"\{\{#if\s*!?(\w+)\}\}", re.DOTALL)

    result = _process_all_if_blocks(template_text, variables, if_pattern)
    result = _substitute_remaining_variables(result, variables)
    return result


def _process_all_if_blocks(
    template_text: str, variables: dict, if_pattern: re.Pattern
) -> str:
    """Iteratively scan for if/else/endif directives and expand each one
    in place. Stops when no more if directives remain.
    """
    result = template_text
    while True:
        new_result = _process_one_if_block(result, variables, if_pattern)
        if new_result is None:
            break
        result = new_result
    return result


def _process_one_if_block(
    text: str, variables: dict, if_pattern: re.Pattern
) -> str | None:
    """Process the first if-block in text, returning the rewritten string;
    return None when no if-block remains.
    """
    match = if_pattern.search(text)
    if not match:
        return None

    var_name, is_negated = _if_block_metadata(match)
    start_pos = match.start()
    after_open = match.end()

    endif_pos, else_pos = _find_endif_and_else(text, after_open)
    if endif_pos is None:
        return None

    if_content, else_content = _split_if_content(text, after_open, else_pos, endif_pos)

    replacement = _eval_if_condition(variables, var_name, is_negated, if_content, else_content)
    return text[:start_pos] + replacement + text[endif_pos + 7:]


def _if_block_metadata(match: re.Match) -> tuple[str, bool]:
    """Return (variable_name, is_negated) extracted from the if-open regex."""
    return match.group(1), match.group(0).startswith("{{#if !")


def _find_endif_and_else(text: str, search_start: int) -> tuple[int | None, int | None]:
    """Walk the template tracking nested if-blocks; return (endif_pos, else_pos).

    Both positions are absolute indices in ``text``. ``else_pos`` is None
    when the if-block has no else branch.
    """
    search_pos = search_start
    depth = 1
    else_pos = None
    while depth > 0 and search_pos < len(text):
        next_brace = text.find("{{", search_pos)
        if next_brace == -1:
            return None, None
        if text[next_brace:].startswith("{{#if"):
            depth += 1
            search_pos = next_brace + 5
        elif text[next_brace:].startswith("{{/if}}"):
            depth -= 1
            if depth == 0:
                return next_brace, else_pos
            search_pos = next_brace + 6
        elif depth == 1 and text[next_brace:].startswith("{{else}}"):
            else_pos = next_brace
            search_pos = next_brace + 7
        else:
            search_pos = next_brace + 2
    return None, None


def _split_if_content(
    text: str, after_open: int, else_pos: int | None, endif_pos: int
) -> tuple[str, str | None]:
    """Slice the if/else content between directives. else_content is None
    when the if-block has no else branch.
    """
    if else_pos is not None:
        return text[after_open:else_pos], text[else_pos + 7:endif_pos]
    return text[after_open:endif_pos], None


def _eval_if_condition(
    variables: dict, var_name: str, is_negated: bool, if_content: str, else_content: str | None
) -> str:
    """Return the replacement string based on whether the condition holds."""
    truthy = bool(variables.get(var_name))
    if is_negated:
        truthy = not truthy
    if truthy:
        return if_content
    return else_content if else_content else ""


def _substitute_remaining_variables(template_text: str, variables: dict) -> str:
    """Replace {{var}} occurrences with their stringified values after the
    if-block pass has run.
    """
    result = template_text
    for key, value in variables.items():
        replacement = "" if value is None else str(value)
        result = result.replace("{{" + key + "}}", replacement)
    return result

def generate_document(
    template_id: str,
    variables: dict,
    context: dict = None
) -> dict:
    """Genera un documento desde un template.

    Args:
        template_id: ID del template a usar
        variables: Variables para completar el documento
        context: Contexto adicional del matter/documento

    Returns:
        dict con:
        - success: bool
        - content: texto del documento generado
        - template: datos del template usado
        - errors: lista de errores de validación
    """
    template = get_template_by_id(template_id)

    if not template:
        return {
            "success": False,
            "content": None,
            "errors": [f"Template '{template_id}' no encontrado"]
        }

    errors = []
    template_vars = template.get("variables", [])

    # Validar campos requeridos
    for var_def in template_vars:
        key = var_def.get("key")
        required = var_def.get("required", False)

        if required and not variables.get(key):
            errors.append(f"Campo requerido: {var_def.get('label', key)}")

    # Agregar variables de contexto si no están definidas
    if context:
        default_vars = {
            "fecha": datetime.now().strftime("%d de %B de %Y"),
            "ciudad": context.get("ciudad", "Santiago"),
        }
        for key, value in default_vars.items():
            if not variables.get(key):
                variables[key] = value

    # Llenar template
    content = fill_template(template.get("template", ""), variables)

    return {
        "success": len(errors) == 0,
        "content": content,
        "template": template,
        "errors": errors,
        "document_name": f"{template.get('name', 'Documento')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    }


def get_chunks_text_for_matter(matter_id: int, organization_id: int, max_chars: int = 30000) -> str:
    """Obtiene el texto de los documentos de un matter."""
    from app.core.database import SessionLocal
    from app.models.document_chunk import DocumentChunk

    db = SessionLocal()
    try:
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.matter_id == matter_id,
            DocumentChunk.organization_id == organization_id
        ).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()

        text_parts = []
        total_chars = 0
        for chunk in chunks:
            if total_chars + len(chunk.content) <= max_chars:
                text_parts.append(chunk.content)
                total_chars += len(chunk.content)
            else:
                break

        return "\n\n".join(text_parts)
    finally:
        db.close()


def extract_variables_from_matter(
    template_id: str,
    matter_id: int,
    organization_id: int,
    matter_type: str = None
) -> dict:
    """Usa LLM para extraer variables desde los documentos de un matter.

    Analiza los documentos del caso y sugiere valores para las variables
    del template basándose en el contenido.

    Returns:
        dict con:
        - success: bool
        - suggested_variables: dict con {key: value}
        - reasoning: str con explicación del LLM
        - missing_fields: list de campos que no pudo inferir

    S4-10: split out into helpers so the top-level is a linear
    pipeline: lookup template → fetch text → build prompt → call LLM →
    parse response. Each step is independently testable.
    """
    template = get_template_by_id(template_id)
    if not template:
        return _missing_template_response(template_id)

    documents_text = get_chunks_text_for_matter(matter_id, organization_id)
    template_vars = template.get("variables", [])

    if not _has_enough_text(documents_text):
        return _insufficient_text_response(template_vars)

    prompt = _build_extraction_prompt(template, template_vars, documents_text)
    raw_response = _invoke_extraction_llm(prompt)
    return _parse_extraction_response(raw_response, template_vars)


def _missing_template_response(template_id: str) -> dict:
    return {
        "success": False,
        "suggested_variables": {},
        "reasoning": f"Template '{template_id}' no encontrado",
        "missing_fields": [],
    }


def _insufficient_text_response(template_vars: list) -> dict:
    return {
        "success": False,
        "suggested_variables": {},
        "reasoning": "No hay suficiente texto en los documentos del caso",
        "missing_fields": [v["key"] for v in template_vars],
    }


def _has_enough_text(documents_text: str | None) -> bool:
    return bool(documents_text) and len(documents_text.strip()) >= 100


def _build_extraction_prompt(
    template: dict, template_vars: list, documents_text: str
) -> str:
    """Compose the LLM prompt with template variables + document excerpts."""
    vars_description = "\n".join([
        f"- {v['key']}: {v.get('description', v.get('label', ''))} "
        f"(tipo: {v.get('type', 'text')})"
        for v in template_vars
    ])
    return (
        f"Analiza los siguientes documentos de un caso legal y extrae la "
        f"información relevante para completar un documento.\n\n"
        f"TEMPLATE A COMPLETAR: {template.get('name', '')}\n"
        f"{template.get('description', '')}\n\n"
        f"VARIABLES A COMPLETAR:\n{vars_description}\n\n"
        f"DOCUMENTOS DEL CASO:\n{documents_text[:30000]}\n\n"
        f"Responde en JSON con el siguiente formato:\n"
        f"{{\n"
        f'  "suggested_variables": {{"variable_key": "valor_extraído", ...}},\n'
        f'  "reasoning": "Explicación breve de cómo se infirieron los valores",\n'
        f'  "missing_fields": ["lista de campos que no pudieron inferirse"]\n'
        f"}}\n\n"
        f"Solo incluye en suggested_variables los valores que puedas extraer "
        f"con certeza del texto. Para campos no mencionados en los documentos, "
        f"usa null o no los incluyas."
    )


def _invoke_extraction_llm(prompt: str) -> str:
    """Call the LLM. On any provider error return an empty string so the
    caller always sees a deterministic error path.
    """
    from app.services.llm import get_llm_provider

    try:
        provider = get_llm_provider()
        return provider.generate(
            prompt=prompt,
            system_prompt=None,
            max_tokens=2048,
            temperature=0.3,
        )
    except Exception as exc:
        logger.error(f"Error invoking extraction LLM: {exc}", exc_info=True)
        return ""


def _parse_extraction_response(raw_response: str, template_vars: list) -> dict:
    """Extract JSON from the LLM output, with two fallback strategies:
    1. Look for an inline JSON object that mentions suggested_variables
    2. Fall back to the first ``{...}`` block of any kind
    """
    parsed = _match_json_with_suggested_variables(raw_response)
    if parsed is None:
        parsed = _match_any_json_object(raw_response)

    if parsed is not None:
        return {
            "success": True,
            "suggested_variables": parsed.get("suggested_variables", {}),
            "reasoning": parsed.get(
                "reasoning", "Valores extraídos del contexto"
            ),
            "missing_fields": parsed.get("missing_fields", []),
        }

    # No usable JSON in the response — record what came back so a human
    # can debug the model later.
    return {
        "success": True,
        "suggested_variables": {},
        "reasoning": raw_response[:500],
        "missing_fields": [v["key"] for v in template_vars],
    }


def _match_json_with_suggested_variables(response: str):
    """Greedy regex that prefers an object containing suggested_variables
    over a stray bracket later in the response.
    """
    raw_pattern = r"\{[^{}]*\"suggested_variables\"[^{}]*\}"
    match = re.search(raw_pattern, response, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _match_any_json_object(response: str):
    """Last-resort: take the first balanced object."""
    raw_pattern = r"\{.*\}"
    match = re.search(raw_pattern, response, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

def validate_variables(template_id: str, variables: dict) -> dict:
    """Valida las variables contra un template.

    Returns dict con:
    - valid: bool
    - missing: lista de campos requeridos faltantes
    - all_vars: todas las variables del template
    """
    template = get_template_by_id(template_id)

    if not template:
        return {"valid": False, "missing": [], "all_vars": []}

    template_vars = template.get("variables", [])
    missing = []

    for var_def in template_vars:
        key = var_def.get("key")
        required = var_def.get("required", False)
        if required and not variables.get(key):
            missing.append({
                "key": key,
                "label": var_def.get("label", key),
                "type": var_def.get("type", "text")
            })

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "all_vars": template_vars
    }
