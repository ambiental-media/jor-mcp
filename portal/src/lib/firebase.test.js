import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getApps: vi.fn(),
  getApp: vi.fn(),
  initializeApp: vi.fn(),
  getAuth: vi.fn(),
  getFirestore: vi.fn()
}))

vi.mock('firebase/app', () => ({
  getApps: mocks.getApps,
  getApp: mocks.getApp,
  initializeApp: mocks.initializeApp
}))

vi.mock('firebase/auth', () => ({ getAuth: mocks.getAuth }))
vi.mock('firebase/firestore', () => ({ getFirestore: mocks.getFirestore }))

describe('firebase client', () => {
  beforeEach(() => {
    vi.resetModules()
    mocks.getApps.mockReset()
    mocks.getApp.mockReset()
    mocks.initializeApp.mockReset()
    mocks.getAuth.mockReset()
    mocks.getFirestore.mockReset()
    mocks.getAuth.mockReturnValue({ kind: 'auth' })
    mocks.getFirestore.mockReturnValue({ kind: 'db' })
  })

  it('initializes the app once and reuses the auth and db instances', async () => {
    let apps = []
    mocks.getApps.mockImplementation(() => apps)
    mocks.initializeApp.mockImplementation(() => {
      apps = [{ name: 'app' }]
      return { name: 'app' }
    })

    const { getFirebaseAuth, getFirebaseDb } = await import('./firebase')

    expect(getFirebaseAuth()).toBe(getFirebaseAuth())
    expect(getFirebaseDb()).toBe(getFirebaseDb())
    expect(mocks.initializeApp).toHaveBeenCalledTimes(1)
  })

  it('reuses an already initialized app', async () => {
    mocks.getApps.mockReturnValue([{ name: 'app' }])
    mocks.getApp.mockReturnValue({ name: 'app' })

    const { getFirebaseAuth } = await import('./firebase')

    expect(getFirebaseAuth()).toEqual({ kind: 'auth' })
    expect(mocks.initializeApp).not.toHaveBeenCalled()
    expect(mocks.getApp).toHaveBeenCalledTimes(1)
  })
})
