"""HTML static-site renderer plugin for Codebase Architect.

Demonstrates the renderer plugin contract: implement the host's ``DocRenderer``
port and register it under the ``codebase_architect.renderers`` entry-point
group. The host discovers it via ``--renderer html`` with no core changes.
"""

from ca_plugin_html.renderer import HtmlSiteRenderer

__all__ = ["HtmlSiteRenderer"]
