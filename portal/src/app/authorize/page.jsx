// The discovery metadata advertises /authorize, while the consent page lives
// under the locale segment. This static shim preserves the query string.
export default function AuthorizeRedirect() {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html:
          "window.location.replace('/pt/authorize/' + window.location.search + window.location.hash)"
      }}
    />
  )
}
