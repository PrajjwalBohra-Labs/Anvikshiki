import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { NotebookPage } from './NotebookPage';

const api = vi.hoisted(() => ({
  createNotebook: vi.fn(),
  deleteNotebook: vi.fn(),
  getNotebook: vi.fn(),
  listNotebooks: vi.fn(),
  updateNotebook: vi.fn(),
}));
vi.mock('../../api/services', () => api);
vi.mock('../../routing', () => ({ navigate: vi.fn() }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const notebook = {
  notebook_id: 'notebook-1', title: 'Research notes', content: '# Observation',
  created_at: '2026-08-31T10:00:00Z', updated_at: '2026-08-31T10:00:00Z',
};

describe('notebook page', () => {
  it('renders an empty owned-notebook index without fabricating content', async () => {
    api.listNotebooks.mockResolvedValue([]);
    render(<NotebookPage />);
    expect(await screen.findByText('No notebooks yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /New notebook/ })).toBeInTheDocument();
  });

  it('creates a notebook through the authenticated service', async () => {
    api.listNotebooks.mockResolvedValue([]);
    api.createNotebook.mockResolvedValue(notebook);
    render(<NotebookPage />);
    await screen.findByText('No notebooks yet');
    fireEvent.click(screen.getByRole('button', { name: /New notebook/ }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Research notes' } });
    fireEvent.change(screen.getByLabelText('Notes'), { target: { value: '# Observation' } });
    fireEvent.click(screen.getByRole('button', { name: /Create notebook/ }));
    await waitFor(() => expect(api.createNotebook).toHaveBeenCalledWith({ title: 'Research notes', content: '# Observation' }));
  });

  it('loads, edits, and saves a deep-linked notebook as text', async () => {
    api.getNotebook.mockResolvedValue(notebook);
    api.updateNotebook.mockResolvedValue({ ...notebook, title: 'Edited notes', content: 'Updated text' });
    render(<NotebookPage notebookId="notebook-1" />);
    expect(await screen.findByDisplayValue('Research notes')).toBeInTheDocument();
    expect(screen.getByDisplayValue('# Observation')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Edited notes' } });
    fireEvent.change(screen.getByLabelText('Notes'), { target: { value: 'Updated text' } });
    fireEvent.click(screen.getByRole('button', { name: /Save notebook/ }));
    await waitFor(() => expect(api.updateNotebook).toHaveBeenCalledWith('notebook-1', { title: 'Edited notes', content: 'Updated text' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Notebook saved.');
  });

  it('sanitizes unavailable notebook errors', async () => {
    api.getNotebook.mockRejectedValue(new ApiError(404, 'private database details'));
    render(<NotebookPage notebookId="foreign" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('This notebook is unavailable to the current session.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('private database details');
  });
});
