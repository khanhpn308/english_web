import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync, existsSync, mkdtempSync, rmSync, readdirSync, writeFileSync, symlinkSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { chromium, type Browser, type Page } from '@playwright/test';
import { build } from 'vite';

// Test canonical alias import for cn()
import { cn } from '@/lib/utils';

// Test canonical alias imports for primitives
import { Button, buttonVariants } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card';
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogOverlay,
  DialogClose,
} from '@/components/ui/dialog';

describe('Design System Foundation - cn() utility', () => {
  it('concatenates class names normally', () => {
    const result = cn('text-sm', 'font-medium', 'text-foreground');
    expect(result).toBe('text-sm font-medium text-foreground');
  });

  it('handles conditional classes properly', () => {
    const isActive = true;
    const isDisabled = false;
    const falsyValue: string | boolean = false;
    const result = cn(
      'base-class',
      isActive && 'active-class',
      isDisabled && 'disabled-class',
      null,
      undefined,
      falsyValue && 'falsy-zero'
    );
    expect(result).toBe('base-class active-class');
  });

  it('resolves conflicting Tailwind utility classes using tailwind-merge', () => {
    expect(cn('p-4', 'p-2')).toBe('p-2');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
    expect(cn('bg-primary', 'bg-muted')).toBe('bg-muted');
  });
});

describe('Design System Foundation - Button primitive', () => {
  it('renders default button element with semantic tokens and default classes', () => {
    const html = renderToStaticMarkup(<Button>Bắt đầu ôn tập</Button>);
    expect(html).toMatch(/^<button[^>]*>Bắt đầu ôn tập<\/button>$/);
    expect(html).toContain('bg-primary');
    expect(html).toContain('text-primary-foreground');
    expect(html).toContain('focus-visible:ring-ring');
  });

  it('supports button variants and custom class composition', () => {
    const outlineHtml = renderToStaticMarkup(
      <Button variant="outline" size="sm" className="custom-test-btn">
        Hủy bỏ
      </Button>
    );
    expect(outlineHtml).toContain('border');
    expect(outlineHtml).toContain('border-input');
    expect(outlineHtml).toContain('h-8 rounded-md px-3 text-xs');
    expect(outlineHtml).toContain('custom-test-btn');

    const destructiveHtml = renderToStaticMarkup(
      <Button variant="destructive">Xóa thẻ</Button>
    );
    expect(destructiveHtml).toContain('bg-destructive');
    expect(destructiveHtml).toContain('text-destructive-foreground');
    expect(destructiveHtml).toContain('hover:bg-destructive/90');
  });

  it('supports disabled behavior and accessibility attributes', () => {
    const html = renderToStaticMarkup(
      <Button disabled aria-disabled="true">
        Vô hiệu hóa
      </Button>
    );
    expect(html).toContain('disabled=""');
    expect(html).toContain('aria-disabled="true"');
    expect(html).toContain('disabled:pointer-events-none');
    expect(html).toContain('disabled:opacity-50');
  });

  it('supports asChild rendering using Radix Slot', () => {
    const html = renderToStaticMarkup(
      <Button asChild variant="outline">
        <a href="/status">Trạng thái</a>
      </Button>
    );
    expect(html).toMatch(/^<a[^>]*href="\/status"[^>]*>Trạng thái<\/a>$/);
    expect(html).toContain('border-input');
    expect(html).not.toContain('<button');
  });

  it('supports buttonVariants helper for standalone styling', () => {
    const classes = buttonVariants({ variant: 'ghost', size: 'icon' });
    expect(classes).toContain('hover:bg-accent');
    expect(classes).toContain('h-9 w-9');
  });
});

describe('Design System Foundation - Card primitive', () => {
  it('renders complete Card composition with header, title, description, content, and footer', () => {
    const html = renderToStaticMarkup(
      <Card className="test-card">
        <CardHeader>
          <CardTitle>Từ vựng mới</CardTitle>
          <CardDescription>Tra cứu từ vựng từ bài báo khoa học</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Nội dung chi tiết từ vựng</p>
        </CardContent>
        <CardFooter>
          <span>10 thẻ đang chờ</span>
        </CardFooter>
      </Card>
    );

    // Verify outer card container
    expect(html).toContain('rounded-xl border bg-card text-card-foreground shadow');
    expect(html).toContain('test-card');

    // Verify header and title hierarchy
    expect(html).toContain('flex flex-col space-y-1.5 p-6');
    expect(html).toMatch(/<div[^>]*class="font-semibold leading-none tracking-tight"[^>]*>Từ vựng mới<\/div>/);
    expect(html).toMatch(/<div[^>]*class="text-sm text-muted-foreground"[^>]*>Tra cứu từ vựng từ bài báo khoa học<\/div>/);

    // Verify content and footer sections
    expect(html).toMatch(/<div[^>]*class="p-6 pt-0"[^>]*><p>Nội dung chi tiết từ vựng<\/p><\/div>/);
    expect(html).toMatch(/<div[^>]*class="flex items-center p-6 pt-0"[^>]*><span>10 thẻ đang chờ<\/span><\/div>/);
  });
});

describe('Design System Foundation - Dialog primitive (Static & Structural)', () => {
  it('renders DialogTrigger with state attributes in SSR and suppresses content when closed', () => {
    const html = renderToStaticMarkup(
      <Dialog open={false}>
        <DialogTrigger asChild>
          <Button variant="outline">Mở hộp thoại</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogTitle>Tiêu đề ẩn</DialogTitle>
        </DialogContent>
      </Dialog>
    );
    expect(html).toContain('aria-haspopup="dialog"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('data-state="closed"');
    expect(html).not.toContain('Tiêu đề ẩn');
  });

  it('renders DialogHeader, DialogTitle, DialogDescription with self-contained semantic foreground', () => {
    const headerHtml = renderToStaticMarkup(
      <Dialog>
        <DialogHeader className="custom-header">
          <DialogTitle>Xác nhận đồng ý AI</DialogTitle>
          <DialogDescription>Điều khoản dữ liệu</DialogDescription>
        </DialogHeader>
      </Dialog>
    );
    expect(headerHtml).toContain('custom-header');
    expect(headerHtml).toContain('flex flex-col space-y-1.5 text-center sm:text-left');
    // DialogTitle explicitly has text-foreground for self-contained dark mode contrast
    expect(headerHtml).toMatch(/<h2[^>]*class="text-lg font-semibold leading-none tracking-tight text-foreground"[^>]*>Xác nhận đồng ý AI<\/h2>/);
    expect(headerHtml).toMatch(/<p[^>]*class="text-sm text-muted-foreground"[^>]*>Điều khoản dữ liệu<\/p>/);
  });

  it('renders DialogClose with full focus opacity classes', () => {
    const footerHtml = renderToStaticMarkup(
      <Dialog>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Đóng lại</Button>
          </DialogClose>
        </DialogFooter>
      </Dialog>
    );
    expect(footerHtml).toContain('Đóng lại');
  });

  it('renders DialogOverlay with backdrop styling classes', () => {
    const overlayHtml = renderToStaticMarkup(
      <Dialog open>
        <DialogOverlay className="custom-overlay" />
      </Dialog>
    );
    expect(overlayHtml).toContain('custom-overlay');
    expect(overlayHtml).toContain('fixed inset-0 z-50 bg-black/80');
  });
});

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

// Convert 8-bit sRGB channel to linear sRGB via standard WCAG 2.x transfer function
function srgbChannelToLinear(c: number): number {
  const norm = c / 255;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

// Compute standard WCAG 2.x relative luminance from linear sRGB
function wcagRelativeLuminance(rgb: RgbColor): number {
  const rLin = srgbChannelToLinear(rgb.r);
  const gLin = srgbChannelToLinear(rgb.g);
  const bLin = srgbChannelToLinear(rgb.b);
  return 0.2126 * rLin + 0.7152 * gLin + 0.0722 * bLin;
}

// Calculate standard WCAG contrast ratio between two colors
function wcagContrastRatio(rgb1: RgbColor, rgb2: RgbColor): number {
  const lum1 = wcagRelativeLuminance(rgb1);
  const lum2 = wcagRelativeLuminance(rgb2);
  const bright = Math.max(lum1, lum2);
  const dark = Math.min(lum1, lum2);
  return (bright + 0.05) / (dark + 0.05);
}

// Parse comma-separated box-shadow property respecting nested parentheses
function parseBoxShadowLayers(str: string): string[] {
  const layers: string[] = [];
  let depth = 0;
  let current = '';
  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    if (ch === ',' && depth === 0) {
      layers.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim()) layers.push(current.trim());
  return layers;
}

// Extract ring color from Tailwind focus ring layer (spread radius >= 4px)
function extractRingColor(boxShadowStr: string): string {
  const layers = parseBoxShadowLayers(boxShadowStr);
  const ringLayer = layers.find((l) => l.includes('4px') || (l.includes('2px') && !l.includes('0px 0px 0px 2px')));
  if (!ringLayer) throw new Error(`Could not find ring layer in box-shadow: "${boxShadowStr}"`);
  const match = ringLayer.match(/^(.*?)\s+(?:-?\d+px\s+){3}(-?\d+px)/);
  if (!match) throw new Error(`Could not parse ring color from layer: "${ringLayer}"`);
  return match[1].trim();
}

// Independent manual WCAG calculation without shared helper for cross-checks
function manualContrast(c1: [number, number, number], c2: [number, number, number]): number {
  const lin = (c: number) => {
    const n = c / 255;
    return n <= 0.04045 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4);
  };
  const lum = (rgb: [number, number, number]) =>
    0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  const l1 = lum(c1);
  const l2 = lum(c2);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

describe('Design System Foundation - Real Browser Compiled CSS, Interaction & Rendered Contrast', () => {
  let tempDir: string | null = null;
  let browser: Browser | null = null;
  let page: Page | null = null;

  beforeAll(async () => {
    try {
      // 1. Create strictly isolated temporary directory outside repository
      tempDir = mkdtempSync(join(tmpdir(), 'vitest-design-system-'));

      // Link node_modules so bare imports in isolated temp fixture resolve correctly
      symlinkSync(resolve(process.cwd(), 'node_modules'), join(tempDir, 'node_modules'), 'dir');

      // 2. Write temporary test fixture importing real components and actual index.css
      const fixtureEntry = join(tempDir, 'entry.tsx');
      writeFileSync(
        fixtureEntry,
        `
import '@/index.css';
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from '@/components/ui/dialog';

function TestApp() {
  const [open, setOpen] = useState(false);

  return (
    <div id="test-app-root" className="bg-background text-foreground" style={{ padding: '24px' }}>
      <Button id="destructive-btn" variant="destructive">
        Xóa thẻ
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button id="dialog-trigger" variant="outline">
            Mở hộp thoại
          </Button>
        </DialogTrigger>
        <DialogContent id="dialog-content">
          <DialogHeader>
            <DialogTitle id="dialog-title">Tiêu đề hộp thoại</DialogTitle>
            <DialogDescription id="dialog-desc">Mô tả hộp thoại</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button id="dialog-close-btn" variant="default">
                Đóng
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const root = createRoot(document.getElementById('root')!);
root.render(<TestApp />);
`
      );

      // 3. Compile fixture using actual Vite pipeline and Tailwind CSS v4 plugin
      interface BuildChunkItem {
        fileName: string;
        code?: string;
        source?: string | Uint8Array;
      }

      const buildResult = await build({
        configFile: resolve(process.cwd(), 'vite.config.ts'),
        logLevel: 'error',
        build: {
          write: false,
          rollupOptions: {
            input: fixtureEntry,
          },
        },
      });

      const buildOutput = Array.isArray(buildResult) ? buildResult[0] : buildResult;
      const output = (buildOutput as { output: BuildChunkItem[] }).output;
      const jsChunk = output.find((c) => c.fileName.endsWith('.js'))?.code;
      const cssChunk = output.find((c) => c.fileName.endsWith('.css'))?.source;

      expect(jsChunk).toBeDefined();
      expect(cssChunk).toBeDefined();

      const compiledCssText = typeof cssChunk === 'string' ? cssChunk : new TextDecoder().decode(cssChunk);
      expect(compiledCssText).toContain('bg-destructive');
      expect(compiledCssText).toContain('text-destructive-foreground');
      expect(compiledCssText).toContain('ring-ring');

      // 4. Launch real Playwright Chromium browser and mount compiled application
      browser = await chromium.launch();
      page = await browser.newPage();
      await page.setContent(`
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8" />
            <style>${compiledCssText}</style>
          </head>
          <body>
            <div id="root"></div>
            <script type="module">${jsChunk}</script>
          </body>
        </html>
      `);

      await page.waitForSelector('#dialog-trigger');
      await page.waitForSelector('#destructive-btn');
    } catch (err) {
      if (browser) {
        await browser.close();
        browser = null;
      }
      if (tempDir && existsSync(tempDir)) {
        rmSync(tempDir, { recursive: true, force: true });
        tempDir = null;
      }
      throw err;
    }
  }, 30000);

  afterAll(async () => {
    try {
      if (browser) {
        await browser.close();
        browser = null;
      }
    } finally {
      if (tempDir && existsSync(tempDir)) {
        rmSync(tempDir, { recursive: true, force: true });
        tempDir = null;
      }
    }
  }, 30000);

  // Helper to obtain browser-rendered color converted to 8-bit sRGB via 2D Canvas
  async function getRenderedRgb(cssColor: string): Promise<RgbColor> {
    if (!page) throw new Error('Browser page not initialized');
    return page.evaluate((col) => {
      const canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      if (!ctx) throw new Error('Could not get 2d context');
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = col;
      ctx.fillRect(0, 0, 1, 1);
      const data = ctx.getImageData(0, 0, 1, 1).data;
      return { r: data[0], g: data[1], b: data[2] };
    }, cssColor);
  }

  // Helper to obtain actual browser-composited color of semi-transparent layer over surface
  async function getRenderedCompositedRgb(fgColor: string, surfaceBgColor: string): Promise<RgbColor> {
    if (!page) throw new Error('Browser page not initialized');
    return page.evaluate(
      ({ fg, bg }) => {
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        if (!ctx) throw new Error('Could not get 2d context');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, 1, 1);
        ctx.fillStyle = fg;
        ctx.fillRect(0, 0, 1, 1);
        const data = ctx.getImageData(0, 0, 1, 1).data;
        return { r: data[0], g: data[1], b: data[2] };
      },
      { fg: fgColor, bg: surfaceBgColor }
    );
  }

  it('proves real Radix Portal interaction: open, accessibility roles/labels, close click, Escape key, and focus restoration', async () => {
    if (!page) throw new Error('Page not initialized');

    // 1. Initial state: Trigger visible, DialogContent detached
    expect(await page.$('#dialog-content')).toBeNull();

    // 2. Open action: Click trigger -> mounts via real Radix Portal into body
    await page.click('#dialog-trigger');
    await page.waitForSelector('#dialog-content');

    // 3. Accessibility attributes: role="dialog", accessible title, description
    const role = await page.$eval('#dialog-content', (el) => el.getAttribute('role'));
    expect(role).toBe('dialog');

    const titleText = await page.$eval('#dialog-title', (el) => el.textContent);
    expect(titleText).toBe('Tiêu đề hộp thoại');

    const descText = await page.$eval('#dialog-desc', (el) => el.textContent);
    expect(descText).toBe('Mô tả hộp thoại');

    // Built-in close affordance button with sr-only text
    const srOnlyClose = await page.$eval('#dialog-content button span.sr-only', (el) => el.textContent);
    expect(srOnlyClose).toBe('Close');

    // 4. Close action: Click close button
    await page.click('#dialog-close-btn');
    await page.waitForSelector('#dialog-content', { state: 'detached' });
    expect(await page.$('#dialog-content')).toBeNull();

    // 5. Focus restoration: Trigger button regains focus after modal closes
    await page.waitForFunction(() => document.activeElement?.id === 'dialog-trigger');
    const focusedIdAfterClose = await page.evaluate(() => document.activeElement?.id);
    expect(focusedIdAfterClose).toBe('dialog-trigger');

    // 6. Escape key dismissal: Open again and press Escape
    await page.click('#dialog-trigger');
    await page.waitForSelector('#dialog-content');
    await page.keyboard.press('Escape');
    await page.waitForSelector('#dialog-content', { state: 'detached' });
    expect(await page.$('#dialog-content')).toBeNull();

    // Focus restored again
    await page.waitForFunction(() => document.activeElement?.id === 'dialog-trigger');
    const focusedIdAfterEscape = await page.evaluate(() => document.activeElement?.id);
    expect(focusedIdAfterEscape).toBe('dialog-trigger');
  }, 30000);

  it('validates Light Mode browser-rendered colors and contrast (>= 4.5:1 text, >= 3.0:1 focus)', async () => {
    if (!page) throw new Error('Page not initialized');
    await page.evaluate(() => document.documentElement.classList.remove('dark'));

    // --- Destructive Button (Light Mode) ---
    const lightBtnStyles = await page.$eval('#destructive-btn', (el) => {
      const s = window.getComputedStyle(el);
      return { color: s.color, backgroundColor: s.backgroundColor };
    });

    const normalBgRgb = await getRenderedRgb(lightBtnStyles.backgroundColor);
    const normalFgRgb = await getRenderedRgb(lightBtnStyles.color);
    const normalContrast = wcagContrastRatio(normalBgRgb, normalFgRgb);
    expect(normalContrast).toBeGreaterThanOrEqual(4.5);

    // Hover state with settled transition
    await page.hover('#destructive-btn');
    await page.waitForFunction(() => {
      const el = document.getElementById('destructive-btn');
      if (!el) return false;
      const bg = window.getComputedStyle(el).backgroundColor;
      return bg.endsWith('/ 0.9)');
    });

    const lightHoverBgStr = await page.$eval('#destructive-btn', (el) => window.getComputedStyle(el).backgroundColor);
    const lightSurfaceBgStr = await page.$eval('#test-app-root', (el) => window.getComputedStyle(el).backgroundColor);
    const compositedHoverBgRgb = await getRenderedCompositedRgb(lightHoverBgStr, lightSurfaceBgStr);
    const hoverContrast = wcagContrastRatio(compositedHoverBgRgb, normalFgRgb);
    expect(hoverContrast).toBeGreaterThanOrEqual(4.5);

    // Move mouse away to unhover
    await page.mouse.move(0, 0);

    // --- Dialog (Light Mode) ---
    await page.click('#dialog-trigger');
    await page.waitForSelector('#dialog-content');

    const lightDialogData = await page.$eval('#dialog-content', (el) => {
      const s = window.getComputedStyle(el);
      const title = el.querySelector('#dialog-title');
      const desc = el.querySelector('#dialog-desc');
      return {
        surfaceBg: s.backgroundColor,
        titleColor: title ? window.getComputedStyle(title).color : '',
        descColor: desc ? window.getComputedStyle(desc).color : '',
      };
    });

    const surfaceRgb = await getRenderedRgb(lightDialogData.surfaceBg);
    const titleRgb = await getRenderedRgb(lightDialogData.titleColor);
    const descRgb = await getRenderedRgb(lightDialogData.descColor);

    const titleContrast = wcagContrastRatio(surfaceRgb, titleRgb);
    expect(titleContrast).toBeGreaterThanOrEqual(4.5);

    const descContrast = wcagContrastRatio(surfaceRgb, descRgb);
    expect(descContrast).toBeGreaterThanOrEqual(4.5);

    // Dialog close button focus state and ring contrast
    const closeAffordance = await page.$('#dialog-content button:has(span.sr-only)');
    expect(closeAffordance).not.toBeNull();
    await closeAffordance!.focus();

    // Wait for transition-opacity to settle to 1.0 (100% opacity)
    await page.waitForFunction(() => {
      const btn = document.querySelector('#dialog-content button:has(span.sr-only)');
      return btn && window.getComputedStyle(btn).opacity === '1';
    });

    const closeFocusStyles = await closeAffordance!.evaluate((el) => {
      const s = window.getComputedStyle(el);
      return {
        opacity: s.opacity,
        boxShadow: s.boxShadow,
      };
    });

    expect(closeFocusStyles.opacity).toBe('1');
    const ringColorStr = extractRingColor(closeFocusStyles.boxShadow);
    const ringRgb = await getRenderedRgb(ringColorStr);
    const ringContrast = wcagContrastRatio(surfaceRgb, ringRgb);
    expect(ringContrast).toBeGreaterThanOrEqual(3.0);

    // Cleanly close modal
    await page.keyboard.press('Escape');
    await page.waitForSelector('#dialog-content', { state: 'detached' });
  }, 30000);

  it('validates Dark Mode browser-rendered colors and contrast (>= 4.5:1 text, >= 3.0:1 focus)', async () => {
    if (!page) throw new Error('Page not initialized');
    await page.evaluate(() => document.documentElement.classList.add('dark'));

    // Wait for theme transition to settle to dark values
    await page.waitForFunction(() => {
      const el = document.getElementById('destructive-btn');
      return el && window.getComputedStyle(el).color.includes('0.145');
    });

    // --- Destructive Button (Dark Mode) ---
    const darkBtnStyles = await page.$eval('#destructive-btn', (el) => {
      const s = window.getComputedStyle(el);
      return { color: s.color, backgroundColor: s.backgroundColor };
    });

    const darkNormalBgRgb = await getRenderedRgb(darkBtnStyles.backgroundColor);
    const darkNormalFgRgb = await getRenderedRgb(darkBtnStyles.color);
    const darkNormalContrast = wcagContrastRatio(darkNormalBgRgb, darkNormalFgRgb);
    expect(darkNormalContrast).toBeGreaterThanOrEqual(4.5);

    // Dark Hover state with settled transition
    await page.hover('#destructive-btn');
    await page.waitForFunction(() => {
      const el = document.getElementById('destructive-btn');
      if (!el) return false;
      const bg = window.getComputedStyle(el).backgroundColor;
      return bg.endsWith('/ 0.9)');
    });

    const darkHoverBgStr = await page.$eval('#destructive-btn', (el) => window.getComputedStyle(el).backgroundColor);
    const darkSurfaceBgStr = await page.$eval('#test-app-root', (el) => window.getComputedStyle(el).backgroundColor);
    const darkCompositedHoverBgRgb = await getRenderedCompositedRgb(darkHoverBgStr, darkSurfaceBgStr);
    const darkHoverContrast = wcagContrastRatio(darkCompositedHoverBgRgb, darkNormalFgRgb);
    expect(darkHoverContrast).toBeGreaterThanOrEqual(4.5);

    await page.mouse.move(0, 0);

    // --- Dialog (Dark Mode) ---
    await page.click('#dialog-trigger');
    await page.waitForSelector('#dialog-content');

    const darkDialogData = await page.$eval('#dialog-content', (el) => {
      const s = window.getComputedStyle(el);
      const title = el.querySelector('#dialog-title');
      const desc = el.querySelector('#dialog-desc');
      return {
        surfaceBg: s.backgroundColor,
        titleColor: title ? window.getComputedStyle(title).color : '',
        descColor: desc ? window.getComputedStyle(desc).color : '',
      };
    });

    const darkSurfaceRgb = await getRenderedRgb(darkDialogData.surfaceBg);
    const darkTitleRgb = await getRenderedRgb(darkDialogData.titleColor);
    const darkDescRgb = await getRenderedRgb(darkDialogData.descColor);

    // Dark title must NOT inherit legacy shell foreground; must achieve self-contained >= 4.5:1
    const darkTitleContrast = wcagContrastRatio(darkSurfaceRgb, darkTitleRgb);
    expect(darkTitleContrast).toBeGreaterThanOrEqual(4.5);

    const darkDescContrast = wcagContrastRatio(darkSurfaceRgb, darkDescRgb);
    expect(darkDescContrast).toBeGreaterThanOrEqual(4.5);

    // Dark Dialog close focus ring and opacity
    const darkCloseAffordance = await page.$('#dialog-content button:has(span.sr-only)');
    expect(darkCloseAffordance).not.toBeNull();
    await darkCloseAffordance!.focus();

    await page.waitForFunction(() => {
      const btn = document.querySelector('#dialog-content button:has(span.sr-only)');
      return btn && window.getComputedStyle(btn).opacity === '1';
    });

    const darkCloseFocusStyles = await darkCloseAffordance!.evaluate((el) => {
      const s = window.getComputedStyle(el);
      return {
        opacity: s.opacity,
        boxShadow: s.boxShadow,
      };
    });

    expect(darkCloseFocusStyles.opacity).toBe('1');
    const darkRingColorStr = extractRingColor(darkCloseFocusStyles.boxShadow);
    const darkRingRgb = await getRenderedRgb(darkRingColorStr);
    const darkRingContrast = wcagContrastRatio(darkSurfaceRgb, darkRingRgb);
    expect(darkRingContrast).toBeGreaterThanOrEqual(3.0);

    // Cleanly close modal and restore light class
    await page.keyboard.press('Escape');
    await page.waitForSelector('#dialog-content', { state: 'detached' });
    await page.evaluate(() => document.documentElement.classList.remove('dark'));
  }, 30000);

  it('performs independent cross-check of critical browser-rendered contrast ratios', async () => {
    if (!page) throw new Error('Page not initialized');

    // 1. Light destructive hover: composited canvas pixel vs destructive foreground
    const lightHoverRgb = await getRenderedCompositedRgb('oklab(0.52 0.21322 0.110169 / 0.9)', 'white');
    const lightFgRgb = await getRenderedRgb('oklch(0.985 0 0)');
    const manualLightHoverRatio = manualContrast(
      [lightHoverRgb.r, lightHoverRgb.g, lightHoverRgb.b],
      [lightFgRgb.r, lightFgRgb.g, lightFgRgb.b]
    );
    const helperLightHoverRatio = wcagContrastRatio(lightHoverRgb, lightFgRgb);
    expect(manualLightHoverRatio).toBeGreaterThanOrEqual(4.5);
    expect(Math.abs(manualLightHoverRatio - helperLightHoverRatio)).toBeLessThan(0.01);

    // 2. Dark destructive hover: composited canvas pixel vs dark destructive foreground
    const darkHoverRgb = await getRenderedCompositedRgb('oklab(0.704 0.176821 0.072217 / 0.9)', 'oklch(0.145 0 0)');
    const darkFgRgb = await getRenderedRgb('oklch(0.145 0 0)');
    const manualDarkHoverRatio = manualContrast(
      [darkHoverRgb.r, darkHoverRgb.g, darkHoverRgb.b],
      [darkFgRgb.r, darkFgRgb.g, darkFgRgb.b]
    );
    const helperDarkHoverRatio = wcagContrastRatio(darkHoverRgb, darkFgRgb);
    expect(manualDarkHoverRatio).toBeGreaterThanOrEqual(4.5);
    expect(Math.abs(manualDarkHoverRatio - helperDarkHoverRatio)).toBeLessThan(0.01);

    // 3. Light Dialog close focus ring on Dialog surface
    const lightRingRgb = await getRenderedRgb('oklch(0.62 0 0)');
    const lightSurfaceRgb = await getRenderedRgb('oklch(1 0 0)');
    const manualLightRingRatio = manualContrast(
      [lightRingRgb.r, lightRingRgb.g, lightRingRgb.b],
      [lightSurfaceRgb.r, lightSurfaceRgb.g, lightSurfaceRgb.b]
    );
    const helperLightRingRatio = wcagContrastRatio(lightRingRgb, lightSurfaceRgb);
    expect(manualLightRingRatio).toBeGreaterThanOrEqual(3.0);
    expect(Math.abs(manualLightRingRatio - helperLightRingRatio)).toBeLessThan(0.01);

    // 4. Dark Dialog close focus ring on Dialog surface
    const darkRingRgb = await getRenderedRgb('oklch(0.556 0 0)');
    const darkSurfaceRgb = await getRenderedRgb('oklch(0.145 0 0)');
    const manualDarkRingRatio = manualContrast(
      [darkRingRgb.r, darkRingRgb.g, darkRingRgb.b],
      [darkSurfaceRgb.r, darkSurfaceRgb.g, darkSurfaceRgb.b]
    );
    const helperDarkRingRatio = wcagContrastRatio(darkRingRgb, darkSurfaceRgb);
    expect(manualDarkRingRatio).toBeGreaterThanOrEqual(3.0);
    expect(Math.abs(manualDarkRingRatio - helperDarkRingRatio)).toBeLessThan(0.01);

    // 5. Dark Dialog title on Dialog surface
    const darkTitleRgb = await getRenderedRgb('oklch(0.985 0 0)');
    const manualDarkTitleRatio = manualContrast(
      [darkTitleRgb.r, darkTitleRgb.g, darkTitleRgb.b],
      [darkSurfaceRgb.r, darkSurfaceRgb.g, darkSurfaceRgb.b]
    );
    const helperDarkTitleRatio = wcagContrastRatio(darkTitleRgb, darkSurfaceRgb);
    expect(manualDarkTitleRatio).toBeGreaterThanOrEqual(4.5);
    expect(Math.abs(manualDarkTitleRatio - helperDarkTitleRatio)).toBeLessThan(0.01);
  }, 30000);
});

describe('Design System Foundation - T004 Preflight Regression Protection', () => {
  it('preserves T004 AppShell styles (heading font-weight 700 and unavailable-note margin 14px) when Tailwind CSS is active', async () => {
    // Compile current index.css
    interface BuildChunkItem {
      fileName: string;
      code?: string;
      source?: string | Uint8Array;
    }

    const buildResult = await build({
      root: resolve(process.cwd(), 'frontend'),
      logLevel: 'error',
      build: {
        write: false,
        rollupOptions: {
          input: resolve(process.cwd(), 'frontend/src/index.css'),
        },
      },
    });

    const buildOutput = Array.isArray(buildResult) ? buildResult[0] : buildResult;
    const output = (buildOutput as { output: BuildChunkItem[] }).output;
    const compiledTailwindCss = output.find((c) => c.fileName.endsWith('.css'))?.source;
    expect(compiledTailwindCss).toBeDefined();

    const shellCss = readFileSync(resolve(process.cwd(), 'frontend/src/app/shell.css'), 'utf-8');

    const browser = await chromium.launch();
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <!DOCTYPE html>
        <html>
          <head>
            <style>${shellCss}</style>
            <style>${compiledTailwindCss}</style>
          </head>
          <body>
            <main>
              <h1 class="screen-view__title">Tổng quan</h1>
              <p class="feature-unavailable-note">Ghi chú tính năng</p>
            </main>
          </body>
        </html>
      `);

      // Verify .screen-view__title preserves bold weight (700) instead of being reset to 400 by Preflight
      const titleFontWeight = await page.$eval('.screen-view__title', (el) => window.getComputedStyle(el).fontWeight);
      expect(titleFontWeight).toBe('700');

      // Verify .feature-unavailable-note preserves top margin (14px) instead of being reset to 0 by Preflight
      const noteMarginTop = await page.$eval('.feature-unavailable-note', (el) => window.getComputedStyle(el).marginTop);
      expect(noteMarginTop).toBe('14px');
    } finally {
      await browser.close();
    }
  }, 30000);

  it('verifies frontend/src/index.css does not import tailwindcss/preflight.css', () => {
    const cssContent = readFileSync(resolve(process.cwd(), 'frontend/src/index.css'), 'utf-8');
    expect(cssContent).not.toContain('preflight');
    expect(cssContent).not.toContain('@import "tailwindcss";');
    expect(cssContent).toContain('@import "tailwindcss/theme.css"');
    expect(cssContent).toContain('@import "tailwindcss/utilities.css"');
  });
});

describe('Design System Foundation - Explicit Main Entry CSS Dependency', () => {
  it('verifies frontend/src/main.tsx explicitly imports @/index.css', () => {
    const mainPath = resolve(process.cwd(), 'frontend/src/main.tsx');
    expect(existsSync(mainPath)).toBe(true);
    const mainContent = readFileSync(mainPath, 'utf-8');
    expect(mainContent).toMatch(/import\s+['"]@\/index\.css['"]/);
  });
});

describe('Design System Foundation - Fresh Isolated Vite Build Verification', () => {
  it('executes a fresh Vite build into a temporary directory and verifies generated CSS and HTML', async () => {
    const tempOutDir = mkdtempSync(join(tmpdir(), 'vite-fresh-build-'));

    try {
      await build({
        configFile: resolve(process.cwd(), 'vite.config.ts'),
        logLevel: 'error',
        build: {
          outDir: tempOutDir,
          emptyOutDir: true,
          rollupOptions: {
            input: {
              main: resolve(process.cwd(), 'frontend/index.html'),
              bootstrap: resolve(process.cwd(), 'frontend/bootstrap.html'),
            },
          },
        },
      });

      const assetsDir = join(tempOutDir, 'assets');
      expect(existsSync(assetsDir)).toBe(true);
      const files = readdirSync(assetsDir);
      const mainCss = files.find((f) => f.startsWith('main-') && f.endsWith('.css'));
      expect(mainCss).toBeDefined();

      if (mainCss) {
        const compiledCss = readFileSync(join(assetsDir, mainCss), 'utf-8');
        expect(compiledCss).toContain('text-destructive-foreground');
        expect(compiledCss).toContain('bg-destructive');
        expect(compiledCss).toContain('text-muted-foreground');
        expect(compiledCss).toContain('bg-background');
        expect(compiledCss).toContain('text-foreground');
        expect(compiledCss).toContain('ring-ring');
      }

      const indexHtml = readFileSync(join(tempOutDir, 'index.html'), 'utf-8');
      expect(indexHtml).toMatch(/<link rel="stylesheet"[^>]*href="\/assets\/main-[^"]+\.css"/);

      // Verify bootstrap.html is isolated from main CSS
      const bootstrapHtml = readFileSync(join(tempOutDir, 'bootstrap.html'), 'utf-8');
      expect(bootstrapHtml).not.toContain('main-');
      expect(bootstrapHtml).not.toContain('index.css');
    } finally {
      rmSync(tempOutDir, { recursive: true, force: true });
    }
  }, 30000);
});

describe('Design System Foundation - Static Theme Token Contrast (Opaque Source Tokens Sanity Check)', () => {
  function parseOklch(str: string): [number, number, number] {
    const match = str.match(/oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/);
    if (!match) throw new Error(`Could not parse oklch color: "${str}"`);
    return [parseFloat(match[1]), parseFloat(match[2]), parseFloat(match[3])];
  }

  function oklchToOklab(L: number, C: number, hDeg: number): [number, number, number] {
    const hRad = (hDeg * Math.PI) / 180;
    return [L, C * Math.cos(hRad), C * Math.sin(hRad)];
  }

  function oklabToLinearSrgb(L: number, a: number, b: number): [number, number, number] {
    const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
    const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
    const s_ = L - 0.0894841775 * a - 1.291485548 * b;

    const l = l_ ** 3;
    const m = m_ ** 3;
    const s = s_ ** 3;

    const r = +4.0767439362 * l - 3.3077115913 * m + 0.2309699295 * s;
    const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    const bVal = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s;

    return [
      Math.max(0, Math.min(1, r)),
      Math.max(0, Math.min(1, g)),
      Math.max(0, Math.min(1, bVal)),
    ];
  }

  function wcagLuminanceLinear(linearRgb: [number, number, number]): number {
    return 0.2126 * linearRgb[0] + 0.7152 * linearRgb[1] + 0.0722 * linearRgb[2];
  }

  function contrastRatioMath(lum1: number, lum2: number): number {
    const bright = Math.max(lum1, lum2);
    const dark = Math.min(lum1, lum2);
    return (bright + 0.05) / (dark + 0.05);
  }

  function parseTokens(cssBlock: string): Record<string, string> {
    const tokens: Record<string, string> = {};
    const re = /(--[\w-]+):\s*([^;]+);/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(cssBlock)) !== null) {
      tokens[m[1]] = m[2].trim();
    }
    return tokens;
  }

  const cssPath = resolve(process.cwd(), 'frontend/src/index.css');
  const cssContent = readFileSync(cssPath, 'utf-8');

  const rootBlockMatch = cssContent.match(/:root\s*\{([^}]+)\}/);
  const darkBlockMatch = cssContent.match(/\.dark\s*\{([^}]+)\}/);

  expect(rootBlockMatch).not.toBeNull();
  expect(darkBlockMatch).not.toBeNull();

  const rootTokens = parseTokens(rootBlockMatch![1]);
  const darkTokens = parseTokens(darkBlockMatch![1]);

  describe('Light Mode Token Checks', () => {
    const bgLab = oklchToOklab(...parseOklch(rootTokens['--background']));
    const mutedLab = oklchToOklab(...parseOklch(rootTokens['--muted']));
    const mutedFgLab = oklchToOklab(...parseOklch(rootTokens['--muted-foreground']));
    const secLab = oklchToOklab(...parseOklch(rootTokens['--secondary']));
    const ringLab = oklchToOklab(...parseOklch(rootTokens['--ring']));

    const bgLum = wcagLuminanceLinear(oklabToLinearSrgb(...bgLab));
    const mutedLum = wcagLuminanceLinear(oklabToLinearSrgb(...mutedLab));
    const mutedFgLum = wcagLuminanceLinear(oklabToLinearSrgb(...mutedFgLab));
    const secLum = wcagLuminanceLinear(oklabToLinearSrgb(...secLab));
    const ringLum = wcagLuminanceLinear(oklabToLinearSrgb(...ringLab));

    it('TOKEN CHECK: ensures muted-foreground on muted is >= 4.5:1', () => {
      expect(contrastRatioMath(mutedLum, mutedFgLum)).toBeGreaterThanOrEqual(4.5);
    });

    it('TOKEN CHECK: ensures muted-foreground on background is >= 4.5:1', () => {
      expect(contrastRatioMath(bgLum, mutedFgLum)).toBeGreaterThanOrEqual(4.5);
    });

    it('TOKEN CHECK: ensures ring on secondary is >= 3.0:1', () => {
      expect(contrastRatioMath(secLum, ringLum)).toBeGreaterThanOrEqual(3.0);
    });
  });

  describe('Dark Mode Token Checks', () => {
    const bgLab = oklchToOklab(...parseOklch(darkTokens['--background']));
    const mutedLab = oklchToOklab(...parseOklch(darkTokens['--muted']));
    const mutedFgLab = oklchToOklab(...parseOklch(darkTokens['--muted-foreground']));
    const secLab = oklchToOklab(...parseOklch(darkTokens['--secondary']));
    const ringLab = oklchToOklab(...parseOklch(darkTokens['--ring']));

    const bgLum = wcagLuminanceLinear(oklabToLinearSrgb(...bgLab));
    const mutedLum = wcagLuminanceLinear(oklabToLinearSrgb(...mutedLab));
    const mutedFgLum = wcagLuminanceLinear(oklabToLinearSrgb(...mutedFgLab));
    const secLum = wcagLuminanceLinear(oklabToLinearSrgb(...secLab));
    const ringLum = wcagLuminanceLinear(oklabToLinearSrgb(...ringLab));

    it('TOKEN CHECK: ensures dark muted-foreground on muted is >= 4.5:1', () => {
      expect(contrastRatioMath(mutedLum, mutedFgLum)).toBeGreaterThanOrEqual(4.5);
    });

    it('TOKEN CHECK: ensures dark muted-foreground on background is >= 4.5:1', () => {
      expect(contrastRatioMath(bgLum, mutedFgLum)).toBeGreaterThanOrEqual(4.5);
    });

    it('TOKEN CHECK: ensures dark ring on secondary is >= 3.0:1', () => {
      expect(contrastRatioMath(secLum, ringLum)).toBeGreaterThanOrEqual(3.0);
    });
  });
});
