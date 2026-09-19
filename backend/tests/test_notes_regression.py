"""Regression coverage for broad study-note content recognition."""

from app.services.analysis.classify import classify


def _classify(text: str):
    return classify(text, len(text.split()))


class TestStudyNoteVariants:
    def test_handwritten_short_lines(self):
        text = """CELL RESPIRATION
- Glucose is broken down
- Energy stored as ATP
- occurs in mitochondria
Aerobic -> uses oxygen
Anaerobic -> no oxygen"""
        assert _classify(text).category == "notes"

    def test_lecture_definitions_and_algorithm(self):
        text = """Lecture 4: Binary Search Trees
Definition: a tree in which each node has at most two children.
Properties:
1. left values are smaller
2. right values are larger
Complexity = O(log n)"""
        assert _classify(text).category == "notes"

    def test_formula_revision_notes(self):
        text = """PHYSICS REVISION
Newton second law
F = m × a
Momentum p = mv
Force is defined as rate of change of momentum."""
        assert _classify(text).category == "notes"

    def test_labelled_diagram_notes(self):
        text = """PLANT CELL DIAGRAM
Cell wall -> outer layer
Nucleus -> controls cell
Chloroplast -> photosynthesis
Vacuole -> stores water"""
        assert _classify(text).category == "notes"

    def test_textbook_reference_paragraph(self):
        text = """Chapter 3 Ecosystems
An ecosystem consists of organisms and their physical environment.
Energy flows through food chains. Producers convert sunlight into chemical energy.
Consumers obtain energy by feeding on other organisms."""
        assert _classify(text).category == "notes"

    def test_genuinely_unknown_stays_other(self):
        result = _classify("Beautiful day at the beach\nBlue sky and waves")
        assert result.category == "other"
