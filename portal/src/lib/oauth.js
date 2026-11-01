const FORBIDDEN_PROTOCOLS = ['javascript:', 'data:', 'vbscript:']

/**
 * Return true when the URI is safe to navigate to.
 *
 * Defense in depth only: the backend refuses any redirect_uri that is not
 * registered for the requesting client.
 */
export function isSafeRedirectUri(uri) {
  if (!uri) return false
  try {
    const parsed = new URL(uri)
    return !FORBIDDEN_PROTOCOLS.includes(parsed.protocol.toLowerCase())
  } catch {
    const lower = uri.trim().toLowerCase()
    const isForbiddenProtocol = FORBIDDEN_PROTOCOLS.some((protocol) =>
      lower.startsWith(protocol)
    )
    return !isForbiddenProtocol && !uri.startsWith('//')
  }
}

/**
 * Build the cancel redirect, or null when the redirect URI is unusable.
 */
export function buildCancelUrl(redirectUri, state) {
  if (!isSafeRedirectUri(redirectUri)) return null

  // RFC 6749 forbids a fragment in redirect_uri; drop one defensively so the
  // error parameters are actually sent to the server.
  const base = redirectUri.split('#')[0]
  const separator = base.includes('?') ? '&' : '?'
  let cancelUrl = `${base}${separator}error=access_denied`
  if (state) {
    cancelUrl += `&state=${encodeURIComponent(state)}`
  }
  return cancelUrl
}

/**
 * Extract the OAuth authorization parameters from the query string.
 */
export function parseAuthorizeParams(params) {
  const clientId = params.get('client_id')
  const codeChallenge = params.get('code_challenge')

  return {
    clientId,
    clientName: params.get('client_name') || clientId || 'Claude Desktop',
    codeChallenge,
    codeChallengeMethod: params.get('code_challenge_method') || 'S256',
    redirectUri: params.get('redirect_uri'),
    state: params.get('state'),
    missingParams: !clientId || !codeChallenge
  }
}
