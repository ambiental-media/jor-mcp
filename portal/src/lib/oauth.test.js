import { describe, expect, it } from 'vitest'
import {
  buildCancelUrl,
  isSafeRedirectUri,
  parseAuthorizeParams
} from './oauth'

describe('isSafeRedirectUri', () => {
  it('accepts absolute http and https URLs', () => {
    expect(isSafeRedirectUri('https://example.com/callback')).toBe(true)
    expect(isSafeRedirectUri('http://localhost:5555/callback')).toBe(true)
  })

  it('rejects missing and empty values', () => {
    expect(isSafeRedirectUri(null)).toBe(false)
    expect(isSafeRedirectUri('')).toBe(false)
    expect(isSafeRedirectUri(undefined)).toBe(false)
  })

  it.each(['javascript:alert(1)', 'data:text/html,x', 'vbscript:msgbox'])(
    'rejects the %s protocol',
    (uri) => {
      expect(isSafeRedirectUri(uri)).toBe(false)
    }
  )

  it('rejects protocol-relative URIs', () => {
    expect(isSafeRedirectUri('//evil.example/callback')).toBe(false)
  })
})

describe('buildCancelUrl', () => {
  it('appends the error to a URI without a query string', () => {
    expect(buildCancelUrl('https://example.com/callback', 'abc')).toBe(
      'https://example.com/callback?error=access_denied&state=abc'
    )
  })

  it('appends the error to a URI that already has a query string', () => {
    expect(buildCancelUrl('https://example.com/callback?foo=bar', 'abc')).toBe(
      'https://example.com/callback?foo=bar&error=access_denied&state=abc'
    )
  })

  it('encodes the state value', () => {
    expect(buildCancelUrl('https://example.com/callback', 'a b&c')).toBe(
      'https://example.com/callback?error=access_denied&state=a%20b%26c'
    )
  })

  it('omits the state when it is absent', () => {
    expect(buildCancelUrl('https://example.com/callback', null)).toBe(
      'https://example.com/callback?error=access_denied'
    )
  })

  it('returns null for an unusable redirect URI', () => {
    expect(buildCancelUrl(null, 'abc')).toBeNull()
    expect(buildCancelUrl('javascript:alert(1)', 'abc')).toBeNull()
  })

  it('drops a fragment so the error reaches the server', () => {
    expect(buildCancelUrl('https://example.com/callback#frag', 'abc')).toBe(
      'https://example.com/callback?error=access_denied&state=abc'
    )
  })
})

describe('parseAuthorizeParams', () => {
  it('reads every OAuth parameter', () => {
    const params = new URLSearchParams({
      client_id: 'client-1',
      client_name: 'Claude Desktop',
      code_challenge: 'challenge',
      code_challenge_method: 'S256',
      redirect_uri: 'http://localhost:5555/callback',
      state: 'state-1'
    })

    expect(parseAuthorizeParams(params)).toEqual({
      clientId: 'client-1',
      clientName: 'Claude Desktop',
      codeChallenge: 'challenge',
      codeChallengeMethod: 'S256',
      redirectUri: 'http://localhost:5555/callback',
      state: 'state-1',
      missingParams: false
    })
  })

  it('falls back to the client id as the display name', () => {
    const params = new URLSearchParams({
      client_id: 'client-1',
      code_challenge: 'challenge'
    })

    expect(parseAuthorizeParams(params).clientName).toBe('client-1')
  })

  it('defaults the challenge method to S256', () => {
    const params = new URLSearchParams({
      client_id: 'client-1',
      code_challenge: 'challenge'
    })

    expect(parseAuthorizeParams(params).codeChallengeMethod).toBe('S256')
  })

  it('flags a request without client id or challenge', () => {
    expect(parseAuthorizeParams(new URLSearchParams()).missingParams).toBe(true)
    expect(
      parseAuthorizeParams(new URLSearchParams({ client_id: 'client-1' }))
        .missingParams
    ).toBe(true)
  })
})
