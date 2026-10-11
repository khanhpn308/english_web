// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QuizRunner } from './QuizRunner';
import { apiClient, ApiError, MutationUnknownError } from '@/shared/api/client';
import type { components } from '@/shared/api/generated';

vi.mock('@/shared/api/client', async importOriginal => {
  const real = await importOriginal<typeof import('@/shared/api/client')>();
  return { ...real, apiClient: vi.fn() };
});

type QuizAttempt = components['schemas']['QuizAttempt'];
type Answer = components['schemas']['Answer'];
const client = vi.mocked(apiClient);
const etag = (digit: string) => '"qa-v1-' + digit.repeat(64) + '"';
let serial = 0;
const attempt = (options: {
  answer?: string;
  score?: number | null;
  revision?: number;
  status?: 'IN_PROGRESS' | 'SUBMITTED';
} = {}): QuizAttempt => {
  const revision = options.revision ?? 0;
  const answer = options.answer ?? '';
  return {
    id: 'att-123',
    noteDate: '2026-10-11',
    status: options.status ?? 'IN_PROGRESS',
    savedAnswerCount: revision > 0 ? 1 : 0,
    snapshotRevision: 1,
    submissionRevision: 0,
    result: null,
    questions: [
      { id: 'q1', wordFormId: 'wf1', type: 'MCQ', promptEn: 'MCQ Prompt', options: [
        { id: 'opt1', textEn: 'Opt 1' }, { id: 'opt2', textEn: 'Opt 2' },
      ] },
      { id: 'q2', wordFormId: 'wf2', type: 'CLOZE', promptEn: 'CLOZE Prompt',
        answerPolicyVersion: 'cloze-answer-v1' },
      { id: 'q3', wordFormId: 'wf3', type: 'WRITING', promptEn: 'WRITING Prompt',
        targetLemma: 'apple', rubricVersion: 'writing-rubric-v1',
        rubric: { descriptors: [0, 1, 2, 3, 4].map(score => ({ score, textVi: 'Mức ' + score })) } },
    ],
    answerPreconditions: ['q1', 'q2', 'q3'].map(questionId => ({
      questionId, draftRevision: questionId === 'q2' ? revision : 0,
      etag: etag(questionId === 'q2' ? String(revision + 1) : '1'),
    })),
    answers: revision ? [{
      questionId: 'q2', attemptId: 'att-123', answer, selfScore: options.score ?? null,
      draftRevision: revision, savedAt: '2026-10-11T00:00:00Z',
      operationId: 'op1', state: 'DRAFT',
    }] : [],
  } as QuizAttempt;
};

const receipt = (revision: number, answer: string, score: number | null = null): Answer & { _etag: string } => ({
  questionId: 'q2',
  attemptId: 'att-123',
  answer,
  selfScore: score,
  draftRevision: revision,
  state: 'DRAFT',
  savedAt: '2026-10-11T00:00:00Z',
  operationId: 'operation-' + revision,
  _etag: etag(String(revision + 1)),
});

const loaded = async () => {
  render(<QuizRunner attemptId="att-123" />);
  await screen.findByText('CLOZE Prompt');
};

const putCalls = () => client.mock.calls.filter(([, options]) => options?.method === 'PUT');

beforeEach(() => {
  serial = 0;
  vi.stubGlobal('crypto', { randomUUID: () => 'key-' + (++serial) });
  client.mockReset();
  client.mockResolvedValue(attempt() as never);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('T050 QuizRunner', () => {
  it('restores the three answer types and disables submitted inputs', async () => {
    await loaded();
    expect(screen.getByText('MCQ Prompt')).toBeInTheDocument();
    expect(screen.getByText('Viết câu chứa "apple":')).toBeInTheDocument();
    expect(screen.getByLabelText('Điểm 4')).toBeEnabled();
    expect(screen.getByRole('button', { name: /Nộp bài/ })).toBeDisabled();
  });

  it('sends a PUT at 500ms, not before; blur flushes immediately', async () => {
    client.mockResolvedValueOnce(attempt() as never);
    client.mockResolvedValueOnce(receipt(1, 'first') as never);
    client.mockResolvedValueOnce(receipt(2, 'second') as never);
    await loaded();
    vi.useFakeTimers();
    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'first' } });
    act(() => { vi.advanceTimersByTime(499); });
    expect(putCalls()).toHaveLength(0);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(putCalls()).toHaveLength(1);
    expect(JSON.parse(putCalls()[0][1]?.body as string)).toEqual({
      answer: 'first', selfScore: null, draftRevision: 0,
    });
    expect(screen.getByText('Đã lưu')).toBeInTheDocument();
    fireEvent.change(input, { target: { value: 'second' } });
    fireEvent.blur(input);
    await act(async () => {});
    expect(putCalls()).toHaveLength(2);
    expect(putCalls()[1][1]?.headers).toMatchObject({ 'If-Match': etag('2') });
    expect(screen.getByText('Đã lưu')).toBeInTheDocument();
  });

  it('never shows saved before durable receipt and sends newest edit after an in-flight PUT', async () => {
    client.mockResolvedValueOnce(attempt() as never);
    let resolveFirst: (value: Answer & { _etag: string }) => void = () => {};
    client.mockImplementationOnce(() => new Promise<never>(resolve => {
      resolveFirst = value => resolve(value as never);
    }));
    client.mockResolvedValueOnce(receipt(2, 'new') as never);
    await loaded();
    vi.useFakeTimers();
    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'old' } });
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(screen.queryByText('Đã lưu')).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: 'new' } });
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(putCalls()).toHaveLength(1);
    await act(async () => { resolveFirst(receipt(1, 'old')); });
    expect(putCalls()).toHaveLength(2);
    expect(JSON.parse(putCalls()[1][1]?.body as string)).toEqual({
      answer: 'new', selfScore: null, draftRevision: 1,
    });
    expect(putCalls()[1][1]?.headers).toMatchObject({ 'If-Match': etag('2') });
    expect(input).toHaveValue('new');
    expect(screen.getByText('Đã lưu')).toBeInTheDocument();
  });

  it('reconciles an unknown receipt before replaying the exact original intent', async () => {
    client.mockResolvedValueOnce(attempt() as never);
    client.mockRejectedValueOnce(new MutationUnknownError('lost ack', 'PUT', '/answers/q2', 'key-1'));
    client.mockResolvedValueOnce(attempt() as never);
    client.mockResolvedValueOnce(receipt(1, 'draft') as never);
    await loaded();
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('Câu trả lời:'), { target: { value: 'draft' } });
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(screen.getByText('Chưa rõ kết quả lưu')).toBeInTheDocument();
    expect(putCalls()).toHaveLength(1);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra bản đã lưu' })); });
    expect(putCalls()).toHaveLength(2);
    expect(putCalls()[1][1]?.headers).toEqual(putCalls()[0][1]?.headers);
    expect(putCalls()[1][1]?.body).toEqual(putCalls()[0][1]?.body);
    expect(screen.getByText('Đã lưu')).toBeInTheDocument();
  });

  it('treats GET-confirmed unknown as saved without a second PUT', async () => {
    client.mockResolvedValueOnce(attempt() as never);
    client.mockRejectedValueOnce(new MutationUnknownError('lost ack', 'PUT', '/answers/q2', 'key-1'));
    client.mockResolvedValueOnce(attempt({ answer: 'draft', revision: 1 }) as never);
    await loaded();
    vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('Câu trả lời:'), { target: { value: 'draft' } });
    await act(async () => { vi.advanceTimersByTime(500); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra bản đã lưu' })); });
    expect(putCalls()).toHaveLength(1);
    expect(screen.getByText('Đã lưu')).toBeInTheDocument();
  });

  it('holds stale-tab revision conflicts until the user compares and chooses', async () => {
    client.mockResolvedValueOnce(attempt() as never);
    client.mockRejectedValueOnce(new ApiError(409, {
      code: 'REVISION_CONFLICT', message: 'Conflict', requestId: 'req-1',
    }));
    client.mockResolvedValueOnce(attempt({ answer: 'server', revision: 1 }) as never);
    client.mockResolvedValueOnce(receipt(2, 'mine') as never);
    await loaded();
    vi.useFakeTimers();
    const input = screen.getByLabelText('Câu trả lời:');
    fireEvent.change(input, { target: { value: 'mine' } });
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(screen.getByText(/Xung đột phiên bản/)).toBeInTheDocument();
    expect(putCalls()).toHaveLength(1);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Đọc phiên bản máy chủ' })); });
    expect(input).toHaveValue('mine');
    expect(screen.getByText(/Máy chủ: server/)).toBeInTheDocument();
    expect(putCalls()).toHaveLength(1);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Lưu bản đang nhập' })); });
    expect(putCalls()).toHaveLength(2);
    expect(putCalls()[1][1]?.headers).toMatchObject({ 'If-Match': etag('2') });
  });

  it('keeps failure visible instead of presenting an empty quiz; supports retry', async () => {
    client.mockRejectedValueOnce(new Error('offline'));
    client.mockResolvedValueOnce(attempt() as never);
    render(<QuizRunner attemptId="att-123" />);
    await screen.findByText(/Không thể tải bài kiểm tra/);
    expect(screen.queryByText('CLOZE Prompt')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    await screen.findByText('CLOZE Prompt');
  });

  it('shows submitted input as read-only on restore', async () => {
    // The terminal result is a T048 concern; only read-only controls are in T050.
    client.mockResolvedValueOnce({ ...attempt(), status: 'SUBMITTED' } as never);
    await loaded();
    expect(screen.getByLabelText('Câu trả lời:')).toBeDisabled();
    expect(screen.getByLabelText('Điểm 0')).toBeDisabled();
  });

  it('flushes pending answers before invoking the future T051 submit handler', async () => {
    const onSubmit = vi.fn(async () => {});
    client.mockResolvedValueOnce(attempt() as never);
    client.mockResolvedValueOnce(receipt(1, 'ready') as never);
    render(<QuizRunner attemptId="att-123" onSubmit={onSubmit} />);
    await screen.findByText('CLOZE Prompt');
    fireEvent.change(screen.getByLabelText('Câu trả lời:'), { target: { value: 'ready' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' }));
    });
    expect(putCalls()).toHaveLength(1);
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit).toHaveBeenCalledWith('att-123');
  });

  it('rejects submit when a draft receipt remains unresolved', async () => {
    const onSubmit = vi.fn();
    client.mockResolvedValueOnce(attempt() as never);
    client.mockImplementationOnce(() => new Promise<never>(() => {}));
    render(<QuizRunner attemptId="att-123" onSubmit={onSubmit} />);
    await screen.findByText('CLOZE Prompt');
    fireEvent.change(screen.getByLabelText('Câu trả lời:'), { target: { value: 'pending' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' }));
    });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent('Chưa thể nộp bài');
  });

  it('keeps a saved draft across a fresh mount', async () => {
    client.mockResolvedValueOnce(attempt({ answer: 'restored text', revision: 1 }) as never);
    await loaded();
    expect(screen.getByLabelText('Câu trả lời:')).toHaveValue('restored text');
    expect(putCalls()).toHaveLength(0);
  });
});
