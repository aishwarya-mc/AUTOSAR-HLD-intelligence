from app.extraction.entity_schema import (
    ArchitectureEntityRecord,
    EntityEvidence,
    EntityType,
)
from app.extraction.normalization import (
    EntityNormalizer,
    normalize_and_deduplicate,
)


def make_entity(
    name: str,
    confidence: float = 0.90,
    page: int = 1,
) -> ArchitectureEntityRecord:

    evidence = EntityEvidence(
        document_id="doc_test",
        document_version="v1",
        page_number=page,
        section="3. Software Components",
        source_text=f"Evidence for {name}",
    )

    return ArchitectureEntityRecord(
        entity_id=f"entity_{name.lower()}",
        entity_type=EntityType.COMPONENT,
        name=name,
        description=f"Description for {name}",
        confidence=confidence,
        document_id="doc_test",
        document_version="v1",
        evidence=[evidence],
    )


def test_name_normalization():
    entity = make_entity("  BodyControlManager  ")

    normalized = EntityNormalizer.normalize(entity)

    assert normalized.name == "BodyControlManager"


def test_deduplicates_case_and_whitespace_variations():
    first = make_entity(
        "BodyControlManager",
        confidence=0.90,
        page=1,
    )

    duplicate = make_entity(
        "  bodycontrolmanager  ",
        confidence=0.95,
        page=2,
    )

    result = normalize_and_deduplicate(
        [first, duplicate]
    )

    assert len(result) == 1
    assert result[0].name == "BodyControlManager"
    assert result[0].confidence == 0.95
    assert len(result[0].evidence) == 2


def test_does_not_remove_meaningful_underscores():
    entity = make_entity("DoorStatus_Out")

    normalized = EntityNormalizer.normalize(entity)

    assert normalized.name == "DoorStatus_Out"


def test_different_entity_types_are_not_collapsed():
    component = make_entity("VehicleState")

    interface = ArchitectureEntityRecord(
        entity_id="entity_interface",
        entity_type=EntityType.INTERFACE,
        name="VehicleState",
        description="Interface",
        confidence=0.90,
        document_id="doc_test",
        document_version="v1",
    )

    result = normalize_and_deduplicate(
        [component, interface]
    )

    assert len(result) == 2