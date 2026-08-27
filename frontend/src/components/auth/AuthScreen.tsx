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
      <section className="auth-card">
        <div className="brand-mark" aria-hidden="true">A</div>
        <div className="eyebrow">Anvikshiki / Local research instrument</div>
        <h1>Begin with a research identity.</h1>
        <p className="page-lede">Create a local session to keep your investigations, evidence trails, and epistemic context scoped to you.</p>
        <form onSubmit={submit} className="auth-form">
          <label htmlFor="username"><span className="eyebrow">Username</span><input id="username" value={username} onChange={(event) => setUsername(event.target.value)} pattern="[A-Za-z0-9_.-]+" maxLength={128} autoComplete="username" required placeholder="e.g. researcher" /></label>
          <button className="button button-primary" type="submit" disabled={busy || !username.trim()}>{busy ? <LoaderCircle className="spin" size={14} /> : <KeyRound size={14} />} Create local session</button>
        </form>
        {error && <div className="inline-error" role="alert"><ShieldCheck size={15} />{error}</div>}
        <small className="muted-copy">The backend issues a bearer session after registration. No password or token is displayed here.</small>
      </section>
    </main>
  );
}
