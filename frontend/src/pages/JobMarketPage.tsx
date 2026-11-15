import { useState } from 'react';
import { Upload } from 'lucide-react';
import { errorMessage, request } from '../api/client';
import { Empty } from '../components/common';
import type { ImportResult, Job } from '../types';

export function JobMarketPage({
  jobs,
  reload,
  setNotice,
}: {
  jobs: Job[];
  reload: () => Promise<void>;
  setNotice: (message: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function importCsv() {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await request<ImportResult>('/api/v1/jobs/import-csv', { method: 'POST', body: fd });
      setNotice(
        `Imported ${r.imported} jobs; skipped ${r.skipped}. Extracted skills: ${
          Object.keys(r.skills_found).join(', ') || 'none detected'
        }`,
      );
      setFile(null);
      await reload();
    } catch (e) {
      setNotice(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        <h2>Import job-market dataset</h2>
        <p className="muted">
          Upload a CSV containing a job title and description. Optional columns: company, location, date or
          posted_date. The current baseline extracts known skills using a curated dictionary.
        </p>
        <div className="upload">
          <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <button className="primary" disabled={!file || busy} onClick={importCsv}>
            <Upload size={16} /> Import CSV
          </button>
        </div>
        <a href="/sample_jobs.csv" download>
          Download sample CSV template
        </a>
      </section>

      <section className="panel">
        <h2>Imported job postings ({jobs.length})</h2>
        {jobs.map((j) => (
          <div className="job" key={j.id}>
            <b>{j.title}</b>
            <small>
              {j.company || 'Company not specified'} · {j.location || 'Location not specified'}
            </small>
            <div className="tags">
              {j.skills.map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
          </div>
        ))}
        {!jobs.length && <Empty text="No job postings imported yet." />}
      </section>
    </>
  );
}
