"""Phase 11: the complete 20-step workflow from the project brief, through the HTTP API only.

The only shortcut: answer keys for the "perfect" assessment are read from the attempt's
server-side snapshot (a test cannot know them otherwise). Everything else is public API.
"""

import io
import re

from conftest import auth_headers, login, make_user

API = "/api/v1"
PW = "Journey-pass1"


def test_complete_student_mentor_admin_journey(client, db):
    from app import models
    from app.models import UserRole
    from app.services.email import OUTBOX

    # Bootstrap: one administrator exists (created by the CLI in real deployments).
    make_user(db, "admin@college.example.com", UserRole.admin, password=PW, name="Admin")
    admin = auth_headers(login(client, "admin@college.example.com", PW).json()["access_token"])

    # 1. Register a student
    r = client.post(f"{API}/auth/register", json={"email": "riya@college.example.com", "full_name": "Riya Sharma",
                                                  "password": PW, "confirm_password": PW, "terms_accepted": True})
    assert r.status_code == 201

    # 2. Log in as the student (and the session survives a "reload" via the refresh cookie)
    s = login(client, "riya@college.example.com", PW)
    assert s.status_code == 200
    stu = auth_headers(s.json()["access_token"])
    assert client.post(f"{API}/auth/refresh").status_code == 200

    # 3. Complete the profile
    careers = {c["name"]: c["id"] for c in client.get(f"{API}/careers", headers=stu).json()}
    r = client.put(f"{API}/students/me/profile", headers=stu, json={
        "full_name": "Riya Sharma", "phone": "+91 90000 22222", "location": "Mysuru", "college": "Example Institute",
        "degree": "MCA", "department": "Computer Applications", "specialization": "Data", "current_semester": 3,
        "graduation_year": 2027, "career_interests": "data analysis and dashboards", "preferred_locations": "Bengaluru",
        "experience_level": "fresher"})
    assert r.status_code == 200 and r.json()["completion"]["percent"] > 50

    # 4. Select a career
    da = careers["Data Analyst"]
    assert client.put(f"{API}/students/me/target-career", headers=stu, json={"target_career_id": da}).json()["target_career_name"] == "Data Analyst"

    # 5. Take an assessment (SQL, all answers correct)
    sql = next(x for x in client.get(f"{API}/assessments/skills", headers=stu).json() if x["name"] == "SQL")
    att = client.post(f"{API}/assessments/attempts", headers=stu, json={"skill_id": sql["id"], "question_count": 10}).json()
    assert all("correct_option" not in q for q in att["questions"])
    key = {q.question_id: q.correct_option for q in db.query(models.AssessmentAttemptQuestion).filter_by(attempt_id=att["attempt_id"])}
    res = client.post(f"{API}/assessments/attempts/{att['attempt_id']}/submit", headers=stu,
                      json={"answers": [{"question_id": k, "answer": v} for k, v in key.items()]})

    # 6. View the assessment result
    assert res.status_code == 200
    result = client.get(f"{API}/assessments/attempts/{att['attempt_id']}", headers=stu).json()
    assert result["score_percent"] == 100 and result["estimated_level"] == 5 and len(result["review"]) == 10

    # 7. The skill profile is updated
    dash = client.get(f"{API}/students/me/dashboard", headers=stu).json()
    assert [x["skill"] for x in dash["assessed_skills"]] == ["SQL"]

    # 8. Skill-gap analysis
    gaps = client.get(f"{API}/gaps/{da}", headers=stu).json()
    assert gaps["alignment_score"] == 17  # SQL 4/4*5 = 5 of 29 (unchanged weighted formula)
    assert next(x for x in gaps["skills"] if x["skill"] == "SQL")["status"] == "meets"

    # 9. Career recommendations
    recs = client.get(f"{API}/careers/recommendations", headers=stu).json()["recommendations"]
    assert recs[0]["alignment_score"] >= recs[-1]["alignment_score"] and any(r["is_target"] for r in recs)

    # 10. Import job postings (as staff)
    csv_body = ("title,company,location,description,posted_date\n"
                "SQL Analyst,Acme,Bengaluru,\"Strong SQL required. Excel is a plus.\",2026-10-01\n"
                "Python Developer,Beta,Pune,\"Python, FastAPI and PostgreSQL.\",2026-10-02\n")
    imp = client.post(f"{API}/jobs/import-csv", headers=admin, files={"file": ("jobs.csv", io.BytesIO(csv_body.encode()), "text/csv")})
    assert imp.json()["imported"] == 2

    # 11. View matching jobs
    jobs = client.get(f"{API}/jobs", headers=stu).json()["items"]
    assert jobs[0]["title"] == "SQL Analyst" and jobs[0]["match_percent"] == 100

    # 12. Open a job detail page
    detail = client.get(f"{API}/jobs/{jobs[0]['id']}", headers=stu).json()
    assert detail["description"] and detail["additional_skills"] == ["Excel"]

    # 13. Personalised learning resources
    path = client.get(f"{API}/learning/path", headers=stu).json()
    assert path["career"] == "Data Analyst" and path["steps"] and "SQL" in [c["skill"] for c in path["completed_skills"]]
    first = path["steps"][0]["resources"][0]

    # 14. Complete a resource
    assert client.post(f"{API}/progress/{first['id']}", headers=stu, json={"status": "completed", "notes": "done"}).status_code == 200

    # 15. Progress updates
    assert client.get(f"{API}/progress", headers=stu).json()["resources"]["completed"] == 1
    assert client.get(f"{API}/learning/history", headers=stu).json()[0]["completed_at"]

    # 16. A mentor joins by invitation and logs in
    client.post(f"{API}/admin/invitations", headers=admin, json={"email": "mentor@college.example.com", "full_name": "Prof Mentor"})
    token = re.search(r"token=([\w-]+)", OUTBOX[-1]["body"]).group(1)
    assert client.post(f"{API}/auth/accept-invitation", json={"token": token, "password": PW, "confirm_password": PW}).status_code == 201
    mentor = auth_headers(login(client, "mentor@college.example.com", PW).json()["access_token"])
    assert client.get(f"{API}/mentor/students", headers=mentor).json() == []  # nobody assigned yet

    # 17. Admin assigns the student to the mentor (authorised workflow)
    ids = {u.email: u.id for u in db.query(models.User)}
    assert client.post(f"{API}/admin/assignments", headers=admin, json={
        "student_id": ids["riya@college.example.com"], "teacher_id": ids["mentor@college.example.com"]}).status_code == 201

    # 18. Mentor reviews the student's performance
    view = client.get(f"{API}/mentor/students/{ids['riya@college.example.com']}", headers=mentor).json()
    assert view["summary"]["target_career"]["alignment_score"] == 17 and view["skill_performance"][0]["skill"] == "SQL"

    # 19. Mentor adds feedback, which the student sees
    client.post(f"{API}/mentor/students/{ids['riya@college.example.com']}/notes", headers=mentor,
                json={"note": "Great SQL score. Next: Statistics.", "note_type": "feedback"})
    assert client.get(f"{API}/students/me/mentoring", headers=stu).json()["notes"][0]["note"].startswith("Great SQL")

    # 20. Unauthorised access is rejected
    make_user(db, "other.mentor@college.example.com", UserRole.teacher, password=PW)
    other = auth_headers(login(client, "other.mentor@college.example.com", PW).json()["access_token"])
    assert client.get(f"{API}/mentor/students/{ids['riya@college.example.com']}", headers=other).status_code == 404
    assert client.get(f"{API}/admin/accounts", headers=mentor).status_code == 403
    assert client.get(f"{API}/assessments/attempts/{att['attempt_id']}", headers=other).status_code == 403
    assert client.get(f"{API}/students/me/profile").status_code == 401
    audit = {a.action for a in db.query(models.AuditLog)}
    assert {"auth.register", "auth.login", "jobs.csv_import", "admin.assignment_created", "mentor.note_added"} <= audit
