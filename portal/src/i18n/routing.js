import { defineRouting } from 'next-intl/routing'

// Static export cannot negotiate a locale on the server, so the prefix is
// always present and detection is disabled (see next-intl static export docs).
export const routing = defineRouting({
  locales: ['pt', 'en'],
  defaultLocale: 'pt',
  localePrefix: 'always',
  localeDetection: false
})
