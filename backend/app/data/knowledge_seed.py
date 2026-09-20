"""Corpus A source material that does not already live elsewhere.

The concept articles, glossary and quiz explanations are indexed directly from
their existing modules — duplicating them here would create two sources of truth.
This file holds only the material that has no other home: Indian market and
regulatory context, and behavioural-finance background.

Why this content specifically: a general-purpose language model has no reliable
knowledge of Indian capital-gains rules, SEBI investor guidance, or NSE
conventions, and will confidently produce US-centric answers. Grounding on this
is what stops "consult a 401(k) advisor" appearing in an Indian product.
"""

from __future__ import annotations

# Each entry becomes one chunk. Bodies are kept to a few hundred words so several
# can fit in a prompt together.
INDIAN_MARKET_CONTEXT: list[dict] = [
    {
        "key": "india:exchanges",
        "title": "NSE and BSE — India's stock exchanges",
        "body": (
            "India has two main stock exchanges. The National Stock Exchange (NSE) is the "
            "larger by trading volume, and the Bombay Stock Exchange (BSE) is the older, "
            "founded in 1875. Most large companies are listed on both. The NSE's benchmark "
            "index is the Nifty 50, covering India's fifty largest listed companies by "
            "free-float market capitalisation; the BSE's is the Sensex, covering thirty. "
            "Trading runs from 9:15 am to 3:30 pm IST on weekdays, excluding market "
            "holidays. In DolFin, symbols carry a .NS suffix because prices are sourced "
            "for the NSE listing."
        ),
    },
    {
        "key": "india:capital_gains",
        "title": "Capital gains tax on listed Indian equity",
        "body": (
            "Gains on listed Indian equity are taxed differently depending on how long the "
            "shares were held. Selling within twelve months produces a short-term capital "
            "gain, taxed at a higher rate than long-term gains. Holding beyond twelve "
            "months produces a long-term capital gain, taxed at a lower rate and subject to "
            "an annual exemption threshold. The practical consequence for a beginner is "
            "that frequent trading is penalised twice over: brokerage costs on every "
            "transaction, and a higher tax rate on any profit. Rates and thresholds are set "
            "in the annual Union Budget and change periodically, so specific figures should "
            "always be checked against current rules rather than memorised."
        ),
    },
    {
        "key": "india:sebi",
        "title": "SEBI and investor protection",
        "body": (
            "The Securities and Exchange Board of India (SEBI) regulates India's securities "
            "markets. It registers brokers and advisers, enforces disclosure requirements on "
            "listed companies, and runs investor-education programmes. Two things matter to "
            "a beginner. First, only SEBI-registered investment advisers may give "
            "personalised investment advice for a fee — which is why an educational product "
            "explains principles rather than recommending specific securities. Second, SEBI "
            "requires brokers to segregate client funds, and investors should verify a "
            "broker's registration before opening an account. SEBI also publishes warnings "
            "about unregistered advisory schemes, which frequently target new investors "
            "through social media."
        ),
    },
]


INDIAN_MARKET_CONTEXT += [
    {
        "key": "india:demat",
        "title": "Demat accounts and how buying actually works",
        "body": (
            "Shares in India are held electronically in a dematerialised (demat) account, "
            "maintained by a depository participant and backed by one of two depositories, "
            "NSDL or CDSL. A trading account, usually opened with the same broker, is what "
            "places orders. Opening both requires KYC verification: PAN card, proof of "
            "address, and a linked bank account. Settlement in Indian equity markets is T+1, "
            "meaning shares and money change hands one working day after the trade. DolFin "
            "simulates the trading experience but not the account-opening process, so a "
            "learner graduating to real money still needs to complete KYC with a broker."
        ),
    },
    {
        "key": "india:emergency_fund",
        "title": "Emergency funds before investing",
        "body": (
            "Standard Indian personal-finance guidance is to hold three to six months of "
            "living expenses in a savings account or liquid fund before investing in equity. "
            "For someone with irregular income, the upper end is safer. This money is not "
            "investment capital and should not be exposed to market movements. Its entire "
            "purpose is to ensure that a job loss, medical bill, or family obligation never "
            "forces a sale of investments at whatever price the market happens to offer that "
            "week. An investor without this buffer is structurally a forced seller, which is "
            "the single most expensive position to be in during a downturn."
        ),
    },
]

BEHAVIOURAL_FINANCE: list[dict] = [
    {
        "key": "behaviour:loss_aversion",
        "title": "Loss aversion",
        "body": (
            "Loss aversion is the finding, established by Kahneman and Tversky, that losses "
            "are felt roughly twice as intensely as equivalent gains. Losing Rs 5,000 hurts "
            "about twice as much as gaining Rs 5,000 feels good. This asymmetry drives two "
            "opposite errors. Investors sell winners early to lock in the pleasant feeling of "
            "a realised gain, capping their best outcomes. And they hold losers far too long, "
            "because selling would make the loss official. The corrective question ignores "
            "the purchase price entirely: knowing what I know now, would I buy this today?"
        ),
    },
    {
        "key": "behaviour:disposition_effect",
        "title": "The disposition effect",
        "body": (
            "The disposition effect is the observed tendency to sell assets that have gained "
            "value while keeping assets that have lost value. It follows directly from loss "
            "aversion and is one of the most consistently documented patterns in retail "
            "investing. The result is a portfolio that gradually concentrates in an "
            "investor's worst holdings, because the better ones keep getting sold. Recognising "
            "it is straightforward: if your realised gains are consistently small and your "
            "unrealised losses are consistently large, the disposition effect is operating."
        ),
    },
    {
        "key": "behaviour:recency_bias",
        "title": "Recency bias",
        "body": (
            "Recency bias is the tendency to weight recent events far more heavily than "
            "longer-term evidence. After a strong month, investors extrapolate the rise and "
            "buy; after a fall, they extrapolate the decline and sell. This is why fund "
            "inflows peak near market tops and redemptions peak near bottoms. A simple "
            "defence is to look at a longer window: a five-year price chart makes a "
            "dramatic one-month move look like the ordinary noise it usually is."
        ),
    },
    {
        "key": "behaviour:herding",
        "title": "Herding",
        "body": (
            "Herding is following the crowd rather than one's own analysis, and it feels "
            "rational because widespread agreement resembles evidence. In practice, by the "
            "time an investment is widely discussed on social media or in group chats, the "
            "price has usually already moved to reflect that enthusiasm. Herding is "
            "particularly costly for new investors in India, where unregistered advisory "
            "schemes actively manufacture the appearance of consensus. The useful test: can "
            "I state why I want to own this without referring to anyone else owning it?"
        ),
    },
    {
        "key": "behaviour:action_bias",
        "title": "Action bias",
        "body": (
            "Action bias is the preference for doing something over doing nothing, even when "
            "inaction is the better choice. In investing it shows up as unnecessary trading: "
            "a portfolio that is performing adequately gets rearranged because sitting still "
            "feels passive. Every such trade costs brokerage and possibly tax, and adds a "
            "chance of being wrong. For long-term investors, the ability to hold an unchanged "
            "portfolio through an uneventful year is a skill rather than a failure of "
            "attention."
        ),
    },
]


def all_extra_chunks() -> list[dict]:
    """Corpus A material sourced from this module only."""
    return INDIAN_MARKET_CONTEXT + BEHAVIOURAL_FINANCE
