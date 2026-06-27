"""Tests for sequence-diagram generation from a functional spec."""

from __future__ import annotations

from codebase_architect.domain.model.functional_spec import (
    EndpointRef,
    FlowStep,
    FunctionalSpec,
    SpecFeature,
)
from codebase_architect.domain.services.sequence_diagram import (
    feature_sequence,
    spec_sequences,
)


def _feature() -> SpecFeature:
    return SpecFeature(
        name="User verification",
        actors=("Usuario",),
        main_flow=(
            FlowStep("Usuario", "introduce email + telefono", "App cliente"),
            FlowStep("App cliente", "user verification", "Libreria B-FY"),
            FlowStep("Libreria B-FY", "registro create_user", "Plataforma B-FY"),
            FlowStep("Plataforma B-FY", "200 OK inicia verificacion", "Libreria B-FY"),
        ),
        alternative_flows=("datos validos y unicos", "datos rechazados"),
        systems=("App cliente", "Libreria B-FY", "Plataforma B-FY"),
        endpoints=(EndpointRef("POST", "/users"),),
    )


def test_sequence_has_participants_messages_and_alt() -> None:
    code = feature_sequence(_feature())
    assert code.startswith("sequenceDiagram")
    assert 'participant p0 as "Usuario"' in code
    assert 'participant p3 as "Plataforma B-FY"' in code
    # request arrow (solid) and response arrow (dashed)
    assert "p0 ->> p1 : introduce email + telefono" in code
    assert "-->>" in code  # the "200 OK ..." step is a response
    # alternative flows become an alt/else block
    assert "alt datos validos y unicos" in code
    assert "else datos rechazados" in code
    assert code.rstrip().endswith("end") or "Note over" in code


def test_endpoints_annotated_with_grounding() -> None:
    code = feature_sequence(_feature(), confirmed={"/users"})
    assert "POST /users — ✓ found in code" in code
    code2 = feature_sequence(_feature(), confirmed={"/other"})
    assert "POST /users — ✗ not found" in code2


def test_spec_sequences_one_per_feature() -> None:
    spec = FunctionalSpec(id="s", product="P", features=(_feature(), _feature()))
    diagrams = spec_sequences(spec)
    assert len(diagrams) == 2
    assert diagrams[0][0] == "User verification"
    assert diagrams[0][1].startswith("sequenceDiagram")


def test_conceptual_detail_omits_code_grounding() -> None:
    import dataclasses

    feature = dataclasses.replace(_feature(), detail="conceptual")
    code = feature_sequence(feature, confirmed={"/users"})
    assert "found in code" not in code  # no concrete grounding notes
    assert "POST /users" not in code
    # the authored flow is still there
    assert "introduce email + telefono" in code


def test_empty_flow_still_valid() -> None:
    feature = SpecFeature(name="Empty", systems=("A",))
    code = feature_sequence(feature)
    assert "sequenceDiagram" in code
    assert "No flow steps defined" in code
