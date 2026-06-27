"""CodeModel: the aggregate of static facts about a codebase.

Built during a scan from parsed files and detected stacks. In this phase it
captures languages, parsed files, technology stacks and dependencies; later
phases enrich it with the module/dependency graph and entrypoints.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from codebase_architect.domain.model.code import Language, ParsedFile
from codebase_architect.domain.model.stack import Dependency, DetectedStack


@dataclass(frozen=True)
class LanguageStat:
    """Aggregated counts for a single language."""

    language: Language
    files: int
    loc: int


@dataclass
class CodeModel:
    """Static analysis result for one scanned workspace."""

    parsed_files: list[ParsedFile] = field(default_factory=list)
    stacks: list[DetectedStack] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    #: Count of files per extension that were seen but not parsed.
    other_file_count: int = 0

    @property
    def symbol_count(self) -> int:
        return sum(len(f.symbols) for f in self.parsed_files)

    @property
    def total_loc(self) -> int:
        return sum(f.loc for f in self.parsed_files)

    def language_breakdown(self) -> list[LanguageStat]:
        """Per-language file and LOC counts, ordered by LOC descending."""
        files: Counter[Language] = Counter()
        loc: Counter[Language] = Counter()
        for parsed in self.parsed_files:
            files[parsed.language] += 1
            loc[parsed.language] += parsed.loc
        stats = [
            LanguageStat(language=lang, files=files[lang], loc=loc[lang]) for lang in files
        ]
        return sorted(stats, key=lambda s: s.loc, reverse=True)
