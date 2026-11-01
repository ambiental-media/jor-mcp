import { ChakraProvider } from '@chakra-ui/react'
import { NextIntlClientProvider } from 'next-intl'
import { getMessages, setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'
import SetHtmlLang from '../../components/SetHtmlLang'
import { routing } from '../../i18n/routing'

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({ children, params }) {
  const { locale } = await params
  if (!routing.locales.includes(locale)) {
    notFound()
  }
  setRequestLocale(locale)

  const messages = await getMessages()

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <SetHtmlLang locale={locale} />
      <ChakraProvider>{children}</ChakraProvider>
    </NextIntlClientProvider>
  )
}
