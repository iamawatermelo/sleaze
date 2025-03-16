# sleaze

Log your Monzo transactions to Slack.

## Get started

Install Sleaze with your favourite package manager:

```sh
pip install sleaze@git+https://github.com/iamawatermelo/sleaze
```

Create a Slack application and a bot. It will need `chat:write` and 
`chat:write.customize` permissions. You'll need the token.

Run this web server somewhere. Run `sleaze --help` for the arguments you
need to provide. For example:

> ```
> $ SLEAZE_SLACK_TOKEN=xoxb-... \
>   # the channel ID to send to
>   SLEAZE_SLACK_CHANNEL=C... \
>   # the user to ping (use <@USER_ID> format)
>   SLEAZE_SLACK_PING="<@U...>" \
>   # of course, generate your own :p
>   # you can use `openssl rand -hex 16`
>   SLEAZE_WEBHOOK_AUTH_TOKEN=2ab799aa8ebba70f01f452ac1ce7f012 \
>   # the user's pronouns (defaults to they)
>   SLEAZE_USER_PRONOUN="she/her/her/hers/herself" \
>   sleaze
> ```

The webhook auth token is used to validate that requests come from
Monzo. There is currently no better way to ensure webhook requests
are legitimate.

Note that, if you choose to specify a set of pronouns, they must be in
the form `subject/object/posessive determiner/posessive pronoun/reflexive`.

In the [Monzo Developers console](https://developers.monzo.com/),
register a webhook with the URL of the web server. **Include the
webhook auth token as a query parameter.** For example:

> ```
> {
>   "account_id": "$account_id",
>   "url": "https://lexis-ipad.yak-bebop.ts.net/monzo-webhook?token=2ab799aa8ebba70f01f452ac1ce7f012"
> }
> ```

And you're done. Happy spending!