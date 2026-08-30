"""The concept library — DolFin's browsable teaching content.

Why this exists: every explanation in the app used to live inside an
intervention message, which meant a learner could only encounter a concept by
*almost making the mistake first*. That is great for retention and terrible as
the only route in. A beginner who wants to understand diversification before
risking anything had nowhere to go.

Each concept links to the rule that can fire on it and the quiz that tests it,
so the three surfaces (learn → practise → verify) stay in sync.

Content rules followed here:
- Plain language. No jargon without an inline definition.
- Indian context and rupee amounts throughout.
- Educational framing only: never a recommendation to buy or sell anything.
"""

from __future__ import annotations

CONCEPTS: list[dict] = [
    {
        "key": "diversification",
        "title": "Diversification",
        "one_liner": "Spread your money around so one bad company can't sink you.",
        "difficulty": "beginner",
        "read_minutes": 3,
        "related_rules": ["concentration", "sector_overlap"],
        "quiz": "diversification",
        "body": [
            {
                "heading": "The idea in one sentence",
                "text": (
                    "Diversification means not putting all your money in one place. If you own "
                    "one stock and that company has a bad year, your whole portfolio has a bad "
                    "year. If you own eight companies across different industries, one stumble "
                    "barely dents you."
                ),
            },
            {
                "heading": "A concrete example",
                "text": (
                    "Say you have Rs 1,00,000. You put all of it into one IT company. That "
                    "company loses a big client and the stock falls 40%. You are down Rs 40,000. "
                    "Now imagine you had split it: Rs 12,500 each across eight companies in IT, "
                    "banking, pharma, FMCG and energy. The same 40% fall in that one company "
                    "costs you Rs 5,000, which is 5% of your portfolio instead of 40%."
                ),
            },
            {
                "heading": "Two kinds of concentration to watch",
                "text": (
                    "Single-stock concentration is when one company is too large a share of your "
                    "portfolio. A common rule of thumb is to keep any one stock under 20%. Sector "
                    "concentration is subtler: you might own four different companies and still be "
                    "undiversified if all four are banks. When one industry hits trouble, every "
                    "company in it usually falls together. Aim to spread across at least four or "
                    "five sectors."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "Two rules watch for this. The concentration rule warns you when a buy would "
                    "push one stock past 20% of your portfolio, and turns critical past 30%. The "
                    "sector rule warns when one sector would exceed 40%. Your Diversification "
                    "sub-score, which is 30% of your Readiness Score, is calculated from exactly "
                    "these two measures plus how many sectors you hold."
                ),
            },
        ],
        "takeaways": [
            "Keep any single stock under about 20% of your portfolio.",
            "Owning four banks is not diversified — spread across sectors, not just names.",
            "Diversification lowers how hard any single mistake can hit you.",
            "It reduces risk, not returns: you are not giving up upside by spreading out.",
        ],
        "misconception": {
            "myth": "Diversification means buying lots of stocks.",
            "reality": (
                "It means buying stocks whose fortunes are not tied together. Twenty IT companies "
                "is barely more diversified than one, because the same industry-wide problem hits "
                "all twenty at once."
            ),
        },
    },
    {
        "key": "panic_selling",
        "title": "Panic selling",
        "one_liner": "Selling because prices fell is how paper losses become real ones.",
        "difficulty": "beginner",
        "read_minutes": 4,
        "related_rules": ["panic_sell"],
        "quiz": "panic_selling",
        "body": [
            {
                "heading": "The single most expensive beginner mistake",
                "text": (
                    "Markets fall sometimes. That is normal and unavoidable. What separates "
                    "investors who do well from those who do badly is usually not stock picking "
                    "at all: it is what they do during those falls. Selling while prices are down "
                    "converts a temporary dip in value into a permanent loss of money."
                ),
            },
            {
                "heading": "Paper loss vs real loss",
                "text": (
                    "If you bought at Rs 1,000 and the price is now Rs 700, you have an unrealised "
                    "or paper loss of Rs 300. Nothing has actually happened to your money yet. If "
                    "the price recovers to Rs 1,100 next year and you still hold, that paper loss "
                    "quietly disappears. But if you sell at Rs 700, you have realised the loss. "
                    "The Rs 300 is gone for good, and you are no longer holding the thing that "
                    "would have recovered."
                ),
            },
            {
                "heading": "Why it feels so urgent",
                "text": (
                    "Losses hurt roughly twice as much as equivalent gains feel good. This is a "
                    "well-documented bias called loss aversion. During a fall your brain treats a "
                    "falling number as danger and pushes you to make it stop. Selling makes the "
                    "feeling stop immediately, which is exactly why it is such a tempting and such "
                    "an expensive move."
                ),
            },
            {
                "heading": "What history actually shows",
                "text": (
                    "Indian markets fell sharply in 2008 and again in March 2020. Both times the "
                    "fall felt like it would never end, and both times the market went on to reach "
                    "new highs. Investors who sold near the bottom locked in their losses and then "
                    "had to decide when to buy back, usually at higher prices. Investors who simply "
                    "held recovered without doing anything. Past recoveries do not guarantee future "
                    "ones, but the pattern is why patience is the default advice."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "This is what the crash simulator is for. Start a simulated crash from the "
                    "Scenarios page and your portfolio really does drop. If you then try to sell, "
                    "the panic-sell rule fires as a critical warning. Choosing 'Cancel and reflect' "
                    "records that you held, and raises your Discipline sub-score. Afterwards your "
                    "portfolio chart shows the dip and the recovery you sat through."
                ),
            },
        ],
        "takeaways": [
            "A fall in price is a paper loss; selling is what makes it permanent.",
            "Losses feel about twice as intense as gains, which is why selling feels urgent.",
            "Decide your reaction to a crash before one happens, not during.",
            "Sell because your reason for owning it changed, never because the price moved.",
        ],
        "misconception": {
            "myth": "Selling during a crash protects my money.",
            "reality": (
                "It converts a recoverable dip into a locked-in loss, and leaves you guessing when "
                "to buy back. Most people who sell in a panic buy back higher than they sold."
            ),
        },
    },
    {
        "key": "fomo",
        "title": "FOMO buying",
        "one_liner": "Buying because something already went up usually means paying the top price.",
        "difficulty": "beginner",
        "read_minutes": 3,
        "related_rules": ["fomo", "buy_during_rally"],
        "quiz": "fomo",
        "body": [
            {
                "heading": "The pattern",
                "text": (
                    "A stock jumps 20% in a week. It is suddenly all over the news and your group "
                    "chats. Buying now feels safe because the thing is clearly working. This is "
                    "fear of missing out, and it reliably leads people to buy after the gain has "
                    "already happened rather than before."
                ),
            },
            {
                "heading": "Why the timing works against you",
                "text": (
                    "By the time a price move is widely discussed, the people who were going to buy "
                    "have largely bought. Sharp run-ups often partly reverse, so entering right "
                    "after one means you frequently sit through a fall before seeing any gain. You "
                    "are buying the news of the rise, not the reason for it."
                ),
            },
            {
                "heading": "What to do instead",
                "text": (
                    "Separate the decision from the price move. Ask whether you would want to own "
                    "this business if the price had not moved at all. If you still want in, buying "
                    "in smaller instalments over several weeks means you are not betting everything "
                    "on today's price being a fair one."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "The FOMO rule checks real recent price history and fires if the stock has "
                    "risen more than 15% in about five trading days. A separate rule fires when you "
                    "buy during a simulated rally, since that is the same psychology at work."
                ),
            },
        ],
        "takeaways": [
            "A recent sharp rise is not evidence that buying now is a good idea.",
            "Ask if you'd want the stock at the old price; if not, you're chasing the move.",
            "Staggering purchases avoids betting everything on one day's price.",
        ],
        "misconception": {
            "myth": "A rising stock is a safe stock.",
            "reality": (
                "Rising prices tell you what already happened, not what happens next. The safest "
                "entry is usually the least exciting one."
            ),
        },
    },
    {
        "key": "loss_aversion",
        "title": "Loss aversion",
        "one_liner": "Losses feel about twice as strong as gains, which distorts your decisions.",
        "difficulty": "intermediate",
        "read_minutes": 3,
        "related_rules": ["loss_lock_in"],
        "quiz": "loss_aversion",
        "body": [
            {
                "heading": "The asymmetry",
                "text": (
                    "Losing Rs 5,000 feels roughly twice as bad as gaining Rs 5,000 feels good. "
                    "Because the pain is bigger than the pleasure, people take irrational steps to "
                    "avoid registering a loss, and that shows up in two opposite mistakes."
                ),
            },
            {
                "heading": "Mistake one: selling winners too early",
                "text": (
                    "A stock is up 15% and you sell to lock in the gain. Booking a profit feels "
                    "good and safe. But if the business is still doing well, you have just capped "
                    "your best outcome. Long-term returns often come from a small number of "
                    "positions held for a long time."
                ),
            },
            {
                "heading": "Mistake two: holding losers too long",
                "text": (
                    "A stock is down 30% and you refuse to sell because that would make the loss "
                    "official. So you hold a business you no longer believe in, purely to avoid "
                    "admitting the mistake. The money stays stuck in the weakest thing you own."
                ),
            },
            {
                "heading": "The test that cuts through it",
                "text": (
                    "Ignore what you paid. The market does not know or care about your purchase "
                    "price. Ask only this: knowing what I know now, would I buy this today? If yes, "
                    "hold. If no, the loss is a sunk cost and holding on will not undo it."
                ),
            },
        ],
        "takeaways": [
            "Your purchase price is irrelevant to whether the stock is worth owning now.",
            "Selling winners early caps your upside; holding losers ties up your money.",
            "Ask 'would I buy this today?' instead of 'am I up or down?'",
        ],
        "misconception": {
            "myth": "It isn't a real loss until I sell.",
            "reality": (
                "The money is already gone either way. Refusing to sell only keeps it trapped in "
                "the position you least believe in."
            ),
        },
    },
    {
        "key": "long_term_thinking",
        "title": "Long-term thinking",
        "one_liner": "Time in the market beats timing the market, mostly because of compounding.",
        "difficulty": "beginner",
        "read_minutes": 4,
        "related_rules": ["short_hold"],
        "quiz": "long_term_thinking",
        "body": [
            {
                "heading": "Compounding is the whole argument",
                "text": (
                    "Compounding means your returns start earning returns. Rs 1,00,000 growing at "
                    "12% a year becomes about Rs 3,10,000 after ten years and about Rs 9,65,000 "
                    "after twenty. The second decade adds far more than the first even though the "
                    "rate never changed. That extra growth is the reward for simply staying "
                    "invested, and it is the one advantage a beginner has automatically."
                ),
            },
            {
                "heading": "What frequent trading costs you",
                "text": (
                    "Every trade has a brokerage fee, and in India selling within a year attracts "
                    "short-term capital gains tax at a higher rate than long-term. Beyond the "
                    "direct costs, frequent trading means more decisions, and more decisions means "
                    "more chances to be wrong. DolFin charges a realistic 0.05% fee on each side "
                    "so you can watch this drag accumulate."
                ),
            },
            {
                "heading": "Why timing rarely works",
                "text": (
                    "Selling out and buying back in requires being right twice: about when to leave "
                    "and about when to return. Market gains also tend to cluster into a handful of "
                    "very good days, and missing those while sitting in cash badly damages returns. "
                    "Staying invested guarantees you are present for them."
                ),
            },
        ],
        "takeaways": [
            "Compounding does most of the work, and it needs time more than skill.",
            "Every trade costs fees and possibly higher tax; activity is not progress.",
            "Timing the market means being right twice instead of once.",
        ],
        "misconception": {
            "myth": "Good investors trade often.",
            "reality": (
                "Professional traders trade often. Long-term investors mostly wait, and historically "
                "the waiting is what pays."
            ),
        },
    },
    {
        "key": "risk_appetite",
        "title": "Risk appetite",
        "one_liner": "Take only as much volatility as you can sit through without selling.",
        "difficulty": "beginner",
        "read_minutes": 3,
        "related_rules": ["volatility_mismatch"],
        "quiz": "risk_appetite",
        "body": [
            {
                "heading": "Risk here means swinging, not losing",
                "text": (
                    "In investing, risk usually refers to volatility: how much a price moves up and "
                    "down. A high-volatility stock might swing 8% in a week in either direction. "
                    "That is not automatically bad. It only becomes a problem when the swings are "
                    "larger than you can tolerate, because then you sell at the worst moment."
                ),
            },
            {
                "heading": "Capacity and temperament are different things",
                "text": (
                    "Two questions decide your real risk appetite. How long until you need this "
                    "money? Money needed in a year should not be exposed to big swings; money for "
                    "twenty years away can be. And how will you actually behave in a 30% fall? The "
                    "highest-return portfolio you cannot hold through a crash is worse than a "
                    "calmer one you can."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "You picked a risk appetite during onboarding, and every stock in the catalogue "
                    "carries a risk level. Buying a high-risk stock on a low-risk profile triggers a "
                    "mismatch warning. The crash simulator is the honest test: it shows you how you "
                    "actually react rather than how you predicted you would."
                ),
            },
        ],
        "takeaways": [
            "Risk mostly means volatility, not guaranteed loss.",
            "Your time horizon and your temperament both cap how much you should take.",
            "A portfolio you can hold through a crash beats a better one you'll abandon.",
        ],
        "misconception": {
            "myth": "Higher risk always means higher returns.",
            "reality": (
                "Higher risk means a wider range of outcomes, including worse ones. It raises "
                "potential return, it does not promise it."
            ),
        },
    },
    {
        "key": "cash_management",
        "title": "Cash management",
        "one_liner": "Keep some cash uninvested so you are never a forced seller.",
        "difficulty": "beginner",
        "read_minutes": 3,
        "related_rules": ["cash_drain"],
        "quiz": "cash_management",
        "body": [
            {
                "heading": "Why holding cash is a position, not laziness",
                "text": (
                    "Being fully invested feels efficient, but it removes all your flexibility. If "
                    "an expense appears and you hold no cash, you must sell something, and markets "
                    "do not check your calendar first. Being forced to sell at a bad moment is "
                    "exactly the situation a cash buffer prevents."
                ),
            },
            {
                "heading": "The emergency fund comes first",
                "text": (
                    "Before investing at all, the standard guidance in India is to hold three to "
                    "six months of expenses in a savings account or liquid fund. This is not "
                    "investment money and should not be exposed to the market. Its entire job is to "
                    "mean that a job loss or medical bill never forces you to sell your investments."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "The cash-drain rule fires when a buy would push your cash below 10% of your "
                    "portfolio. It is an informational nudge rather than a block, because there are "
                    "legitimate reasons to be nearly fully invested."
                ),
            },
        ],
        "takeaways": [
            "Cash is what stops you being a forced seller at a bad price.",
            "Keep three to six months of expenses out of the market entirely.",
            "Being 100% invested is a choice with a real cost: no flexibility.",
        ],
        "misconception": {
            "myth": "Cash is wasted money because it earns nothing.",
            "reality": (
                "Cash buys you the ability to not sell at the wrong time, which is worth more than "
                "the small return you give up."
            ),
        },
    },
    {
        "key": "market_cycles",
        "title": "Market cycles",
        "one_liner": "Markets move in cycles; neither the falls nor the booms last forever.",
        "difficulty": "intermediate",
        "read_minutes": 4,
        "related_rules": ["buy_during_rally"],
        "quiz": "market_cycles",
        "body": [
            {
                "heading": "The vocabulary",
                "text": (
                    "A correction is a fall of about 10%, and these happen roughly once a year. A "
                    "bear market is a fall of 20% or more and shows up every few years. A bull "
                    "market is a sustained rise. None of these are malfunctions; they are the normal "
                    "rhythm of markets, and knowing the words makes the events much less alarming."
                ),
            },
            {
                "heading": "Sentiment flips at the extremes",
                "text": (
                    "Near the top, optimism is everywhere, everyone has a winning stock story, and "
                    "buying feels obviously right. Near the bottom, the mood is that markets are "
                    "broken and investing was a mistake. This is why doing the comfortable thing "
                    "tends to mean buying high and selling low."
                ),
            },
            {
                "heading": "What to do about it",
                "text": (
                    "You cannot predict turning points reliably, so do not try. What helps is "
                    "deciding your plan while you are calm, investing on a schedule rather than on "
                    "a feeling, and treating your own excitement or dread as information about your "
                    "emotional state rather than about the market."
                ),
            },
        ],
        "takeaways": [
            "Corrections are annual, bear markets are periodic; both are normal.",
            "Confidence peaks near tops and collapses near bottoms.",
            "A schedule protects you from your own mood better than a forecast does.",
        ],
        "misconception": {
            "myth": "A crash means something is fundamentally broken.",
            "reality": (
                "Falls are a routine feature of markets. Every past Indian market decline has so far "
                "been followed by a recovery to new highs, though timing is never predictable."
            ),
        },
    },
    {
        "key": "sip",
        "title": "SIP and rupee-cost averaging",
        "one_liner": "Investing a fixed amount on a schedule removes timing from the decision.",
        "difficulty": "beginner",
        "read_minutes": 4,
        "related_rules": [],
        "quiz": "sip",
        "body": [
            {
                "heading": "What a SIP is",
                "text": (
                    "A Systematic Investment Plan means investing a fixed amount at a fixed "
                    "interval, usually monthly, regardless of what prices are doing. Rs 5,000 on the "
                    "first of every month, every month, whether the market is up or down."
                ),
            },
            {
                "heading": "Rupee-cost averaging, with numbers",
                "text": (
                    "Because the amount is fixed, you automatically buy more units when prices are "
                    "low and fewer when prices are high. Invest Rs 6,000 monthly at unit prices of "
                    "Rs 100, Rs 75 and Rs 50 and you buy 60, 80 and 120 units: 260 units for "
                    "Rs 18,000, an average of about Rs 69 per unit. That is below the Rs 75 average "
                    "of the three prices, and you did nothing clever to get it."
                ),
            },
            {
                "heading": "The real benefit is behavioural",
                "text": (
                    "The mathematical edge is modest. The genuine value is that a SIP removes the "
                    "decision. You never have to judge whether today is a good day to invest, which "
                    "means you keep investing during downturns, which is precisely when most people "
                    "stop and when units are cheapest."
                ),
            },
            {
                "heading": "Practising it here",
                "text": (
                    "The catalogue includes index-tracking funds you can buy like any other symbol. "
                    "Buying a fixed rupee amount of one every simulated month, especially while a "
                    "crash scenario is running, is the closest thing to real SIP practice: the point "
                    "is to feel what it is like to keep buying while prices fall."
                ),
            },
        ],
        "takeaways": [
            "A fixed rupee amount buys more units when prices are low, automatically.",
            "The main benefit is removing the decision, not beating the market.",
            "SIPs work because they keep you investing during the falls.",
        ],
        "misconception": {
            "myth": "I should wait for the market to drop before starting a SIP.",
            "reality": (
                "Waiting to time the start recreates the exact problem a SIP is designed to remove. "
                "Starting and continuing matters far more than the entry date."
            ),
        },
    },
    {
        "key": "index_funds",
        "title": "Index funds and ETFs",
        "one_liner": "Buy the whole market in one purchase instead of picking winners.",
        "difficulty": "beginner",
        "read_minutes": 4,
        "related_rules": [],
        "quiz": "index_funds",
        "body": [
            {
                "heading": "What an index fund is",
                "text": (
                    "An index is a basket of companies used to represent a market. The Nifty 50 is "
                    "India's fifty largest listed companies. An index fund simply holds all of them "
                    "in the right proportions. Buying one unit gives you a slice of all fifty at "
                    "once, so you are diversified from your very first purchase."
                ),
            },
            {
                "heading": "Passive versus active",
                "text": (
                    "An active fund employs a manager who tries to beat the index by choosing "
                    "stocks, and charges more for the attempt. A passive index fund just tracks the "
                    "index and charges very little. Over long periods the majority of active funds "
                    "fail to beat their index after fees, which is why index funds are the standard "
                    "recommendation for beginners."
                ),
            },
            {
                "heading": "Why fees matter more than they look",
                "text": (
                    "A 1.5% annual fee versus 0.2% sounds like a rounding error. Over twenty years "
                    "on Rs 1,00,000 at 12% growth, that gap costs roughly Rs 2,00,000 in final "
                    "value, because you lose the compounding on every fee you paid as well as the "
                    "fee itself. Fees are the one variable you fully control."
                ),
            },
            {
                "heading": "Where you'll meet this in DolFin",
                "text": (
                    "The catalogue contains index ETFs alongside individual stocks. Because they "
                    "hold many companies, DolFin treats them as their own diversified sector, so "
                    "buying one does not trigger the same concentration warnings a single stock does."
                ),
            },
        ],
        "takeaways": [
            "One index fund purchase gives you instant diversification.",
            "Most active funds fail to beat their index after fees over the long run.",
            "Small fee differences compound into very large amounts over decades.",
        ],
        "misconception": {
            "myth": "Index funds are only for people who don't understand investing.",
            "reality": (
                "They are the default recommendation of most finance research precisely because "
                "beating the market consistently is extremely hard, even for professionals."
            ),
        },
    },
]


# ---------------------------------------------------------------------------
# Glossary — short definitions for inline tooltips.
#
# Every term the UI shows a beginner should be explainable without leaving the
# page. Definitions are deliberately one or two sentences: a tooltip that needs
# scrolling has failed at its job.
# ---------------------------------------------------------------------------
GLOSSARY: dict[str, str] = {
    "share": (
        "One unit of ownership in a company. Owning 10 shares of a company with 1,000 shares "
        "means you own 1% of it."
    ),
    "stock": "Another word for shares in a company, used to talk about the company's shares generally.",
    "portfolio": "Everything you hold together: all your shares plus any uninvested cash.",
    "nse": (
        "National Stock Exchange, India's largest stock exchange. Symbols on it carry a .NS "
        "suffix in DolFin."
    ),
    "bse": "Bombay Stock Exchange, India's other main exchange and the oldest in Asia.",
    "nifty_50": "An index of India's 50 largest listed companies, used as a summary of the market.",
    "sector": (
        "The industry a company operates in, such as IT, Banking or Pharma. Companies in the same "
        "sector tend to rise and fall together."
    ),
    "avg_cost": (
        "The average price you paid per share across all your purchases of it. Buy 10 at Rs 100 "
        "and 10 at Rs 120 and your average cost is Rs 110."
    ),
    "market_value": "What your holding is worth right now: current price multiplied by quantity.",
    "cost_basis": "The total amount you originally paid for a holding, including all purchases.",
    "unrealised_pnl": (
        "Profit or loss on something you still own. It moves with the price and is not actual money "
        "until you sell. Also called a paper gain or paper loss."
    ),
    "realised_pnl": (
        "Profit or loss that became real when you sold. Unlike unrealised P&L, this amount is locked "
        "in and cannot change."
    ),
    "diversification": (
        "Spreading money across different companies and sectors so one bad outcome cannot damage "
        "everything you own."
    ),
    "concentration": (
        "How much of your portfolio sits in a single stock. Above roughly 20% in one name is usually "
        "considered concentrated."
    ),
    "volatility": (
        "How much a price swings up and down. High volatility means larger moves in both directions, "
        "not necessarily losses."
    ),
    "risk_appetite": "How much price swinging you are willing and able to sit through without selling.",
    "correction": "A market fall of around 10%. These happen roughly once a year and are normal.",
    "bear_market": "A market fall of 20% or more, typically occurring every few years.",
    "bull_market": "A sustained period of rising prices.",
    "drawdown": "The fall from a peak to a low, expressed as a percentage. A 30% drawdown means prices fell 30% from their high.",
    "brokerage_fee": (
        "What a broker charges to execute your trade. DolFin simulates 0.05% per side, similar to an "
        "Indian discount broker."
    ),
    "sip": (
        "Systematic Investment Plan: investing a fixed amount at fixed intervals, usually monthly, "
        "regardless of price."
    ),
    "rupee_cost_averaging": (
        "The effect of a fixed investment amount buying more units when prices are low and fewer when "
        "they are high."
    ),
    "index_fund": (
        "A fund that holds every company in an index in the correct proportions, giving broad "
        "diversification in a single purchase."
    ),
    "etf": (
        "Exchange Traded Fund: a fund you buy and sell on the exchange exactly like a share. Most "
        "ETFs track an index."
    ),
    "expense_ratio": (
        "The annual fee a fund charges, as a percentage of your investment. Lower is better, and small "
        "differences compound into large amounts."
    ),
    "large_cap": "A large, well-established company. Generally less volatile than smaller companies.",
    "mid_cap": "A medium-sized company. Typically more volatile than large caps with more room to grow.",
    "small_cap": "A smaller company. The most volatile of the three bands.",
    "paper_trading": (
        "Practising with simulated money and real prices, so mistakes cost nothing. This is what all "
        "of DolFin is."
    ),
    "emergency_fund": (
        "Three to six months of expenses kept in savings, not invested, so an unexpected cost never "
        "forces you to sell."
    ),
    "loss_aversion": (
        "The tendency for losses to feel roughly twice as intense as equivalent gains, which pushes "
        "people into poor decisions."
    ),
    "compounding": (
        "When your returns start earning returns of their own. It is the main reason time in the "
        "market matters so much."
    ),
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------
_BY_KEY = {c["key"]: c for c in CONCEPTS}


def all_concepts(*, summary: bool = True) -> list[dict]:
    """Every concept. ``summary=True`` omits the long body for list views."""
    if not summary:
        return list(CONCEPTS)
    return [
        {
            "key": c["key"],
            "title": c["title"],
            "one_liner": c["one_liner"],
            "difficulty": c["difficulty"],
            "read_minutes": c["read_minutes"],
            "quiz": c.get("quiz"),
            "related_rules": c.get("related_rules", []),
        }
        for c in CONCEPTS
    ]


def get_concept(key: str) -> dict | None:
    return _BY_KEY.get(key)


def concept_for_rule(rule_id: str) -> dict | None:
    """Find the concept a given intervention rule teaches."""
    for c in CONCEPTS:
        if rule_id in c.get("related_rules", []):
            return c
    return None


def glossary_terms() -> list[dict]:
    return [
        {"term": k, "label": k.replace("_", " ").title(), "definition": v}
        for k, v in sorted(GLOSSARY.items())
    ]
