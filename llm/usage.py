"""Cost of a call from the price table. An estimate: the gateway's own spend figure is the truth."""

import config


def cost_usd(tier: config.Tier, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = config.PRICE_PER_MTOK[tier]
    cost = (tokens_in * price_in + tokens_out * price_out) / config.TOKENS_PER_MTOK
    return round(cost, config.COST_DECIMALS)
