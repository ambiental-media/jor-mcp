'use client'

import { useEffect } from 'react'

// Root layout is shared by the redirect shims, which have no locale segment,
// so the document language is corrected once the locale layout hydrates.
export default function SetHtmlLang({ locale }) {
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  return null
}
