import asyncio
from time import monotonic
from typing import Annotated, Literal
import pydantic
from typer import Argument, Typer

from sleaze.context import Context
from fastapi import FastAPI, HTTPException
from uvicorn import Server, Config

DEFAULT_PROFILE_PICTURE = "https://hc-cdn.hel1.your-objectstorage.com/s/v3/abf87c75bbf7d36496a436e24bc0ecaa484cf1fe_frame_1__1_.png"

class SlackMessage(pydantic.BaseModel):
    text: str
    icon_url: str = DEFAULT_PROFILE_PICTURE
    username: str = "Monzo"
    unfurl_links: bool = False
    unfurl_media: bool = False
    
    async def send(self):
        ctx = Context.from_context()
        async with ctx.slack_session.post(
            "https://slack.com/api/chat.postMessage",
            data={
                **self.model_dump(),
                "channel": ctx.slack_channel
            }
        ) as response:
            response.raise_for_status()
            print(await response.json())


class MonzoAddress(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    
    city: str
    country: str


class MonzoWebhookMerchant(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    
    emoji: str
    name: str
    logo: str
    address: MonzoAddress


CURRENCY_TO_SYMBOL = {
    "GBP": "£",
    "USD": "U$",
    "CAD": "C$",
    "EUR": "€"
}


DECLINE_REASON_MAP = {
    "INSUFFICIENT_FUNDS": "because {subject} didn't have enough money",
    "CARD_INACTIVE": "because {subject} froze {posessive_determiner} card",
    "CARD_BLOCKED": "because {posessive_determiner} card is blocked",
    "INVALID_CVC": "because {subject} got {posessive_determiner} CVC wrong",
    "OTHER": "for some reason"
}


def format_money(amount: int, currency: str):
    amount_str = str(abs(amount)).rjust(3, "0")
    
    if abs(amount) < 100 and currency == "GBP":
        return f"{amount_str[-2:].lstrip("0")}p"
    
    if amount % 100 == 0:
        amount_str = amount_str[:-2]
    else:
        amount_str = f"{amount_str[:-2]}.{amount_str[-2:]}"
    
    if symbol := CURRENCY_TO_SYMBOL.get(currency):
        return f"{symbol}{amount_str}"
    
    return f"{amount_str} {currency}"


class MonzoTransaction(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    
    amount: int
    currency: str
    local_amount: int
    local_currency: str
    merchant: MonzoWebhookMerchant | None = None
    dedupe_id: str
    scheme: str
    decline_reason: str | None = None
    
    def format_money(self):
        tx_formatted = format_money(self.amount, self.currency)
        
        if self.currency != self.local_currency:
            return f"{tx_formatted} ({format_money(self.local_amount, self.local_currency)})"
        
        return tx_formatted
    
    def format(self):
        ctx = Context.from_context()
        is_send = self.amount < 0
        is_decline = self.decline_reason is not None
        
        if self.merchant is not None:
            merchant_details = {
                "username": f"{self.merchant.name}, {self.merchant.address.city}, {self.merchant.address.country}",
                "icon_url": self.merchant.logo if self.merchant.logo != "" else DEFAULT_PROFILE_PICTURE
            }
            payee = self.merchant.name
        else:
            merchant_details = {}
            payee = "someone"
            
        match self.scheme:
            case "payport_faster_payments":
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} sent {self.format_money()} to {payee}",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} received {self.format_money()} from {payee}",
                        **merchant_details
                    )
            case "uk_retail_pot":
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} put {self.format_money()} into a pot",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} took {self.format_money()} from a pot",
                        **merchant_details
                    )
            case "3dsecure":
                if is_decline:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} was declined for {self.format_money()} {ctx.user_pronoun.format(DECLINE_REASON_MAP.get(self.decline_reason, "for some reason"))}",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{self.merchant.emoji if self.merchant is not None else "🤷"} {ctx.slack_ping_user} spent {self.format_money()} on an online transaction",
                        **merchant_details
                    )
            case "mastercard":
                if is_decline:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} was declined for {self.format_money()} {ctx.user_pronoun.format(DECLINE_REASON_MAP.get(self.decline_reason, "for some reason"))}",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{self.merchant.emoji if self.merchant is not None else "🤷"} {ctx.slack_ping_user} spent {self.format_money()}",
                        **merchant_details
                    )
            case "bacs":
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} sent {self.format_money()} to {payee}",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} received {self.format_money()} from {payee}",
                        **merchant_details
                    )
            case "rbs_cheque":
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} sent {self.format_money()} via cheque",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} received {self.format_money()} via cheque",
                        **merchant_details
                    )
            case "p2p_payment":
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} sent {self.format_money()} to a Monzo user",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} received {self.format_money()} from a Monzo user",
                        **merchant_details
                    )
            case scheme:
                if is_send:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} sent {self.format_money()} via an unknown scheme ({scheme})",
                        **merchant_details
                    )
                else:
                    return SlackMessage(
                        text=f"{ctx.slack_ping_user} received {self.format_money()} via an unknown scheme ({scheme})",
                        **merchant_details
                    )

class MonzoTransactionCreated(pydantic.BaseModel):
    type: Literal["transaction.created"]
    data: MonzoTransaction

class MonzoTransactionUpdated(pydantic.BaseModel):
    type: Literal["transaction.updated"]
    data: MonzoTransaction

app = FastAPI(
    docs_url=None,
    openapi_url=None
)
webhook_cache = dict()


@app.post("/monzo-webhook")
async def process_webhook(
    payload: MonzoTransactionCreated | MonzoTransactionUpdated,
    token: str
):
    ctx = Context.from_context()
    
    if token != ctx.webhook_auth_token:
        raise HTTPException(400)
    
    if type(payload) is MonzoTransactionUpdated:
        return # I don't care
    
    if webhook_cache.get(payload.data.dedupe_id) is not None:
        return
    
    webhook_cache[payload.data.dedupe_id] = monotonic()
    
    await payload.data.format().send()

cli = Typer()

@cli.command()
def main(
    slack_token: Annotated[str, Argument(envvar="SLEAZE_SLACK_TOKEN")],
    slack_channel: Annotated[str, Argument(envvar="SLEAZE_SLACK_CHANNEL")],
    slack_ping_user: Annotated[str, Argument(envvar="SLEAZE_SLACK_PING")],
    webhook_auth_token: Annotated[str, Argument(envvar="SLEAZE_WEBHOOK_AUTH_TOKEN")],
    user_pronoun: Annotated[str, Argument(envvar="SLEAZE_USER_PRONOUN")] = "they/them/their/theirs/themselves",
):
    async def inner():
        async with Context(
            slack_token=slack_token,
            slack_channel=slack_channel,
            slack_ping_user=slack_ping_user,
            webhook_auth_token=webhook_auth_token,
            user_pronoun=user_pronoun
        ).enter():
            await Server(Config(
                app=app,
                port=33113
            )).serve()
    
    asyncio.run(inner())


if __name__ == "__main__":
    cli()