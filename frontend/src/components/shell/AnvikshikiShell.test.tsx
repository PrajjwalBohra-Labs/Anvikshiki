import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnvikshikiShell } from './AnvikshikiShell';

const navigate = vi.hoisted(() => vi.fn());
vi.mock('../../routing', () => ({ navigate }));

afterEach(() => {
  cleanup();
  navigate.mockReset();
});

describe('workspace mode shell', () => {
  it('shows the active mode and only that mode navigation group', () => {
    render(<AnvikshikiShell activeView="knowledge-graph" onViewChange={vi.fn()} userName="reader" onLogout={vi.fn()}><p>Graph</p></AnvikshikiShell>);

    expect(screen.getByRole('tab', { name: /Knowledge: Memory, graph, notebook, and dialogue/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /Investigation:/i })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByRole('button', { name: 'Notebook' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Research' })).not.toBeInTheDocument();
  });

  it('navigates to an existing default route when a mode is selected', () => {
    render(<AnvikshikiShell activeView="inquiry" onViewChange={vi.fn()} userName="reader" onLogout={vi.fn()}><p>Research</p></AnvikshikiShell>);

    fireEvent.click(screen.getByRole('tab', { name: /Knowledge:/i }));
    expect(navigate).toHaveBeenCalledWith('/memory');
  });

  it('supports arrow-key mode switching through the tablist', () => {
    render(<AnvikshikiShell activeView="inquiry" onViewChange={vi.fn()} userName="reader" onLogout={vi.fn()}><p>Research</p></AnvikshikiShell>);

    fireEvent.keyDown(screen.getByRole('tab', { name: /Investigation:/i }), { key: 'ArrowRight' });
    expect(navigate).toHaveBeenCalledWith('/library/sources');
  });
});
