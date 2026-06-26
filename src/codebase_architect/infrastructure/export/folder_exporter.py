"""Write rendered documentation files to a local folder."""

from __future__ import annotations

from pathlib import Path

from codebase_architect.domain.model.documentation import DocumentationBundle, RenderedFile
from codebase_architect.domain.ports.documentation import DocExporter
from codebase_architect.shared.errors import ValidationError


class FolderExporter(DocExporter):
    """Persists the bundle as files under a destination directory."""

    def export(self, files: list[RenderedFile], dest: Path) -> DocumentationBundle:
        dest.mkdir(parents=True, exist_ok=True)
        for file in files:
            target = (dest / file.path).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise ValidationError(f"Refusing to write outside destination: {file.path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file.content, encoding="utf-8")
        return DocumentationBundle(root=str(dest), files=list(files))
