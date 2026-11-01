import { getApp, getApps, initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID
}

let authInstance = null
let dbInstance = null

function getFirebaseApp() {
  return getApps().length ? getApp() : initializeApp(firebaseConfig)
}

// Initialized lazily (client-side only): calling getAuth at module load throws
// auth/invalid-api-key during the static-export prerender, when the
// NEXT_PUBLIC_FIREBASE_* values are not inlined yet.
export function getFirebaseAuth() {
  if (!authInstance) {
    authInstance = getAuth(getFirebaseApp())
  }
  return authInstance
}

export function getFirebaseDb() {
  if (!dbInstance) {
    dbInstance = getFirestore(getFirebaseApp())
  }
  return dbInstance
}
