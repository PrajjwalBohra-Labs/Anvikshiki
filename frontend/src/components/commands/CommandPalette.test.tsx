import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CommandPalette } from './CommandPalette';

afterEach(cleanup);

const commands = [
  { id: 'research', label: 'Research', keywords: ['inquiry'], path: '/research', icon: (() => null) as never, execute: vi.fn() },
  { id: 'notebook', label: 'Notebook', keywords: ['notes'], path: '/notebook', icon: (() => null) as never, execute: vi.fn() },
];

describe('command palette', () => {
  it('opens with dialog semantics, filters, navigates by keyboard, and closes on escape', () => {
    const onClose = vi.fn();
    render(<CommandPalette isOpen onClose={onClose} commands={commands} />);
    const input = screen.getByRole('combobox', { name: 'Search commands' });
    expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(2);
    fireEvent.change(input, { target: { value: 'notes' } });
    expect(screen.getByRole('option', { name: 'Notebook' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(commands[1].execute).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('reports no results and closes on escape', () => {
    const onClose = vi.fn();
    render(<CommandPalette isOpen onClose={onClose} commands={commands} />);
    const input = screen.getByRole('combobox', { name: 'Search commands' });
    fireEvent.change(input, { target: { value: 'missing' } });
    expect(screen.getByRole('status')).toHaveTextContent('No matching commands.');
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
