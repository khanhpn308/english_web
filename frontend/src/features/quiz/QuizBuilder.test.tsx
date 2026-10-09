import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QuizBuilder } from './QuizBuilder';
import { AiConsentProvider } from '@/features/consent/AiConsentGate';
import * as client from '@/shared/api/client';
import { ApiError } from '@/shared/api/client';

// Mock broadcast channel if needed
if (typeof BroadcastChannel === 'undefined') {
  global.BroadcastChannel = class BroadcastChannel {
    name = '';
    onmessage = null;
    postMessage = vi.fn();
    close = vi.fn();
    constructor(name: string) { this.name = name; }
  } as any;
}

const mockApiClient = vi.spyOn(client, 'apiClient');

const renderWithConsent = (ui: React.ReactElement) => {
  return render(
    <AiConsentProvider>
      {ui}
    </AiConsentProvider>
  );
};

describe('QuizBuilder', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockApiClient.mockImplementation(async (url: string) => {
      if (url === '/api/v1/ai-consent') {
        return {
          state: 'GRANTED',
          revision: 1,
          canRequestAi: true,
          acceptedPolicyVersion: 'test-v1',
          acceptedPolicyDigest: 'a'.repeat(64),
          lastChoiceAt: '2025-01-01T00:00:00Z',
          policy: {
            version: 'test-v1',
            digest: 'a'.repeat(64),
            disclosureText: 'Test',
            retentionStatement: 'Test',
            regionStatement: 'Test',
            costQuotaStatement: 'Test',
            withdrawalStatement: 'Test',
            dataCategories: ['TERM'],
            recipients: ['Test'],
            scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'],
            blockedReasons: [],
            dispatchRules: [
              { scope: 'LOOKUP', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' },
              { scope: 'QUIZ_GENERATION', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' },
              { scope: 'WRITING_FEEDBACK', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }
            ],
            reviewStatus: 'READY'
          },
          _etag: 'w/"test"'
        };
      }
      return {};
    });
  });

  it('rejects invalid total less than 5', async () => {
    renderWithConsent(<QuizBuilder />);
    const user = userEvent.setup();

    const mcq = screen.getByLabelText('Trắc nghiệm');
    const cloze = screen.getByLabelText('Điền từ');
    const writing = screen.getByLabelText('Tự luận');

    await user.clear(mcq); await user.type(mcq, '1');
    await user.clear(cloze); await user.type(cloze, '1');
    await user.clear(writing); await user.type(writing, '1');

    const submit = screen.getByRole('button', { name: 'Tạo bài kiểm tra' });
    await user.click(submit);

    expect(await screen.findByText('Tổng số câu hỏi phải từ 5 đến 30 câu.')).toBeInTheDocument();
    expect(mockApiClient).not.toHaveBeenCalledWith('/api/v1/quiz-attempts', expect.anything());
  });

  it('rejects count > 20 for a single type', async () => {
    renderWithConsent(<QuizBuilder />);
    const user = userEvent.setup();

    const mcq = screen.getByLabelText('Trắc nghiệm');
    const cloze = screen.getByLabelText('Điền từ');
    const writing = screen.getByLabelText('Tự luận');

    await user.clear(mcq); await user.type(mcq, '21');
    await user.clear(cloze); await user.type(cloze, '0');
    await user.clear(writing); await user.type(writing, '0');

    const submit = screen.getByRole('button', { name: 'Tạo bài kiểm tra' });
    await user.click(submit);

    expect(await screen.findByText(/Số lượng câu hỏi mỗi loại phải là số nguyên từ 0 đến 20/i)).toBeInTheDocument();
  });

  it('submits successfully with valid counts and navigates', async () => {
    const onNavigate = vi.fn();
    renderWithConsent(<QuizBuilder onNavigate={onNavigate} />);
    const user = userEvent.setup();

    mockApiClient.mockImplementation(async (url: string) => {
      if (url === '/api/v1/ai-consent') return { /* ...mocked earlier... */ state: 'GRANTED', revision: 1, canRequestAi: true, acceptedPolicyVersion: 'test-v1', acceptedPolicyDigest: 'a'.repeat(64), lastChoiceAt: '2025-01-01T00:00:00Z', policy: { version: 'test-v1', digest: 'a'.repeat(64), disclosureText: 'Test', retentionStatement: 'Test', regionStatement: 'Test', costQuotaStatement: 'Test', withdrawalStatement: 'Test', dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'], recipients: ['Test'], scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [], dispatchRules: [{ scope: 'LOOKUP', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }, { scope: 'QUIZ_GENERATION', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }, { scope: 'WRITING_FEEDBACK', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }], reviewStatus: 'READY' }, _etag: 'w/"1"' };
      if (url === '/api/v1/quiz-attempts') return { id: 'test-attempt-123' };
      return {};
    });

    const mcq = screen.getByLabelText('Trắc nghiệm');
    const cloze = screen.getByLabelText('Điền từ');
    const writing = screen.getByLabelText('Tự luận');

    await user.clear(mcq); await user.type(mcq, '2');
    await user.clear(cloze); await user.type(cloze, '2');
    await user.clear(writing); await user.type(writing, '1');

    const submit = screen.getByRole('button', { name: 'Tạo bài kiểm tra' });
    await user.click(submit);

    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith('/api/v1/quiz-attempts', expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('{"counts":{"mcq":2,"cloze":2,"writing":1}')
      }));
    });

    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalledWith('/quiz/test-attempt-123');
    });
  });

  it('handles API errors correctly', async () => {
    renderWithConsent(<QuizBuilder />);
    const user = userEvent.setup();

    mockApiClient.mockImplementation(async (url: string) => {
      if (url === '/api/v1/ai-consent') return { state: 'GRANTED', revision: 1, canRequestAi: true, acceptedPolicyVersion: 'test-v1', acceptedPolicyDigest: 'a'.repeat(64), lastChoiceAt: '2025-01-01T00:00:00Z', policy: { version: 'test-v1', digest: 'a'.repeat(64), disclosureText: 'Test', retentionStatement: 'Test', regionStatement: 'Test', costQuotaStatement: 'Test', withdrawalStatement: 'Test', dataCategories: ['TERM', 'WORD_FORMS', 'WRITING_ANSWER'], recipients: ['Test'], scopes: ['LOOKUP', 'QUIZ_GENERATION', 'WRITING_FEEDBACK'], blockedReasons: [], dispatchRules: [{ scope: 'LOOKUP', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }, { scope: 'QUIZ_GENERATION', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }, { scope: 'WRITING_FEEDBACK', providerLabel: 'Antigravity/Google', modelId: 'gemini-3.8-flash-high', route: 'primary', billingMode: 'configured-account' }], reviewStatus: 'READY' }, _etag: 'w/"1"' };
      if (url === '/api/v1/quiz-attempts') {
        throw new ApiError(400, { code: 'VALIDATION_ERROR', message: 'Not enough words', requestId: 'req_test' });
      }
      return {};
    });

    const submit = screen.getByRole('button', { name: 'Tạo bài kiểm tra' });
    await user.click(submit);

    expect(await screen.findByText('Dữ liệu không hợp lệ. Vui lòng kiểm tra lại số lượng hoặc ngày học. Có thể nguồn từ vựng chưa đủ.')).toBeInTheDocument();
  });
});
