import React, { Component, useEffect, useState, type ErrorInfo, type ReactNode } from 'react';
import './shell.css';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { AiConsentProvider } from '@/features/consent/AiConsentGate';
import { AiConsentPanel } from '@/features/consent/AiConsentPanel';
import { LookupPage } from '@/features/lookup/LookupPage';


export interface RouteMatch {
  routeId: string;
  pattern: string;
  params: Record<string, string>;
  title: string;
}

export interface RouteDefinition {
  id: string;
  pattern: RegExp;
  title: string;
  navKey?: string;
  extractParams?: (matches: RegExpMatchArray) => Record<string, string>;
}

export const V1_ROUTES: Record<string, RouteDefinition> = {
  dashboard: {
    id: 'dashboard',
    pattern: /^\/$/,
    title: 'Tổng quan',
    navKey: 'dashboard',
  },
  lookup: {
    id: 'lookup',
    pattern: /^\/lookup$/,
    title: 'Tra cứu từ vựng',
    navKey: 'lookup',
  },
  search: {
    id: 'search',
    pattern: /^\/search$/,
    title: 'Tìm kiếm từ vựng',
    navKey: 'search',
  },
  wordFormDetail: {
    id: 'word-form-detail',
    pattern: /^\/word-forms\/([^/]+)$/,
    title: 'Chi tiết từ vựng',
    extractParams: (matches) => ({ wordFormId: matches[1] }),
  },
  review: {
    id: 'review',
    pattern: /^\/review$/,
    title: 'Ôn tập flashcard',
    navKey: 'review',
  },
  quizBuilder: {
    id: 'quiz-builder',
    pattern: /^\/quiz\/new$/,
    title: 'Tạo bài kiểm tra',
    navKey: 'quiz',
  },
  quizResult: {
    id: 'quiz-result',
    pattern: /^\/quiz\/([^/]+)\/result$/,
    title: 'Kết quả kiểm tra',
    extractParams: (matches) => ({ attemptId: matches[1] }),
  },
  quizRunner: {
    id: 'quiz-runner',
    pattern: /^\/quiz\/([^/]+)$/,
    title: 'Làm bài kiểm tra',
    extractParams: (matches) => ({ attemptId: matches[1] }),
  },
  status: {
    id: 'status',
    pattern: /^\/status$/,
    title: 'Trạng thái hệ thống & Quyền AI',
    navKey: 'status',
  },
};

export const matchRoute = (pathname: string): RouteMatch | null => {
  const normalizedPath = pathname.split('?')[0].split('#')[0] || '/';

  for (const key of Object.keys(V1_ROUTES)) {
    const route = V1_ROUTES[key];
    const match = normalizedPath.match(route.pattern);
    if (match) {
      const params = route.extractParams ? route.extractParams(match) : {};
      return {
        routeId: route.id,
        pattern: route.pattern.source,
        params,
        title: route.title,
      };
    }
  }

  return null;
};

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  errorMessage: string;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, errorMessage: '' };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || 'Lỗi không xác định',
    };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Correlation and diagnostic context only; no learning or private content logged
    if (typeof console !== 'undefined' && console.error) {
      console.error('[ErrorBoundary caught error]', {
        name: error.name,
        componentStack: errorInfo.componentStack,
      });
    }
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, errorMessage: '' });
  };

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Card className="border-destructive/50 bg-destructive/10" role="alert" aria-live="assertive">
          <CardHeader>
            <CardTitle className="text-destructive">
              <h2 className="text-xl font-semibold m-0 leading-none">Đã xảy ra lỗi không mong muốn</h2>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="font-mono bg-background/50 p-3 rounded-md text-destructive">{this.state.errorMessage}</p>
          </CardContent>
          <CardFooter className="flex flex-wrap gap-4">
            <Button onClick={this.handleRetry} variant="default" className="whitespace-normal h-auto py-2">
              Thử lại màn hình này
            </Button>
            <Button asChild variant="outline" className="whitespace-normal h-auto py-2">
              <a href="/status">Kiểm tra trạng thái hệ thống</a>
            </Button>
          </CardFooter>
        </Card>
      );
    }

    return this.props.children;
  }
}

interface NavItem {
  id: string;
  href: string;
  label: string;
  matchPrefix?: boolean;
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', href: '/', label: 'Tổng quan' },
  { id: 'lookup', href: '/lookup', label: 'Tra cứu' },
  { id: 'search', href: '/search', label: 'Tìm kiếm' },
  { id: 'review', href: '/review', label: 'Ôn tập' },
  { id: 'quiz', href: '/quiz/new', label: 'Kiểm tra', matchPrefix: true },
  { id: 'status', href: '/status', label: 'Trạng thái' },
];

function isNavActive(item: NavItem, currentPath: string): boolean {
  const cleanPath = currentPath.split('?')[0].split('#')[0] || '/';
  if (item.href === '/') {
    return cleanPath === '/';
  }
  if (item.matchPrefix) {
    return cleanPath.startsWith('/quiz');
  }
  return cleanPath === item.href;
}

export interface AppShellProps {
  currentPath?: string;
  onNavigate?: (path: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({ currentPath: propPath, onNavigate }) => {
  const [internalPath, setInternalPath] = useState<string>(() => {
    if (propPath !== undefined) {
      return propPath;
    }
    if (typeof window !== 'undefined') {
      return window.location.pathname || '/';
    }
    return '/';
  });

  const activePath = propPath !== undefined ? propPath : internalPath;

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handlePopState = () => {
      const newPath = window.location.pathname || '/';
      setInternalPath(newPath);
    };

    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (typeof window === 'undefined') {
      return;
    }

    // Allow external or hash links to behave normally
    if (href.startsWith('http') || href.startsWith('#') || href.includes('#ai-consent')) {
      return;
    }

    // Intercept client-side routing
    if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey && e.button === 0) {
      e.preventDefault();
      window.history.pushState(null, '', href);
      setInternalPath(href);
      if (onNavigate) {
        onNavigate(href);
      }

      // Route change moves focus to screen h1 per UI architecture §7
      requestAnimationFrame(() => {
        const heading = document.querySelector<HTMLHeadingElement>('#main-content h1');
        if (heading) {
          heading.focus();
        }
      });
    }
  };

  const matchedRoute = matchRoute(activePath);

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground">
      {/* Accessible skip link */}
      <a href="#main-content" className="skip-link absolute -top-[100px] left-4 z-[9999] bg-foreground text-background px-6 py-3 font-semibold rounded-md shadow-md transition-[top] duration-150 ease-out focus:top-4 focus:outline focus:outline-2 focus:outline-ring focus:outline-offset-2 no-underline">
        Chuyển đến nội dung chính
      </a>

      {/* Screen announcement live region */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {matchedRoute ? `Đang hiển thị màn hình ${matchedRoute.title}` : 'Không tìm thấy trang'}
      </div>

      <header className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center justify-between px-6 py-4 bg-background border-b border-border gap-4" role="banner">
        <div className="flex items-center">
          <a href="/" className="text-foreground font-bold text-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 rounded-sm no-underline" onClick={(e) => handleLinkClick(e, '/')}>
            <span>Học Từ Vựng Học Thuật</span>
          </a>
        </div>

        <nav className="flex items-center w-full sm:w-auto" aria-label="Điều hướng chính" role="navigation">
          <ul className="flex flex-wrap gap-2 w-full sm:w-auto m-0 p-0 list-none">
            {PRIMARY_NAV_ITEMS.map((item) => {
              const active = isNavActive(item, activePath);
              return (
                <li key={item.id} className="flex-1 sm:flex-none text-center sm:text-left">
                  <a
                    href={item.href}
                    className={cn(
                      "inline-block px-3 py-2 text-muted-foreground font-medium rounded-md border-b-2 border-transparent transition-colors hover:text-foreground hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 no-underline w-full sm:w-auto",
                      active && "text-primary font-bold border-primary bg-muted"
                    )}
                    aria-current={active ? 'page' : undefined}
                    onClick={(e) => handleLinkClick(e, item.href)}
                  >
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="flex items-center">
          <a
            href="/status#ai-consent"
            className="text-sm text-muted-foreground underline p-2 rounded-sm hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            title="Xem và quản lý quyền chia sẻ dữ liệu với AI bridge"
            onClick={(e) => handleLinkClick(e, '/status')}
          >
            Quyền gửi dữ liệu AI
          </a>
        </div>
      </header>

      <main id="main-content" className="flex-1 w-full max-w-[1200px] mx-auto p-4 sm:p-6 outline-none" tabIndex={-1} role="main">
        <ErrorBoundary>
          <AiConsentProvider>
          {matchedRoute ? (
            <article className="flex flex-col gap-6">
              <h1 className="screen-view__title m-0 text-3xl font-bold text-foreground outline-none" tabIndex={-1}>
                {matchedRoute.title}
              </h1>
              {matchedRoute.routeId === 'status' && <AiConsentPanel />}
              {matchedRoute.routeId !== 'lookup' && <Card role="region" aria-label="Thông báo trạng thái tính năng">
                <CardHeader>
                  <CardTitle className="text-primary text-lg">Tính năng đang được xây dựng (chưa khả dụng) trong giai đoạn khởi tạo shell.</CardTitle>
                </CardHeader>
                <CardContent>
                  {Object.keys(matchedRoute.params).length > 0 && (
                    <dl className="bg-muted p-4 rounded-md my-4 space-y-2">
                      {Object.entries(matchedRoute.params).map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                          <dt className="font-semibold text-muted-foreground">{key}:</dt>
                          <dd className="m-0 font-mono">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  <p className="feature-unavailable-note mb-0 text-sm text-muted-foreground">
                    Dữ liệu bài học và tính năng tương tác thực tế sẽ được nạp sau khi tích hợp API backend.
                  </p>
                </CardContent>
              </Card>}
            </article>
          ) : (
            <article className="flex flex-col gap-6 text-center py-8">
              <h1 className="screen-view__title m-0 text-3xl font-bold text-foreground outline-none" tabIndex={-1}>
                Không tìm thấy trang
              </h1>
              <p className="text-muted-foreground">Địa chỉ bạn yêu cầu không tồn tại hoặc đã được thay đổi.</p>
              <div className="mt-6">
                <Button asChild className="whitespace-normal h-auto py-2">
                  <a href="/" onClick={(e) => handleLinkClick(e, '/')}>
                    Quay lại trang chủ
                  </a>
                </Button>
              </div>
            </article>
          )}
          {/* Keep the draft and operation identity during local route navigation. */}
          <LookupPage active={matchedRoute?.routeId === 'lookup'} />
          </AiConsentProvider>
        </ErrorBoundary>
      </main>
    </div>
  );
};
