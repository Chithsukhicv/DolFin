# Requirements Document

## Introduction

DolFin is an AI-assisted behavioural investing simulator for first-time Indian investors. Today the platform's intelligence is almost entirely deterministic: nine threshold-based rules in `backend/app/services/interventions.py` detect risky trades, and Google Gemini is used in exactly one place (`backend/app/services/coach.py`) to rephrase those rule messages in friendlier language. Every other surface — the learning path, the quizzes, the readiness score, the reflection capture — is a fixed rule, a lookup, or a hardcoded list.

This feature adds an **AI Reasoning Layer** on top of the existing deterministic engine. The layer contributes judgment that rules cannot express: correlated exposure across sectors, goal-horizon mismatch, repeat behavioural patterns across time, evaluation of free-text reasoning, and grounded free-form question answering.

The layer is **additive, not a replacement**. The nine rules remain the sole detection mechanism and the sole input to scoring, for three reasons: the rules are arithmetic comparisons that a language model would sometimes compute wrongly; the Investment Readiness Score counts heeded versus ignored warnings, so identical trades must produce identical warnings; and 140 existing unit tests assert exact rule-firing behaviour. The architecture is therefore **deterministic guardrails (detection) + AI reasoning layer (judgment)**, with a hard boundary between them enforced by source flagging.

Because a general-purpose language model has no finance-specific, India-specific, or learner-specific knowledge, all AI features are grounded through **Retrieval-Augmented Generation (RAG)** over two corpora: a curated finance knowledge base (Corpus A) and the individual learner's own behavioural record (Corpus B).

### Scope of this document

Seven AI features, the two-corpus RAG pipeline that grounds them, and the non-functional constraints (degradation, latency, cost, prompt safety, prompt injection, hallucination control, determinism boundary, testability) that keep the additions safe and academically defensible.

### Out of scope

- Replacing or modifying any of the nine deterministic rules.
- Changing the Readiness Score formula, weights, or graduation threshold.
- Introducing real authentication (`user_id` remains a request-body parameter; see Requirement 11).
- Fine-tuning or self-hosting a language model.

## Glossary

### AI and retrieval terms

- **LLM (Large Language Model)**: A general-purpose text generation model. In DolFin this is Google Gemini, accessed through the `google-generativeai` client with model name taken from `settings.gemini_model` (currently `gemini-1.5-flash`).
- **RAG (Retrieval-Augmented Generation)**: A technique in which relevant source text is retrieved from a document collection and inserted into the prompt before generation, so the model answers from supplied evidence rather than from its training data alone.
- **Chunk**: One retrievable unit of source text, sized to fit in a prompt alongside other chunks. A concept article section, a single glossary definition, one quiz explanation, or one summarised behavioural fact each form one chunk.
- **Embedding**: A fixed-length numeric vector representing the meaning of a chunk, such that chunks with similar meaning have vectors close together under a distance measure.
- **Retrieval**: Selecting the top-K chunks most relevant to a query, ranked by similarity between the query representation and each chunk's representation.
- **Grounding**: Constraining a generated answer to information present in the retrieved chunks and in the structured application data supplied in the prompt.
- **Hallucination**: A generated statement that is not supported by the retrieved chunks or the supplied structured data, presented as if it were fact.
- **Citation**: A machine-readable reference attached to a generated answer that names the corpus, chunk identifier, and human-readable source title supporting a statement.
- **Corpus A**: The curated knowledge base. Static or semi-static, shared by all learners. Contents listed in Requirement 9.
- **Corpus B**: The learner's own behavioural record. Per-user and live. Contents listed in Requirement 10.
- **Top-K**: The number of highest-ranked chunks passed into a prompt.
- **Relevance floor**: The minimum similarity score a retrieved chunk must reach to be treated as usable evidence.

### DolFin system components (existing)

- **Intervention_Engine**: `backend/app/services/interventions.py`. The nine deterministic pre-trade rules. Produces `Intervention` records with `rule_id`, `severity`, `title`, `message`, `concept`, `context`.
- **Readiness_Engine**: `backend/app/services/readiness.py`. Computes the Investment Readiness Score from five weighted sub-scores (diversification 0.30, discipline 0.30, goal_alignment 0.15, autonomy 0.15, engagement 0.10), with graduation at 80.0 and an evidence-confidence ramp.
- **Coach**: `backend/app/services/coach.py`. Wraps the LLM to rephrase fired interventions; falls back to `_offline_message` when no API key is present.
- **Path_Planner**: `backend/app/services/learning_path.py`. Currently returns eight hardcoded steps, identical for every learner.
- **Quiz_Engine**: `backend/app/services/quizzes.py`. Scores attempts against the 30 seeded questions; `PASS_THRESHOLD_PCT` is 80.0.
- **Market_Service**: `backend/app/services/market.py`. Provides live quotes and OHLCV history, cached in `prices.db`.
- **Intervention log**: A row in `intervention_logs`, written at preview time with a `preview_id` and `user_action='pending'`, later resolved to `'heeded'` or `'ignored'`. Only `'ignored'` rows produce Readiness Score penalties.
- **Heed rate**: For a learner, the count of resolved intervention logs with `user_action='heeded'` divided by the count with `user_action` in (`'heeded'`, `'ignored'`).

### DolFin system components (introduced by this feature)

- **AI_Reasoning_Layer**: The collective name for the seven AI capabilities and the RAG pipeline described in this document.
- **LLM_Gateway**: The single component through which every LLM call passes. Owns prompt assembly, the shared safety constraint block, timeouts, retry policy, request budgeting, caching, and the availability check.
- **Indexer**: The component that converts source material into chunks with embeddings and stores them for retrieval.
- **Retriever**: The component that, given a query and a user identifier, returns ranked chunks from Corpus A, Corpus B, or both.
- **Risk_Reviewer**: The second-tier AI portfolio reviewer (Requirement 2).
- **Reflection_Analyzer**: The component that evaluates a learner's free-text reason for cancelling a trade (Requirement 4).
- **Pattern_Analyzer**: The component that names behavioural patterns across a learner's whole history (Requirement 5).
- **Quiz_Generator**: The component that produces adaptive quiz questions (Requirement 8).
- **Chatbot**: The grounded free-form question-answering component (Requirement 7).
- **AI finding**: A single advisory observation produced by the AI_Reasoning_Layer, carrying `source='ai'`, a title, a body, a severity label, a confidence label, and citations.
- **Rule finding**: An `Intervention` produced by the Intervention_Engine, carrying `source='rule'`.
- **Deterministic fallback**: The output a component produces when the LLM is unavailable, unconfigured, over budget, timed out, or filtered. Fallbacks are computed from application data with no network call.

## Requirements

### Requirement 1: Determinism boundary and source flagging

**User Story:** As a learner, I want my Investment Readiness Score to mean the same thing every time I look at it, so that the number reflects my habits rather than variation in a language model's output.

This is the load-bearing safety requirement of the whole feature. AI findings are advisory and visible; they never move the score.

#### Acceptance Criteria

1. THE AI_Reasoning_Layer SHALL attach the field `source` with the literal value `"ai"` to every finding, message, question, and answer the AI_Reasoning_Layer emits.
2. THE Intervention_Engine SHALL attach the field `source` with the literal value `"rule"` to every `Intervention` the Intervention_Engine emits.
3. THE Readiness_Engine SHALL compute all five sub-scores using only records where `source` equals `"rule"`.
4. THE AI_Reasoning_Layer SHALL persist AI findings in storage that is separate from the `intervention_logs` table.
5. THE AI_Reasoning_Layer SHALL leave the `user_action` lifecycle field of every `intervention_logs` row unmodified.
6. WHEN an AI finding is displayed alongside rule findings, THE Frontend SHALL render a visible label that identifies the finding as an AI observation that does not affect the Investment Readiness Score.
7. WHERE a learner's `preview_id` produced both rule findings and AI findings, THE Intervention_Engine SHALL resolve only the rule findings to `"heeded"` or `"ignored"`.
8. FOR ALL learner states, THE Readiness_Engine SHALL return identical `score` and `breakdown` values when invoked twice with no intervening database write (determinism invariant).
9. THE Backend SHALL pass the 140 existing pytest unit tests with their assertions unmodified after the AI_Reasoning_Layer is added.
10. THE AI_Reasoning_Layer SHALL leave the nine `rule_id` values, their firing thresholds, and their severity assignments unchanged.

---

### Requirement 2: AI portfolio risk review (second-tier reviewer)

**User Story:** As a learner previewing a trade, I want a reviewer that looks at my whole portfolio and my goal and tells me what the nine rules did not check, so that I learn about risks that thresholds cannot express.

#### Acceptance Criteria

1. WHEN a request to `/portfolio/preview` completes rule evaluation, THE Risk_Reviewer SHALL receive the portfolio snapshot, the proposed trade, the learner's active goal, the learner's risk appetite, and the rule findings that fired.
2. THE Risk_Reviewer SHALL return between 0 and 3 AI findings per review.
3. THE Risk_Reviewer SHALL be capable of raising findings in the following categories: correlated exposure across nominally different sectors, aggregate volatility concentration despite sector spread, goal-horizon mismatch between the goal's `horizon_months` and the risk profile of the resulting portfolio, and repeat-trade patterns in the same symbol following realised losses.
4. THE Risk_Reviewer SHALL exclude any finding that restates a rule finding already present in the same preview response.
5. THE Risk_Reviewer SHALL attach to each finding a `severity` label of `"info"`, `"warn"`, or `"critical"` for display ordering only.
6. THE Risk_Reviewer SHALL set the `blocking` field of the preview response independently of AI findings, deriving `blocking` solely from rule findings with severity `"critical"`.
7. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Risk_Reviewer SHALL return an empty list of AI findings and THE preview response SHALL remain complete and valid.
8. THE Risk_Reviewer SHALL ground each finding in the structured portfolio data supplied in the prompt and SHALL cite the Corpus A concept that explains the risk named.
9. WHEN the Risk_Reviewer produces a finding, THE AI_Reasoning_Layer SHALL persist the finding with the originating `preview_id`, the learner identifier, and the creation timestamp.

---

### Requirement 3: Context-aware coaching

**User Story:** As a learner who has made the same mistake three times, I want the coaching message to acknowledge that history, so that the advice reads as a response to me rather than a description of a rule.

Reference case: two learners both trip `concentration` at 25%. Learner A has 3 trades and has panic-sold twice. Learner B has 40 trades across 8 sectors and heeded 9 of the last 10 warnings. Today both receive an identical message.

#### Acceptance Criteria

1. WHEN the Coach builds a prompt for a fired rule, THE Coach SHALL include the learner's trade count, the learner's heed rate for the `concept` attached to the fired rule, the count of prior firings of the same `rule_id` for that learner, the learner's goal horizon in months, the learner's `risk_appetite`, and the learner's `persona`.
2. WHERE the learner has ignored the same `rule_id` two or more times previously, THE Coach SHALL produce a message that references the repetition.
3. WHERE the learner's heed rate for the fired `concept` is 0.80 or higher, THE Coach SHALL produce a message that acknowledges the learner's track record before restating the concern.
4. THE Coach SHALL derive the decision of which rules fired solely from the Intervention_Engine output.
5. THE Coach SHALL produce a message of 120 words or fewer.
6. THE Coach SHALL produce the message in the language identified by the learner's `users.language` value for the values `"en"` and `"hi"`.
7. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Coach SHALL return the existing deterministic message and THE Coach SHALL set `mode` to `"offline"`.
8. WHILE the LLM_Gateway reports the LLM as available, THE Coach SHALL set `mode` to a generated-content value and SHALL return generated content.
9. THE Coach SHALL preserve the existing response shape with the keys `mode` and `message`.

---

### Requirement 4: Reflection analysis

**User Story:** As a learner who backs out of a trade, I want to type why in my own words and get a response to my actual reasoning, so that I find out whether my thinking was sound rather than just being credited for cancelling.

Rules cannot read free text at all, so this capability is entirely AI-provided. The `reflections.reason` column already exists and is currently written with a hardcoded string from the frontend.

#### Acceptance Criteria

1. WHEN a learner selects "Cancel & reflect", THE Frontend SHALL present a free-text input for the learner's reason.
2. THE Frontend SHALL submit the learner-typed text as the `reason` field of the reflection payload.
3. WHEN a reflection is created with a non-empty learner-typed `reason`, THE Reflection_Analyzer SHALL classify the reasoning as `"sound"`, `"partly_sound"`, or `"prediction_based"`.
4. THE Reflection_Analyzer SHALL return a response message that names which behavioural concept the learner's stated reasoning demonstrates or contradicts.
5. WHEN the learner's reason states an unchanged business fundamental as the basis for holding, THE Reflection_Analyzer SHALL classify the reasoning as `"sound"`.
6. WHEN the learner's reason states a future price movement as the basis for the decision, THE Reflection_Analyzer SHALL classify the reasoning as `"prediction_based"` and THE Reflection_Analyzer SHALL return a message that distinguishes a prediction from a reason.
7. THE Reflection_Analyzer SHALL cite at least one Corpus A chunk in each response.
8. THE Reflection_Analyzer SHALL leave the count of warnings resolved to `"heeded"` by the reflection unchanged, regardless of the classification assigned.
9. IF the learner submits an empty or whitespace-only reason, THEN THE Reflection_Analyzer SHALL skip analysis and THE reflection SHALL be stored with the classification field absent.
10. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Reflection_Analyzer SHALL store the learner's reason text and SHALL return the deterministic acknowledgement currently produced.
11. IF storing the learner's reason text fails, THEN THE Reflection_Analyzer SHALL return an error response and SHALL omit the acknowledgement, so that a stored reason and a returned acknowledgement always occur together.
12. THE Reflection_Analyzer SHALL persist the classification and the response message against the reflection record.

---

### Requirement 5: Behavioural pattern analysis

**User Story:** As a learner, I want the coach page to tell me the pattern in my own behaviour over weeks, so that I can see what I keep doing rather than being told about one trade at a time.

Target output quality: "You've sold four times in three weeks, and every single time it was within two days of a 5% dip. Your buys are well diversified — the problem isn't your stock picking, it's that small dips make you flinch."

#### Acceptance Criteria

1. WHEN a learner opens the `/coach` page, THE Pattern_Analyzer SHALL return a behavioural analysis for that learner.
2. THE Pattern_Analyzer SHALL construct the analysis input from the learner's transactions, intervention logs with `user_action` outcomes, quiz attempts, reflections, portfolio snapshots, active scenario, and goals.
3. THE Pattern_Analyzer SHALL name between 1 and 3 patterns, each with a pattern label, a supporting evidence list, and a suggested next action.
4. THE Pattern_Analyzer SHALL include in each pattern's evidence list at least one countable fact drawn from the learner's records, stated with the count and the time window observed.
5. WHERE the learner's records contain a `concept` with a heed rate of 0.50 or higher, THE Pattern_Analyzer SHALL name at least one behaviour the learner performs well.
6. IF the learner has fewer than 3 transactions and fewer than 1 resolved intervention log, THEN THE Pattern_Analyzer SHALL return a message stating that more activity is needed and SHALL make no LLM call.
7. THE Pattern_Analyzer SHALL persist each analysis with the learner identifier, the generation timestamp, and the record counts the analysis was computed from.
8. WHEN a persisted analysis exists for the learner and the learner's transaction count, resolved intervention count, quiz attempt count, and reflection count are all unchanged since that analysis, THE Pattern_Analyzer SHALL return the persisted analysis and SHALL make no LLM call.
9. IF the LLM_Gateway reports the LLM as unavailable AND the learner has 3 or more transactions or 1 or more resolved intervention logs, THEN THE Pattern_Analyzer SHALL return a deterministic summary computed from counted rule firings, heed rate, and holding spread.
10. IF the learner has fewer than 3 transactions and fewer than 1 resolved intervention log, THEN THE Pattern_Analyzer SHALL return the more-activity-needed message defined in criterion 6, whether or not the LLM_Gateway reports the LLM as available.
11. THE Pattern_Analyzer SHALL flag every returned pattern with `source` set to `"ai"`.

---

### Requirement 6: Adaptive learning path

**User Story:** As a learner who keeps panic-selling but diversifies well, I want the next step suggested to me to address panic-selling, so that the path teaches what I actually need instead of a fixed sequence.

The current Path_Planner returns eight hardcoded steps identical for every learner.

#### Acceptance Criteria

1. WHEN a learner requests the learning path, THE Path_Planner SHALL order the returned steps by the learner's demonstrated weaknesses, measured as the count of ignored intervention logs per `concept` and the count of failed quiz attempts per `concept`.
2. THE Path_Planner SHALL return a `next_step` that targets the `concept` with the highest ignored-warning count among concepts the learner has not yet passed a quiz on.
3. THE Path_Planner SHALL include a rationale string on each step that names the learner evidence the step was selected from.
4. THE Path_Planner SHALL retain the existing step fields `key`, `title`, `description`, `done`, `href`, and `action` on every returned step.
5. THE Path_Planner SHALL compute the `done` state of every step deterministically from application data, without an LLM call.
6. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Path_Planner SHALL return the existing eight steps in the existing fixed order.
7. IF computing the ordered eight steps raises an exception, THEN THE Path_Planner SHALL return the eight step definitions with every `done` field set to `false` and THE Path_Planner SHALL set `next_step` to the first step.
8. THE Path_Planner SHALL restrict AI-selected steps to concepts present in Corpus A.
9. THE Path_Planner SHALL return the `completed`, `total`, `percent`, `next_step`, and `all_done` fields with the same semantics as the current implementation.

---

### Requirement 7: Grounded RAG chatbot

**User Story:** As a learner, I want to ask questions in my own words — what a P/E ratio is, why markets crashed in 2020, why DolFin warned me about a particular trade — and get answers grounded in the platform's material and my own record, so that the answers are specific rather than generic.

#### Acceptance Criteria

1. WHEN a learner submits a question, THE Chatbot SHALL retrieve chunks from Corpus A and from that learner's Corpus B before generating an answer.
2. THE Chatbot SHALL return an answer containing at least one citation naming the corpus, the chunk identifier, and the source title for each corpus drawn from.
3. WHEN a question refers to the learner's own trades, warnings, score, holdings, or reflections, THE Chatbot SHALL answer using retrieved Corpus B chunks belonging to that learner.
4. WHEN a question refers to a current or historical price of a catalogue symbol, THE Chatbot SHALL include quote or history data obtained from the Market_Service in the prompt and SHALL cite the retrieval timestamp of that data.
5. IF the highest similarity score among retrieved chunks is below the relevance floor, THEN THE Chatbot SHALL return a message stating that DolFin has no grounded material for the question and SHALL list up to 3 Corpus A topics that are available.
6. THE Chatbot SHALL persist each question and each answer against a chat session belonging to the asking learner.
7. THE Chatbot SHALL retain the preceding 6 messages of the active chat session in the prompt as conversation context.
8. THE Chatbot SHALL answer in the language identified by the learner's `users.language` value for the values `"en"` and `"hi"`.
9. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Chatbot SHALL return the top 3 retrieved Corpus A chunks as a reading list with their source titles and SHALL state that generated answers are unavailable.
10. THE Chatbot SHALL restrict answers to the retrieved chunks, the supplied structured learner data, and the supplied market data.

---

### Requirement 8: AI-generated adaptive quizzes

**User Story:** As a learner who fails the loss-aversion quiz twice, I want new questions on that concept rather than the same three, so that I am tested on understanding instead of recall of one question set.

#### Acceptance Criteria

1. WHEN a learner requests a quiz for a concept the learner has previously failed, THE Quiz_Generator SHALL produce questions targeting that concept.
2. THE Quiz_Generator SHALL produce each question with a question string, exactly 4 options, exactly 1 correct option index, and an explanation string.
3. THE Quiz_Generator SHALL ground each generated question in retrieved Corpus A chunks for the target concept.
4. THE Quiz_Engine SHALL score generated quizzes with the existing pass threshold of 80.0 percent.
5. THE Quiz_Engine SHALL record a passed generated quiz as a `QuizAttempt` with the existing `concept` value, so that the Readiness_Engine continues to count each distinct concept once.
6. THE Quiz_Generator SHALL apply a quality check to every generated question that verifies the question text is 200 characters or fewer, that the 4 options are mutually distinct, that no option text exceeds 120 characters, that the explanation is 20 characters or longer, and that the question text names or paraphrases the target concept.
7. IF a generated question fails structural validation or fails the quality check, THEN THE Quiz_Generator SHALL discard the question and SHALL substitute a seeded question for the same concept.
8. IF no seeded question exists for the requested concept and every generated question is discarded, THEN THE Quiz_Engine SHALL return HTTP 422 with a message naming the concept for which no question is available.
9. IF the LLM_Gateway reports the LLM as unavailable, THEN THE Quiz_Engine SHALL serve the existing seeded questions for the requested concept.
10. THE Quiz_Generator SHALL exclude any question whose text duplicates a seeded question already answered correctly by that learner.
11. THE Quiz_Generator SHALL persist generated questions with their concept, their source citations, and the generation timestamp.

---

### Requirement 9: Corpus A — curated knowledge base

**User Story:** As a learner, I want answers drawn from DolFin's own teaching material and from Indian-market reality, so that explanations match what the platform taught me and the market I actually invest in.

#### Acceptance Criteria

1. THE Indexer SHALL index the 10 concept articles in `backend/app/data/concepts_seed.py`, chunked by article section, with the concept key and section heading retained as metadata.
2. THE Indexer SHALL index each of the 33 glossary terms in `concepts_seed.GLOSSARY` as one chunk.
3. THE Indexer SHALL index each of the 30 quiz explanations in `backend/app/data/quizzes_seed.py` as one chunk, with the concept key retained as metadata.
4. THE Indexer SHALL index one chunk per deterministic rule, containing the `rule_id`, the threshold the rule applies, the severity assigned, and the reason the rule exists.
5. THE Indexer SHALL index Indian-market context material covering SEBI investor-education guidance, NSE and BSE market basics, short-term and long-term capital gains treatment for listed equity in India, and emergency-fund norms.
6. THE Indexer SHALL index behavioural-finance material covering loss aversion, recency bias, the disposition effect, and herding.
7. THE Indexer SHALL record for every Corpus A chunk the fields `corpus` set to `"A"`, `chunk_id`, `source_title`, `source_reference`, and `indexed_at`.
8. THE Indexer SHALL set `owner_user_id` to null on every Corpus A chunk.
9. WHEN Corpus A source material changes, THE Indexer SHALL re-index the affected chunks through a single repeatable command that performs every insert, update, and delete required, so that no manual database edit is needed for any re-indexing scenario.
10. WHEN a re-index updates a chunk whose source section is unchanged in identity, THE Indexer SHALL update the existing chunk row in place and SHALL preserve the existing `chunk_id`.
11. WHEN a re-index finds a chunk whose source section no longer exists, THE Indexer SHALL delete that chunk row.
12. WHEN the Indexer runs twice over unchanged Corpus A source material, THE Indexer SHALL produce the same set of `chunk_id` values.

---

### Requirement 10: Corpus B — the learner's own behavioural record

**User Story:** As a learner, I want the AI to know what I have actually done, so that its answers describe my behaviour instead of investors in general.

Corpus B is the grounding that exists in no language model's training data, and it is what makes answers specific. It is also the highest-risk data in the system, because it is per-user.

#### Acceptance Criteria

1. THE Indexer SHALL derive Corpus B chunks for a learner from that learner's transactions, holdings, intervention logs with `user_action` outcomes, per-concept heed rates, quiz attempts, reflections, portfolio snapshots, active scenario, and goals.
2. THE Indexer SHALL set `owner_user_id` to the learner's identifier and `corpus` to `"B"` on every Corpus B chunk.
3. THE Retriever SHALL restrict every Corpus B candidate set to chunks whose `owner_user_id` equals the requesting learner's identifier.
4. IF a retrieved chunk carries `corpus` equal to `"B"` and an `owner_user_id` that differs from the requesting learner's identifier, THEN THE Retriever SHALL discard the chunk and SHALL write a security event to the application log.
5. THE Indexer SHALL refresh a learner's Corpus B chunks when that learner's transaction, intervention-log, quiz-attempt, or reflection records change.
6. THE Indexer SHALL exclude the learner's email address and display name from every Corpus B chunk body.
7. WHEN a learner record is deleted, THE Indexer SHALL delete every Corpus B chunk carrying that learner's `owner_user_id`.
8. WHERE a learner record exists in a deactivated or suspended state, THE Indexer SHALL retain that learner's Corpus B chunks.
9. THE Indexer SHALL state each Corpus B chunk as a factual summary with counts, dates, symbols, and outcomes, and SHALL exclude interpretation from the chunk body.

---

### Requirement 11: Retrieval, ranking, and per-user scoping

**User Story:** As a developer, I want retrieval to be a single audited path with per-user scoping enforced in one place, so that no AI feature can accidentally leak one learner's record into another learner's prompt.

DolFin has no authentication today: `user_id` arrives in the request body. That makes single-point scoping enforcement the only defence available.

#### Acceptance Criteria

1. THE Retriever SHALL accept a query string, a learner identifier, a corpus selector, and a Top-K value on every retrieval call.
2. THE Retriever SHALL return each result with its `chunk_id`, `corpus`, `source_title`, chunk text, and similarity score.
3. THE Retriever SHALL rank results by similarity between the query representation and each chunk representation, in descending order.
4. THE Retriever SHALL return at most Top-K results, with a default Top-K of 6 and a maximum Top-K of 12.
5. THE Retriever SHALL exclude results whose similarity score falls below the configured relevance floor.
6. THE AI_Reasoning_Layer SHALL obtain every chunk used in every prompt through the Retriever.
7. WHEN a retrieval repeats an earlier retrieval's query string, learner identifier, and corpus selector within the configured cache time-to-live, THE Retriever SHALL return the cached result set for that key.
8. WHEN an AI endpoint receives a request, THE AI_Reasoning_Layer SHALL verify that the supplied `user_id` matches an existing `users` row and SHALL return HTTP 404 when no such row exists.
9. WHERE no embedding provider is configured, THE Retriever SHALL rank chunks using a local text-similarity method, and THE Retriever SHALL perform no network call for ranking, preprocessing, or dictionary lookup while that method is in use.
10. THE Retriever SHALL record for each retrieval the query, the learner identifier, the returned `chunk_id` values, and the returned similarity scores, for audit and for the design-phase data-flow documentation.
11. THE Retriever SHALL complete a retrieval over Corpus A and one learner's Corpus B within 300 milliseconds at a corpus size of 2000 chunks.

---

### Requirement 12: Graceful degradation

**User Story:** As a developer running DolFin with no API key, I want the whole platform to work, so that demos, tests, and offline development are never blocked by an external service.

The pattern already exists in `coach.py` via `_offline_message` and must be applied consistently.

#### Acceptance Criteria

1. WHILE `settings.gemini_api_key` is empty, THE AI_Reasoning_Layer SHALL report the LLM as unavailable and every AI feature SHALL return the deterministic fallback defined for that feature.
2. WHILE `settings.gemini_api_key` is empty, THE Backend SHALL serve all 38 existing REST endpoints with unchanged response shapes.
3. WHILE `settings.gemini_api_key` is empty, THE endpoints introduced by this feature SHALL return HTTP 200 with the fallback payload defined for the feature and with `mode` identifying the content as fallback content.
4. IF an LLM call raises an exception, THEN THE LLM_Gateway SHALL log the failure at warning level and SHALL return the unavailable status to the calling component.
5. IF an LLM call exceeds its configured timeout, THEN THE LLM_Gateway SHALL abandon the call and SHALL return the unavailable status to the calling component.
6. IF an LLM response is empty after trimming whitespace, THEN THE LLM_Gateway SHALL treat the call as failed.
7. IF an LLM response fails schema validation for the requesting feature, THEN THE LLM_Gateway SHALL treat the call as failed.
8. THE AI_Reasoning_Layer SHALL include in every AI-bearing response a `mode` field whose value identifies whether the content was generated or produced by the deterministic fallback.
9. THE AI_Reasoning_Layer SHALL return HTTP 200 with fallback content when the LLM is unavailable, for every endpoint that carries AI content alongside deterministic content.

---

### Requirement 13: Latency on interactive paths

**User Story:** As a learner clicking "Preview trade", I want the warnings immediately, so that adding AI review does not make the app feel broken.

#### Acceptance Criteria

1. THE `/portfolio/preview` endpoint SHALL return rule findings, the quote, the `blocking` flag, and the estimated cost without waiting for any LLM call.
2. IF the quote, the rule evaluation, or the estimated cost cannot be produced, THEN THE `/portfolio/preview` endpoint SHALL return an error status and SHALL omit a partial preview payload.
3. WHEN a preview completes, THE Risk_Reviewer SHALL make AI findings for that `preview_id` retrievable through a separate request.
4. WHILE AI findings for a `preview_id` are still being computed, THE AI_Reasoning_Layer SHALL return a status of `"pending"` for that `preview_id`.
5. THE LLM_Gateway SHALL apply a timeout of 8 seconds to LLM calls on interactive paths, covering the Risk_Reviewer, the Coach, the Reflection_Analyzer, and the Chatbot.
6. THE LLM_Gateway SHALL apply a timeout of 25 seconds to LLM calls on deferred paths, covering the Pattern_Analyzer and the Quiz_Generator.
7. THE Frontend SHALL render rule findings before AI findings arrive, and SHALL keep every rule finding displayed after AI findings arrive, so that the findings feeding the Investment Readiness Score remain visible.
8. WHEN AI findings become available, THE Frontend SHALL append the AI findings to the displayed findings in a section labelled as AI observations.
9. THE Frontend SHALL display an in-progress indicator while AI findings carry the status `"pending"`.
10. IF AI findings for a `preview_id` have not become available within 15 seconds of the preview, THEN THE Frontend SHALL hide the in-progress indicator and SHALL continue to display the rule findings.
11. WHERE AI findings for a `preview_id` arrive after the 15-second wait has ended and the preview is still displayed, THE Frontend SHALL append the AI findings to the displayed findings.

---

### Requirement 14: Cost and quota management

**User Story:** As a student running on the Gemini free tier, I want the platform to stay inside roughly 60 requests per minute, so that a demo does not fail on a quota error.

#### Acceptance Criteria

1. THE LLM_Gateway SHALL enforce a configurable per-minute request budget with a default value of 50 requests per minute across the whole application.
2. THE LLM_Gateway SHALL accept per-minute request budget values from 1 to 1000 inclusive.
3. IF the configured per-minute request budget falls outside 1 to 1000 inclusive, THEN THE Backend SHALL fail startup with a message naming the setting and the accepted range.
4. IF the per-minute request budget is exhausted, THEN THE LLM_Gateway SHALL return the unavailable status without issuing a network call.
5. THE LLM_Gateway SHALL cache each LLM response against a cache key derived from the feature name, the model name, the language, and a hash of the assembled prompt inputs.
6. WHEN an LLM_Gateway cache key matches a cached entry that has not expired, THE LLM_Gateway SHALL return the cached response and SHALL issue no network call.
7. THE LLM_Gateway SHALL apply a configurable cache time-to-live per feature, with a default of 24 hours for the Pattern_Analyzer and the Quiz_Generator and 15 minutes for the Coach and the Risk_Reviewer.
8. THE AI_Reasoning_Layer SHALL issue no LLM call when a page loads and the underlying learner data is unchanged since the cached AI content for that page was produced.
9. THE Indexer SHALL compute embeddings for a Corpus A chunk once per chunk version and SHALL reuse stored embeddings on subsequent retrievals.
10. THE LLM_Gateway SHALL record the count of LLM calls issued, the count of cache hits, and the count of budget rejections, and SHALL expose those counts through the health endpoint.
11. THE LLM_Gateway SHALL retry a failed LLM call at most once, and SHALL count each retry against the per-minute request budget.

---

### Requirement 15: Prompt safety and regulatory compliance

**User Story:** As a learner in India, I want the AI to teach principles rather than tell me what to buy, so that the platform stays on the correct side of the line between education and regulated investment advice.

The existing coach prompt already forbids naming specific stocks to buy or sell and forbids price predictions. Every new prompt inherits these constraints.

#### Acceptance Criteria

1. THE LLM_Gateway SHALL prepend a shared safety constraint block to every prompt the AI_Reasoning_Layer sends.
2. THE shared safety constraint block SHALL instruct the LLM to explain principles rather than to name a specific security to buy or to sell.
3. THE shared safety constraint block SHALL instruct the LLM to omit predictions of future prices, future returns, and future market direction.
4. THE shared safety constraint block SHALL instruct the LLM to describe DolFin holdings as simulated practice positions.
5. THE LLM_Gateway SHALL screen every LLM response for a directive to buy or to sell a named catalogue symbol and for a stated future price or return figure.
6. IF a screened LLM response contains a directive to buy or to sell a named catalogue symbol, THEN THE LLM_Gateway SHALL discard the response and SHALL return the unavailable status to the calling component.
7. IF a screened LLM response contains a stated future price or return figure, THEN THE LLM_Gateway SHALL discard the response and SHALL return the unavailable status to the calling component.
8. THE LLM_Gateway SHALL evaluate every screening check against a response before discarding the response, so that a response violating both checks is recorded as violating both.
9. THE LLM_Gateway SHALL log one entry per detected violation, each entry naming the feature, the violation type, and the learner identifier.
10. THE Frontend SHALL display an educational-purpose disclaimer on every surface that renders AI-generated content.

---

### Requirement 16: Prompt injection resistance

**User Story:** As a developer, I want learner free text to be treated as data rather than as instructions, so that a learner cannot talk the AI out of its safety constraints or into revealing another learner's record.

Reflection text and chatbot questions are user-controlled free text that flows into prompts.

#### Acceptance Criteria

1. THE LLM_Gateway SHALL place learner-supplied free text inside a delimited section that is labelled as untrusted learner input.
2. THE LLM_Gateway SHALL instruct the LLM to treat the contents of the untrusted learner input section as material to analyse rather than as instructions to follow.
3. THE LLM_Gateway SHALL truncate learner-supplied reflection text to 1000 characters and learner-supplied chatbot questions to 500 characters before prompt assembly.
4. THE LLM_Gateway SHALL remove the delimiter sequence used for the untrusted learner input section from learner-supplied text before prompt assembly.
5. THE LLM_Gateway SHALL apply the shared safety constraint block after the untrusted learner input section, so that the constraints are the final instructions in the prompt.
6. WHEN learner-supplied text requests content that the shared safety constraint block forbids, THE LLM_Gateway SHALL apply the response screening defined in Requirement 15.
7. THE AI_Reasoning_Layer SHALL derive the learner identifier used for Corpus B scoping from the request's `user_id` field only.
8. THE AI_Reasoning_Layer SHALL pass learner-supplied free text to prompt assembly alone, and SHALL exclude learner-supplied free text from every argument of the Retriever scoping call, so that injected text cannot reach the scoping logic.
9. THE Reflection_Analyzer and THE Chatbot SHALL store learner-supplied text exactly as submitted, and SHALL apply truncation and delimiter removal only to the prompt copy.

---

### Requirement 17: Hallucination control

**User Story:** As a learner, I want the AI to tell me when it does not know, so that I can trust the answers it does give.

#### Acceptance Criteria

1. THE Chatbot SHALL attach to every answer the list of `chunk_id` values retrieved for that answer.
2. THE Chatbot SHALL return at least one citation on every generated answer.
3. IF a generated answer carries no citation, THEN THE Chatbot SHALL discard the answer and SHALL return the no-grounded-material message defined in Requirement 7.
4. WHEN a generated answer carries one or more citations, THE Chatbot SHALL return that generated answer with the citations attached.
5. IF retrieval returns no chunk at or above the relevance floor, THEN THE AI_Reasoning_Layer SHALL return the declining response for the requesting feature and SHALL issue no generation call.
6. THE LLM_Gateway SHALL instruct the LLM to answer from the supplied retrieved material and the supplied structured data only, and to state that the material does not cover the question when the material is insufficient.
7. THE Chatbot SHALL state every numeric claim about the learner's own record using values supplied in the structured learner data section of the prompt.
8. THE Chatbot SHALL state every numeric claim about a market price using values supplied by the Market_Service, together with the timestamp of those values.
9. THE Frontend SHALL render each citation with its `source_title` and SHALL link the citation to the concept page when the cited chunk belongs to a concept article.

---

### Requirement 18: Testability with a stubbed LLM

**User Story:** As a developer, I want to test every AI feature without a network call, so that the suite stays fast, deterministic, and runnable in CI with no API key.

The existing `tests/conftest.py` already stubs the market feed through an `autouse` fixture; the LLM follows the same pattern.

#### Acceptance Criteria

1. THE AI_Reasoning_Layer SHALL route every LLM call and every embedding call through the LLM_Gateway, so that a single stub replaces all external model access.
2. THE test suite SHALL provide an `autouse` fixture that replaces the LLM_Gateway generation function with a deterministic stub.
3. WHEN the LLM stub is active, THE test suite SHALL run every AI feature test with no outbound network call.
4. THE test suite SHALL provide a fixture that forces the LLM unavailable status, so that each deterministic fallback is directly assertable.
5. THE test suite SHALL assert that the Investment Readiness Score is unchanged when AI findings are present for a learner.
6. THE test suite SHALL assert that a Corpus B retrieval for one learner returns no chunk owned by a different learner.
7. THE test suite SHALL assert that the response screening in Requirement 15 discards a stubbed response containing only a buy directive, and separately discards a stubbed response containing only a predicted price.
8. THE test suite SHALL assert that a learner-supplied text containing an instruction naming a different learner identifier produces a Retriever scoping call carrying the request's `user_id`.
9. THE test suite SHALL assert that every Corpus B chunk returned for a request carries the request's `user_id` as `owner_user_id`.
10. THE test suite SHALL seed a fixed miniature corpus for retrieval tests, so that retrieval assertions depend on no external content.

---

### Requirement 19: Bilingual AI output

**User Story:** As a Hindi-preferring learner, I want AI explanations, pattern analyses, and chatbot answers in Hindi, so that the AI layer is as usable to me as the coach message already is.

#### Acceptance Criteria

1. THE AI_Reasoning_Layer SHALL read the learner's language preference from `users.language` for every generated output.
2. WHERE `users.language` equals `"hi"`, THE AI_Reasoning_Layer SHALL generate the Coach message, the Risk_Reviewer findings, the Reflection_Analyzer response, the Pattern_Analyzer output, and the Chatbot answer in Hindi.
3. WHERE `users.language` equals `"en"`, THE AI_Reasoning_Layer SHALL generate those outputs in English.
4. THE Retriever SHALL retrieve from the English Corpus A regardless of the learner's language preference.
5. THE AI_Reasoning_Layer SHALL render citation `source_title` values in the language of the indexed source material.
6. IF `users.language` holds a value other than `"en"` or `"hi"`, THEN THE AI_Reasoning_Layer SHALL generate output in English.
7. IF a generation request for Hindi output fails or returns content that is not Hindi, THEN THE AI_Reasoning_Layer SHALL return the English output for that feature and SHALL record the language fallback in the application log.

---

### Requirement 20: Design documentation for academic review

**User Story:** As a student presenting Phase 2 Review 1, I want the design phase to produce high-level and low-level design artefacts, so that I can explain the AI layer to reviewers with diagrams rather than prose.

#### Acceptance Criteria

1. THE design document SHALL contain a system architecture diagram showing the Frontend, the 12 existing routers, the Intervention_Engine, the Readiness_Engine, the AI_Reasoning_Layer components, the LLM_Gateway, the Retriever, the Indexer, and the external Gemini and market-data dependencies.
2. THE design document SHALL contain a RAG pipeline data-flow diagram covering source material, chunking, embedding, storage, retrieval, prompt assembly, generation, and response screening.
3. THE design document SHALL contain one sequence diagram per AI feature defined in Requirements 2 through 8.
4. THE design document SHALL contain an updated entity-relationship diagram covering the 11 existing tables and every table introduced for chunks and embeddings, AI findings, chat sessions and messages, pattern analyses, and generated quiz questions.
5. THE design document SHALL contain a diagram or table showing the determinism boundary, identifying which data feeds the Investment Readiness Score and which data is advisory.
6. THE design document SHALL contain a table listing each AI feature, the LLM call it makes, its timeout, its cache time-to-live, and its deterministic fallback.
7. THE design document SHALL specify the Alembic migration required for each new table.
