import { FlatCompat } from '@eslint/eslintrc'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const compat = new FlatCompat({
  baseDirectory: dirname(fileURLToPath(import.meta.url))
})

const config = [
  ...compat.extends('next/core-web-vitals'),
  {
    ignores: ['.next/**', 'out/**', 'coverage/**', 'node_modules/**']
  },
  {
    files: ['**/*.test.{js,jsx}'],
    languageOptions: {
      globals: {
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly'
      }
    }
  }
]

export default config
