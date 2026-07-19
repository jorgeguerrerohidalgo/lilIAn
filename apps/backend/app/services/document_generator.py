"""
Document Generator Service

Generates documents from templates with context from matters/documents.
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


# Ruta a los templates
TEMPLATES_DIR = Path(__file__).parent / "document_templates"


def get_all_templates() -> List[dict]:
    """Obtiene todos los templates disponibles."""
    templates = []

    if not TEMPLATES_DIR.exists():
        return templates

    for file in TEMPLATES_DIR.glob("*.json"):
        if file.name == "__init__.py":
            continue
        try:
            with open(file, "r", encoding="utf-8") as f:
                template_data = json.load(f)
                templates.append(template_data)
        except Exception:
            continue

    return templates


def get_template_by_id(template_id: str) -> Optional[dict]:
    """Obtiene un template específico por su ID."""
    templates = get_all_templates()
    for template in templates:
        if template.get("id") == template_id:
            return template
    return None


def get_templates_by_category(category: str) -> List[dict]:
    """Obtiene templates filtrados por categoría."""
    templates = get_all_templates()
    return [t for t in templates if t.get("category") == category]


def get_categories() -> List[str]:
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
    """
    import re

    if_pattern = re.compile(r'\{\{#if\s*!?(\w+)\}}', re.DOTALL)

    def process_one_if(text):
        """Encuentra y procesa el primer bloque if en el texto."""
        match = if_pattern.search(text)
        if not match:
            return None

        var_name = match.group(1)
        is_negated = match.group(0).startswith('{{#if !')
        start_pos = match.start()
        after_open = match.end()

        # Buscar el {{/if}} o {{else}} correspondiente
        search_pos = after_open
        depth = 1
        else_pos = None

        while depth > 0 and search_pos < len(text):
            next_brace = text.find('{{', search_pos)
            if next_brace == -1:
                return None

            if text[next_brace:].startswith('{{#if'):
                depth += 1
                search_pos = next_brace + 5
            elif text[next_brace:].startswith('{{/if}}'):
                depth -= 1
                if depth == 0:
                    endif_pos = next_brace
                    break
                search_pos = next_brace + 6
            elif depth == 1 and text[next_brace:].startswith('{{else}}'):
                else_pos = next_brace
                search_pos = next_brace + 7
            else:
                search_pos = next_brace + 2
        else:
            return None

        # Extraer contenido
        if else_pos:
            if_content = text[after_open:else_pos]
            else_content = text[else_pos + 7:endif_pos]
        else:
            if_content = text[after_open:endif_pos]
            else_content = None

        # Evaluar condición
        condition = bool(variables.get(var_name))
        if is_negated:
            condition = not condition

        if condition:
            replacement = if_content
        else:
            replacement = else_content if else_content else ""

        # Retornar: texto antes + replacement + texto después del endif
        return text[:start_pos] + replacement + text[endif_pos + 7:]

    # Procesar todos los ifs iterativamente
    result = template_text
    while True:
        new_result = process_one_if(result)
        if new_result is None:
            break
        result = new_result

    # Procesar todas las variables restantes
    for key, value in variables.items():
        if value is None:
            value = ""
        result = result.replace('{{' + key + '}}', str(value))

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
    from app.models.document import Document
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
    """
    from app.services.llm import get_llm_provider

    template = get_template_by_id(template_id)
    if not template:
        return {
            "success": False,
            "suggested_variables": {},
            "reasoning": f"Template '{template_id}' no encontrado",
            "missing_fields": []
        }

    # Obtener texto de los documentos
    documents_text = get_chunks_text_for_matter(matter_id, organization_id)

    if not documents_text or len(documents_text.strip()) < 100:
        return {
            "success": False,
            "suggested_variables": {},
            "reasoning": "No hay suficiente texto en los documentos del caso",
            "missing_fields": [v["key"] for v in template.get("variables", [])]
        }

    # Construir prompt para extracción
    template_vars = template.get("variables", [])
    vars_description = "\n".join([
        f"- {v['key']}: {v.get('description', v.get('label', ''))} (tipo: {v.get('type', 'text')})"
        for v in template_vars
    ])

    prompt = f"""Analiza los siguientes documentos de un caso legal y extrae la información relevante para completar un documento.

TEMPLATE A COMPLETAR: {template.get('name', template_id)}
{template.get('description', '')}

VARIABLES A COMPLETAR:
{vars_description}

DOCUMENTOS DEL CASO:
{documents_text[:30000]}

Responde en JSON con el siguiente formato:
{{
    "suggested_variables": {{"variable_key": "valor_extraído", ...}},
    "reasoning": "Explicación breve de cómo se infirieron los valores",
    "missing_fields": ["lista de campos que no pudieron inferirse de los documentos"]
}}

Solo incluye en suggested_variables los valores que puedas extraer con certeza del texto.
Para campos no mencionados en los documentos, usa null o no los incluyas."""

    try:
        provider = get_llm_provider()
        response = provider.generate(prompt=prompt, system_prompt=None, max_tokens=2048, temperature=0.3)

        # Intentar parsear JSON de la respuesta
        import json
        import re

        # Buscar JSON en la respuesta
        json_match = re.search(r'\{[^{}]*"suggested_variables"[^{}]*\}', response, re.DOTALL)
        if not json_match:
            # Intentar buscar cualquier objeto JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)

        if json_match:
            result = json.loads(json_match.group(0))
            return {
                "success": True,
                "suggested_variables": result.get("suggested_variables", {}),
                "reasoning": result.get("reasoning", "Valores extraídos del contexto"),
                "missing_fields": result.get("missing_fields", [])
            }
        else:
            return {
                "success": True,
                "suggested_variables": {},
                "reasoning": response[:500],
                "missing_fields": [v["key"] for v in template_vars]
            }

    except Exception as e:
        return {
            "success": False,
            "suggested_variables": {},
            "reasoning": f"Error al extraer variables: {str(e)}",
            "missing_fields": [v["key"] for v in template_vars]
        }


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
