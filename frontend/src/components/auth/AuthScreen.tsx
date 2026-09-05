import { useState, type FormEvent } from 'react';
import { KeyRound, LoaderCircle, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../auth/AuthProvider';
import './AuthScreen.css';

export function AuthScreen() {
  const { error, register } = useAuth();
  const [username, setUsername] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = username.trim();
    if (!normalized) return;
    setBusy(true);
    try { await register(normalized); } catch { /* AuthProvider exposes the actionable message. */ } finally { setBusy(false); }
  };

  return (
    <main className="auth-screen">
      <div className="auth-frame">
        <section className="auth-card">
          <div className="auth-brand"><div className="brand-mark" aria-hidden="true">A</div><div><div className="eyebrow">Private research instrument</div><strong>ANVIKSHIKI</strong></div></div>
          <div className="eyebrow">Local session / Entry</div>
          <h1>Begin with a research identity.</h1>
          <p className="page-lede">Enter your username to create or authenticate a local research identity and keep your investigations scoped to you.</p>
          <form onSubmit={submit} className="auth-form">
            <label htmlFor="username"><span className="eyebrow">Username</span><input id="username" value={username} onChange={(event) => setUsername(event.target.value)} pattern="[A-Za-z0-9_.-]+" maxLength={128} autoComplete="username" required placeholder="e.g. researcher" /></label>
            <button className="button button-primary" type="submit" disabled={busy || !username.trim()}>{busy ? <LoaderCircle className="spin" size={14} /> : <KeyRound size={14} />} Continue with username</button>
          </form>
          {error && <div className="inline-error" role="alert"><ShieldCheck size={15} />{error}</div>}
          <small className="muted-copy">The backend issues a bearer session after username authentication. No password, email, or browser identity is used.</small>
        </section>
        <aside className="auth-notes" aria-label="Instrument notes">
          <div className="eyebrow">Anvikshiki / प्रवेश</div>
          <p>Enter a workspace for questions, sources, evidence, and carefully held conclusions.</p>
          <div className="auth-note-list"><span><i />Research runs</span><span><i />Provenance trails</span><span><i />Epistemic memory</span></div>
          <small>Session state remains local to this browser.</small>
        </aside>
      </div>
    </main>
  );
}
