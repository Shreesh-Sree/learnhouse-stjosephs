import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException

from src.db.courses.assignments import (
    Assignment,
    AssignmentTask,
    AssignmentTaskSubmission,
    AssignmentUserSubmission,
    AssignmentUserSubmissionStatus,
)
from src.db.courses.courses import Course
from src.db.courses.peer_reviews import PeerReview, PeerReviewStatus
from src.db.users import PublicUser
from src.services.courses.activities.peer_reviews import (
    assign_peer_reviews,
    list_my_peer_reviews_to_do,
    get_peer_review_submission_view,
    submit_peer_review,
    list_peer_reviews_received,
    get_peer_review_summary_for_user,
)


@pytest.fixture
def mock_request():
    req = MagicMock()
    return req


@pytest.fixture
def instructor_user():
    return PublicUser(id=1, email="instructor@test.com", username="prof", first_name="Prof", last_name="Oak", user_uuid="u_prof")


@pytest.fixture
def student_1():
    return PublicUser(id=10, email="s1@test.com", username="student1", first_name="Student", last_name="One", user_uuid="u_s1")


@pytest.fixture
def student_2():
    return PublicUser(id=20, email="s2@test.com", username="student2", first_name="Student", last_name="Two", user_uuid="u_s2")


@pytest.fixture
def student_3():
    return PublicUser(id=30, email="s3@test.com", username="student3", first_name="Student", last_name="Three", user_uuid="u_s3")


@pytest.fixture
def sample_course():
    return Course(id=100, course_uuid="course_100", name="Data Structures", org_id=1)


@pytest.fixture
def sample_assignment():
    return Assignment(
        id=200,
        assignment_uuid="asgn_200",
        course_id=100,
        title="Binary Trees",
        enable_peer_review=True,
        peer_reviews_per_submission=2,
    )


@pytest.mark.asyncio
async def test_assign_peer_reviews_not_enabled(mock_request, instructor_user, sample_course):
    disabled_assignment = Assignment(
        id=200,
        assignment_uuid="asgn_200",
        course_id=100,
        enable_peer_review=False,
    )
    fake_db = MagicMock()
    fake_db.execute = AsyncMock()

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(disabled_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await assign_peer_reviews(mock_request, "asgn_200", instructor_user, fake_db)
            assert exc_info.value.status_code == 400
            assert "does not use peer review" in exc_info.value.detail


@pytest.mark.asyncio
async def test_assign_peer_reviews_not_enough_candidates(mock_request, instructor_user, sample_course, sample_assignment):
    fake_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [10]  # only 1 candidate
    fake_db.execute = AsyncMock(return_value=mock_result)

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await assign_peer_reviews(mock_request, "asgn_200", instructor_user, fake_db)
            assert exc_info.value.status_code == 400
            assert "Not enough submitted attempts" in exc_info.value.detail


@pytest.mark.asyncio
async def test_assign_peer_reviews_success(mock_request, instructor_user, sample_course, sample_assignment):
    candidates = [10, 20, 30]
    existing_pairs = []

    fake_db = MagicMock()
    added_reviews = []
    fake_db.add = MagicMock(side_effect=lambda x: added_reviews.append(x))
    fake_db.commit = AsyncMock()

    def fake_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt).lower()
        if "assignmentusersubmission" in stmt_str:
            mock_result.scalars.return_value.all.return_value = candidates
        elif "peer_review" in stmt_str:
            mock_result.all.return_value = existing_pairs
        return mock_result

    fake_db.execute = AsyncMock(side_effect=fake_execute)

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            res = await assign_peer_reviews(mock_request, "asgn_200", instructor_user, fake_db)
            assert res["created"] == 6  # 3 students * 2 reviews each
            assert len(added_reviews) == 6
            # Ensure no self-reviews
            for r in added_reviews:
                assert r.reviewer_user_id != r.target_user_id
                assert r.status == PeerReviewStatus.PENDING


@pytest.mark.asyncio
async def test_list_my_peer_reviews_to_do(mock_request, student_1, sample_course, sample_assignment):
    review1 = PeerReview(
        id=1,
        review_uuid="rev_1",
        assignment_id=200,
        reviewer_user_id=10,
        target_user_id=20,
        status=PeerReviewStatus.PENDING,
        creation_date="2026-09-09T10:00:00",
    )
    fake_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [review1]
    fake_db.execute = AsyncMock(return_value=mock_result)

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            todos = await list_my_peer_reviews_to_do(mock_request, "asgn_200", student_1, fake_db)
            assert len(todos) == 1
            # Anonymity check: reviewer_user_id and target_user_id must be stripped
            assert todos[0].review_uuid == "rev_1"
            assert todos[0].reviewer_user_id is None
            assert todos[0].target_user_id is None


@pytest.mark.asyncio
async def test_submit_peer_review(mock_request, student_1, sample_course, sample_assignment):
    review = PeerReview(
        id=1,
        review_uuid="rev_1",
        assignment_id=200,
        reviewer_user_id=10,
        target_user_id=20,
        status=PeerReviewStatus.PENDING,
    )
    fake_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = review
    fake_db.execute = AsyncMock(return_value=mock_result)
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            submitted = await submit_peer_review(
                mock_request, "asgn_200", "rev_1", score=88, feedback="Great job on binary trees!",
                current_user=student_1, db_session=fake_db
            )
            assert submitted.status == PeerReviewStatus.COMPLETED
            assert submitted.score == 88
            assert submitted.feedback == "Great job on binary trees!"
            # Identity masked
            assert submitted.reviewer_user_id is None
            assert submitted.target_user_id is None


@pytest.mark.asyncio
async def test_list_peer_reviews_received_withheld_and_revealed(mock_request, student_2, sample_course, sample_assignment):
    pending_review = PeerReview(
        id=1,
        review_uuid="rev_1",
        assignment_id=200,
        reviewer_user_id=10,
        target_user_id=20,
        status=PeerReviewStatus.PENDING,
    )
    completed_review = PeerReview(
        id=2,
        review_uuid="rev_2",
        assignment_id=200,
        reviewer_user_id=30,
        target_user_id=20,
        status=PeerReviewStatus.COMPLETED,
        score=95,
        feedback="Clean code!",
    )

    fake_db = MagicMock()
    
    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            # Case 1: Partial completion -> Withheld
            mock_result_partial = MagicMock()
            mock_result_partial.scalars.return_value.all.return_value = [pending_review, completed_review]
            fake_db.execute = AsyncMock(return_value=mock_result_partial)

            res_partial = await list_peer_reviews_received(mock_request, "asgn_200", student_2, fake_db)
            assert res_partial["revealed"] is False
            assert res_partial["completed_count"] == 1
            assert res_partial["total_count"] == 2
            assert res_partial["reviews"] == []

            # Case 2: All completed -> Revealed
            pending_review.status = PeerReviewStatus.COMPLETED
            pending_review.score = 90
            pending_review.feedback = "Good work."

            mock_result_full = MagicMock()
            mock_result_full.scalars.return_value.all.return_value = [pending_review, completed_review]
            fake_db.execute = AsyncMock(return_value=mock_result_full)

            res_full = await list_peer_reviews_received(mock_request, "asgn_200", student_2, fake_db)
            assert res_full["revealed"] is True
            assert res_full["completed_count"] == 2
            assert len(res_full["reviews"]) == 2
            # Reviewer identities are still masked for anonymity
            assert res_full["reviews"][0].reviewer_user_id is None
            assert res_full["reviews"][1].reviewer_user_id is None


@pytest.mark.asyncio
async def test_get_peer_review_summary_for_user_instructor(mock_request, instructor_user, sample_course, sample_assignment):
    review1 = PeerReview(
        id=1,
        review_uuid="rev_1",
        assignment_id=200,
        reviewer_user_id=10,
        target_user_id=20,
        status=PeerReviewStatus.COMPLETED,
        score=80,
        feedback="Good.",
    )
    review2 = PeerReview(
        id=2,
        review_uuid="rev_2",
        assignment_id=200,
        reviewer_user_id=30,
        target_user_id=20,
        status=PeerReviewStatus.COMPLETED,
        score=90,
        feedback="Excellent.",
    )
    fake_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [review1, review2]
    fake_db.execute = AsyncMock(return_value=mock_result)

    with patch("src.services.courses.activities.peer_reviews._resolve_assignment_and_course", return_value=(sample_assignment, sample_course)):
        with patch("src.services.courses.activities.peer_reviews.check_resource_access", return_value=True):
            summary = await get_peer_review_summary_for_user(mock_request, "asgn_200", target_user_id=20, current_user=instructor_user, db_session=fake_db)
            assert summary["average_score"] == 85.0
            assert summary["completed_count"] == 2
            assert summary["total_count"] == 2
            # Instructor CAN see reviewer identities
            assert summary["reviews"][0].reviewer_user_id == 10
            assert summary["reviews"][1].reviewer_user_id == 30
