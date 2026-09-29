import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

describe('Frontend Toolchain & Quality Gates', () => {
  it('executes in a supported Node runtime (>=20.19.0)', () => {
    const versionParts = process.versions.node.split('.').map(Number);
    const major = versionParts[0];
    const minor = versionParts[1];
    expect(major).toBeGreaterThanOrEqual(20);
    if (major === 20) {
      expect(minor).toBeGreaterThanOrEqual(19);
    }
  });

  it('runs assertions successfully with vitest test runner', () => {
    expect(1 + 1).toBe(2);
    expect('vocabulary-app').toContain('vocabulary');
    expect({ ready: true }).toEqual({ ready: true });
    expect([1, 2, 3]).toHaveLength(3);
  });

  it('verifies that negative assertions fail properly', () => {
    expect(() => {
      expect(1 + 1).toBe(3);
    }).toThrow();
  });

  it('reports build readiness as BUILD_PENDING_SHELL before T004 creates entry point', () => {
    const entryHtml = path.resolve(process.cwd(), 'index.html');
    const entryExists = fs.existsSync(entryHtml);
    const buildReadiness = entryExists ? 'BUILD_READY' : 'BUILD_PENDING_SHELL';

    // Prior to T004, index.html is absent and build is expected to be pending shell
    expect(entryExists).toBe(false);
    expect(buildReadiness).toBe('BUILD_PENDING_SHELL');
  });
});
