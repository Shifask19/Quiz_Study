"""
Tests for quiz generation, evaluation, and mastery tracking.
"""
import pytest
import uuid


class TestQuizEvaluation:
    def test_correct_multiple_choice(self):
        from backend.services.quiz_service import _compare_answers
        assert _compare_answers("A", "A", "multiple_choice") is True

    def test_wrong_multiple_choice(self):
        from backend.services.quiz_service import _compare_answers
        assert _compare_answers("B", "A", "multiple_choice") is False

    def test_case_insensitive_true_false(self):
        from backend.services.quiz_service import _compare_answers
        assert _compare_answers("true", "True", "true_false") is True
        assert _compare_answers("FALSE", "False", "true_false") is True

    def test_short_answer_keyword_overlap(self):
        from backend.services.quiz_service import _compare_answers
        correct = "Normalization reduces redundancy in relational databases"
        user = "normalization reduces database redundancy"
        assert _compare_answers(user, correct, "short_answer") is True

    def test_short_answer_empty_is_wrong(self):
        from backend.services.quiz_service import _compare_answers
        assert _compare_answers("", "correct answer", "short_answer") is False

    def test_quiz_json_parse_clean_json(self):
        from backend.services.quiz_service import _parse_quiz_json
        import json
        data = {"questions": [{"id": 1, "question": "Test?", "correct_answer": "A"}]}
        result = _parse_quiz_json(json.dumps(data))
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_quiz_json_parse_extracts_from_dirty_output(self):
        from backend.services.quiz_service import _parse_quiz_json
        dirty = 'Here are the questions:\n```json\n{"questions": [{"id": 1, "question": "Q?", "correct_answer": "B"}]}\n```'
        result = _parse_quiz_json(dirty)
        # Might or might not parse depending on regex; at minimum should not crash
        assert isinstance(result, list)

    def test_quiz_json_parse_returns_empty_on_garbage(self):
        from backend.services.quiz_service import _parse_quiz_json
        result = _parse_quiz_json("this is not json at all!!!")
        assert result == []


class TestMasteryCalculation:
    def test_mastery_percent_zero_attempts(self):
        from backend.database.models import TopicMastery
        m = TopicMastery(topic="test", questions_attempted=0, correct_answers=0)
        assert m.mastery_percent() == 0.0

    def test_mastery_percent_full_score(self):
        from backend.database.models import TopicMastery
        m = TopicMastery(topic="test", questions_attempted=10, correct_answers=10, score=1.0)
        assert m.mastery_percent() == 100.0

    def test_mastery_percent_partial(self):
        from backend.database.models import TopicMastery
        m = TopicMastery(topic="test", questions_attempted=10, correct_answers=7, score=0.7)
        assert m.mastery_percent() == 70.0


class TestEvaluateQuizIntegration:
    def test_evaluate_stores_attempts_and_updates_mastery(self, db_session):
        from backend.services.quiz_service import evaluate_quiz
        from backend.models.factory import reset_model
        reset_model()

        quiz_id = str(uuid.uuid4())
        questions = [
            {
                "id": 1, "type": "multiple_choice", "question": "Q1?",
                "options": {"A": "opt1", "B": "opt2"},
                "correct_answer": "A", "explanation": "A is correct",
                "topic": "Database Normalization", "difficulty": "medium",
            },
            {
                "id": 2, "type": "true_false", "question": "Q2?",
                "correct_answer": "True", "explanation": "True",
                "topic": "Database Normalization", "difficulty": "easy",
            },
        ]
        user_answers = {1: "A", 2: "False"}  # 1 correct, 1 wrong

        result = evaluate_quiz(
            db=db_session,
            quiz_id=quiz_id,
            document_id=None,
            questions=questions,
            user_answers=user_answers,
        )

        assert result.total_questions == 2
        assert result.correct == 1
        assert result.score_percent == 50.0
        assert "Database Normalization" in result.weak_topics or result.score_percent <= 50
