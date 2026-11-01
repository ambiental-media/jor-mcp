import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NextIntlClientProvider } from 'next-intl'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import messagesFile from '../../../../messages/pt.json'

const messages = messagesFile.authorize
import AuthorizePage from './page'

const mocks = vi.hoisted(() => ({
  useSearchParams: vi.fn(),
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  getDoc: vi.fn()
}))

vi.mock('next/navigation', () => ({
  useSearchParams: () => mocks.useSearchParams()
}))

vi.mock('../../../lib/firebase', () => ({
  getFirebaseAuth: () => ({}),
  getFirebaseDb: () => ({})
}))

vi.mock('firebase/auth', () => ({
  GoogleAuthProvider: vi.fn(),
  onAuthStateChanged: (...args) => mocks.onAuthStateChanged(...args),
  signInWithPopup: (...args) => mocks.signInWithPopup(...args),
  signOut: (...args) => mocks.signOut(...args)
}))

vi.mock('firebase/firestore', () => ({
  doc: vi.fn(),
  getDoc: (...args) => mocks.getDoc(...args)
}))

const VALID_PARAMS = {
  client_id: 'client-1',
  code_challenge: 'challenge',
  code_challenge_method: 'S256',
  redirect_uri: 'http://localhost:5555/callback',
  state: 'state-1'
}

const user = {
  email: 'journalist@example.com',
  getIdToken: vi.fn().mockResolvedValue('id-token')
}

function renderPage() {
  return render(
    <NextIntlClientProvider locale="pt" messages={messagesFile}>
      <AuthorizePage />
    </NextIntlClientProvider>
  )
}

function setParams(params) {
  mocks.useSearchParams.mockReturnValue(new URLSearchParams(params))
}

function signedInAsUser() {
  mocks.onAuthStateChanged.mockImplementation((_auth, callback) => {
    callback(user)
    return () => {}
  })
}

function allowedUser() {
  mocks.getDoc.mockResolvedValue({
    exists: () => true,
    data: () => ({ status: 'active' })
  })
}

describe('AuthorizePage', () => {
  const originalLocation = window.location

  beforeEach(() => {
    setParams(VALID_PARAMS)
    mocks.onAuthStateChanged.mockImplementation((_auth, callback) => {
      callback(null)
      return () => {}
    })
    mocks.getDoc.mockReset()
    mocks.signOut.mockReset()
    mocks.signInWithPopup.mockReset()
    global.fetch = vi.fn()

    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' }
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      value: originalLocation
    })
    vi.clearAllMocks()
  })

  it('reports missing authorization parameters', async () => {
    setParams({})

    renderPage()

    expect(await screen.findByText(messages.missingParams)).toBeInTheDocument()
  })

  it('offers Google sign-in when the user is signed out', async () => {
    renderPage()

    expect(
      await screen.findByRole('button', { name: messages.signInWithGoogle })
    ).toBeInTheDocument()
  })

  it('denies access when the allow-list document is not active', async () => {
    signedInAsUser()
    mocks.getDoc.mockResolvedValue({
      exists: () => true,
      data: () => ({ status: 'disabled' })
    })

    renderPage()

    expect(
      await screen.findByText(messages.accessDeniedTitle)
    ).toBeInTheDocument()
  })

  it('shows the retry state when the allow-list cannot be read', async () => {
    signedInAsUser()
    mocks.getDoc.mockRejectedValue(new Error('offline'))

    renderPage()

    expect(
      await screen.findByText(messages.accessErrorTitle)
    ).toBeInTheDocument()
  })

  it('approves access and follows the returned redirect URI', async () => {
    signedInAsUser()
    allowedUser()
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        authorization_code: 'code',
        redirect_uri: 'http://localhost:5555/callback?code=code&state=state-1'
      })
    })

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.authorizeButton })
    )

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/oauth/approve',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer id-token'
        })
      })
    )
    const requestBody = JSON.parse(global.fetch.mock.calls[0][1].body)
    expect(requestBody).toEqual({
      client_id: 'client-1',
      code_challenge: 'challenge',
      code_challenge_method: 'S256',
      redirect_uri: 'http://localhost:5555/callback',
      state: 'state-1'
    })
    expect(window.location.href).toBe(
      'http://localhost:5555/callback?code=code&state=state-1'
    )
  })

  it('flips to denied when the backend answers 403', async () => {
    signedInAsUser()
    allowedUser()
    global.fetch.mockResolvedValue({ ok: false, status: 403 })

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.authorizeButton })
    )

    expect(
      await screen.findByText(messages.accessDeniedTitle)
    ).toBeInTheDocument()
    expect(window.location.href).toBe('')
  })

  it('reports a failure when the approve request throws', async () => {
    signedInAsUser()
    allowedUser()
    global.fetch.mockRejectedValue(new Error('network'))

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.authorizeButton })
    )

    expect(
      await screen.findByText(messages.errors.authorize)
    ).toBeInTheDocument()
    expect(window.location.href).toBe('')
  })

  it('redirects with access_denied when the user cancels', async () => {
    signedInAsUser()
    allowedUser()

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.cancel })
    )

    expect(window.location.href).toBe(
      'http://localhost:5555/callback?error=access_denied&state=state-1'
    )
  })

  it('signs in through the Google popup', async () => {
    mocks.signInWithPopup.mockResolvedValue({})

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.signInWithGoogle })
    )

    expect(mocks.signInWithPopup).toHaveBeenCalledTimes(1)
  })

  it('reports a popup sign-in failure', async () => {
    mocks.signInWithPopup.mockRejectedValue(new Error('popup closed'))

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.signInWithGoogle })
    )

    expect(await screen.findByText(messages.errors.signIn)).toBeInTheDocument()
  })

  it('refuses an unsafe redirect URI returned by the backend', async () => {
    signedInAsUser()
    allowedUser()
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ redirect_uri: 'javascript:alert(1)' })
    })

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.authorizeButton })
    )

    expect(
      await screen.findByText(messages.errors.authorize)
    ).toBeInTheDocument()
    expect(window.location.href).toBe('')
  })

  it('signs the user out from the account link', async () => {
    signedInAsUser()
    allowedUser()

    renderPage()
    await userEvent.click(
      await screen.findByRole('button', { name: messages.useAnotherAccount })
    )

    expect(mocks.signOut).toHaveBeenCalledTimes(1)
  })
})
