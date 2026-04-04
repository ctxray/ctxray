"""Tests for persona data model and centroids."""

from __future__ import annotations

import pytest

from ctxray.core.persona import PERSONAS, Persona, classify_persona

EXPECTED_NAMES = {"architect", "debugger", "explorer", "novelist", "sniper", "teacher"}


class TestPersonaDataclass:
    """Verify the Persona dataclass is frozen and has all required fields."""

    def test_persona_is_frozen(self):
        p = Persona(
            name="test",
            emoji="T",
            description="desc",
            traits=["a", "b"],
            centroid=[0.5, 0.5],
        )
        with pytest.raises(AttributeError):
            p.name = "changed"  # type: ignore[misc]

    def test_persona_has_required_fields(self):
        p = Persona(
            name="test",
            emoji="T",
            description="A test persona.",
            traits=["trait1", "trait2"],
            centroid=[0.1, 0.2, 0.3],
        )
        assert p.name == "test"
        assert p.emoji == "T"
        assert p.description == "A test persona."
        assert p.traits == ["trait1", "trait2"]
        assert p.centroid == [0.1, 0.2, 0.3]


class TestPersonasDict:
    """Verify the PERSONAS dict contains exactly the 6 expected personas."""

    def test_personas_count(self):
        assert len(PERSONAS) == 6

    def test_personas_names(self):
        assert set(PERSONAS.keys()) == EXPECTED_NAMES

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_name_matches_key(self, name: str):
        assert PERSONAS[name].name == name

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_has_nonempty_emoji(self, name: str):
        assert PERSONAS[name].emoji
        assert len(PERSONAS[name].emoji.strip()) > 0

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_has_nonempty_description(self, name: str):
        assert PERSONAS[name].description
        assert len(PERSONAS[name].description.strip()) > 0

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_has_at_least_two_traits(self, name: str):
        assert len(PERSONAS[name].traits) >= 2

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_traits_are_nonempty_strings(self, name: str):
        for trait in PERSONAS[name].traits:
            assert isinstance(trait, str)
            assert len(trait.strip()) > 0

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_has_nonempty_centroid(self, name: str):
        centroid = PERSONAS[name].centroid
        assert len(centroid) > 0

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_centroid_values_in_unit_range(self, name: str):
        for val in PERSONAS[name].centroid:
            assert 0.0 <= val <= 1.0, f"{name} centroid value {val} out of [0,1]"

    @pytest.mark.parametrize("name", sorted(EXPECTED_NAMES))
    def test_persona_centroid_has_five_dimensions(self, name: str):
        assert len(PERSONAS[name].centroid) == 5


class TestPersonaCentroids:
    """Verify specific centroid values for known personas."""

    def test_architect_centroid(self):
        assert PERSONAS["architect"].centroid == [0.85, 0.70, 0.75, 0.50, 0.70]

    def test_debugger_centroid(self):
        assert PERSONAS["debugger"].centroid == [0.50, 0.95, 0.60, 0.40, 0.55]

    def test_explorer_centroid(self):
        assert PERSONAS["explorer"].centroid == [0.20, 0.25, 0.60, 0.15, 0.40]

    def test_novelist_centroid(self):
        assert PERSONAS["novelist"].centroid == [0.80, 0.60, 0.70, 0.65, 0.60]

    def test_sniper_centroid(self):
        assert PERSONAS["sniper"].centroid == [0.40, 0.50, 0.85, 0.30, 0.90]

    def test_teacher_centroid(self):
        assert PERSONAS["teacher"].centroid == [0.90, 0.55, 0.65, 0.70, 0.65]


class TestClassifyPersona:
    """Verify classify_persona returns the nearest persona by Euclidean distance."""

    def test_architect_profile(self):
        scores = {
            "structure": 22.0,
            "context": 18.0,
            "position": 15.0,
            "repetition": 8.0,
            "clarity": 10.0,
        }
        result = classify_persona(scores)
        assert result.name == "architect"

    def test_debugger_profile(self):
        scores = {
            "structure": 12.0,
            "context": 24.0,
            "position": 12.0,
            "repetition": 6.0,
            "clarity": 8.0,
        }
        result = classify_persona(scores)
        assert result.name == "debugger"

    def test_explorer_profile(self):
        scores = {
            "structure": 5.0,
            "context": 6.0,
            "position": 12.0,
            "repetition": 2.0,
            "clarity": 6.0,
        }
        result = classify_persona(scores)
        assert result.name == "explorer"

    def test_sniper_profile(self):
        scores = {
            "structure": 10.0,
            "context": 12.0,
            "position": 18.0,
            "repetition": 4.0,
            "clarity": 14.0,
        }
        result = classify_persona(scores)
        assert result.name == "sniper"

    def test_returns_persona_object(self):
        scores = {
            "structure": 15.0,
            "context": 15.0,
            "position": 10.0,
            "repetition": 8.0,
            "clarity": 8.0,
        }
        result = classify_persona(scores)
        assert isinstance(result, Persona)

    def test_zero_scores(self):
        scores = {
            "structure": 0.0,
            "context": 0.0,
            "position": 0.0,
            "repetition": 0.0,
            "clarity": 0.0,
        }
        result = classify_persona(scores)
        assert isinstance(result, Persona)


class TestMathImport:
    """Verify that math is importable from the persona module (needed by Task 2)."""

    def test_math_imported_in_module(self):
        import ctxray.core.persona as mod

        assert hasattr(mod, "math")
