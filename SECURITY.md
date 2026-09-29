# Security

## Scope and trust boundaries

HandWave is a local desktop application. Its untrusted inputs are MP3 files and their metadata, album images, camera frames, settings JSON, YouTube responses, device behavior, and native dependencies. It has no web listener, account system, remote API, or telemetry.

## Implemented controls

- Only direct regular-file children of `music/` whose suffix is `.mp3` are considered.
- Every candidate is resolved, then required to have the resolved music directory as its parent; symlink/path traversal escapes are rejected.
- MP3 files over 512 MiB and embedded artwork over 8 MiB are rejected to reduce resource exhaustion.
- Metadata is treated only as text, stripped of control characters, and capped at 180 characters. It is never executed or used as a path, URL, stylesheet, or command.
- Invalid and corrupt media is skipped with bounded user messaging and diagnostic logging.
- Settings accept only declared fields and normalize enum/range values before use.
- Camera enumeration is bounded; a disconnected camera produces a controlled shutdown of the vision worker.
- Audio analysis is skipped above 64 MiB, otherwise bounded to 3,600 windows, and runs outside the UI thread.
- Logs rotate at 1 MiB with three backups and do not record camera frames or MP3 contents.
- No shell commands are constructed from metadata or filenames.
- YouTube downloads accept only exact `youtube.com` and `youtu.be` hosts, disable third-party yt-dlp plugins, reject playlists, limit downloads to one item and 512 MiB, and sanitize optional output names.
- Existing MP3 files are never overwritten; imports use a numbered destination when a name already exists.
- MP3 content, local settings, environments, logs, and caches are excluded from Git.

## OWASP-oriented review

The classic OWASP Top 10 targets web applications, but the principles still apply:

| Risk family | Desktop relevance and mitigation |
|---|---|
| Broken access control | No network privilege boundary; file discovery is constrained to one directory. |
| Cryptographic failures | No secrets or sensitive data are collected or stored. |
| Injection | Metadata never enters a command, query, HTML engine, or dynamic import. |
| Insecure design | Vision emits typed events through a debounce controller before playback actions. |
| Security misconfiguration | Dependencies are pinned; private data and logs are ignored by Git. |
| Vulnerable components | Dependencies require periodic upstream review and fresh-environment testing. |
| Authentication failures | Not applicable; the application has no accounts. |
| Integrity failures | Install from this repository and obtain model assets only from official Google sources. |
| Logging failures | Errors are logged with rotation; user-facing messages avoid raw tracebacks. |
| SSRF | Network retrieval is constrained to exact YouTube hostnames; arbitrary URLs and local schemes are rejected. |

## Native decoder warning

MP3, image, camera, and computer-vision parsing ultimately use native libraries. A malicious file could target a dependency vulnerability even when Python code treats data safely. Keep the OS and pinned dependencies current, do not run the application with elevated privileges, and only add music from sources you trust.

## Reporting

Do not publish exploit details in an issue before a fix is available. Contact the repository owner privately through their GitHub profile when possible, including affected version, reproduction steps, and impact.
