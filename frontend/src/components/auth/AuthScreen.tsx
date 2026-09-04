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
          <div className="auth-brand"><div className="brand-mark"><img src="/anvikshiki-logo.png" alt="" /></div><div><div className="eyebrow">Private research instrument</div><strong>ANVIKSHIKI</strong></div><span className="auth-index">01 / 04</span></div>
          <div className="auth-heading"><div className="eyebrow">Local session / Entry</div><span className="auth-live"><i /> Encrypted session boundary</span></div>
          <h1>Enter with a question worth pursuing.</h1>
          <p className="page-lede">Create a local session to keep your investigations, evidence trails, and epistemic context scoped to you.</p>
          <form onSubmit={submit} className="auth-form">
            <label htmlFor="username"><span className="eyebrow">Research identity</span><input id="username" value={username} onChange={(event) => setUsername(event.target.value)} pattern="[A-Za-z0-9_.-]+" maxLength={128} autoComplete="username" required placeholder="e.g. researcher" /><small>Letters, numbers, underscore, dot, and hyphen.</small></label>
            <button className="button button-primary" type="submit" disabled={busy || !username.trim()}>{busy ? <LoaderCircle className="spin" size={14} /> : <KeyRound size={14} />} Create local session</button>
          </form>
          {error && <div className="inline-error" role="alert"><ShieldCheck size={15} />{error}</div>}
          <small className="muted-copy">The backend issues a bearer session after registration. No password or token is displayed here.</small>
        </section>
        <aside className="auth-notes" aria-label="Instrument notes">
          <div className="auth-orbit" aria-hidden="true"><span className="orbit-ring ring-a" /><span className="orbit-ring ring-b" /><img src="/anvikshiki-logo.png" alt="" /></div>
          <div className="eyebrow">Anvikshiki / प्रवेश</div>
          <p>Observe carefully.<br />Name what is known.<br /><em>Keep the question open.</em></p>
          <div className="auth-note-list"><span><b>01</b> Research runs</span><span><b>02</b> Provenance trails</span><span><b>03</b> Epistemic memory</span></div>
          <small>Session state remains local to this browser.</small>
        </aside>
      </div>
    </main>
  );
}
