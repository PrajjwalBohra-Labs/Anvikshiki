import React from 'react';
import './styles/tokens.css';

export const App: React.FC = () => {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem'
    }}>
      <div style={{
        maxWidth: '680px',
        width: '100%',
        backgroundColor: 'var(--surface-1)',
        border: '1px solid var(--border-warm)',
        borderRadius: '6px',
        padding: '2.5rem',
        boxShadow: 'var(--glow-warm)'
      }}>
        <div style={{
          display: 'inline-block',
          fontSize: '12px',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.15em',
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
          marginBottom: '1rem'
        }}>
          Research Instrument
        </div>
        <h1 style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '2rem',
          margin: '0 0 0.5rem 0',
          color: 'var(--text-secondary)',
          fontWeight: 600,
          letterSpacing: '-0.02em'
        }}>
          ANVĪKṢIKĪ
        </h1>
        <p style={{
          fontSize: '1rem',
          lineHeight: '1.6',
          color: 'var(--text-primary)',
          marginBottom: '2rem'
        }}>
          An environment for inquiry, dialectical reasoning, and evidence verification across philosophical traditions and empirical methodologies.
        </p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1rem',
          marginTop: '1.5rem',
          borderTop: '1px solid var(--border-subtle)',
          paddingTop: '1.5rem'
        }}>
          <div style={{ padding: '0.75rem', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-subtle)', borderRadius: '4px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>PALETTE</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>Ink Black / Aged Bronze</div>
          </div>
          <div style={{ padding: '0.75rem', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-cool)', borderRadius: '4px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>REASONING</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>Socratic / Evidence-Linked</div>
          </div>
          <div style={{ padding: '0.75rem', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border-hypothesis)', borderRadius: '4px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>SECURITY</div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>MCP Boundary Active</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;