from contextlib import asynccontextmanager
from collections import Counter
import csv, io, re, json
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.config import settings
from app.db import Base, check_database_connection, engine, get_db
from app import models

CATALOG = {
 'Python':('Programming', 'Python programming language'), 'Java':('Programming','Java programming language'),
 'SQL':('Database','Querying relational databases'), 'PostgreSQL':('Database','Relational database management'),
 'Excel':('Analytics','Spreadsheet analysis'), 'Power BI':('Analytics','Business intelligence and dashboards'),
 'Tableau':('Analytics','Data visualization'), 'Statistics':('Analytics','Statistical reasoning'),
 'Data Analysis':('Analytics','Analyzing and interpreting data'), 'Machine Learning':('AI/ML','Machine learning methods'),
 'Pandas':('Data Science','Python data manipulation'), 'NumPy':('Data Science','Numerical computing'),
 'React':('Web Development','Frontend UI library'), 'JavaScript':('Programming','Web programming language'),
 'HTML':('Web Development','Markup language'), 'CSS':('Web Development','Stylesheets'),
 'FastAPI':('Backend','Python API framework'), 'Django':('Backend','Python web framework'),
 'Git':('Tools','Version control'), 'Linux':('Systems','Linux operating system'),
 'Docker':('DevOps','Containerization'), 'Communication':('Soft Skills','Communication skills'),
 'Problem Solving':('Soft Skills','Analytical problem solving'), 'Teamwork':('Soft Skills','Collaborative work'),
 'Data Structures':('Computer Science','Core data structures'), 'Algorithms':('Computer Science','Algorithm design')
}
ROLE_SKILLS = {
 'Software Developer': [('Java',4,5),('Data Structures',4,5),('Algorithms',4,5),('SQL',3,3),('Git',3,3),('Problem Solving',4,5)],
 'Data Analyst': [('SQL',4,5),('Excel',4,4),('Python',3,4),('Statistics',4,5),('Power BI',3,4),('Data Analysis',4,5),('Communication',3,2)],
 'Python Backend Developer': [('Python',4,5),('FastAPI',3,4),('SQL',4,4),('PostgreSQL',3,4),('Git',3,3),('Docker',2,2)],
 'Frontend Developer': [('HTML',4,4),('CSS',4,4),('JavaScript',4,5),('React',4,5),('Git',3,3),('Communication',3,2)],
 'Machine Learning Engineer': [('Python',4,5),('Statistics',4,5),('Machine Learning',4,5),('Pandas',3,4),('NumPy',3,3),('SQL',3,3)]
}
QUESTIONS = {
 'Python': [
 ('Which keyword defines a function in Python?',['func','def','function','lambda'],'B','The def keyword begins a function definition.','beginner'),
 ('What does len([2, 4, 6]) return?',['2','3','6','Error'],'B','len returns the number of elements: three.','beginner'),
 ('Which structure stores unique elements?',['list','tuple','set','dict'],'C','A set stores unique values.','beginner'),
 ('What is the result of 7 // 2?',['3.5','3','4','2'],'B','// performs floor division.','intermediate'),
 ('Which library is commonly used for tabular data?',['Pandas','Turtle','Tkinter','Pygame'],'A','Pandas provides DataFrame structures for tabular data.','intermediate')],
 'SQL': [
 ('Which SQL command retrieves rows?',['GET','FETCH','SELECT','OPEN'],'C','SELECT retrieves data from tables.','beginner'),
 ('Which clause filters rows before grouping?',['HAVING','WHERE','ORDER BY','LIMIT'],'B','WHERE filters individual rows before grouping.','beginner'),
 ('Which join returns only matching rows?',['LEFT JOIN','FULL JOIN','INNER JOIN','CROSS JOIN'],'C','INNER JOIN returns rows with matching join keys.','intermediate'),
 ('Which function counts rows?',['SUM()','COUNT()','TOTAL()','NUMBER()'],'B','COUNT returns the number of rows or non-null values.','beginner'),
 ('What does a primary key ensure?',['Duplicate values','Unique row identity','Sorted rows','Encrypted data'],'B','A primary key uniquely identifies each row.','intermediate')],
 'Java': [
 ('Which method is the usual Java program entry point?',['start()','run()','main()','init()'],'C','The JVM starts a standard application at public static void main.','beginner'),
 ('Which keyword creates an object?',['this','new','class','make'],'B','The new keyword creates an object.','beginner'),
 ('Which collection does not allow duplicate elements?',['ArrayList','LinkedList','HashSet','Vector'],'C','HashSet stores unique elements.','intermediate')],
 'Statistics': [
 ('Which measure is the arithmetic average?',['Median','Mode','Mean','Range'],'C','Mean is the sum divided by the count.','beginner'),
 ('What does standard deviation measure?',['Central value','Spread of data','Sample size','Correlation'],'B','Standard deviation measures dispersion around the mean.','intermediate')],
 'React': [
 ('Which hook manages local component state?',['useEffect','useState','useMemo','useRef'],'B','useState declares state in a function component.','beginner'),
 ('What is JSX?',['A database','A syntax extension for JavaScript','A CSS framework','A router'],'B','JSX lets developers write markup-like syntax in JavaScript.','beginner')]
}
RESOURCES = {
 'Python':[('Python Tutorial','Python.org','https://docs.python.org/3/tutorial/','documentation','beginner','Official language tutorial'),('Python for Everybody','freeCodeCamp','https://www.freecodecamp.org/learn/scientific-computing-with-python/','course','beginner','Free guided Python course')],
 'SQL':[('PostgreSQL Tutorial','PostgreSQL','https://www.postgresql.org/docs/current/tutorial.html','documentation','beginner','Official SQL and PostgreSQL tutorial'),('SQLBolt','SQLBolt','https://sqlbolt.com/','practice','beginner','Interactive SQL exercises')],
 'Java':[('Java Tutorials','Dev.java','https://dev.java/learn/','documentation','beginner','Official Java learning path')],
 'React':[('React Learn','React','https://react.dev/learn','documentation','beginner','Official React learning guide')],
 'Statistics':[('OpenIntro Statistics','OpenIntro','https://www.openintro.org/book/os/','book','beginner','Free statistics textbook')],
 'Machine Learning':[('Google Machine Learning Crash Course','Google','https://developers.google.com/machine-learning/crash-course','course','beginner','Free practical ML course')],
 'Git':[('Pro Git Book','Git','https://git-scm.com/book/en/v2','book','beginner','Free version control book')],
 'Excel':[('Excel Training','Microsoft','https://support.microsoft.com/excel','documentation','beginner','Official Excel training')],
 'Power BI':[('Power BI Learning','Microsoft','https://learn.microsoft.com/power-bi/','documentation','beginner','Official Power BI learning')]
}

def seed(db: Session):
    user=db.scalar(select(models.User).where(models.User.email=='student@skillalign.local'))
    if not user:
        user=models.User(email='student@skillalign.local',full_name='Student Demo',role='student'); db.add(user)
    for name,(cat,desc) in CATALOG.items():
        if not db.scalar(select(models.Skill).where(models.Skill.name==name)): db.add(models.Skill(name=name,category=cat,description=desc))
    db.flush()
    for role, entries in ROLE_SKILLS.items():
        obj=db.scalar(select(models.CareerRole).where(models.CareerRole.name==role))
        if not obj: obj=models.CareerRole(name=role,description=f'Skills and competencies commonly associated with a {role.lower()} role.'); db.add(obj); db.flush()
        for skill,level,weight in entries:
            sk=db.scalar(select(models.Skill).where(models.Skill.name==skill))
            if sk and not db.scalar(select(models.CareerRoleSkill).where(models.CareerRoleSkill.career_role_id==obj.id,models.CareerRoleSkill.skill_id==sk.id)):
                db.add(models.CareerRoleSkill(career_role_id=obj.id,skill_id=sk.id,required_level=level,importance_weight=weight))
    db.flush()
    for skill,qs in QUESTIONS.items():
        sk=db.scalar(select(models.Skill).where(models.Skill.name==skill))
        for q,opts,correct,explain,diff in qs:
            if not db.scalar(select(models.AssessmentQuestion).where(models.AssessmentQuestion.skill_id==sk.id,models.AssessmentQuestion.question==q)):
                db.add(models.AssessmentQuestion(skill_id=sk.id,question=q,option_a=opts[0],option_b=opts[1],option_c=opts[2],option_d=opts[3],correct_option=correct,explanation=explain,difficulty=diff))
    db.flush()
    for skill,items in RESOURCES.items():
        sk=db.scalar(select(models.Skill).where(models.Skill.name==skill))
        for title,provider,url,typ,diff,desc in items:
            if not db.scalar(select(models.LearningResource).where(models.LearningResource.skill_id==sk.id,models.LearningResource.title==title)):
                db.add(models.LearningResource(skill_id=sk.id,title=title,provider=provider,url=url,resource_type=typ,difficulty=diff,description=desc,is_free=True))
    db.commit()

def get_or_create_skill(db,name):
    name=name.strip()
    if not name: return None
    obj=db.scalar(select(models.Skill).where(func.lower(models.Skill.name)==name.lower()))
    if not obj:
        cat,desc=CATALOG.get(name,( 'Other','Extracted from job description'))
        obj=models.Skill(name=name[:100],category=cat,description=desc); db.add(obj); db.flush()
    return obj

def extract_skills(text):
    low=text.lower(); found=[]
    aliases={'js':'JavaScript','postgres':'PostgreSQL','powerbi':'Power BI','problem-solving':'Problem Solving','data analytics':'Data Analysis'}
    for term,canonical in aliases.items():
        if re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',low): found.append(canonical)
    for name in CATALOG:
        if re.search(r'(?<![a-z0-9])'+re.escape(name.lower())+r'(?![a-z0-9])',low): found.append(name)
    return sorted(set(found))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.create_tables_on_start: Base.metadata.create_all(bind=engine)
    with next(get_db()) as db: seed(db)
    yield
app=FastAPI(title=settings.app_name,description='Skill assessment, job-market intelligence, gap analysis and learning recommendations.',version='1.0.0',lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get('/health')
def health(): return {'status':'ok','service':'skill-alignment-api','environment':settings.app_env}
@app.get('/health/db')
def db_health():
    try: check_database_connection(); return {'status':'ok','database':'connected'}
    except Exception as e: raise HTTPException(503,'Database connection unavailable') from e
@app.get('/api/v1/careers')
def careers(db:Session=Depends(get_db)):
    rows=db.scalars(select(models.CareerRole).options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill)).order_by(models.CareerRole.name)).all()
    return [{'id':r.id,'name':r.name,'description':r.description,'skills':[{'skill_id':x.skill_id,'skill_name':x.skill.name,'required_level':x.required_level,'importance_weight':x.importance_weight} for x in r.skills]} for r in rows]
@app.get('/api/v1/skills')
def skills(db:Session=Depends(get_db)):
    return [{'id':s.id,'name':s.name,'category':s.category,'description':s.description} for s in db.scalars(select(models.Skill).order_by(models.Skill.name)).all()]
@app.get('/api/v1/dashboard')
def dashboard(db:Session=Depends(get_db)):
    return {'job_count':db.scalar(select(func.count(models.JobPosting.id))) or 0,'skill_count':db.scalar(select(func.count(models.Skill.id))) or 0,'assessment_count':db.scalar(select(func.count(models.AssessmentAttempt.id))) or 0,'resource_count':db.scalar(select(func.count(models.LearningResource.id))) or 0,'top_skills':[{'name':n,'count':c} for n,c in db.query(models.Skill.name,func.count(models.JobSkill.id)).join(models.JobSkill,models.Skill.id==models.JobSkill.skill_id,isouter=True).group_by(models.Skill.id).order_by(func.count(models.JobSkill.id).desc()).limit(8).all()]}
@app.get('/api/v1/assessments/skills')
def assessment_skills(db:Session=Depends(get_db)):
    rows=db.query(models.Skill).join(models.AssessmentQuestion,models.Skill.id==models.AssessmentQuestion.skill_id).distinct().order_by(models.Skill.name).all()
    return [{'id':s.id,'name':s.name,'question_count':db.scalar(select(func.count(models.AssessmentQuestion.id)).where(models.AssessmentQuestion.skill_id==s.id))} for s in rows]
@app.get('/api/v1/assessments/questions/{skill_id}')
def questions(skill_id:int,limit:int=10,db:Session=Depends(get_db)):
    rows=db.scalars(select(models.AssessmentQuestion).where(models.AssessmentQuestion.skill_id==skill_id).limit(min(limit,30))).all()
    if not rows: raise HTTPException(404,'No assessment questions available for this skill yet.')
    return [{'id':q.id,'question':q.question,'options':{'A':q.option_a,'B':q.option_b,'C':q.option_c,'D':q.option_d},'difficulty':q.difficulty} for q in rows]
@app.post('/api/v1/assessments/submit')
def submit_assessment(payload:dict,db:Session=Depends(get_db)):
    skill_id=int(payload.get('skill_id',0)); answers=payload.get('answers',{})
    rows=db.scalars(select(models.AssessmentQuestion).where(models.AssessmentQuestion.skill_id==skill_id)).all()
    if not rows: raise HTTPException(404,'Assessment skill not found')
    correct=sum(1 for q in rows if answers.get(str(q.id))==q.correct_option)
    pct=round(correct/len(rows)*100,2); user=db.scalar(select(models.User).where(models.User.email=='student@skillalign.local'))
    attempt=models.AssessmentAttempt(user_id=user.id,skill_id=skill_id,total_questions=len(rows),correct_answers=correct,score_percent=pct,answers_json=json.dumps(answers)); db.add(attempt)
    level=max(1,min(5,round(pct/20)))
    current=db.scalar(select(models.StudentSkill).where(models.StudentSkill.user_id==user.id,models.StudentSkill.skill_id==skill_id))
    if current: current.level=level
    else: db.add(models.StudentSkill(user_id=user.id,skill_id=skill_id,level=level))
    db.commit()
    review=[{'question_id':q.id,'correct_option':q.correct_option,'your_answer':answers.get(str(q.id)),'is_correct':answers.get(str(q.id))==q.correct_option,'explanation':q.explanation} for q in rows]
    return {'attempt_id':attempt.id,'correct':correct,'total':len(rows),'score_percent':pct,'estimated_level':level,'review':review}
@app.get('/api/v1/assessments/history')
def history(db:Session=Depends(get_db)):
    rows=db.scalars(select(models.AssessmentAttempt).order_by(models.AssessmentAttempt.created_at.desc()).limit(50)).all()
    return [{'id':a.id,'skill':db.get(models.Skill,a.skill_id).name,'score_percent':a.score_percent,'correct':a.correct_answers,'total':a.total_questions,'created_at':a.created_at.isoformat() if a.created_at else None} for a in rows]
@app.get('/api/v1/gaps/{career_id}')
def gaps(career_id:int,db:Session=Depends(get_db)):
    role=db.scalar(select(models.CareerRole).options(selectinload(models.CareerRole.skills).selectinload(models.CareerRoleSkill.skill)).where(models.CareerRole.id==career_id))
    if not role: raise HTTPException(404,'Career not found')
    user=db.scalar(select(models.User).where(models.User.email=='student@skillalign.local')); out=[]; weighted=0; total=0
    for link in role.skills:
        st=db.scalar(select(models.StudentSkill).where(models.StudentSkill.user_id==user.id,models.StudentSkill.skill_id==link.skill_id)); level=st.level if st else 0
        weight=link.importance_weight; weighted+=min(level,link.required_level)/max(link.required_level,1)*weight; total+=weight
        out.append({'skill_id':link.skill_id,'skill':link.skill.name,'current_level':level,'required_level':link.required_level,'importance':weight,'gap':max(0,link.required_level-level),'priority':'High' if link.required_level-level>=2 and weight>=4 else ('Medium' if link.required_level>level else 'On track')})
    return {'career':role.name,'alignment_score':round(weighted/total*100) if total else 0,'skills':out}
@app.get('/api/v1/resources')
def resources(skill_id:int|None=None,db:Session=Depends(get_db)):
    stmt=select(models.LearningResource).order_by(models.LearningResource.title)
    if skill_id: stmt=stmt.where(models.LearningResource.skill_id==skill_id)
    return [{'id':r.id,'skill_id':r.skill_id,'skill':db.get(models.Skill,r.skill_id).name,'title':r.title,'provider':r.provider,'url':r.url,'type':r.resource_type,'difficulty':r.difficulty,'description':r.description,'is_free':r.is_free} for r in db.scalars(stmt).all()]
@app.post('/api/v1/progress/{resource_id}')
def update_progress(resource_id:int,payload:dict,db:Session=Depends(get_db)):
    user=db.scalar(select(models.User).where(models.User.email=='student@skillalign.local')); r=db.get(models.LearningResource,resource_id)
    if not r: raise HTTPException(404,'Resource not found')
    row=db.scalar(select(models.LearningProgress).where(models.LearningProgress.user_id==user.id,models.LearningProgress.resource_id==resource_id))
    if not row: row=models.LearningProgress(user_id=user.id,resource_id=resource_id); db.add(row)
    status=payload.get('status','in_progress')
    if status not in ['not_started','in_progress','completed']: raise HTTPException(400,'Invalid status')
    row.status=status; row.notes=payload.get('notes',''); db.commit(); return {'status':row.status,'resource_id':resource_id}
@app.get('/api/v1/progress')
def progress(db:Session=Depends(get_db)):
    user=db.scalar(select(models.User).where(models.User.email=='student@skillalign.local'))
    attempts=db.scalars(select(models.AssessmentAttempt).where(models.AssessmentAttempt.user_id==user.id).order_by(models.AssessmentAttempt.created_at)).all()
    records=db.scalars(select(models.LearningProgress).where(models.LearningProgress.user_id==user.id)).all()
    return {'attempts':[{'skill':db.get(models.Skill,a.skill_id).name,'score':a.score_percent,'date':a.created_at.isoformat() if a.created_at else None} for a in attempts],'resources':{'completed':sum(x.status=='completed' for x in records),'in_progress':sum(x.status=='in_progress' for x in records),'total_tracked':len(records)}}
@app.post('/api/v1/jobs/import-csv')
async def import_jobs(file:UploadFile=File(...),db:Session=Depends(get_db)):
    if not file.filename.lower().endswith('.csv'): raise HTTPException(400,'Upload a CSV file')
    raw=(await file.read()).decode('utf-8-sig',errors='replace')
    reader=csv.DictReader(io.StringIO(raw)); fields={f.lower().strip():f for f in (reader.fieldnames or [])}
    title_col=next((fields[x] for x in ['title','job_title','position'] if x in fields),None)
    desc_col=next((fields[x] for x in ['description','job_description','job_details'] if x in fields),None)
    if not title_col or not desc_col: raise HTTPException(400,'CSV must contain title/job_title and description/job_description columns')
    count=0; skipped=0; found=Counter()
    for row in reader:
        title=(row.get(title_col) or '').strip(); desc=(row.get(desc_col) or '').strip()
        if not title or not desc: skipped+=1; continue
        company=(row.get(fields.get('company','')) or '').strip() or None
        location=(row.get(fields.get('location','')) or '').strip() or None
        dupe=db.scalar(select(models.JobPosting).where(models.JobPosting.title==title,models.JobPosting.description==desc))
        if dupe: skipped+=1; continue
        job=models.JobPosting(title=title[:200],company=company,location=location,description=desc,source=file.filename,posted_date=(row.get(fields.get('date','')) or row.get(fields.get('posted_date','')) or None)); db.add(job); db.flush()
        for name in extract_skills(desc+' '+title):
            sk=get_or_create_skill(db,name); db.add(models.JobSkill(job_id=job.id,skill_id=sk.id)); found[name]+=1
        count+=1
    db.commit(); return {'imported':count,'skipped':skipped,'skills_found':dict(found),'message':'CSV imported and skill extraction completed using the built-in dictionary baseline.'}
@app.get('/api/v1/jobs')
def jobs(limit:int=50,db:Session=Depends(get_db)):
    rows=db.scalars(select(models.JobPosting).order_by(models.JobPosting.created_at.desc()).limit(min(limit,200))).all()
    return [{'id':j.id,'title':j.title,'company':j.company,'location':j.location,'source':j.source,'skills':[x.skill.name for x in j.skills]} for j in rows]
@app.get('/api/v1/analytics/skills')
def analytics(db:Session=Depends(get_db)):
    rows=db.query(models.Skill.name,func.count(models.JobSkill.id)).join(models.JobSkill,models.Skill.id==models.JobSkill.skill_id).group_by(models.Skill.id).order_by(func.count(models.JobSkill.id).desc()).limit(20).all()
    return [{'skill':n,'postings':c} for n,c in rows]
@app.get('/api/v1/faculty/summary')
def faculty_summary(db:Session=Depends(get_db)):
    return {'students':db.scalar(select(func.count(models.User.id)).where(models.User.role=='student')) or 0,'job_postings':db.scalar(select(func.count(models.JobPosting.id))) or 0,'assessments':db.scalar(select(func.count(models.AssessmentAttempt.id))) or 0,'skills_catalogued':db.scalar(select(func.count(models.Skill.id))) or 0,'average_assessment_score':round(db.scalar(select(func.avg(models.AssessmentAttempt.score_percent))) or 0,1)}
