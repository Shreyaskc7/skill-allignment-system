"""Seed catalogue: skills, career-role requirements, starter questions and resources.

Role entries are (skill, required_level 1-5, importance_weight 1-5).
Resource entries are (title, provider, url, type, difficulty, description).
"""

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
# Assessment questions moved to app/question_bank/*.json in Phase 6 (the 17 version 1
# questions are included there verbatim).
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
