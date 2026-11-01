import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import SetHtmlLang from './SetHtmlLang'

describe('SetHtmlLang', () => {
  afterEach(() => {
    cleanup()
    document.documentElement.lang = 'pt'
  })

  it('sets the document language to the active locale', () => {
    render(<SetHtmlLang locale="en" />)

    expect(document.documentElement.lang).toBe('en')
  })

  it('updates the language when the locale changes', () => {
    const { rerender } = render(<SetHtmlLang locale="en" />)
    rerender(<SetHtmlLang locale="pt" />)

    expect(document.documentElement.lang).toBe('pt')
  })
})
