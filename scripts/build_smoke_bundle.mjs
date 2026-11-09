/**
 * Bundle the app (with CSS/JSX handled by esbuild) so it can be rendered in
 * jsdom. Kept separate from the Vite build because we need a CJS entry point
 * that Node can require directly.
 */
import { build } from 'esbuild'
import path from 'node:path'

const ROOT = path.resolve(import.meta.dirname, '..')

await build({
  entryPoints: [path.join(ROOT, 'scripts/smoke_entry.jsx')],
  bundle: true,
  outfile: path.join(ROOT, 'scripts/.smoke-bundle.cjs'),
  platform: 'node',
  format: 'cjs',
  jsx: 'automatic',
  loader: { '.js': 'jsx', '.jsx': 'jsx', '.css': 'empty' },
  define: { 'import.meta.env': '{"BASE_URL":"/apea/study/","PROD":false}' },
  logLevel: 'error',

})
console.log('smoke bundle ready')
