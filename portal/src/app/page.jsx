// Static export has no server-side redirect: forward to the locale-prefixed
// consent page, preserving the OAuth query string and hash.
export default function Home() {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html:
          "window.location.replace('/pt/authorize/' + window.location.search + window.location.hash)"
      }}
    />
  )
}
