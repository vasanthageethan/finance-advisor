# Personal Finance Advisor: Project Roadmap & Career Plan

## Where this fits in your overall goal

You're an SE1 at Dish/Boost Mobile working order orchestration, already hands-on with AWS CloudWatch, S3, Lambda, Step Functions, EKS, DynamoDB, MongoDB, and Dynatrace, and you're building MCP servers at work to connect logs, Dynatrace, and GitLab for anomaly detection. That work already makes you a decent case study for "AI-augmented cloud engineer." The finance advisor project is meant to do two things at once: give you a real system to design end-to-end (not just operate), and produce a portfolio artifact that demonstrates cloud architecture plus applied AI, which is exactly the combination you want for a systems designer/architect track.

## Phased build plan

**Phase 1 — Spend ingestion and categorization (current).** Parse CSV exports from your card and bank statements, normalize transactions, and categorize spend using a hybrid pipeline: cheap rule-based matching on merchant names first, a local Hugging Face zero-shot classifier for anything the rules miss, and the Claude API reserved for the harder cases and for generating the actual written insights (trend summaries, anomalies, monthly narrative). This mirrors a pattern worth internalizing for your day job too: cheap deterministic logic first, small local models for the middle tier, a frontier LLM only where reasoning quality actually matters. It's also the cost-control story any interviewer will ask about if you say "I used an LLM for everything."

**Phase 2 — Trend analysis and reporting.** Monthly rollups, category-over-time charts, and anomaly flags (a spend spike, a new recurring charge). This is a direct parallel to the anomaly detection you're already doing with Dynatrace/logs at work — worth explicitly drawing that line in interviews and on LinkedIn.

**Phase 3 — Goal setting and forecasting.** Budget targets per category, projected savings, simple forecasting (even a naive moving-average or Prophet-style model is enough to start).

**Phase 4 — Stock/investment tracking.** Portfolio import, performance vs. benchmarks, and Claude-generated plain-language explanations of what's driving performance. Keep this read-only and advisory — no automated trading.

**Phase 5 — Move it onto AWS.** Re-platform the working local app onto Lambda, Step Functions for the monthly ingestion/report pipeline, DynamoDB for transaction storage, S3 for raw statement storage, and CloudWatch for observability. This is the phase that turns "a script that works" into "a system I designed," and it's the part that maps most directly onto the architect role you want next.

Each phase should get its own short design doc before you write code: what are the components, what are the failure modes, why this data store over that one. That habit — writing a one-page design doc before building — is itself one of the highest-leverage things you can practice for the architect transition, more than any individual technology.

## Skills and certifications worth targeting

For the cloud/architect track: AWS Certified Solutions Architect – Associate if you don't already have it, then Professional once you've got a couple of designed-and-shipped systems to point to (the finance app and your work MCP servers both count). Given your EKS exposure, the Certified Kubernetes Administrator (CKA) is a reasonable complement. Terraform (HashiCorp Certified: Terraform Associate) is worth having even if you're not writing much IaC yet, since architect roles assume it.

For the AI/data track: AWS Certified AI Practitioner or Machine Learning Specialty, depending on how deep you want to go. More valuable than any single certificate, though, is reading Designing Data-Intensive Applications and a system design book (Alex Xu's System Design Interview series) cover to cover — this is what actually gets tested in architect-level interviews, and it directly informs the design docs mentioned above.

For LLM-specific skill: get comfortable with retrieval-augmented generation, agent/tool-use patterns (which you're already touching via MCP), and prompt evaluation. The MCP server work you're doing at Dish is genuinely current and not that common yet — it's worth turning into a talk, blog post, or detailed LinkedIn writeup (sanitized of anything proprietary).

## Making this visible

Keep the finance advisor repo public and well-documented on GitHub, with the design docs from each phase included — that's what a hiring manager or interviewer actually reads. Post short updates as you complete each phase rather than one big reveal at the end; "building X in public" content performs well and gives you a natural cadence. A reasonable rhythm is one substantive post every one to two weeks: a design decision and why you made it, a bug that taught you something, a before/after metric (e.g., "cut categorization cost 80% by routing 90% of transactions through a local model instead of Claude"). Mix in one or two posts specifically about your MCP/observability work at Dish, since that's the most differentiated thing on your résumé right now — most SE1s aren't building anomaly-detection MCP integrations.

## Suggested near-term sequence

1. Ship Phase 1 end-to-end with your own real statement data.
2. Write the one-page design doc for Phase 1 and post it.
3. Start the AWS Solutions Architect Associate study track in parallel (roughly 4-6 weeks of evening study is typical).
4. Ship Phase 2, post again.
5. Revisit whether Phase 5 (AWS re-platform) or continuing to Phase 3/4 makes more sense based on what's getting the most interview traction.

## AI Delivery Engineer track (added 2026-10-18)

This runs alongside the phased plan above, not instead of it — same project, same phases, with "AI delivery" discipline folded into whichever phase you're on. Everything below uses free/local tooling; the only recurring cost is the Claude API calls you're already paying for per request (no new subscriptions).

**Why this framing differs from the architect angle:** an AI Delivery Engineer is judged less on the diagram and more on whether you tested the AI's output like a real dependency, know what it costs and how slow it is, can ship a prompt change without breaking something silently, and can explain the tradeoff to someone else. That layers directly on top of Phases 1-5, it doesn't replace them.

### Sequence to induce into finance-advisor (do in this order — each step is cheap and builds on the last)

1. **Evaluation harness (~1 week, do this first).** Extend `backend/tests/test_categorizer.py` and `test_api.py` with a small golden dataset: expand `sample_transactions.csv` with edge cases, add expected-category assertions, and a rubric check for `/insights` output (e.g. "flags the $400 Amazon spike," "mentions the dining trend"). This is the single thing that makes every later change safe. No new dependency — you already have pytest.
2. **CI on every push (~1 day).** A GitHub Actions workflow (free minutes) running the full pytest suite, including the new eval harness, on every push. This is the "I ship with guardrails" proof point interviewers actually probe for.
3. **Cost/latency logging (~3-5 days).** Wrap the Claude call in the `/insights` handler to log `{tokens_in, tokens_out, latency_ms, estimated_cost}` to a local SQLite file (stdlib `sqlite3`, no server). Surface totals with one small script or a recharts panel in the existing frontend. Turns "I route to cheap tiers to save cost" into a measured claim with a real number instead of a story.
4. **Local RAG over transaction history (~1-2 weeks).** Add free-form Q&A ("how much did I spend on dining in March vs Feb") using `sentence-transformers` (same Hugging Face dependency family you already use for the zero-shot tier) + FAISS running in-process — pip install only, no server, no account, no cost. Demonstrates retrieval patterns beyond fixed endpoints, which is the most commonly-probed AI delivery skill after evaluation.
5. **Expose the app as an MCP server (~1 week).** Wrap `get_summary` / `get_insights` as MCP tools with the open-source `mcp` Python SDK so Claude Desktop/Code can call your own app directly. Free, and reuses exactly what you're already building at work with MCP — just pointed at your own system instead of Dish's.
6. **Bedrock comparison, once Phase 5 starts (a few cents, not a subscription).** Run the same `/insights` prompt through Bedrock vs. the direct Anthropic API once or twice and write a half-page comparison (cost, latency, governance/VPC isolation). One deliberate side-by-side is enough to speak to it in an interview — no need to run it continuously.

Steps 1-2 should land before or alongside finishing Phase 1. Steps 3-5 interleave naturally with Phase 2/3. Step 6 belongs to Phase 5.

### Practicing the same muscle at work, for free

The AI pods at work already do the coding — that's structurally the same split an AI Delivery Engineer has with an agent doing implementation while you own design, evaluation, and delivery. Use that directly, at no cost:

- Before a pod starts a task, write the one-paragraph design doc yourself first (same habit as the per-phase design docs above). Reps for the part of the job that doesn't get automated away.
- Define the acceptance criteria / tests the pod's output has to pass *before* it starts, not after — same muscle as the evaluation harness in step 1, applied to code instead of prompts.
- When a pod's output needs an architectural correction, keep a private, sanitized note of what and why. This becomes interview material and LinkedIn content later — "where AI-generated code needed a human architecture call" is a sharp, differentiated post topic most SE1s can't write.
- If you have Dynatrace/CloudWatch access, set up or review observability for whatever the pod ships — the same skill as step 3, already half in your day job.
