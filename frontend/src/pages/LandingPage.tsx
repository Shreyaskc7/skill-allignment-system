import { Link } from 'react-router-dom';
import { BookOpen, Briefcase, ClipboardList, GraduationCap, Target, Users } from 'lucide-react';

const FEATURES = [
  { icon: ClipboardList, title: 'Skill assessments', text: 'Multiple-choice assessments with explanations update your proficiency profile.' },
  { icon: Target, title: 'Explainable skill gaps', text: 'A transparent weighted score compares your assessed skills with a target role.' },
  { icon: Briefcase, title: 'Job-market insight', text: 'Skills are extracted from imported job postings to show what employers ask for.' },
  { icon: BookOpen, title: 'Learning resources', text: 'Curated free documentation, courses and practice, with progress tracking.' },
  { icon: Users, title: 'Mentor support', text: 'Teachers and mentors follow the progress of the students assigned to them.' },
  { icon: GraduationCap, title: 'Built for students', text: 'Designed around the journey from assessment to career readiness.' },
];

export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="brand">
          <div className="brand-icon">S</div>
          <b>
            skill<span>align</span>
          </b>
        </div>
        <nav>
          <Link to="/login">Sign in</Link>
          <Link to="/register" className="primary">
            Create account
          </Link>
        </nav>
      </header>

      <section className="landing-hero">
        <label>INTELLIGENT WORKFORCE SKILL ALIGNMENT</label>
        <h1>
          Know where you stand.
          <br />
          <em>Close the gap to your career.</em>
        </h1>
        <p>
          SkillAlign helps students assess their skills, compare them with the requirements of a target role and
          follow a practical learning path, with support from their mentors.
        </p>
        <div className="landing-cta">
          <Link to="/register" className="primary">
            Get started as a student →
          </Link>
          <Link to="/login" className="secondary">
            I already have an account
          </Link>
        </div>
      </section>

      <section className="landing-features" aria-label="Features">
        {FEATURES.map((f) => (
          <article key={f.title}>
            <f.icon aria-hidden="true" />
            <h3>{f.title}</h3>
            <p>{f.text}</p>
          </article>
        ))}
      </section>

      <footer className="landing-footer">
        SkillAlign · MCA academic project. Scores are guidance from rule-based calculations, not hiring predictions.
      </footer>
    </div>
  );
}
