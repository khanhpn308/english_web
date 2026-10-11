import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QuizRunner } from './QuizRunner';
import { apiClient, ApiError, MutationUnknownError } from '@/shared/api/client';
import React from 'react';

jest.mock('@/shared/api/client', () => ({
  apiClient: jest.fn(),
  ApiError: class ApiError extends Error {
    code: string;
    constructor(status: number, payload: any) {
      super(payload.message);
      this.code = payload.code;
    }
  },
  MutationUnknownError: class MutationUnknownError extends Error {
    constructor() { super('Unknown error'); }
  },
}));

const mockApiClient = apiClient as jest.MockedFunction<typeof apiClient>;

describe('QuizRunner', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockApiClient.mockClear();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const mockAttempt = (status: 'IN_PROGRESS' | 'SUBMITTED' = 'IN_PROGRESS') => ({
    id: 'att-123',
    status,
    questions: [
      { id: 'q1', type: 'MCQ', promptEn: 'MCQ Prompt', options: [{ id: 'opt1', textEn: 'Opt 1' }, { id: 'opt2', textEn: 'Opt 2' }] },
      { id: 'q2', type: 'CLOZE', promptEn: 'CLOZE Prompt' },
      { id: 'q3', type: 'WRITING', promptEn: 'WRITING Prompt', targetLemma: 'apple', rubric: { descriptors: [{ score: 0, textVi: 'Không' }, { score: 1, textVi: 'Một' }] } }
    ],
    answerPreconditions: [
      { questionId: 'q1', draftRevision: 1, etag: 'etag-q1-1' },
      { questionId: 'q2', draftRevision: 1, etag: 'etag-q2-1' },
      { questionId: 'q3', draftRevision: 1, etag: 'etag-q3-1' }
    ],
    answers: []
  });

  it('renders loading state then all question types', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt());
    render(<QuizRunner attemptId="att-123" />);
    expect(screen.getByText('Đang tải bài kiểm tra...')).toBeInTheDocument();
    
    await waitFor(() => expect(screen.getByText('MCQ Prompt')).toBeInTheDocument());
    expect(screen.getByText('CLOZE Prompt')).toBeInTheDocument();
    expect(screen.getByText('Viết câu chứa "apple":')).toBeInTheDocument();
    expect(screen.queryByText('Đang tải bài kiểm tra...')).not.toBeInTheDocument();
  });

  it('handles failed GET restore without displaying empty quiz', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('Network error'));
    render(<QuizRunner attemptId="att-123" />);
    
    await waitFor(() => expect(screen.getByText('Không thể tải bài kiểm tra. Vui lòng kiểm tra kết nối.')).toBeInTheDocument());
    expect(screen.queryByText('MCQ Prompt')).not.toBeInTheDocument();
  });

  it('debounces autosave exactly 500ms and flushes on blur', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt());
    render(<QuizRunner attemptId="att-123" />);
    await waitFor(() => expect(screen.getByText('MCQ Prompt')).toBeInTheDocument());

    const input = screen.getByLabelText('Câu trả lời:');
    
    // Type and trigger debounce
    fireEvent.change(input, { target: { value: 'test' } });
    
    expect(mockApiClient).toHaveBeenCalledTimes(1); // Only the initial GET
    
    act(() => { jest.advanceTimersByTime(499); });
    expect(mockApiClient).toHaveBeenCalledTimes(1);
    
    mockApiClient.mockResolvedValueOnce({ answer: 'test', selfScore: null, draftRevision: 2, _etag: 'etag-q2-2' });
    act(() => { jest.advanceTimersByTime(1); });
    
    expect(mockApiClient).toHaveBeenCalledTimes(2);
    expect(mockApiClient.mock.calls[1][0]).toContain('/answers/q2');
    expect(JSON.parse(mockApiClient.mock.calls[1][1]!.body as string).answer).toBe('test');
    
    // Test blur trigger
    mockApiClient.mockClear();
    fireEvent.change(input, { target: { value: 'test2' } });
    fireEvent.blur(input); // immediately triggers save
    expect(mockApiClient).toHaveBeenCalledTimes(1);
  });

  it('does not claim saved before durable receipt', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt());
    render(<QuizRunner attemptId="att-123" />);
    await waitFor(() => expect(screen.getByText('CLOZE Prompt')).toBeInTheDocument());

    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'test' } });
    
    let resolveSave: any;
    mockApiClient.mockImplementationOnce(() => new Promise(r => resolveSave = r));
    
    act(() => { jest.advanceTimersByTime(500); });
    
    // At this point it should say "Đang lưu..."
    await waitFor(() => expect(screen.getByText('Đang lưu...')).toBeInTheDocument());
    
    act(() => {
      resolveSave({ answer: 'test', selfScore: null, draftRevision: 2, _etag: 'new-etag' });
    });
    
    await waitFor(() => expect(screen.getByText('Đã lưu')).toBeInTheDocument());
  });

  it('queues concurrent edits while previous PUT is unresolved', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt());
    render(<QuizRunner attemptId="att-123" />);
    await waitFor(() => expect(screen.getByText('CLOZE Prompt')).toBeInTheDocument());

    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'test' } });
    
    let resolveSave1: any;
    mockApiClient.mockImplementationOnce(() => new Promise(r => resolveSave1 = r));
    
    act(() => { jest.advanceTimersByTime(500); });
    
    // Save 1 is in flight. Now user types more.
    fireEvent.change(input, { target: { value: 'test2' } });
    act(() => { jest.advanceTimersByTime(500); }); // Timer fires, but Save 1 still in flight
    
    expect(mockApiClient).toHaveBeenCalledTimes(2); // Initial GET, Save 1. Save 2 is queued.
    
    let resolveSave2: any;
    mockApiClient.mockImplementationOnce(() => new Promise(r => resolveSave2 = r));
    
    // Finish Save 1
    await act(async () => {
      resolveSave1({ answer: 'test', selfScore: null, draftRevision: 2, _etag: 'etag-2' });
    });
    
    // Because pending mutation was queued, Save 2 should now fire immediately.
    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(3));
    expect(mockApiClient.mock.calls[2][1]!.headers).toMatchObject({ 'If-Match': 'etag-2' });
    
    await act(async () => {
      resolveSave2({ answer: 'test2', selfScore: null, draftRevision: 3, _etag: 'etag-3' });
    });
  });

  it('preserves local draft on HTTP 409 conflict', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt());
    render(<QuizRunner attemptId="att-123" />);
    await waitFor(() => expect(screen.getByText('CLOZE Prompt')).toBeInTheDocument());

    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'test' } });
    
    mockApiClient.mockRejectedValueOnce(new (ApiError as any)(409, { code: 'REVISION_CONFLICT', message: 'Conflict' }));
    act(() => { jest.advanceTimersByTime(500); });
    
    await waitFor(() => expect(screen.getByText('Xung đột phiên bản')).toBeInTheDocument());
    
    // Tải lại
    mockApiClient.mockResolvedValueOnce({
      ...mockAttempt(),
      answers: [{ questionId: 'q2', answer: 'server', selfScore: null, draftRevision: 2, state: 'DRAFT' }],
      answerPreconditions: [{ questionId: 'q2', draftRevision: 2, etag: 'etag-q2-2' }]
    });
    
    fireEvent.click(screen.getByText('Tải lại'));
    await waitFor(() => expect(screen.queryByText('Xung đột phiên bản')).not.toBeInTheDocument());
    
    // Local answer should be preserved
    expect(input).toHaveValue('test');
    
    // Save is queued again automatically due to difference
    mockApiClient.mockResolvedValueOnce({ answer: 'test', selfScore: null, draftRevision: 3, _etag: 'etag-q2-3' });
    act(() => { jest.advanceTimersByTime(500); });
    await waitFor(() => expect(screen.getByText('Đã lưu')).toBeInTheDocument());
  });

  it('submitted attempts are read-only', async () => {
    mockApiClient.mockResolvedValueOnce(mockAttempt('SUBMITTED'));
    render(<QuizRunner attemptId="att-123" />);
    await waitFor(() => expect(screen.getByText('CLOZE Prompt')).toBeInTheDocument());

    const input = screen.getByLabelText('Câu trả lời:');
    expect(input).toBeDisabled();
    
    const radio = screen.getByLabelText('Điểm 0');
    expect(radio).toBeDisabled();
  });
});
