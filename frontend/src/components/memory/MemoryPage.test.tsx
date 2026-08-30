import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryPage } from './MemoryPage';

const api = vi.hoisted(() => ({
  getEpistemicPositions: vi.fn(),
  createEpistemicPosition: vi.fn(),
  updateEpistemicPositionStatus: vi.fn(),
}));
vi.mock('../../api/services', () => api);
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const position = {
  position_id: 'position-1',
  claim_statement: 'Perception requires valid epistemic conditions.',
  position: 'I currently hold this as a tentative position.',
  confidence: 0.7,
  status: 'tentative',
  supporting_evidence: [{ text: 'A returned passage supports the question.' }],
  counterarguments: [{ text: 'Illusory perception remains a challenge.' }],
  updated_at: '2026-08-30T10:00:00Z',
  history: [{ previous_status: 'accepted', new_status: 'tentative', change_reason: 'New counterargument', timestamp: '2026-08-29T10:00:00Z' }],
};

describe('memory and understanding view', () => {
  it('loads an authenticated user position with context and history visible', async () => {
    api.getEpistemicPositions.mockResolvedValue([position]);
    render(<MemoryPage userId="user-1" />);

    await waitFor(() => expect(screen.getByText(position.claim_statement)).toBeInTheDocument());
    expect(api.getEpistemicPositions).toHaveBeenCalledWith('user-1');
    expect(screen.getByText('A returned passage supports the question.')).toBeInTheDocument();
    expect(screen.getByText('Illusory perception remains a challenge.')).toBeInTheDocument();
    expect(screen.getByText('Status history')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Confidence 70 percent' })).toHaveAttribute('aria-valuenow', '70');
  });

  it('records a position with the authenticated owner supplied by the app', async () => {
    api.getEpistemicPositions.mockResolvedValue([]);
    api.createEpistemicPosition.mockResolvedValue({ ...position, position_id: 'position-2', claim_statement: 'A newly recorded claim.' });
    render(<MemoryPage userId="user-2" />);

    fireEvent.click(await screen.findByRole('button', { name: /Record position/ }));
    fireEvent.change(screen.getByLabelText('Claim or question'), { target: { value: 'A newly recorded claim.' } });
    fireEvent.change(screen.getByLabelText('Your position'), { target: { value: 'This is currently unresolved.' } });
    fireEvent.click(screen.getByRole('button', { name: /Save position/ }));

    await waitFor(() => expect(api.createEpistemicPosition).toHaveBeenCalledWith(expect.objectContaining({ user_id: 'user-2', claim_statement: 'A newly recorded claim.', position: 'This is currently unresolved.', confidence: 0.7, status: 'tentative' })));
    expect(await screen.findByText('Understanding position recorded.')).toBeInTheDocument();
  });

  it('updates status through the existing ownership-checked endpoint', async () => {
    api.getEpistemicPositions.mockResolvedValue([position]);
    api.updateEpistemicPositionStatus.mockResolvedValue({ ...position, status: 'contested' });
    render(<MemoryPage userId="user-3" />);

    await screen.findByText(position.claim_statement);
    fireEvent.click(screen.getByRole('button', { name: 'Update status' }));
    fireEvent.change(screen.getByLabelText('New status'), { target: { value: 'contested' } });
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: 'Counterargument requires review.' } });
    fireEvent.click(screen.getByRole('button', { name: /Save status/ }));

    await waitFor(() => expect(api.updateEpistemicPositionStatus).toHaveBeenCalledWith('position-1', { new_status: 'contested', change_reason: 'Counterargument requires review.' }));
    expect(await screen.findByText('Understanding status updated.')).toBeInTheDocument();
  });

  it('shows an empty state without fabricating memory', async () => {
    api.getEpistemicPositions.mockResolvedValue([]);
    render(<MemoryPage userId="user-empty" />);
    expect(await screen.findByText('No epistemic positions are currently recorded for this user.')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Other memory tiers remain unavailable here because no corresponding frontend API contract exists.');
  });
});
