// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
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

  it('preserves h2 heading semantics within CardTitle in ErrorBoundary fallback', () => {
    const boundary = new ErrorBoundary({ children: <div>child</div> });
    boundary.state = {
      hasError: true,
      errorMessage: 'Lỗi kiểm thử heading semantics',
    };
    const html = renderToStaticMarkup(boundary.render() as React.ReactElement);
    expect(html).toMatch(/<h2[^>]*>Đã xảy ra lỗi không mong muốn<\/h2>/);
  });


  it('logs diagnostic correlation context via componentDidCatch without throwing', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const boundary = new ErrorBoundary({ children: <div>child</div> });
    boundary.componentDidCatch(new Error('Thử nghiệm chẩn đoán lỗi'), {
      componentStack: '\n    in BuggyComponent\n    in ErrorBoundary',
    });
    expect(errorSpy).toHaveBeenCalledWith('[ErrorBoundary caught error]', {
      name: 'Error',
      componentStack: '\n    in BuggyComponent\n    in ErrorBoundary',
    });
    errorSpy.mockRestore();
  });

  it('renders long Vietnamese labels properly without breaking markup', () => {
    const longTextRoute = '/status';
    const html = renderToStaticMarkup(<AppShell currentPath={longTextRoute} />);
    expect(html).toContain('Trạng thái hệ thống &amp; Quyền AI');
    expect(html).toContain('Chuyển đến nội dung chính');
  });
});

describe('AppShell - Client-Side Navigation & Routing Invariants', () => {
  it('defaults to dashboard route when currentPath is omitted', () => {
    const html = renderToStaticMarkup(<AppShell />);
    expect(html).toContain('Tổng quan');
    expect(html).toMatch(/href="\/"[^>]*aria-current="page"/);
  });
});


describe('T076 Design System Integration', () => {
  it('uses T075 semantic tailwind tokens for layout', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/" />);
    expect(html).toContain('bg-background');
    expect(html).toContain('text-foreground');
    expect(html).toContain('bg-muted');
    expect(html).toContain('border-border');
  });

  it('preserves screen-view__title and feature-unavailable-note classes in rendered markup', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/" />);
    expect(html).toContain('screen-view__title');
    expect(html).toContain('feature-unavailable-note');
  });

  it('uses canonical Card primitive for placeholders with structured content and route params', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/word-forms/test-item-42" />);
    // Card primitive classes
    expect(html).toContain('bg-card');
    expect(html).toContain('text-card-foreground');
    expect(html).toContain('role="region"');
    expect(html).toContain('aria-label="Thông báo trạng thái tính năng"');
    // Content structure
    expect(html).toContain('Tính năng đang được xây dựng (chưa khả dụng)');
    expect(html).toContain('wordFormId');
    expect(html).toContain('test-item-42');
  });

  it('uses canonical Card and Button primitives for ErrorBoundary recovery actions', () => {
    const boundary = new ErrorBoundary({ children: <div>child</div> });
    boundary.state = {
      hasError: true,
      errorMessage: 'Lỗi kiểm thử ErrorBoundary primitives',
    };
    const html = renderToStaticMarkup(boundary.render() as React.ReactElement);

    // Card primitive with alert role
    expect(html).toContain('role="alert"');
    expect(html).toContain('aria-live="assertive"');
    expect(html).toContain('border-destructive');

    // Button primitives for retry and status navigation
    expect(html).toContain('Thử lại màn hình này');
    expect(html).toContain('Kiểm tra trạng thái hệ thống');
    expect(html).toMatch(/<button[^>]*>Thử lại màn hình này<\/button>/);
    expect(html).toMatch(/<a[^>]*href="\/status"[^>]*>Kiểm tra trạng thái hệ thống<\/a>/);
  });

  it('uses canonical Button primitive for 404 navigation action', () => {
    const html = renderToStaticMarkup(<AppShell currentPath="/unknown-route-probe" />);
    expect(html).toContain('Không tìm thấy trang');
    expect(html).toMatch(/<a[^>]*href="\/"[^>]*>Quay lại trang chủ<\/a>/);
  });
});

describe('AppShell - Mounted Client-Side Interactions (T076 Coverage Extension)', () => {
  let container: HTMLDivElement | null = null;
  let root: Root | null = null;
  let originalRaf: typeof window.requestAnimationFrame | undefined;
  let originalCancelRaf: typeof window.cancelAnimationFrame | undefined;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    originalRaf = window.requestAnimationFrame;
    originalCancelRaf = window.cancelAnimationFrame;
    window.requestAnimationFrame = (callback: FrameRequestCallback): number => {
      return window.setTimeout(() => callback(performance.now()), 0);
    };
    window.cancelAnimationFrame = (id: number): void => {
      window.clearTimeout(id);
    };
  });

  afterEach(async () => {
    const currentRoot = root;
    if (currentRoot) {
      await act(async () => {
        currentRoot.unmount();
      });
      root = null;
    }
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
      container = null;
    }
    window.requestAnimationFrame = originalRaf!;
    window.cancelAnimationFrame = originalCancelRaf!;
    window.history.pushState(null, '', '/');
  });

  it('navigates from /lookup to / via real brand anchor DOM interaction and focuses heading (AppShell:270)', async () => {
    window.history.pushState(null, '', '/lookup');

    await act(async () => {
      root!.render(<AppShell />);
    });

    expect(window.location.pathname).toBe('/lookup');
    expect(container!.textContent).toContain('Tra cứu từ vựng');

    const brandAnchor = container!.querySelector<HTMLAnchorElement>('header a[href="/"]');
    expect(brandAnchor).not.toBeNull();

    await act(async () => {
      brandAnchor!.click();
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(window.location.pathname).toBe('/');
    expect(container!.textContent).toContain('Tổng quan');

    const destinationHeading = container!.querySelector<HTMLHeadingElement>('#main-content h1');
    expect(destinationHeading).not.toBeNull();
    expect(document.activeElement).toBe(destinationHeading);
  });

  it('navigates from invalid path to / via real 404 recovery action DOM interaction and focuses heading (AppShell:346)', async () => {
    window.history.pushState(null, '', '/unknown-broken-path-probe');

    await act(async () => {
      root!.render(<AppShell />);
    });

    expect(window.location.pathname).toBe('/unknown-broken-path-probe');
    expect(container!.textContent).toContain('Không tìm thấy trang');

    const recoveryAnchor = container!.querySelector<HTMLAnchorElement>('main a[href="/"]');
    expect(recoveryAnchor).not.toBeNull();
    expect(recoveryAnchor!.textContent).toContain('Quay lại trang chủ');

    await act(async () => {
      recoveryAnchor!.click();
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(window.location.pathname).toBe('/');
    expect(container!.textContent).toContain('Tổng quan');

    const destinationHeading = container!.querySelector<HTMLHeadingElement>('#main-content h1');
    expect(destinationHeading).not.toBeNull();
    expect(document.activeElement).toBe(destinationHeading);
  });
});
