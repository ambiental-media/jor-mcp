import createNextIntlPlugin from 'next-intl/plugin'

const withNextIntl = createNextIntlPlugin('./src/i18n/request.js')

// Empty in the standalone profile: the portal bucket is the load balancer's
// default backend, so assets keep the native /_next path. Set to a prefix
// (e.g. /authorize-static) only when another site shares the same host.
const assetPrefix = process.env.PORTAL_ASSET_PREFIX || undefined

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  assetPrefix,
  images: {
    unoptimized: true
  }
}

export default withNextIntl(nextConfig)
