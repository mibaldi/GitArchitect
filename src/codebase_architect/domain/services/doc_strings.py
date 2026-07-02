"""Localized string table for generated documentation.

Pure lookup module: no imports beyond stdlib, so it can live in ``domain`` and
be used by any layer without violating the hexagonal import rules. Every
user-facing string that ends up in generated documentation (page titles,
section headings, inline prose, table headers) is defined here for each
supported language, keyed by a stable string id.

Templates use ``str.format`` placeholders (e.g. ``{count}``) for interpolated
values; callers are responsible for filling them in.
"""

from __future__ import annotations

_DEFAULT_LANGUAGE = "en"

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # -- page titles ------------------------------------------------
        "title_architecture": "Architecture",
        "title_modules": "Modules",
        "title_functionalities": "Functionalities",
        "title_entrypoints": "Entrypoints",
        "title_flows": "Flows",
        "title_api": "API surface",
        "title_dependencies": "Dependencies",
        "title_security": "Security",
        # -- section headings --------------------------------------------
        "heading_overview": "Overview",
        "heading_languages": "Languages",
        "heading_technology_stack": "Technology stack",
        "heading_totals": "Totals",
        "heading_features": "Features",
        "heading_layers": "Layers",
        "heading_module_dependencies": "Module dependencies",
        "heading_dependency_rules": "Dependency rules",
        "heading_exposed_endpoints": "Exposed endpoints",
        "heading_outbound_calls": "Outbound calls",
        "heading_external_dependencies": "External dependencies",
        "heading_secret_scan": "Secret scan",
        "heading_modules": "Modules",
        "heading_entrypoints": "Entrypoints",
        "heading_pages": "Pages",
        # -- inline prose / placeholders ----------------------------------
        "no_recognized_source_files": "_No recognized source files._",
        "none_detected": "_None detected._",
        "totals_parsed_files": "Parsed files",
        "totals_symbols": "Symbols",
        "totals_lines_of_code": "Lines of code",
        "totals_dependencies": "Dependencies",
        "static_features_hint": (
            "_Derived statically from entrypoints. Run with an AI provider "
            "(without `--static-only`) to enrich these descriptions._"
        ),
        "no_functionalities": "_No functionalities were derived (no entrypoints detected)._",
        "static_badge": " _(static)_",
        "related_prefix_template": "_Related: {refs}_",
        "no_modules_to_classify": "_No modules to classify._",
        "no_layering_violations": "✓ No layering violations or dependency cycles detected.",
        "layering_violations_count_template": (
            "**{count} layering violation(s)** (an inner layer depends on an outer one):"
        ),
        "dependency_cycles_count_template": "**{count} dependency cycle(s):**",
        "no_modules": "_No modules._",
        "no_entrypoints_detected": "_No entrypoints detected._",
        "flows_intro": (
            "Flows traced from each entrypoint through the modules it "
            "transitively depends on or calls."
        ),
        "no_multi_module_flows": "_No multi-module flows detected._",
        "no_http_endpoints": (
            "_No exposed HTTP endpoints detected (Spring / FastAPI supported)._"
        ),
        "no_outbound_calls": (
            "_No outbound HTTP calls detected (Angular HttpClient / fetch / axios supported)._"
        ),
        "no_external_dependencies": "_No external dependencies detected._",
        "secret_scan_not_run": "_Secret scanning was not run._",
        "no_secrets_detected": "_No secrets detected._",
        "secrets_found_count_template": (
            "**{count}** potential secret(s) found (values redacted):"
        ),
        "meta_generated_at_template": "_Generated at {generated_at}._",
        "meta_generated_at_with_ref_template": (
            "_Generated at {generated_at} · base ref `{base_ref}`._"
        ),
        # -- table column headers -----------------------------------------
        "col_language": "Language",
        "col_files": "Files",
        "col_loc": "LOC",
        "col_module": "Module",
        "col_symbols": "Symbols",
        "col_languages": "Languages",
        "col_depends_on": "Depends on",
        "col_method": "Method",
        "col_path": "Path",
        "col_handler": "Handler",
        "col_from_module": "From module",
        # -- layer display names -------------------------------------------
        "layer_presentation": "Presentation",
        "layer_ui": "Ui",
        "layer_application": "Application",
        "layer_domain": "Domain",
        "layer_data": "Data",
        "layer_infrastructure": "Infrastructure",
        "layer_config": "Config",
        "layer_shared": "Shared",
        "layer_other": "Other",
        # -- graph caption ---------------------------------------------------
        "graph_caption_template": "{modules} modules, {edges} internal dependencies{note}.",
        "graph_caption_note_template": " (showing first {shown} of {total})",
        # -- static feature catalog (features_static.py) --------------------
        "feature_http_api_name": "HTTP API",
        "feature_http_api_desc_template": "Exposes {n} HTTP endpoint(s) across {modules}.",
        "feature_web_ui_name": "Web UI",
        "feature_web_ui_desc_template": "Renders {n} UI component(s) across {modules}.",
        "feature_web_app_modules_name": "Web application modules",
        "feature_web_app_modules_desc_template": (
            "Wires {n} application/routing module(s) across {modules}."
        ),
        "feature_app_bootstrap_name": "Application bootstrap",
        "feature_app_bootstrap_desc_template": (
            "Boots the application from {n} entrypoint(s) in {modules}."
        ),
        "feature_cli_name": "Command-line interface",
        "feature_cli_desc_template": "Provides {n} command-line entrypoint(s) in {modules}.",
        # -- AI narrative prompt instruction ---------------------------------
        "narrative_language_instruction": "Write all prose values in English.",
    },
    "es": {
        # -- page titles ------------------------------------------------
        "title_architecture": "Arquitectura",
        "title_modules": "Módulos",
        "title_functionalities": "Funcionalidades",
        "title_entrypoints": "Puntos de entrada",
        "title_flows": "Flujos",
        "title_api": "Superficie de API",
        "title_dependencies": "Dependencias",
        "title_security": "Seguridad",
        # -- section headings --------------------------------------------
        "heading_overview": "Resumen",
        "heading_languages": "Lenguajes",
        "heading_technology_stack": "Stack tecnológico",
        "heading_totals": "Totales",
        "heading_features": "Funcionalidades",
        "heading_layers": "Capas",
        "heading_module_dependencies": "Dependencias entre módulos",
        "heading_dependency_rules": "Reglas de dependencia",
        "heading_exposed_endpoints": "Endpoints expuestos",
        "heading_outbound_calls": "Llamadas salientes",
        "heading_external_dependencies": "Dependencias externas",
        "heading_secret_scan": "Escaneo de secretos",
        "heading_modules": "Módulos",
        "heading_entrypoints": "Puntos de entrada",
        "heading_pages": "Páginas",
        # -- inline prose / placeholders ----------------------------------
        "no_recognized_source_files": "_No se reconocieron archivos de código fuente._",
        "none_detected": "_No se detectó ninguno._",
        "totals_parsed_files": "Archivos analizados",
        "totals_symbols": "Símbolos",
        "totals_lines_of_code": "Líneas de código",
        "totals_dependencies": "Dependencias",
        "static_features_hint": (
            "_Derivado estáticamente a partir de los puntos de entrada. Ejecute con un "
            "proveedor de IA (sin `--static-only`) para enriquecer estas descripciones._"
        ),
        "no_functionalities": (
            "_No se derivó ninguna funcionalidad (no se detectaron puntos de entrada)._"
        ),
        "static_badge": " _(estático)_",
        "related_prefix_template": "_Relacionado: {refs}_",
        "no_modules_to_classify": "_No hay módulos para clasificar._",
        "no_layering_violations": (
            "✓ No se detectaron violaciones de capas ni ciclos de dependencias."
        ),
        "layering_violations_count_template": (
            "**{count} violación(es) de capas** (una capa interna depende de una externa):"
        ),
        "dependency_cycles_count_template": "**{count} ciclo(s) de dependencias:**",
        "no_modules": "_No hay módulos._",
        "no_entrypoints_detected": "_No se detectaron puntos de entrada._",
        "flows_intro": (
            "Flujos trazados desde cada punto de entrada a través de los módulos de los "
            "que depende o a los que llama transitivamente."
        ),
        "no_multi_module_flows": "_No se detectaron flujos multi-módulo._",
        "no_http_endpoints": (
            "_No se detectaron endpoints HTTP expuestos (compatible con Spring / FastAPI)._"
        ),
        "no_outbound_calls": (
            "_No se detectaron llamadas HTTP salientes "
            "(compatible con Angular HttpClient / fetch / axios)._"
        ),
        "no_external_dependencies": "_No se detectaron dependencias externas._",
        "secret_scan_not_run": "_El escaneo de secretos no se ejecutó._",
        "no_secrets_detected": "_No se detectaron secretos._",
        "secrets_found_count_template": (
            "**{count}** secreto(s) potencial(es) encontrado(s) (valores redactados):"
        ),
        "meta_generated_at_template": "_Generado el {generated_at}._",
        "meta_generated_at_with_ref_template": (
            "_Generado el {generated_at} · ref base `{base_ref}`._"
        ),
        # -- table column headers -----------------------------------------
        "col_language": "Lenguaje",
        "col_files": "Archivos",
        "col_loc": "LOC",
        "col_module": "Módulo",
        "col_symbols": "Símbolos",
        "col_languages": "Lenguajes",
        "col_depends_on": "Depende de",
        "col_method": "Método",
        "col_path": "Ruta",
        "col_handler": "Handler",
        "col_from_module": "Desde el módulo",
        # -- layer display names -------------------------------------------
        "layer_presentation": "Presentación",
        "layer_ui": "Ui",
        "layer_application": "Aplicación",
        "layer_domain": "Dominio",
        "layer_data": "Datos",
        "layer_infrastructure": "Infraestructura",
        "layer_config": "Configuración",
        "layer_shared": "Compartido",
        "layer_other": "Otro",
        # -- graph caption ---------------------------------------------------
        "graph_caption_template": "{modules} módulos, {edges} dependencias internas{note}.",
        "graph_caption_note_template": " (se muestran los primeros {shown} de {total})",
        # -- static feature catalog (features_static.py) --------------------
        "feature_http_api_name": "API HTTP",
        "feature_http_api_desc_template": "Expone {n} endpoint(s) HTTP en {modules}.",
        "feature_web_ui_name": "Interfaz web",
        "feature_web_ui_desc_template": "Renderiza {n} componente(s) de UI en {modules}.",
        "feature_web_app_modules_name": "Módulos de la aplicación web",
        "feature_web_app_modules_desc_template": (
            "Conecta {n} módulo(s) de aplicación/enrutamiento en {modules}."
        ),
        "feature_app_bootstrap_name": "Arranque de la aplicación",
        "feature_app_bootstrap_desc_template": (
            "Inicia la aplicación desde {n} punto(s) de entrada en {modules}."
        ),
        "feature_cli_name": "Interfaz de línea de comandos",
        "feature_cli_desc_template": (
            "Provee {n} punto(s) de entrada de línea de comandos en {modules}."
        ),
        # -- AI narrative prompt instruction ---------------------------------
        "narrative_language_instruction": "Escribe todos los valores de prosa en español.",
    },
}


SUPPORTED_LANGUAGES = frozenset(_STRINGS)


def normalize_language(language: str) -> str:
    """Resolve a requested language code to a supported one (fallback: English)."""
    return language if language in _STRINGS else _DEFAULT_LANGUAGE


def doc_strings(language: str) -> dict[str, str]:
    """Return the string table for ``language``, falling back to English."""
    return _STRINGS[normalize_language(language)]
