// T062: docs/api-contract.md §2 and CONSTRAINTS.md architecture boundaries.
// Syntax: https://github.com/sverweij/dependency-cruiser/blob/v17.4.3/doc/rules-reference.md
/* global module */
const fs = globalThis.process.getBuiltinModule('node:fs');
const source = 'frontend/src';
if (!fs.existsSync(source) || !fs.readdirSync(source, { recursive: true }).some(
  (entry) => /\.(ts|tsx)$/.test(entry) && fs.statSync(`${source}/${entry}`).isFile(),
)) {
  throw new Error('Missing or empty architecture source: frontend/src');
}
if (!fs.existsSync('node_modules/typescript/lib/typescript.js')) {
  throw new Error('Missing TypeScript architecture analyzer');
}

module.exports = {
  forbidden: [
    {
      name: 'frontend-no-server',
      severity: 'error',
      from: { path: '^frontend/src/' },
      // First-party ownership paths. React's server rendering test API is a library,
      // not this application's server boundary; package code is not excluded globally.
      to: {
        path: '^(backend|server)(/|\\.|$)|^frontend/src/(backend|server)(/|\\.|$)|^frontend/src/.*/(backend|server)(/|\\.|$)',
      },
    },
    {
      name: 'frontend-no-sql',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: {
        path: '(^|/)(persistence|database|sql|sqlalchemy|sqlite3?|better-sqlite3|pg|mysql2?|@prisma/client)(/|\\.|$)',
      },
    },
    {
      name: 'frontend-no-credentials',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: { path: '(^|/)(secrets?|credentials?|server-config|proxy[-_]?(key|credentials?))(/|\\.|$)' },
    },
    {
      name: 'frontend-no-server-builtins',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: { path: '^(node:)?(fs|path|child_process|net|tls|http|https|os|process)(/|$)' },
    },
    {
      name: 'frontend-no-cycles',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: { circular: true },
    },
    {
      name: 'frontend-no-unresolved',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: { couldNotResolve: true },
    },
    {
      name: 'generated-dto-types-only',
      severity: 'error',
      from: { path: '^frontend/src/' },
      to: {
        path: '^frontend/src/shared/api/generated\\.ts$',
        dependencyTypesNot: ['type-only'],
      },
    },
  ],
  options: {
    // Include type-only edges: importing a forbidden backend type is still forbidden.
    tsPreCompilationDeps: true,
    tsConfig: { fileName: 'tsconfig.json' },
    doNotFollow: { path: '(^|/)node_modules/' },
    // No generated/shared exclusion: the exact DTO and all siblings stay analyzed.
  },
};
