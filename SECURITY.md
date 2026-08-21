# Security policy

## Protect your Deezer ARL cookie

`DEEZER_ARL` is a Deezer session credential. Anyone who obtains it may be able to act as the
signed-in account. Treat it like a password:

- never commit it to Git, paste it into an issue, or include it in logs;
- keep MCP client configuration files private to your user account;
- invalidate the Deezer session immediately if the cookie is exposed;
- use a dedicated Deezer account if you want to limit the impact of accidental exposure.

The server reads the cookie from the process environment and never intentionally writes it to
disk or returns it through MCP responses.

## Reporting a vulnerability

Do not include credentials or personal data in a public issue. Use GitHub's private vulnerability
reporting feature when available. If private reporting is unavailable, contact the maintainer
privately through the contact information on their GitHub profile.

This project is unofficial and depends on Deezer's internal web API. That API can change without
notice, and this project is not affiliated with or endorsed by Deezer.
