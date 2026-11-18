# Security policy

## Protect your Deezer ARL cookie

`DEEZER_ARL` is a Deezer session credential. Anyone who obtains it may be able to act as the
signed-in account. Treat it like a password:

- never commit it to Git, paste it into an issue, or include it in logs;
- prefer `DEEZER_ARL_FILE` (a `chmod 600` file outside the repository) over a raw value in a
  client configuration file, which is often synced or shared;
- use a dedicated Deezer account if you want to limit the impact of accidental exposure;
- invalidate the Deezer session immediately if the cookie is exposed (log out everywhere, then log
  back in to get a new `arl`).

The server reads the cookie from the environment or from the configured file, and never writes it
to disk. Error messages run through a redaction pass that removes the ARL value, any long
hex-shaped secret and `Authorization: Bearer …` fragments before the text reaches the MCP client.

## Limit what the agent can do

- `DEEZER_READ_ONLY=1` removes the five write tools from `tools/list` **and** refuses them at
  dispatch time. Use it for any unattended or shared agent.
- Write tools are annotated (`destructiveHint`) so clients can require confirmation.
- `delete_playlist` also requires `confirm: true`, which agents only set after asking the user.

## Reporting a vulnerability

Do not include credentials or personal data in a public issue. Use GitHub's private vulnerability
reporting feature when available. If private reporting is unavailable, contact the maintainer
privately through the contact information on their GitHub profile.

This project is unofficial and depends on Deezer's internal web API. That API can change without
notice, and this project is not affiliated with or endorsed by Deezer. Using it may violate
Deezer's terms of service; you are responsible for how you use your own account.
