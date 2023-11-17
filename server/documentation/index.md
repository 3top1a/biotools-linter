# Documentation

Welcome to the bio.tools linter documentation.

## API

This website uses an [API](https://en.wikipedia.org/wiki/API) exposed by the server, that is publicly available.
To see the automatically generated documentation of the API, see [this link](/api/documentation).

## Error types

- [URL\_INVALID](/docs/URL_INVALID)
- [URL\_PERMANENT\_REDIRECT](/docs/URL_PERMANENT_REDIRECT)
- [URL\_BAD\_STATUS](/docs/URL_BAD_STATUS)
- [URL\_NO\_SSL](/docs/URL_NO_SSL)
- [URL\_UNUSED\_SSL](/docs/URL_UNUSED_SSL)
- [URL\_TIMEOUT](/docs/URL_TIMEOUT)
- [URL\_SSL\_ERROR](/docs/URL_SSL_ERROR)
- [URL\_CONN\_ERROR](/docs/URL_CONN_ERROR)
- [URL\_LINTER\_ERROR](/docs/URL_LINTER_ERROR)
- [URL\_TOO\_MANY\_REDIRECTS](/docs/URL_TOO_MANY_REDIRECTS)
- [EDAM\_OBSOLETE](/docs/EDAM_OBSOLETE)
- [EDAM\_NOT\_RECOMMENDED](/docs/EDAM_NOT_RECOMMENDED)
- [EDAM\_INVALID](/docs/EDAM_INVALID)
- [DOI\_BUT\_NOT\_PMID](/docs/PublishingIDConversions)
- [DOI\_BUT\_NOT\_PMCID](/docs/PublishingIDConversions)
- [PMID\_BUT\_NOT\_DOI](/docs/PublishingIDConversions)
- [PMCID\_BUT\_NOT\_DOI](/docs/PublishingIDConversions)

Unfinished:

- EDAM\_GENERIC
  - EDAM\_GENERIC may be removed and substituted with a more advanced filter

## Monitoring

This server runs an instance of [Monitoror](https://monitoror.com/) for status monitoring. Is it available publicly at [this link](/dash/).
