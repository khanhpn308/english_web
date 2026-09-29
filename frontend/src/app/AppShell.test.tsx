import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  AppShell,
  ErrorBoundary,
  matchRoute,
  V1_ROUTES,
} from './AppShell';

describe('AppShell - Landmarks & Core Structure', () => {
  it('renders required landmark elements: header, nav, main, and skip link', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/" />);

    // Skip link must exist and target #main-content
    expect(html).toContain('href="#main-content"');
    expect(html).toContain('Chuyển đến nội dung chính');

    // Landmarks
    expect(html).toContain('<header');
    expect(html).toContain('</header>');
    expect(html).toContain('<nav');
    expect(html).toContain('aria-label="Điều hướng chính"');
    expect(html).toContain('</nav>');
    expect(html).toContain('<main id="main-content"');
    expect(html).toContain('</main>');
  });

  it('marks current navigation item with aria-current="page"', () => {
    const dashboardHtml = renderToStaticMarkup(<AppShell currentPath="/" />);
    expect(dashboardHtml).toMatch(/href="\/"[^>]*aria-current="page"/);

    const lookupHtml = renderToStaticMarkup(<AppShell currentPath="/lookup" />);
    expect(lookupHtml).toMatch(/href="\/lookup"[^>]*aria-current="page"/);
    expect(lookupHtml).not.toMatch(/href="\/"[^>]*aria-current="page"/);

    const reviewHtml = renderToStaticMarkup(<AppShell currentPath="/review" />);
    expect(reviewHtml).toMatch(/href="\/review"[^>]*aria-current="page"/);
    expect(reviewHtml).not.toMatch(/href="\/lookup"[^>]*aria-current="page"/);
  });

  it('contains accessible link to AI consent and status in the shell', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/" />);
    expect(html).toContain('href="/status#ai-consent"');
    expect(html).toContain('Quyền gửi dữ liệu AI');
  });
});

describe('Route Map & v1 Screens', () => {
  it.each([
    ['/', 'Tổng quan'],
    ['/lookup', 'Tra cứu từ vựng'],
    ['/search', 'Tìm kiếm từ vựng'],
    ['/word-forms/wf-123', 'Chi tiết từ vựng'],
    ['/review', 'Ôn tập flashcard'],
    ['/quiz/new', 'Tạo bài kiểm tra'],
    ['/quiz/att-456', 'Làm bài kiểm tra'],
    ['/quiz/att-456/result', 'Kết quả kiểm tra'],
    ['/status', 'Trạng thái hệ thống &amp; Quyền AI'],
  ])('renders route %s with heading %s and screen h1', (path, headingText) => {
    const html = renderToStaticMarkup(<AppShell currentPath={path} />);
    expect(html).toContain(`<h1`);
    expect(html).toContain(headingText);
    // Unimplemented routes indicate availability clearly without fabricated data
    expect(html).toContain('Tính năng đang được xây dựng (chưa khả dụng)');
  });

  it('renders accessible 404 screen when route is not found', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/non-existent-page" />);
    expect(html).toContain('Không tìm thấy trang');
    expect(html).toContain('href="/"');
    expect(html).toContain('Quay lại trang chủ');
  });

  it('extracts dynamic route parameters accurately', () => {
    const matchWf = matchRoute('/word-forms/form-abc-999');
    expect(matchWf).not.toBeNull();
    expect(matchWf?.routeId).toBe('word-form-detail');
    expect(matchWf?.params).toEqual({ wordFormId: 'form-abc-999' });

    const matchQuiz = matchRoute('/quiz/attempt-001');
    expect(matchQuiz).not.toBeNull();
    expect(matchQuiz?.routeId).toBe('quiz-runner');
    expect(matchQuiz?.params).toEqual({ attemptId: 'attempt-001' });

    const matchResult = matchRoute('/quiz/attempt-001/result');
    expect(matchResult).not.toBeNull();
    expect(matchResult?.routeId).toBe('quiz-result');
    expect(matchResult?.params).toEqual({ attemptId: 'attempt-001' });
  });

  it('defines all 9 normative v1 routes in route catalog', () => {
    expect(Object.keys(V1_ROUTES)).toHaveLength(9);
    expect(V1_ROUTES).toHaveProperty('dashboard');
    expect(V1_ROUTES).toHaveProperty('lookup');
    expect(V1_ROUTES).toHaveProperty('search');
    expect(V1_ROUTES).toHaveProperty('wordFormDetail');
    expect(V1_ROUTES).toHaveProperty('review');
    expect(V1_ROUTES).toHaveProperty('quizBuilder');
    expect(V1_ROUTES).toHaveProperty('quizRunner');
    expect(V1_ROUTES).toHaveProperty('quizResult');
    expect(V1_ROUTES).toHaveProperty('status');
  });
});

describe('ErrorBoundary & Edge Cases', () => {
  it('renders fallback recovery UI when an error state is captured', () => {
    const boundary = new ErrorBoundary({ children: <div>child</div> });
    const derivedState = ErrorBoundary.getDerivedStateFromError(
      new Error('Đã xảy ra lỗi thử nghiệm trong màn hình')
    );
    expect(derivedState.hasError).toBe(true);
    expect(derivedState.errorMessage).toBe('Đã xảy ra lỗi thử nghiệm trong màn hình');

    boundary.state = derivedState;
    const html = renderToStaticMarkup(boundary.render() as React.ReactElement);

    expect(html).toContain('Đã xảy ra lỗi không mong muốn');
    expect(html).toContain('Đã xảy ra lỗi thử nghiệm trong màn hình');
    expect(html).toContain('href="/status"');
    expect(html).toContain('Kiểm tra trạng thái hệ thống');
    expect(html).toContain('Thử lại màn hình này');
  });

  it('renders long Vietnamese labels properly without breaking markup', () => {
    const longTextRoute = '/status';
    const html = renderToStaticMarkup(<AppShell currentPath={longTextRoute} />);
    expect(html).toContain('Trạng thái hệ thống &amp; Quyền AI');
    expect(html).toContain('Chuyển đến nội dung chính');
  });
});
