import React, { Component, useEffect, useState, type ErrorInfo, type ReactNode } from 'react';
import './shell.css';

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
        <section className="error-boundary-panel" role="alert" aria-live="assertive">
          <h2>Đã xảy ra lỗi không mong muốn</h2>
          <p className="error-message">{this.state.errorMessage}</p>
          <div className="error-actions">
            <button
              type="button"
              className="button button--primary"
              onClick={this.handleRetry}
            >
              Thử lại màn hình này
            </button>
            <a href="/status" className="button button--secondary">
              Kiểm tra trạng thái hệ thống
            </a>
          </div>
        </section>
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
    <div className="app-container">
      {/* Accessible skip link */}
      <a href="#main-content" className="skip-link">
        Chuyển đến nội dung chính
      </a>

      {/* Screen announcement live region */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {matchedRoute ? `Đang hiển thị màn hình ${matchedRoute.title}` : 'Không tìm thấy trang'}
      </div>

      <header className="app-header" role="banner">
        <div className="app-header__brand">
          <a href="/" className="app-brand-link" onClick={(e) => handleLinkClick(e, '/')}>
            <span className="app-brand-title">Học Từ Vựng Học Thuật</span>
          </a>
        </div>

        <nav className="primary-nav" aria-label="Điều hướng chính" role="navigation">
          <ul className="primary-nav__list">
            {PRIMARY_NAV_ITEMS.map((item) => {
              const active = isNavActive(item, activePath);
              return (
                <li key={item.id} className="primary-nav__item">
                  <a
                    href={item.href}
                    className={`nav-link ${active ? 'nav-link--active' : ''}`}
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

        <div className="app-header__actions">
          <a
            href="/status#ai-consent"
            className="ai-consent-quick-link"
            title="Xem và quản lý quyền chia sẻ dữ liệu với AI bridge"
            onClick={(e) => handleLinkClick(e, '/status')}
          >
            Quyền gửi dữ liệu AI
          </a>
        </div>
      </header>

      <main id="main-content" className="app-main" tabIndex={-1} role="main">
        <ErrorBoundary>
          {matchedRoute ? (
            <article className="screen-view">
              <h1 className="screen-view__title" tabIndex={-1}>
                {matchedRoute.title}
              </h1>
              <div className="feature-unavailable-card" role="region" aria-label="Thông báo trạng thái tính năng">
                <p className="feature-unavailable-message">
                  Tính năng đang được xây dựng (chưa khả dụng) trong giai đoạn khởi tạo shell.
                </p>
                {Object.keys(matchedRoute.params).length > 0 && (
                  <dl className="route-params-list">
                    {Object.entries(matchedRoute.params).map(([key, value]) => (
                      <div key={key} className="route-param-item">
                        <dt>{key}:</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                )}
                <p className="feature-unavailable-note">
                  Dữ liệu bài học và tính năng tương tác thực tế sẽ được nạp sau khi tích hợp API backend.
                </p>
              </div>
            </article>
          ) : (
            <article className="screen-view not-found-view">
              <h1 className="screen-view__title" tabIndex={-1}>
                Không tìm thấy trang
              </h1>
              <p>Địa chỉ bạn yêu cầu không tồn tại hoặc đã được thay đổi.</p>
              <div className="not-found-actions">
                <a
                  href="/"
                  className="button button--primary"
                  onClick={(e) => handleLinkClick(e, '/')}
                >
                  Quay lại trang chủ
                </a>
              </div>
            </article>
          )}
        </ErrorBoundary>
      </main>
    </div>
  );
};
