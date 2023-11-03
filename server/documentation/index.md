# Documentation

Welcome to the bio.tools linter documentation.

## API

This website uses an [API](https://en.wikipedia.org/wiki/API) exposed by the server, that is publicly available.
To see the automatically generated documentation of the API, see [this link](/api/documentation).

## Error types

- [URL_INVALID](/docs/URL_INVALID)
- [URL_PERMANENT_REDIRECT](/docs/URL_PERMANENT_REDIRECT)
- [URL_BAD_STATUS](/docs/URL_BAD_STATUS)
- [URL_NO_SSL](/docs/URL_NO_SSL)
- [URL_UNUSED_SSL](/docs/URL_UNUSED_SSL)
- [URL_TIMEOUT](/docs/URL_TIMEOUT)
- [URL_SSL_ERROR](/docs/URL_SSL_ERROR)
- [URL_CONN_ERROR](/docs/URL_CONN_ERROR)
- [URL_LINTER_ERROR](/docs/URL_LINTER_ERROR)
- [URL_TOO_MANY_REDIRECTS](/docs/URL_TOO_MANY_REDIRECTS)
- [EDAM_OBSOLETE](/docs/EDAM_OBSOLETE)
- [EDAM_NOT_RECOMMENDED](/docs/EDAM_NOT_RECOMMENDED)
- [EDAM_INVALID](/docs/EDAM_INVALID)
- [DOI_BUT_NOT_PMID](/docs/PublishingIDConversions)
- [DOI_BUT_NOT_PMCID](/docs/PublishingIDConversions)
- [PMID_BUT_NOT_DOI](/docs/PublishingIDConversions)
- [PMCID_BUT_NOT_DOI](/docs/PublishingIDConversions)

Unfinished:
- EDAM_GENERIC
    - EDAM_GENERIC may be removed and substituted with a more advanced filter

## Monitoring
This server runs an instance of [Monitoror](https://monitoror.com/) for status monitoring. Is it available publicly at [this link](/dash/).
