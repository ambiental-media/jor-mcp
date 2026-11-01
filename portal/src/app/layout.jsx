import '../styles/consent.scss'

export const metadata = {
  title: 'Jor-MCP',
  description: 'Authorize an MCP client to query Jor-MCP journalistic content.'
}

export default function RootLayout({ children }) {
  return (
    <html lang="pt">
      <body>{children}</body>
    </html>
  )
}
