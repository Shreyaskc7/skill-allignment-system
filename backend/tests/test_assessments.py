"""Phase 6: question bank, secure attempts, scoring, results and question management."""

from datetime import timedelta

import pytest

from conftest import auth_headers, login, register

API = "/api/v1/assessments"


def _skill(client, h, name="Java"):
    return next(s for s in client.get(f"{API}/skills", headers=h).json() if s["name"] == name)


def _start(client, h, skill_id, **kw):
    r = client.post(f"{API}/attempts", headers=h, json={"skill_id": skill_id, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _key(db, attempt_id):
    from app import models

    return {q.question_id: q.correct_option for q in
            db.query(models.AssessmentAttemptQuestion).filter_by(attempt_id=attempt_id)}


def _answers(mapping, pick=lambda qid, right: right):
    return {"answers": [{"question_id": q, "answer": pick(q, a)} for q, a in mapping.items()]}


def _wrong(letter):
    return "B" if letter == "A" else "A"


# ------------------------------------------------------------------ bank

def test_bank_files_are_valid_and_loaded(client, db):
    from app import models
    from app.services.question_bank import read_bank

    bank = read_bank()
    assert bank, "question_bank directory is empty"
    for slug, skill, questions in bank:
        assert len(questions) >= 20, f"{slug}: only {len(questions)} questions"
        diffs = {q["difficulty"] for q in questions}
        assert diffs == {"beginner", "intermediate", "advanced"}, slug
    loaded = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.bank_key.isnot(None)).count()
    assert loaded == sum(len(q) for _, _, q in bank)


def test_bank_loading_is_idempotent_and_keeps_staff_edits(client, db):
    from app import models
    from app.services.question_bank import load_question_bank

    q = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.bank_key.isnot(None)).first()
    q.is_active = False
    q.explanation = "Edited by a teacher"
    db.commit()
    assert load_question_bank(db) == 0
    db.commit()
    db.refresh(q)
    assert q.is_active is False and q.explanation == "Edited by a teacher"


def test_v1_questions_are_adopted_not_duplicated(client, db):
    from app import models

    v1 = "Which keyword creates an object?"  # a version 1 Java question
    rows = db.query(models.AssessmentQuestion).filter_by(question=v1).all()
    assert len(rows) == 1 and rows[0].bank_key


def test_invalid_bank_file_is_rejected(tmp_path):
    from app.services.question_bank import QuestionBankError, read_bank

    (tmp_path / "x.json").write_text('{"skill": "Java", "questions": [{"question": "Q", "options": ["a","a","b","c"],'
                                     ' "correct": "A", "explanation": "e", "difficulty": "beginner"}]}')
    with pytest.raises(QuestionBankError, match="distinct"):
        read_bank(tmp_path)


# ------------------------------------------------------------------ delivery

def test_skills_list_counts_active_questions(client, student):
    java = _skill(client, student)
    assert java["question_count"] >= 20 and set(java["by_difficulty"]) == {"beginner", "intermediate", "advanced"}


def test_start_attempt_hides_answers_and_is_random(client, student):
    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=10)
    assert len(a["questions"]) == 10 and a["status"] == "in_progress" and a["expires_at"] is None
    for q in a["questions"]:
        assert set(q) == {"id", "position", "question", "difficulty", "options"}
    assert len({q["id"] for q in a["questions"]}) == 10
    # Starting again resumes the same attempt (no re-rolling for a better set)...
    again = _start(client, student, java, question_count=10)
    assert again["attempt_id"] == a["attempt_id"] and again["resumed"] is True
    # ...unless the student explicitly restarts, which abandons the old one.
    fresh = _start(client, student, java, question_count=10, restart=True)
    assert fresh["attempt_id"] != a["attempt_id"]
    assert client.get(f"{API}/attempts/{a['attempt_id']}", headers=student).status_code == 409


def test_difficulty_filter_and_mixed_balance(client, student):
    java = _skill(client, student)["id"]
    adv = _start(client, student, java, question_count=5, difficulty="advanced")
    assert {q["difficulty"] for q in adv["questions"]} == {"advanced"}
    mixed = _start(client, student, java, question_count=9, difficulty="mixed", restart=True)
    counts = {d: sum(q["difficulty"] == d for q in mixed["questions"]) for d in ("beginner", "intermediate", "advanced")}
    assert counts == {"beginner": 3, "intermediate": 3, "advanced": 3}


@pytest.mark.parametrize("body,status", [
    ({"question_count": 4}, 422), ({"question_count": 31}, 422), ({"difficulty": "expert"}, 422), ({"skill_id": 999999}, 404),
])
def test_start_validation(client, student, body, status):
    payload = {"skill_id": _skill(client, student)["id"], **body}
    assert client.post(f"{API}/attempts", headers=student, json=payload).status_code == status


def test_not_enough_questions(client, student, db):
    from app import models

    skill = models.Skill(name="Underwater Basket Weaving", category="Other")
    db.add(skill)
    db.commit()
    r = client.post(f"{API}/attempts", headers=student, json={"skill_id": skill.id})
    assert r.status_code == 422 and "Not enough" in r.json()["detail"]


# ------------------------------------------------------------------ submission rules

def test_scores_only_delivered_questions(client, student, db):
    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=5)
    key = _key(db, a["attempt_id"])
    r = client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=_answers(key))
    body = r.json()
    assert r.status_code == 200 and body["total"] == 5 and body["correct"] == 5 and body["score_percent"] == 100
    assert body["estimated_level"] == 5 and len(body["review"]) == 5


def test_submission_rejections(client, student, db):
    from app import models

    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=5)
    aid, key = a["attempt_id"], _key(db, a["attempt_id"])
    qid = next(iter(key))
    other = db.query(models.AssessmentQuestion).filter(models.AssessmentQuestion.id.notin_(list(key))).first().id
    url = f"{API}/attempts/{aid}/submit"
    assert client.post(url, headers=student, json={"answers": [{"question_id": other, "answer": "A"}]}).status_code == 422
    assert client.post(url, headers=student, json={"answers": [{"question_id": qid, "answer": "A"},
                                                               {"question_id": qid, "answer": "B"}]}).status_code == 422
    assert client.post(url, headers=student, json={"answers": [{"question_id": qid, "answer": "E"}]}).status_code == 422
    # Another student cannot submit (or even see) this attempt.
    register(client, email="intruder@example.com")
    intruder = auth_headers(login(client, "intruder@example.com").json()["access_token"])
    assert client.post(url, headers=intruder, json=_answers(key)).status_code == 404
    assert client.get(f"{API}/attempts/{aid}", headers=intruder).status_code == 404
    # Valid submission, then a second submission is refused.
    assert client.post(url, headers=student, json=_answers(key)).status_code == 200
    assert client.post(url, headers=student, json=_answers(key)).status_code == 409


def test_unanswered_questions_count_as_wrong(client, student, db):
    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=10)
    key = _key(db, a["attempt_id"])
    first_four = dict(list(key.items())[:4])
    r = client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=_answers(first_four)).json()
    assert r["correct"] == 4 and r["unanswered"] == 6 and r["score_percent"] == 40.0 and r["estimated_level"] == 3


def test_time_limit_enforced(client, student, db):
    from app import models
    from app.security import utcnow

    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=5, timed=True)
    assert a["expires_at"] is not None
    row = db.get(models.AssessmentAttempt, a["attempt_id"])
    row.expires_at = utcnow() - timedelta(minutes=2)
    db.commit()
    r = client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=_answers(_key(db, a["attempt_id"])))
    assert r.status_code == 409 and "time limit" in r.json()["detail"]
    db.refresh(row)
    assert row.status == "expired"
    assert client.get(f"{API}/history", headers=student).json() == []


def test_staff_cannot_take_assessments(client, teacher):
    java = _skill(client, teacher)["id"]
    assert client.post(f"{API}/attempts", headers=teacher, json={"skill_id": java}).status_code == 403


# ------------------------------------------------------------------ results, history, side effects

def test_results_breakdowns_and_history(client, student, db):
    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=9, difficulty="mixed")
    key = _key(db, a["attempt_id"])
    beginner_ids = {q["id"] for q in a["questions"] if q["difficulty"] == "beginner"}
    body = _answers(key, lambda qid, right: right if qid in beginner_ids else _wrong(right))
    r = client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=body).json()
    by_diff = {d["name"]: d for d in r["by_difficulty"]}
    assert by_diff["beginner"]["percent"] == 100 and by_diff["advanced"]["percent"] == 0
    assert sum(t["total"] for t in r["by_topic"]) == 9
    assert all(x["explanation"] for x in r["review"])
    again = client.get(f"{API}/attempts/{a['attempt_id']}", headers=student).json()
    assert again["score_percent"] == r["score_percent"] == 33.33
    h = client.get(f"{API}/history", headers=student).json()
    assert len(h) == 1 and h[0]["estimated_level"] == 2


def test_in_progress_attempts_do_not_count(client, student):
    java = _skill(client, student)["id"]
    _start(client, student, java)
    assert client.get("/api/v1/students/me/dashboard", headers=student).json()["assessments"]["count"] == 0
    assert client.get("/api/v1/progress", headers=student).json()["attempts"] == []


def test_skill_level_updates_only_after_submit_with_evidence(client, student, db):
    from app import models

    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=5)
    assert db.query(models.StudentSkill).count() == 0
    client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=_answers(_key(db, a["attempt_id"])))
    s = db.query(models.StudentSkill).one()
    assert s.level == 5 and s.evidence_attempt_id == a["attempt_id"] and s.last_assessed_at is not None


def test_history_survives_question_edits(client, student, teacher, db):
    java = _skill(client, student)["id"]
    a = _start(client, student, java, question_count=5)
    key = _key(db, a["attempt_id"])
    client.post(f"{API}/attempts/{a['attempt_id']}/submit", headers=student, json=_answers(key))
    qid = a["questions"][0]["id"]
    original = a["questions"][0]["question"]
    r = client.put(f"/api/v1/question-bank/questions/{qid}", headers=teacher,
                   json={"question": "Rewritten question text?", "correct_option": "A" if key[qid] != "A" else "B"})
    assert r.status_code == 200
    res = client.get(f"{API}/attempts/{a['attempt_id']}", headers=student).json()
    item = next(x for x in res["review"] if x["question_id"] == qid)
    assert item["question"] == original and item["correct_option"] == key[qid] and res["score_percent"] == 100


# ------------------------------------------------------------------ question management

def test_question_management(client, teacher, admin, student):
    java = _skill(client, teacher)["id"]
    new = {"skill_id": java, "question": "Which interface must a class implement to be used in try-with-resources?",
           "option_a": "Closeable only", "option_b": "AutoCloseable", "option_c": "Runnable", "option_d": "Iterable",
           "correct_option": "B", "explanation": "try-with-resources accepts any AutoCloseable.",
           "difficulty": "intermediate", "topic": "Exceptions"}
    r = client.post("/api/v1/question-bank/questions", headers=teacher, json=new)
    assert r.status_code == 201 and r.json()["source"] == "staff"
    qid = r.json()["id"]
    assert client.post("/api/v1/question-bank/questions", headers=admin, json=new).status_code == 409
    assert client.post("/api/v1/question-bank/questions", headers=teacher,
                       json={**new, "question": "Other?", "option_b": "Closeable only"}).status_code == 422
    assert client.post("/api/v1/question-bank/questions", headers=teacher,
                       json={**new, "question": "Other?", "correct_option": "E"}).status_code == 422
    lst = client.get("/api/v1/question-bank/questions", headers=teacher,
                     params={"skill_id": java, "search": "try-with-resources"}).json()
    assert lst["total"] == 1 and lst["items"][0]["correct_option"] == "B"
    assert client.put(f"/api/v1/question-bank/questions/{qid}", headers=teacher, json={"is_active": False}).json()["is_active"] is False
    page = client.get("/api/v1/question-bank/questions", headers=admin, params={"page_size": 10, "page": 2}).json()
    assert page["page"] == 2 and len(page["items"]) == 10 and page["total_pages"] >= 2
    # Students may not use the management API at all.
    assert client.get("/api/v1/question-bank/questions", headers=student).status_code == 403
    assert client.post("/api/v1/question-bank/questions", headers=student, json=new).status_code == 403


def test_deactivated_questions_are_never_delivered(client, student, teacher):
    java = _skill(client, student)["id"]
    items = client.get("/api/v1/question-bank/questions", headers=teacher,
                       params={"skill_id": java, "page_size": 100}).json()["items"]
    keep = {q["id"] for q in items[:6]}
    for q in items[6:]:
        client.put(f"/api/v1/question-bank/questions/{q['id']}", headers=teacher, json={"is_active": False})
    a = _start(client, student, java, question_count=30)
    assert {q["id"] for q in a["questions"]} == keep
