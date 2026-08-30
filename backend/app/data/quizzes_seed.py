"""Concept-tagged micro-quizzes.

Each intervention carries a ``concept`` tag, so the modal that warned you can
offer the quiz that teaches the idea behind the warning. Passing a quiz feeds
the discipline sub-score of the Readiness Score (see ``services/readiness.py``),
counted once per concept so retries cannot farm points.

Every question carries an ``explanation``. That field is the actual teaching
surface: a learner who picks the wrong option needs to know *why* it was wrong,
and "correct answer: 2" tells them nothing. Explanations are shown for right
answers too, since a lucky guess should still leave the reasoning behind.

Banks are kept at three questions so the 80% pass mark is meaningful. With one
question the only possible scores are 0% and 100%, which makes the threshold
arbitrary rather than a real check.
"""

from __future__ import annotations

QUIZZES: dict[str, list[dict]] = {
    "diversification": [
        {
            "question": "Why is putting more than 20% of a portfolio into a single stock risky?",
            "options": [
                "It limits potential upside",
                "One company's poor performance can sink the whole portfolio",
                "Brokers charge extra for concentrated bets",
                "It is illegal in India",
            ],
            "answer": 1,
            "explanation": (
                "Concentration is about damage control. If one stock is 40% of your portfolio and it "
                "falls 50%, you lose 20% of everything. Spread across eight companies, the same fall "
                "costs you closer to 6%. It does not limit your upside, and nothing about it is "
                "illegal or charged extra for."
            ),
        },
        {
            "question": "Roughly how many sectors should a beginner spread across to be reasonably diversified?",
            "options": ["1", "2", "4 to 5", "20 or more"],
            "answer": 2,
            "explanation": (
                "Four to five sectors covers most of the benefit. Beyond that the extra protection "
                "shrinks quickly while the portfolio gets harder to follow. One or two sectors leaves "
                "you exposed to a single industry-wide problem."
            ),
        },
        {
            "question": "You own four different bank stocks and nothing else. Are you diversified?",
            "options": [
                "Yes, four companies is enough",
                "No, all four move with the same sector",
                "Yes, as long as they are large companies",
                "It depends on how much cash you hold",
            ],
            "answer": 1,
            "explanation": (
                "This is the trap sector concentration sets. Companies in one industry face the same "
                "interest-rate changes and the same regulations, so they tend to fall together. Four "
                "names in one sector behaves much more like one bet than four."
            ),
        },
    ],
    "panic_selling": [
        {
            "question": "Selling stocks during a market crash usually leads to what outcome?",
            "options": [
                "Locking in losses that often recover by simply holding",
                "Higher long-term returns",
                "Avoiding all future risk",
                "Lower brokerage fees",
            ],
            "answer": 0,
            "explanation": (
                "While you hold, a fall is only a paper loss and can still reverse. Selling converts "
                "it into a real, permanent one and leaves you holding cash instead of the asset that "
                "would have recovered."
            ),
        },
        {
            "question": "Historically, after a sharp market crash, what tends to happen over a few years?",
            "options": [
                "Markets stay flat forever",
                "Markets keep falling indefinitely",
                "Markets recover and often reach new highs",
                "Markets become illegal to trade",
            ],
            "answer": 2,
            "explanation": (
                "Both 2008 and March 2020 felt unrecoverable at the time, and both were followed by "
                "recoveries to new highs. Timing is never predictable and past recoveries guarantee "
                "nothing, but the pattern is why patience is the default advice."
            ),
        },
        {
            "question": "What is the difference between an unrealised and a realised loss?",
            "options": [
                "There is no real difference",
                "Unrealised is on paper and can still recover; realised is locked in by selling",
                "Realised losses are tax-free",
                "Unrealised losses must be reported to SEBI",
            ],
            "answer": 1,
            "explanation": (
                "This distinction is the whole reason panic selling is expensive. Down 30% but still "
                "holding means nothing has actually happened to your money yet. Pressing sell is the "
                "step that makes it permanent."
            ),
        },
    ],
    "fomo": [
        {
            "question": "Buying right after a stock has run up sharply is risky because:",
            "options": [
                "You may be paying near the local top",
                "The stock is guaranteed to keep rising",
                "Brokers will refuse the order",
                "It is illegal",
            ],
            "answer": 0,
            "explanation": (
                "By the time a jump is widely discussed, most of the buying that caused it has already "
                "happened. Sharp run-ups often partly reverse, so entering right after one frequently "
                "means sitting through a fall first."
            ),
        },
        {
            "question": "A safer way to enter a fast-moving stock is to:",
            "options": [
                "Use all your savings at once",
                "Stagger purchases over time (averaging in)",
                "Only buy on social-media tips",
                "Wait for it to drop 90%",
            ],
            "answer": 1,
            "explanation": (
                "Splitting a purchase across several weeks means you are not betting everything on "
                "today's price being fair. You give up the best case of buying it all at the low, and "
                "in exchange you avoid the worst case of buying it all at the high."
            ),
        },
        {
            "question": "Which question best cuts through FOMO before you buy?",
            "options": [
                "How much has it gone up this week?",
                "Would I want to own this business if the price hadn't moved?",
                "Who else on social media is buying it?",
                "Is it the top gainer today?",
            ],
            "answer": 1,
            "explanation": (
                "This separates the business from the recent price move. If the only reason you want it "
                "is that it went up, you are reacting to the chart rather than making a decision."
            ),
        },
    ],
    "loss_aversion": [
        {
            "question": "Loss aversion describes the human tendency to:",
            "options": [
                "Feel losses more strongly than equivalent gains",
                "Always invest in losing stocks",
                "Avoid all investing",
                "Only buy after losses",
            ],
            "answer": 0,
            "explanation": (
                "Research consistently finds losing an amount hurts roughly twice as much as gaining "
                "the same amount feels good. That imbalance is what drives people to sell in panic and "
                "to cling to losers."
            ),
        },
        {
            "question": "Before selling at a big loss, a healthier first question is:",
            "options": [
                "Did the original reason for buying actually change?",
                "Has my friend sold yet?",
                "Is the market open today?",
                "Am I in a good mood?",
            ],
            "answer": 0,
            "explanation": (
                "This separates a considered decision from an emotional reaction. If the business is "
                "still sound and only the price moved, selling is reacting to the price. If the reason "
                "you bought no longer holds, selling is justified."
            ),
        },
        {
            "question": "Why is your original purchase price mostly irrelevant to the decision to hold?",
            "options": [
                "Because brokers do not record it",
                "Because the market does not know or care what you paid",
                "Because it changes daily",
                "Because taxes reset it every year",
            ],
            "answer": 1,
            "explanation": (
                "Your entry price is a fact about your history, not about the company's future. The "
                "only useful question is whether you would buy it at today's price. Anchoring on what "
                "you paid is what keeps people in positions they no longer believe in."
            ),
        },
    ],
    "long_term_thinking": [
        {
            "question": "Why does frequent trading usually hurt returns?",
            "options": [
                "It triggers fees, taxes, and bad timing",
                "It is the most profitable strategy",
                "Brokers reward it with bonuses",
                "It avoids volatility",
            ],
            "answer": 0,
            "explanation": (
                "Each trade costs brokerage, selling within a year attracts higher short-term capital "
                "gains tax in India, and every extra decision is another chance to be wrong. The costs "
                "are small individually and substantial in aggregate."
            ),
        },
        {
            "question": "Rs 1,00,000 growing at 12% a year is worth about Rs 3,10,000 after 10 years. After 20 years it is closest to:",
            "options": ["Rs 6,20,000", "Rs 9,65,000", "Rs 4,50,000", "Rs 24,00,000"],
            "answer": 1,
            "explanation": (
                "Doubling the time roughly triples the result rather than doubling it, because returns "
                "start earning returns. That gap between Rs 6.2 lakh and Rs 9.65 lakh is compounding, "
                "and the only ingredient it needs is time."
            ),
        },
        {
            "question": "Why is 'timing the market' harder than it sounds?",
            "options": [
                "It requires being right twice — when to exit and when to return",
                "Exchanges block frequent trades",
                "It is only possible with large amounts",
                "It always triggers a SEBI review",
            ],
            "answer": 0,
            "explanation": (
                "Selling out is only half the bet; you also have to choose when to buy back. Market "
                "gains also cluster into a few strong days, and missing those while in cash badly "
                "damages long-run returns."
            ),
        },
    ],
    "risk_appetite": [
        {
            "question": "What is risk appetite?",
            "options": [
                "How much volatility you are comfortable with",
                "The number of stocks you own",
                "Your annual income",
                "How often you check the market",
            ],
            "answer": 0,
            "explanation": (
                "It is the size of price swing you can sit through without being pushed into selling. "
                "It depends on both your time horizon and your temperament, which is why two people "
                "with identical incomes can have very different appetites."
            ),
        },
        {
            "question": "If your risk appetite is low, you should generally:",
            "options": [
                "Avoid concentrated positions in high-volatility stocks",
                "Only buy small-caps",
                "Only buy on margin",
                "Trade options daily",
            ],
            "answer": 0,
            "explanation": (
                "Low risk appetite does not mean avoiding shares entirely. It means keeping position "
                "sizes modest and leaning towards steadier companies, so no single holding can swing "
                "hard enough to make you abandon your plan."
            ),
        },
        {
            "question": "In investing, 'risk' most precisely refers to:",
            "options": [
                "A guarantee that you will lose money",
                "How much and how sharply prices move in either direction",
                "The chance a company commits fraud",
                "How long you plan to invest",
            ],
            "answer": 1,
            "explanation": (
                "Risk means volatility: a wider range of outcomes, both good and bad. A high-risk stock "
                "is not one destined to fall; it is one whose price moves a lot. It becomes a real "
                "problem only when the swings exceed what you can tolerate."
            ),
        },
    ],
    "cash_management": [
        {
            "question": "Why keep some cash in your portfolio?",
            "options": [
                "To buy opportunities and cover emergencies",
                "Cash always outperforms stocks",
                "It is required by law",
                "It prevents inflation",
            ],
            "answer": 0,
            "explanation": (
                "Cash is what stops you becoming a forced seller. Without it, an unexpected expense "
                "means selling whatever you hold at whatever price the market happens to offer that day."
            ),
        },
        {
            "question": "How large should an emergency fund typically be, in Indian personal-finance guidance?",
            "options": [
                "One week of expenses",
                "Three to six months of expenses",
                "Five years of expenses",
                "No emergency fund is needed if you own shares",
            ],
            "answer": 1,
            "explanation": (
                "Three to six months of expenses, held in savings or a liquid fund rather than invested. "
                "Its only job is to make sure a job loss or medical bill never forces you to sell your "
                "investments at a bad moment."
            ),
        },
        {
            "question": "What is the real cost of being 100% invested with no cash buffer?",
            "options": [
                "Higher brokerage fees",
                "You lose the flexibility to handle expenses without selling",
                "Your returns are legally capped",
                "There is no cost at all",
            ],
            "answer": 1,
            "explanation": (
                "Being fully invested looks efficient and removes your options. The cost is not a fee, "
                "it is that any cash need must be met by selling, regardless of what prices are doing "
                "at that moment."
            ),
        },
    ],
    "market_cycles": [
        {
            "question": "Markets that look easiest are usually:",
            "options": [
                "Near the top of a rally, when caution matters most",
                "At the bottom of a crash",
                "When nothing is moving",
                "After a long bear market",
            ],
            "answer": 0,
            "explanation": (
                "Confidence peaks near tops, when everyone has a winning story and buying feels "
                "obvious. It collapses near bottoms, when prices are actually lowest. Doing the "
                "comfortable thing therefore tends to mean buying high and selling low."
            ),
        },
        {
            "question": "A market fall of about 10% is called a:",
            "options": ["Crash", "Correction", "Bear market", "Depression"],
            "answer": 1,
            "explanation": (
                "A correction is roughly a 10% fall and happens about once a year. A bear market is a "
                "fall of 20% or more. Knowing the vocabulary makes these events far less alarming when "
                "they arrive, because they have names and precedents."
            ),
        },
        {
            "question": "Since you cannot reliably predict turning points, the most useful response is to:",
            "options": [
                "Invest on a fixed schedule decided while you are calm",
                "Wait in cash until the bottom is obvious",
                "Sell everything at the first 5% fall",
                "Only invest during bull markets",
            ],
            "answer": 0,
            "explanation": (
                "A schedule made in advance protects you from decisions made under stress. The bottom "
                "is only ever obvious afterwards, and waiting for certainty usually means buying back "
                "at higher prices."
            ),
        },
    ],
    "sip": [
        {
            "question": "What does SIP stand for?",
            "options": [
                "Systematic Investment Plan",
                "Stock Index Portfolio",
                "Single Investor Program",
                "Standard Interest Payout",
            ],
            "answer": 0,
            "explanation": (
                "A Systematic Investment Plan means investing a fixed amount at a fixed interval, "
                "usually monthly, regardless of what prices are doing that month."
            ),
        },
        {
            "question": "You invest Rs 6,000 monthly at unit prices of Rs 100, Rs 75 and Rs 50. Your average cost per unit is:",
            "options": [
                "Rs 75, the average of the three prices",
                "About Rs 69, lower than the average price",
                "Rs 100, the highest price",
                "Rs 50, the lowest price",
            ],
            "answer": 1,
            "explanation": (
                "You buy 60, 80 and 120 units, so 260 units for Rs 18,000, about Rs 69 each. A fixed "
                "rupee amount automatically buys more units when prices are low, which pulls your "
                "average below the simple average of the prices. That is rupee-cost averaging."
            ),
        },
        {
            "question": "The most important benefit of a SIP is:",
            "options": [
                "It guarantees a profit",
                "It removes the decision, so you keep investing during falls",
                "It eliminates all risk",
                "It is tax-free",
            ],
            "answer": 1,
            "explanation": (
                "The mathematical edge from averaging is modest. The real value is behavioural: because "
                "the contribution is automatic, you keep buying during downturns, which is exactly when "
                "most people stop and exactly when units are cheapest."
            ),
        },
    ],
    "index_funds": [
        {
            "question": "What does an index fund hold?",
            "options": [
                "The single best stock its manager can find",
                "Every company in an index, in the index's proportions",
                "Only government bonds",
                "Cash, until the manager sees an opportunity",
            ],
            "answer": 1,
            "explanation": (
                "A Nifty 50 index fund holds all fifty companies in the right weights. One purchase "
                "therefore gives you a slice of the whole index, which is why it is diversified from "
                "the moment you buy it."
            ),
        },
        {
            "question": "Over long periods, most actively managed funds compared with their index:",
            "options": [
                "Beat it comfortably",
                "Fail to beat it after fees",
                "Match it exactly",
                "Are not allowed to be compared",
            ],
            "answer": 1,
            "explanation": (
                "The majority underperform their benchmark once fees are counted. That finding, repeated "
                "across many markets and decades, is the main reason low-cost index funds are the "
                "standard recommendation for beginners."
            ),
        },
        {
            "question": "Why does a 1.5% annual fee matter so much more than it sounds?",
            "options": [
                "It is charged on every trade you make",
                "You lose the fee and all the compounding it would have earned",
                "It is deducted from your salary",
                "It rises automatically every year",
            ],
            "answer": 1,
            "explanation": (
                "Over twenty years on Rs 1,00,000 at 12%, the gap between a 1.5% and a 0.2% fee costs "
                "roughly Rs 2,00,000 of final value. You forgo the fee plus every rupee that fee would "
                "have compounded into. Fees are also the one variable you fully control."
            ),
        },
    ],
}


def quizzes_for_concept(concept: str) -> list[dict]:
    return QUIZZES.get(concept, [])


def concept_keys() -> list[str]:
    return list(QUIZZES.keys())
