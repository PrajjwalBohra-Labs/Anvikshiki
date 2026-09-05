import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CommandPalette } from './CommandPalette';

describe('command palette', () => {
  afterEach(() => cleanup());
  it('filters commands and executes a selected route', () => {
    const close = () => undefined;
    render(<CommandPalette open onClose={close} />);
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Inquiry commands');
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'graph' } });
    expect(screen.getByRole('option', { name: /explore knowledge graph/i })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /open source library/i })).not.toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' });
    expect(window.location.pathname).toBe('/knowledge-graph');
  });

  it('reports no results and closes with Escape', () => {
    const close = vi.fn();
    render(<CommandPalette open onClose={close} />);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'does-not-exist' } });
    expect(screen.getByRole('status')).toHaveTextContent('No commands match');
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(close).toHaveBeenCalled();
  });
});
