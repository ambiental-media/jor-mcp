'use client'

import { Suspense, useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Center,
  Heading,
  Icon,
  Spinner,
  Stack,
  Text
} from '@chakra-ui/react'
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut
} from 'firebase/auth'
import { doc, getDoc } from 'firebase/firestore'
import { getFirebaseAuth, getFirebaseDb } from '../../../lib/firebase'
import {
  buildCancelUrl,
  isSafeRedirectUri,
  parseAuthorizeParams
} from '../../../lib/oauth'

// Empty means same origin, which is the production default for the standalone
// profile. Local development sets it to http://localhost:8080.
const BACKEND_URL = process.env.NEXT_PUBLIC_OAUTH_BACKEND_URL || ''

const FONT = "'Figtree', sans-serif"
const PURPLE = '#35017b'

const buttonStyles = {
  fontFamily: FONT,
  fontSize: '1.8rem',
  fontWeight: '600',
  h: '5.2rem',
  borderRadius: '0.8rem'
}

const linkStyles = {
  fontFamily: FONT,
  fontSize: '1.6rem',
  fontWeight: '600',
  color: PURPLE,
  textAlign: 'center'
}

const GoogleIcon = (props) => (
  <Icon viewBox="0 0 48 48" {...props}>
    <path
      fill="#EA4335"
      d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
    />
    <path
      fill="#4285F4"
      d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
    />
    <path
      fill="#FBBC05"
      d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
    />
    <path
      fill="#34A853"
      d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
    />
  </Icon>
)

export function AuthorizeContent() {
  const t = useTranslations('authorize')
  const params = useSearchParams()
  const {
    clientId,
    clientName,
    codeChallenge,
    codeChallengeMethod,
    redirectUri,
    state,
    missingParams
  } = parseAuthorizeParams(params)

  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [access, setAccess] = useState('unknown')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const checkAccess = useCallback(async (currentUser) => {
    setAccess('checking')
    const email = currentUser.email
    if (!email) {
      setAccess('denied')
      return
    }
    try {
      const snapshot = await getDoc(
        doc(getFirebaseDb(), 'allowed_users', email.toLowerCase())
      )
      const allowed = snapshot.exists() && snapshot.data().status === 'active'
      setAccess(allowed ? 'allowed' : 'denied')
    } catch {
      setAccess('error')
    }
  }, [])

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(getFirebaseAuth(), (currentUser) => {
      setUser(currentUser)
      setAuthReady(true)
      if (!currentUser) {
        setAccess('unknown')
        return
      }
      checkAccess(currentUser)
    })
    return () => unsubscribe()
  }, [checkAccess])

  const handleGoogleSignIn = async () => {
    setError('')
    setSubmitting(true)
    try {
      const provider = new GoogleAuthProvider()
      await signInWithPopup(getFirebaseAuth(), provider)
    } catch {
      setError(t('errors.signIn'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleAuthorize = async () => {
    setError('')
    setSubmitting(true)
    try {
      const idToken = await user.getIdToken()
      const response = await fetch(`${BACKEND_URL}/api/oauth/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${idToken}`
        },
        body: JSON.stringify({
          client_id: clientId,
          code_challenge: codeChallenge,
          code_challenge_method: codeChallengeMethod,
          redirect_uri: redirectUri,
          state
        })
      })
      if (!response.ok) {
        if (response.status === 403) {
          setAccess('denied')
          return
        }
        throw new Error('approve request failed')
      }
      const data = await response.json()
      const targetUri = data.redirect_uri || redirectUri
      if (!targetUri || !isSafeRedirectUri(targetUri)) {
        throw new Error('Unsafe redirect URI')
      }
      window.location.href = targetUri
    } catch {
      setError(t('errors.authorize'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancel = () => {
    const cancelUrl = buildCancelUrl(redirectUri, state)
    if (!cancelUrl) return
    window.location.href = cancelUrl
  }

  const card = (children) => (
    <Center minH="70vh" px={4} py="6rem">
      <Box
        w="100%"
        maxW="48rem"
        bg="white"
        borderWidth="1px"
        borderColor="gray.200"
        borderRadius="1.6rem"
        boxShadow="0 4px 40px rgba(0, 0, 0, 0.12)"
        p="4rem"
      >
        {children}
      </Box>
    </Center>
  )

  const alert = (message, status = 'error') => (
    <Alert
      status={status}
      borderRadius="0.8rem"
      fontFamily={FONT}
      fontSize="1.6rem"
    >
      <AlertIcon boxSize="2.2rem" mr="1.2rem" />
      {message}
    </Alert>
  )

  const heading = (text) => (
    <Heading fontFamily={FONT} fontSize="3rem" fontWeight="800" color={PURPLE}>
      {text}
    </Heading>
  )

  const spinner = (
    <Center>
      <Spinner size="xl" thickness="3px" color={PURPLE} />
    </Center>
  )

  if (missingParams) {
    return card(alert(t('missingParams')))
  }

  if (!authReady) {
    return card(spinner)
  }

  if (!user) {
    return card(
      <Stack spacing="2rem">
        {heading(t('loginTitle'))}
        <Text fontFamily={FONT} fontSize="1.8rem" color="gray.700">
          {t('consentIntro', { clientName })}
        </Text>
        {error && alert(error)}
        <Button
          onClick={handleGoogleSignIn}
          isLoading={submitting}
          leftIcon={<GoogleIcon boxSize="2.4rem" />}
          bg="white"
          color="gray.700"
          borderWidth="1px"
          borderColor="gray.300"
          _hover={{ bg: 'gray.50' }}
          _active={{ bg: 'gray.100' }}
          {...buttonStyles}
        >
          {t('signInWithGoogle')}
        </Button>
      </Stack>
    )
  }

  if (access === 'checking' || access === 'unknown') {
    return card(spinner)
  }

  if (access === 'error') {
    return card(
      <Stack spacing="2rem">
        {heading(t('accessErrorTitle'))}
        {alert(t('accessError'), 'warning')}
        <Button
          onClick={() => checkAccess(user)}
          bg={PURPLE}
          color="white"
          _hover={{ bg: '#4a02a8' }}
          _active={{ bg: '#2a0163' }}
          {...buttonStyles}
        >
          {t('retry')}
        </Button>
      </Stack>
    )
  }

  if (access === 'denied') {
    return card(
      <Stack spacing="2rem">
        {heading(t('accessDeniedTitle'))}
        {alert(t('accessDenied'))}
        <Text fontFamily={FONT} fontSize="1.6rem" color="gray.600">
          {t('loggedInAs', { email: user.email })}
        </Text>
        <Button
          variant="link"
          {...linkStyles}
          onClick={() => signOut(getFirebaseAuth())}
        >
          {t('useAnotherAccount')}
        </Button>
      </Stack>
    )
  }

  return card(
    <Stack spacing="2rem">
      {heading(t('title'))}
      <Text fontFamily={FONT} fontSize="1.8rem" color="gray.700">
        {t('consentIntro', { clientName })}
      </Text>
      <Text fontFamily={FONT} fontSize="1.6rem" color="gray.600">
        {t('loggedInAs', { email: user.email })}
      </Text>
      {error && alert(error)}
      <Button
        colorScheme="green"
        onClick={handleAuthorize}
        isLoading={submitting}
        {...buttonStyles}
      >
        {t('authorizeButton')}
      </Button>
      <Button
        variant="outline"
        onClick={handleCancel}
        isDisabled={submitting}
        {...buttonStyles}
      >
        {t('cancel')}
      </Button>
      <Button
        variant="link"
        {...linkStyles}
        onClick={() => signOut(getFirebaseAuth())}
      >
        {t('useAnotherAccount')}
      </Button>
    </Stack>
  )
}

export default function AuthorizePage() {
  return (
    <Suspense
      fallback={
        <Center minH="70vh">
          <Spinner size="xl" thickness="3px" color={PURPLE} />
        </Center>
      }
    >
      <AuthorizeContent />
    </Suspense>
  )
}
