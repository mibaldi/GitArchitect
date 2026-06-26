"""Codebase Architect.

Autonomous agent that analyzes, plans and implements changes on any codebase.

The core is decoupled from any source-control hosting provider (GitHub, GitLab,
Bitbucket). It only understands the abstractions defined in ``domain.ports``:
SourceProvider, Workspace, AIProvider, GitService, Exporter, Agent and the
persistence repositories. Everything concrete lives in ``infrastructure`` or in
external ``plugins``.
"""

__version__ = "0.0.0"
