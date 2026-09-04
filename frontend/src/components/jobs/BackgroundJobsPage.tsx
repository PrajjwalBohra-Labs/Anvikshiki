import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, CircleDot, LoaderCircle, RotateCcw } from 'lucide-react';
import { listBackgroundJobs } from '../../api/services';
import type { BackgroundJobDTO } from '../../types';

function statusClass(status: string): string { return status.toLowerCase(); }
function Loading() { return <p className="muted-copy loading-message" role="status"><LoaderCircle className="spin" size={14} /> Loading background work...</p>; }
function Failure({ message }: { message: string }) { return <div className="inline-error" role="alert"><AlertTriangle size={15} />{message}</div>; }
function statusMessage(job: BackgroundJobDTO): string { const status = job.status.toUpperCase(); if (status === 'COMPLETED') return 'Worker execution completed.'; if (status === 'RUNNING') return 'Worker execution is active.'; if (status === 'QUEUED') return 'Waiting for a worker slot.'; if (status === 'CANCELLED') return 'Execution was cancelled by the service.'; if (status === 'FAILED') return job.error_message || 'The worker reported a failure.'; return 'State returned by the worker service.'; }

export function BackgroundJobsPage() {
  const [jobs, setJobs] = useState<BackgroundJobDTO[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = () => { setLoading(true); setError(''); void listBackgroundJobs().then(setJobs).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Background work could not be loaded.')).finally(() => setLoading(false)); };
  useEffect(load, []);
  return <section className="secondary-page jobs-page"><div className="eyebrow">Research / Background work</div><h1>Execution ledger</h1><p className="page-lede">Durable job states returned by the authenticated worker service. No progress is simulated.</p><div className="page-actions"><button className="button" type="button" onClick={load} disabled={loading}>{loading ? <LoaderCircle className="spin" size={14} /> : <RotateCcw size={14} />} Refresh jobs</button></div>{loading && <Loading />}{error && <Failure message={error} />}{!loading && !error && jobs.length === 0 && <div className="empty-card"><CircleDot size={18} />No background jobs are currently associated with this session.</div>}<div className="job-list">{jobs.map((job) => <article className="job-card" key={job.job_id}><div className="job-heading"><span className="job-title"><span className={`job-status-orb ${statusClass(job.status)}`} /><span className="eyebrow">{job.job_type}</span></span><span className={`status-chip ${statusClass(job.status)}`}>{job.status}</span></div><div className="job-meta"><span><b>Job</b>{job.job_id}</span><span><b>Attempts</b>{job.attempts} / {job.max_attempts}</span><span><b>Research run</b>{job.research_run_id || 'Not linked'}</span></div><p className={`job-state ${job.status === 'FAILED' ? 'error-text' : ''}`}>{job.status === 'COMPLETED' ? <CheckCircle2 size={14} /> : job.status === 'FAILED' ? <AlertTriangle size={14} /> : <Activity size={14} />} {statusMessage(job)}</p></article>)}</div></section>;
}
