POLYSIA MASTER PLAN
Standalone product, engineering, validation, and operating baseline

Version: 1.10
Prepared: 25 November 2026
Revised: 26 November 2026
Language: English
Status: Ready to guide implementation; product delivery is not claimed.
Format: One portable UTF-8 text file.

START HERE

PolySia will help people discover Polymarket traders, connect their own accounts, understand their money, and operate transparent copy trading in simulated or real mode. It must also remain understandable to its owner and easy for humans and AI agents to develop.

The business ambition is sustainable, risk-aware economic value. Successful execution, attractive software, and profitable copying are separate achievements and must be measured separately. No architecture, leaderboard, or AI model is assumed to guarantee profit.

Choose implementation from current user outcomes, verified provider contracts, and measured constraints. Maintain one supported installation path and one current design. Remove unnecessary work instead of preserving speculative subsystems, duplicate instructions, or undocumented assumptions.

The first implementation objective is one complete journey:
install -> connect one supported account -> inspect readiness -> select one leader -> observe a realistic shadow copy -> enable bounded real copying through an authorized executor -> see the actual outcome -> stop or disconnect with clear remaining exposure.

This file is the initial source of truth for intent. It contains the broad destination, the proposed implementation defaults, the phased delivery sequence, the acceptance criteria, and the information needed to resume without this conversation.

How to read it:

Owner: read sections 0-6, 18-19, and 21-22.

New developer or AI agent: read sections 0-3, 7-8, 16-17, and the current task's relevant sections.

Trading or data implementer: read sections 8-14 and the relevant acceptance scenarios.

Release reviewer: use sections 15, 17, and 20.

Read only the current task's relevant sections and evidence.

Status words:

REQUIREMENT: a necessary outcome or constraint established by the planning goals.

DEFAULT: a provisional implementation starting point; its inclusion is not evidence that alternatives were tested or that the owner selected that technology.

DECISION: an implementation choice accepted through applicable authority or evidence; it remains the shared working baseline until explicitly superseded.

EXPERIMENT: a hypothesis with a baseline and an acceptance or rejection rule.

LATER: preserve feasibility, but do not build it until its stage is justified.

EXTERNAL FACT: a provider capability or restriction supported by the dated sources in section 23.

Final baseline does not mean frozen forever. Change this file when accepted goals or consequential decisions change. Preserve a short reason and the affected acceptance criteria. Do not accumulate competing versions inside the active repository.

Protect the desired outcomes and financial/permission constraints while allowing evidence to improve implementation choices. An incoming model must not treat its own preference as a newly accepted decision. No specification eliminates bias; explicit assumptions, bounded comparisons, and visible decisions make consequential bias easier to identify and correct.

Current implementation state:

This document establishes the plan; it does not establish that the new repository, infrastructure, credentials, or product have been created.

The active repository URL and exact deployed version must be recorded when implementation begins.

Claims of implementation, performance, or completed verification require inspectable artifacts. Design review and hypothetical walkthroughs do not establish working integration, user performance, or economic results.

No real account credentials, approved test budget, or live authorization values are embedded here.

A planning document alone does not grant tools permission to place financial transactions.

CONTENTS

Problem, purpose, and decision principles

Product scope and staged delivery

Shared vocabulary and naming

User journeys and product surfaces

Interface design and accessibility

Owner understanding and project visibility

Architecture and repository structure

Polymarket capability baseline

Data, accounting, and historical evidence

Discovery, selection, and verification

Copy execution and financial invariants

Shadow operation and economic validation

Performance and dynamic capacity

Security, eligibility, and authorized testing

Installation, deployment, and operation

Human and AI development workflow

Quality gates and prevention of accumulation

Measurement and acceptance targets

Implementation sequence

Critical acceptance scenarios

Decisions, dependencies, and unresolved values

Continuation packet and reusable task templates

Sources and evidence

PROBLEM, PURPOSE, AND DECISION PRINCIPLES

1.1 The problem

Rapid development can outpace the owner's understanding and leave incomplete, unnecessary, superseded, or economically unhelpful functionality. A component can be well written and fully tested while no longer serving a useful purpose.

AI-assisted development must preserve understanding and control. Lower token cost and faster code generation are useful only when they increase accepted, valuable outcomes.

Customer problem hypothesis:
An eligible user needs a simple way to identify potentially suitable leaders, connect their own account, copy within clear limits, and understand the actual results without coordinating several tools or reconstructing events manually. Validate this through the first complete journey. If the product does not improve on the user's existing alternative, revise the approach rather than adding features. Demand and differentiation are hypotheses until demonstrated.

1.2 The intended result

Build a product that is:

Easy for a nontechnical person to install, understand, and use.

Capable of real and simulated copy trading with honest results.

Attractive, coherent, responsive, and accessible.

Reliable around money, permissions, incomplete data, and failures.

Easy to understand, change, migrate, and extend.

Efficient in development time, operating cost, human attention, and AI context.

Measurably useful against explicit acceptance targets and relevant reproducible alternatives.

A smaller codebase is a desired consequence of clearer design, not a release criterion by itself. Do not promise a particular code reduction, delivery duration, or superiority ratio before measurement.

1.3 Three kinds of success

User success:
A person can complete important tasks, understand their current situation, and recover from mistakes without reading technical material.

Engineering success:
The system behaves correctly under normal, partial, concurrent, and failure conditions. Changes remain understandable and verifiable.

Economic success:
Follower outcomes after relevant costs and risk are good enough to justify use. A profitable result must be supported by appropriate evidence, not selected examples.

Begin economic validation with the earliest viable execution path. Do not wait for every product feature to be complete.

1.4 Decision principles

Start from the user outcome and observable acceptance examples.

Prefer a clear, reversible implementation with few moving parts.

Use deterministic calculations for deterministic questions.

Use judgment where evidence is incomplete or objectives conflict.

Introduce AI, optimization, or paid infrastructure only for demonstrated value.

Consider future migration at boundaries without implementing hypothetical futures.

Preserve important uncertainty instead of turning unknown values into zeros or certainty.

Past effort does not justify retaining work that no longer serves an accepted outcome.

Deletion, simplification, replacement, and abandonment are legitimate outcomes.

Protect the owner's ability to understand the project as a first-class product quality.

Keep critical authority and acceptance boundaries outside the uncontrolled discretion of a coding agent.

1.5 Prevent requirement inflation

Before an item enters committed scope, classify it as a requirement, default, experiment, or later option. Every important requirement needs a reason and a way to verify it. A helpful suggestion in a conversation is not automatically a launch commitment. This follows ordinary requirements validation principles: necessity, valid assumptions, consistency, and verifiability. [S16]

The owner does not need to approve routine implementation details repeatedly. Escalate only decisions that change the accepted goal, materially expand cost or exposure, or require authority not already granted.

Proactive collaboration is required. The owner is not responsible for enumerating every requirement, discovering technical gaps, or knowing the right questions. Infer the underlying need from their examples, help clarify incomplete goals, and test consequential assumptions instead of treating every suggested solution as a requirement. Raise important omissions, contradictions, and unnecessary complexity, including in this plan, without waiting to be asked. Investigate what could change the next decision, recommend and perform the smallest authorized correction, and report evidence and remaining uncertainty. Simplifying, deferring, or removing work is as valid as adding it. Questions should resolve material preferences, missing information, or authority rather than transfer routine discovery back to the owner.

PRODUCT SCOPE AND STAGED DELIVERY

2.1 First audience and deployment

DEFAULT:
Start with an individual, eligible Polymarket user operating a self-hosted web application. Certify one supported Linux server configuration first. Record the exact supported OS, CPU architecture, minimum resources, and deployment artifact in the support matrix during the first installation milestone.

The first slice connects one account and copies one leader. The data and permission model must already distinguish multiple accounts so expansion does not require an identity rewrite.

Distinguish trading-user tasks from hosting/operation tasks even when one person performs both. Early product trials may use a controlled supported host and record assistance required; this tests usefulness without assuming every novice already operates a server. Preserve the single self-hosted installer requirement and verify it before the useful release. This distinction does not introduce managed SaaS.

2.2 Committed product direction

The product direction includes:

Multiple connected trading accounts with separate permissions and budgets.

A coherent portfolio view with account-level drill-down.

Official-source leader discovery and understandable derived analytics.

Real and shadow copy trading.

Transparent capacity, execution, performance, and risk.

Simple setup, updates, recovery, and exit.

A lightweight owner/developer view of project and runtime state.

Consistent design, naming, notifications, and human/AI handoffs.

These outcomes are delivered incrementally. The first usable release does not need every advanced analytic feature.

2.3 Stages

Stage A: Executable foundation.
A clean repository, shared commands, initial contracts, current provider capability checks, and a truthful thin UI.

Stage B: Complete shadow journey.
One account, one leader, real observations, simulated execution, portfolio explanation, and stop/resume behavior.
Deliver a user-stepped, BUY-only public portfolio first. Keep unobserved intervals, model assumptions, missing marks and open exposure visible. Evidence for executable prices, follower fees and order minimums gates execution-quality claims. Independent portfolio, recovery and usability work can proceed with controlled inputs.

Stage C: Bounded live proof.
An authorized test account executes a limited real copy through the approved runner, reconciles it, and demonstrates safe interruption and recovery.

Stage D: Useful individual product.
Multiple accounts and leaders, practical discovery, selection controls, capacity guidance, understandable notifications, polished installation, and operational ownership.

Stage E: Measured improvement.
Improve copy suitability, economic results, latency, and usability against recorded baselines.

Stage F: Optional distribution expansion.
Managed SaaS, subscriptions, additional operators, native mobile/desktop packaging, and further venues or instruments.

Progress depends on evidence. Do not advance because the calendar says to, or because implementation is easy.

2.4 Explicitly deferred

Do not require these for the first live slice:

Native mobile or desktop clients.

SaaS billing and a public multi-tenant service.

A large marketing site.

AI wallet-selection judges, complex prediction models, or portfolio optimizers.

A custom workflow orchestration platform or software-factory product.

Microservices, Kubernetes, a data lake, or a message broker without a measured need.

Every notification channel.

Automated custody, withdrawals, or account migration.

Unsupported multi-leg, leveraged, perpetual, or other instrument types.

SHARED VOCABULARY AND NAMING

Use these terms consistently in code, UI, APIs, logs, and documentation:

User: a person who accesses PolySia.

Workspace: the ownership and permission boundary; initially one self-hosted workspace.

Trading account: one connected Polymarket account or trading wallet.

Wallet owner: the identity authorized to control a wallet.

Signer: the key or delegated identity that authorizes trading actions.

Leader: a wallet whose observable trading activity may be copied.

Copy strategy: rules connecting a follower account to one or more leaders.

Allocation: capital or inventory reserved for a strategy.

Run: one execution episode with a fixed mode and an append-only history of effective configuration revisions; each intent preserves the revision used for its decision.

Signal: an observed event considered for a copying decision.

Intent: a durable decision to request a financial action.

Order: a request accepted by the trading venue.

Fill: an executed quantity associated with an order.

Position: currently held exposure in an outcome.

Event: the underlying real-world subject or resolution grouping.

Market: a specific tradable question or market within an event.

Outcome: the asset or result being traded.

Shadow: simulated follower execution using explicit assumptions.

Live: real execution using authorized funds and signing authority.

Reconciliation: comparison of internal records with authoritative external evidence.

Readiness: whether an operation can safely proceed now.

Project status: what has been built and verified.

Runtime health: how the deployed system is behaving now.

Do not use "account" interchangeably for application login, signer, leader, and wallet. Do not use "verified" without stating what was verified.

Naming rules:

Prefer familiar domain nouns and specific action verbs.

Use the same concept name across layers where practical.

Keep UI language natural; expose internal IDs only when useful.

Put units in metric definitions and typed fields.

Use a single convention within each language and translate at API boundaries.

Avoid vague containers such as "misc", "helpers", "manager", or "intelligence" when the actual responsibility can be named.

Introduce a new abstraction only when its behavior and ownership are clear.

USER JOURNEYS AND PRODUCT SURFACES

4.1 Installation and first meaningful result

A new user must be able to:

Find the official installation entry point.

See prerequisites and what will run on their server.

Complete setup with clear progress and actionable errors.

Open the application and establish its owner identity.

Connect a supported trading account.

See permissions, available funds, relevant restrictions, and readiness.

Find or paste a leader wallet.

Understand the intended copying rules and maximum allocation.

Start shadow operation or explicitly enable an authorized live run.

Observe what actually happened and what remains unresolved.

Measure time to an understood result. A submitted order is not a filled trade. A live fill is not proof of profitability.

A leader may not trade immediately. Show "waiting for the leader's next eligible trade", the last observation time, and what event will trigger copying. Use a clearly marked demonstration or replay to explain the flow. Do not fabricate live activity to satisfy an onboarding timer.

4.2 Account and portfolio

Show:

Account name, address, external profile link, connection state, and permission scope.

Cash, reserved funds, open-order commitments, positions, and total equity with definitions.

Open positions, closed positions, orders, activity, and relevant settlement/redemption states.

Realized result, open-position estimate, costs, and external cash flows separately.

Individual accounts and a combined view that preserves attribution.

Data freshness, incomplete coverage, and the meaning of approximations.

Support account labels and a profile appropriate to the chosen authentication method. Optional avatars and cosmetic fields must not obstruct the trading journey.

Keep deposits, withdrawals, and owner-level approvals visibly separate from routine copying. Initially, direct users to a verified provider flow where appropriate. Do not improvise an in-app money-transfer flow.

4.3 Discovery and trader detail

The leaderboard and trader-analysis journey are flagship product deliverables, not an optional table added after the engine. Section 10.7 makes the intended experience and its acceptance explicit. An early rendered prototype must make this outcome visible before the full discovery implementation is complete.

A candidate should be identifiable through its wallet address and provider link. Display available profile information, supported leaderboard categories/windows, useful history, exposure, and copy suitability.

The detail screen should answer:

What does this trader do?

What evidence supports the displayed performance?

Can this activity realistically be copied with my capital and latency?

What risks, concentration, or missing data matter?

What would selecting this trader change in my existing allocation?

Make external provenance and derived calculations distinguishable.

4.4 Copy setup and operation

The user chooses a follower account, leader, allocation, mode, sizing rule, price tolerance, and relevant limits. Provide sensible presets and progressive disclosure.

In the assisted route, prefill a supported preset and keep advanced sizing/tolerance fields optional to edit. Shortlist comparison is available, not a compulsory extra step before choosing one leader. Make the consequential account, mode, and allocation choices clear without a technical questionnaire.

Support deliberate differences in economic risk preference. A user seeking greater upside while accepting greater loss can reach a supported configuration, as can a user prioritizing tighter exposure and liquidity needs. Explain presets through their actual settings and tradeoffs; allow changes within current authority and preserve the user's choice. Experience level, desired assistance, and willingness to accept loss are separate dimensions. Higher accepted risk does not establish higher expected profit and never relaxes correctness, eligibility, authorization, or accounting.

The staged engineering proof in section 2 is not a mandatory shadow-trading waiting period for every end user. Offer the supported Shadow/Live choice after its relevant readiness and authorization checks; routine already-authorized copies need no repeated confirmation.

Before activation, show an understandable summary of:

Which account will act.

Which mode is selected.

Maximum order size and total allocation.

Entry and exit behavior.

What happens when data is stale or capacity is unavailable.

How to stop new activity and manage remaining exposure.

During operation, show the chain from leader observation to decision, order, execution, and accounting. Explain rejected or skipped copies with actionable reasons.

Give percentage controls a monetary meaning: name the base, included costs/open-position values, period/reset rule, cash-flow treatment, and triggered action. For example, "Pause new entries after $10 net loss" is clearer than an unexplained "10% stop" on a $100 allocation. A trigger to pause or attempt a sale is not a guaranteed maximum loss. Changes to allocation must preview their effect on these limits. Published copy products use different percentage conventions; do not inherit a label without its meaning. [S40]

4.5 Exit and offboarding

Define separate behavior for:

Logging out of the interface.

Stopping new copies.

Canceling outstanding orders.

Attempting to close existing positions.

Disconnecting the account.

Revoking signing access.

Ending a subscription.

Exporting or deleting an application profile.

Uninstalling or migrating the service.

DEFAULT:
Logout closes the UI session without changing an explicitly running strategy. An action that prevents new entries while allowing existing exit management to continue is labeled "Pause new entries". Its result shows whether automated exits and resting orders remain active. Canceling orders, closing positions, and disabling remaining automation are distinct consequences and must be stated explicitly whenever offered. Disconnecting disables new signal-driven submissions and provides a clear handoff of existing exposure. No action silently liquidates positions.

Revocation must not be delayed merely because positions remain open. If the system loses visibility or authority, report that condition and provide the direct-management route. Never claim cancellation or liquidation is complete without confirming it.

A future subscription ending must not silently continue paid automation indefinitely, erase the user's financial evidence, or force an unrequested sale. Define any operational wind-down period before launching billing.

4.6 Notifications

DEFAULT:
Start with an in-product notification center and one justified external channel. Choose email or Telegram according to actual first-user needs. WhatsApp, push, and additional providers are later integrations.

Notifications need severity, account context, deduplication, timestamps, delivery status, and an actionable destination. Allow preferences and quiet hours for routine messages. Critical safety behavior must work even if notification delivery fails.

Users receive portfolio and strategy information appropriate to their accounts. Operators receive system incidents without exposing another user's secrets or unnecessary financial detail.

4.7 Product surfaces

Keep a coherent navigation:

Overview: current situation and next useful action.

Accounts: connections, portfolio, permissions.

Discover: leaders, filters, comparisons.

Copying: strategies, allocations, runs, results.

Activity: orders, fills, events, explanations.

Settings: identity, theme, notifications, security.

Owner view: role-restricted project and operational understanding.

A small landing or documentation entry page should explain value, installation, limitations, and support, with one clear next action appropriate to the deployment. Use the real implemented journey or a clearly labeled preview to show what the product does. Keep presentation coherent with the application; this must not become a prerequisite marketing project.

The trading Overview must answer "What happened while I was away?" for a clearly selected interval. Summarize effective strategy state and policy changes, the follower's result excluding external cash flows, costs, open exposure, copied/skipped activity and principal reasons, freshness, unresolved issues, and the next useful action. A healthy run without an eligible signal is visibly waiting. Derive this view from existing records; the user should not reconstruct it from logs. Notification failure must not hide its state.

4.8 Need-based journeys and acceptance map

These are review archetypes, not measured market segments or permanent personality labels. One person can have several needs, including different preferences across accounts. The useful individual release must support the following outcomes within the stated scope:

Use these cases to inspect shared journeys. At each milestone cover only supported capabilities and materially different conditions; complete the rest as their capabilities arrive. Seven archetypes do not require seven onboarding flows or every combination to be tested at every stage.

P01. Assisted beginner: "I know no wallet; help me start."
Given an intended allocation and a supported preset, reach an explained shortlist or a useful no-match result, then the correct copy preview without another person choosing for them. Identify the account, mode, amount, and next trigger. Verify through A34 and section 10.3.

P02. Deliberately risk-tolerant user: "I accept more downside for a chance of greater upside."
Reach a different admissible economic configuration from a tighter-risk preset, explain the changed exposure and adverse-case consequences, and later revise it without code. The same financial correctness and authorization still apply. Verify through A37-A39.

P03. Cautious or liquidity-sensitive user: "Keep my exposure understandable; I may need the money."
Express the relevant allocation/loss controls and holding-horizon constraint, inspect any known mismatch with leader activity, and distinguish free cash, commitments, and potentially illiquid positions. No instant-exit or guaranteed-loss-ceiling claim. Verify through A03, A15, A32, and A37.

P04. Limited-capital user: "Work within this budget."
Discover feasibility during selection, distinguish unsupported from unknown, and find an honest alternative without an automatic budget increase. A same-budget shadow run respects actual minimums and shows skipped activity. Verify through A34 and A37.

P05. Time-poor returning user: "Tell me what happened and whether I need to act."
After a seven-day scenario containing a deposit, open exposure, skipped actions, and a pause, identify actual net result, current operation, remaining exposure, and the reason for any required action from Overview. Include a healthy waiting variant. Verify through A03 and A32.

P06. Experienced user or researcher: "Let me verify and compare."
Use advanced controls without a forced beginner tutorial; inspect the effective policy, compare properly identified shadow variants, and export enough retained evidence to reconcile the displayed result. Unretained inputs remain explicit. Verify through A22, A32, and A39.

P07. Multiple-account user: "Keep each account clear."
Choose the intended account and see separate budgets, permissions, and results. Reconnecting the same verified trading wallet preserves one financial account and its history rather than duplicating money. Verify through A08, A14, and A40.

INTERFACE DESIGN AND ACCESSIBILITY

5.1 Design intent

Beauty, clarity, and effortless use are explicit product outcomes. The interface must feel deliberately designed and visually coherent while helping people understand their situation and act confidently. Use visual hierarchy, readable typography, deliberate spacing, consistent components, and progressive disclosure. A functioning but visually careless interface does not satisfy this requirement.

The beginner view should expose the few decisions that matter now. Advanced users can inspect details without forcing everyone through a dense trading terminal.

5.2 Design system

DEFAULT:
Use a small accessible component library and a shared token layer. Evaluate the selected library against keyboard behavior, maintenance, customization, and bundle cost before commitment.

Semantic tokens should cover:

Backgrounds, surfaces, borders, and text.

Interactive accent and focus.

Success, warning, danger, neutral, and unavailable.

Spacing, typography, radii, shadows, and motion.

No fixed palette, named brand colors, color pairings, font family, or component-library aesthetic is prescribed. The implementing model should select and justify a coherent visual direction from the user goals, content, context of use, accessibility, and rendered evidence. ChatGPT and competitor references are optional inspiration, not visual templates. Do not claim access to a proprietary design standard or copy an unverified "2026 OpenAI palette".

Resolve meaningful visual uncertainty with a small rendered prototype; compare alternatives only when that comparison can change the decision. Once the direction is accepted through the project's review process, record it in shared semantic tokens, core components, and representative screens. Later sessions extend this reference instead of choosing a new palette or visual language independently. Intentional changes remain possible through a visible design decision. Verify actual combinations in light and dark themes.

Color cannot be the only indication of profit/loss, account, warning, mode, or state. Pair it with text, shape, or icons. Reserve dangerous styling for actions or conditions with actual consequences.

Supported theme values must be runtime data consumed through the shared semantic tokens. An authorized owner can preview and publish a coherent token revision on representative critical screens without source edits, PRs, rebuilds, or redeployment. Validate token types/references, required values, and accessibility of supported combinations; invalid publication preserves the active theme. User theme selection is a separate personal preference. Persist both across restart/upgrade and support restoring a valid revision. New token meanings or component behavior still require development. The editor accepts supported values, not arbitrary scripts or unrestricted CSS. DTCG is an optional interchange-format reference, not a required editor or a guarantee of accessibility. [S46]

5.3 Interaction rules

Use consistent action names: Connect, Start shadow, Enable live, Pause new entries, Cancel orders.

Keep account and mode visible on consequential actions.

Provide useful loading, empty, stale, partial, error, and reconnecting states.

State what happened, why it matters, and the next useful step.

Show essential warnings beside the affected action.

Confirm activation of real trading, material increases in authority or limits, and destructive owner actions. Routine copies already authorized within the configured account, mode, budget, and policy run without per-trade confirmation. Show their outcomes and keep stopping controls easy to find.

Preserve form input after recoverable errors.

Preserve discovery filters, period, sort order, and return position when opening a trader and going back. Carry applicable selections into copy setup; make any change of account, period, metric basis, or mode explicit. A user should not have to reconstruct the same decision at every screen.

Support undo where meaningful; explain irreversible effects.

Respect reduced motion and avoid decorative animation in critical status displays.

Provide clear search and filtering; add a command palette only if it improves real tasks.

5.4 Accessibility and languages

Target WCAG 2.2 AA for the critical flows, with keyboard navigation, visible focus, useful labels, readable contrast, non-color status signals, and accessible error handling. Test actual components rather than assuming a library guarantees compliance. [S19]

Make layout responsive for desktop and mobile browsers. Externalize user-facing text, formats, time zones, and currency units. English is the sole supported language for all PolySia-maintained content until the owner explicitly changes this decision. Use plain English, familiar technical terms, and copy-ready commands. Test whether a first-time reader with limited English can complete the task using the published instructions. Preserve the original form of external records, user input, identifiers, and standard notation.

5.5 User validation

Use short, realistic tasks:

Connect an account and explain whether it can trade.

Find the difference between live and simulated results.

Identify why a copy did not execute.

Stop new copies without unintentionally selling positions.

Explain available money versus committed money.

Record where people hesitate or misunderstand. A visually attractive screen that fails these tasks is not accepted.

Review each relevant P01-P07 journey in three passes: ordinary first use; insufficient funds/data, waiting, or failure; and return after time away with a changed need. At each step check whether the person can identify the next action, understand its consequence, and recognize the actual result. A cognitive walkthrough is a structured inspection, not observed usability evidence. [S45]

Record the task, initial conditions, observed or predicted obstacle, requirement change, and acceptance evidence in the existing milestone task. A need is specified when it has an outcome and check; it is validated only after the appropriate rendered/user trial. Measure unassisted task completion, material misunderstandings, effort/time, and perceived clarity separately. Calibrate and fix numerical targets before judging the candidate under section 18.1. No blanket claim that all personas are satisfied follows from this document.

5.6 Rendered visual acceptance

At the first UI milestone, implement a small reference covering the core journey and its important loading, empty, error, and partial states. Include desktop/mobile examples and light/dark themes as they become supported. Use realistic, non-sensitive sample content. This is a working reference, not a separate design-platform project.

Inspect the rendered result for visual hierarchy, typography, spacing, density, alignment, coherence, responsive composition, and comprehension of account/mode/financial state. Check that important actions are easy to discover and that long names, instructions, large values, and errors do not break the layout. Revise obvious visual defects before calling the journey complete.

Functional tests and accessibility checks do not by themselves demonstrate aesthetic quality. Evaluate appearance against the accepted reference and the stated user outcomes. Reference screenshots may evolve, but regenerating a snapshot alone does not establish that the new design is better or acceptable.

OWNER UNDERSTANDING AND PROJECT VISIBILITY

6.1 The problem to prevent

AI can produce changes faster than the owner absorbs them. A passing test suite does not establish that the owner knows what exists, why it exists, or how workflows connect.

The owner should be able to return after weeks and regain a useful mental model quickly. A new developer, AI provider, adviser, or investor should obtain an appropriate view without reading the full history.

6.2 Lightweight owner view

DEFAULT:
Start with a concise project overview generated from existing authoritative records. Expand it only when real usage shows a need.

Show:

What user journeys exist and their verification level.

What is in progress, next, blocked, or still experimental.

A small workflow map with optional deeper detail.

Current bottlenecks and which resource limits them.

Excessive coupling, shared failure points, and repeated work.

Important decisions and why they were made.

Recent changes and their observed effects.

Links to code, tests, PRs, and runtime evidence.

Separate "planned", "implemented", "tested in simulation", "verified against the provider", and "released". Also separate project progress from runtime health and from economic performance.

6.3 Visual understanding

Begin with a user journey or capability map. Do not make a giant file-dependency graph the main explanation.

A useful map connects:
user goal -> workflow step -> responsible module -> evidence -> current limitation.

Tools such as CodeGraph or GitNexus may assist dependency inspection. They do not establish product necessity, correctness, or the meaning of an obsolete but well-connected feature.

Use progressive disclosure, highlighted changes, and small scenario-based demonstrations. Avoid turning project comprehension into a second large platform.

6.4 Check shared understanding

Use a short interactive walkthrough or teach-back at consequential changes:

"What happens if we pause here?"

"Which account still has exposure?"

"Which component is responsible for this decision?"

These are collaboration aids, not mandatory examinations after every session. A failed explanation may reveal a poor interface or inaccurate model, not a deficient user.

Measure practical comprehension:

Time to locate a workflow or failure.

Time to resume a task after a cold handoff.

Correct identification of affected components.

Number of consequential surprises after a change.

Do not invent a supposedly scientific cognitive-debt score.

ARCHITECTURE AND REPOSITORY STRUCTURE

7.1 Implementation defaults

DEFAULT:

TypeScript, React, and Vite for the web application.

Python for the API, trading core, data integration, and analysis.

PostgreSQL as the initial production relational store.

One repository and a modular application, with separate runtime processes where isolation matters.

A versioned HTTP API and generated or checked typed client contracts.

A reproducible container-based deployment using one supported installation mechanism.

These are starting choices, not claims of universal superiority. Verify supported stable releases and official SDK compatibility when creating the environment. Record versions in manifests and lockfiles.

During the executable-foundation milestone, confirm or revise the language split, database, deployment shape, and process boundaries against current SDK coverage, installation simplicity, expected workload, maintainability, and verification capability. A short documented comparison or working integration is sufficient. Choose the smallest approach that meets the same outcomes and constraints. Once accepted, retain that baseline across sessions; do not reopen the stack for every task.

React is the UI library; Next.js is a broader React framework. The default here favors a static application frontend with an independent Python backend. Reconsider a framework such as Next.js if a demonstrated rendering, distribution, or product need outweighs the extra runtime boundary.

Do not start with Rust or another low-level execution rewrite. Measure the actual bottleneck. A smaller optimized component remains possible behind the execution interface.

7.2 Modules and authority

Keep clear responsibilities:

Identity and access:
Application users, workspace permissions, sessions, recovery, and connected-account ownership.

Provider integration:
Current Polymarket contracts, normalized data, authentication adapters, market capabilities, and external rate limiting.

Discovery and selection:
Leader history, definitions, filtering, comparisons, and optional evaluated ranking.

Copy policy:
Signal eligibility, sizing, allocation, timing, and entry/exit decisions.

Risk and execution:
Financial reservations, last-moment checks, authorized submission, cancellation, reconciliation, and execution ownership.

Ledger and portfolio:
Financial records, position attribution, cash flows, derived views, and corrections.

Experimentation:
Shadow execution, replay, prospective comparisons, and result evidence.

Presentation and notifications:
UI/API representations and communication of decisions and state.

Operations:
Configuration, health, releases, backup, recovery, and diagnostics.

Only the authorized execution boundary can submit trading actions. UI code, analytics jobs, and general-purpose LLM responses cannot bypass it.

7.3 Runtime separation

DEFAULT: run the API and execution worker as separately controllable processes from the same backend codebase. The requirement is that UI, expensive reporting, and notification failures must not compromise safe execution; the exact process arrangement is a revisable implementation choice.

One server can host the initial product. A failed host cannot continue running software; recovery requires durable state and a controlled restart. High availability is a later, measured investment.

Use bounded queues and explicit backpressure. Prefer database-backed durable work and a transactional outbox where needed before adding a broker.

Do not turn every module into a network service. Separate deployment only when failure isolation, load, ownership, or scaling evidence justifies it.

7.4 Initial repository map

Keep the exact structure small and purpose-driven:

README.md
The product introduction, one installation path, and where to start.

AGENTS.md
Shared development commands, invariants, boundaries, and completion rules.

apps/web/
Frontend source and its directly related tests.

apps/server/
Backend modules, execution worker, integrations, migrations, and related tests.

deploy/
The supported installation, upgrade, recovery, and release packaging path.

docs/
This plan, a brief current-state record, and consequential decision notes when needed.

tests/
Only cross-component scenarios and shared fixtures that do not belong beside a module.

Do not create empty future packages. A generated contract package may be introduced when actual sharing requires it.

Keep this short map aligned with actual module responsibilities. Ordinary file purpose and ownership should follow clear names, module boundaries, and consumers; do not create a separate status record or README for every file or folder. Apply section 17.4 before adding artifacts.

7.5 Single source of truth

Each kind of fact has one authority:

Intent and scope: this plan.

Active work and ownership: the issue/task system.

Actual structure: code and checked contracts.

Current execution state: runtime and ledger records.

Release evidence: immutable build and validation records.

Secrets: the configured secret store.

Short continuity summary: one current-state record linking to the authorities.

Setting definitions: one versioned application schema; deployed values and their effective revisions: the authorized configuration records described in section 7.7.

The owner view and documentation should reference or derive these facts. Do not maintain parallel manual truth in multiple dashboards and files.

7.6 Future portability

Keep business logic separate from HTTP, UI, provider SDKs, and storage details. Use explicit versioned data contracts and reversible migration practices.

Design ownership boundaries early so a future SaaS edition can isolate tenants. Do not claim multi-tenant security until it is implemented and tested. Mobile and desktop clients can reuse APIs and appropriate design assets; shared UI code is a possibility, not a guarantee.

7.7 Everyday change without repeated development

REQUIREMENT:
Supported everyday values change through understandable product settings and the same validated API/CLI path without a source edit, PR, rebuild, or redeployment. Expose genuinely needed controls, not every implementation constant. Use a small module and records in the existing database; a separate configuration service or general-purpose rule builder is not required.

Implement only settings and scopes needed by the active slice using ordinary typed records, explicit forms, and shared validation. Begin with one persistent preference or supported theme-value control; add financial cutover behavior when financial settings appear. A generated editor, complete theme-authoring tool, or generic inheritance engine is not an early prerequisite.

Change classes:

Personal preferences: supported theme selection, time zone, density, and notification choices affect that user's presentation.

Copy-policy values: implemented sizing modes, amounts, allocation, signal age, price tolerance, and supported exit-policy choices use authorized account/strategy settings and a consequence preview.

Operational values: supported refresh/notification/diagnostic parameters use operator settings, with effect timing declared.

Shared theme values: authorized token publication follows section 5.2; it does not change trading configuration.

Feature switches: select already-implemented optional behavior under section 17.5.

Software/contract changes: new algorithms, integrations, permissions, setting semantics, or component behavior remain development with proportionate tests and review. Deployment-only values may require a declared restart; do not present them as live-editable product controls.

Keep one typed, versioned setting schema with stable names, units/bases, allowed ranges and combinations, defaults or required states, allowed scopes, editing authority, sensitivity, and effect timing. Derive or check UI/API/CLI types and validation against it. Reject unknown keys, unsupported versions, and invalid combinations. Shipped defaults and explicitly chosen deployed values remain distinct.

Declare inheritance per key. A simple allowed chain is application default -> workspace -> account -> strategy; user preferences override only personal presentation. Show the effective value and its source. Financial limits are the intersection of all applicable constraints, not a more-specific override of an account or independently protected ceiling. Keep secret values in the secret store; settings, snapshots, exports, and audit records use references without secret material. All entry paths enforce server-side scope and authorization. [S49]

Environment variables bootstrap declared deployment settings; any supported override is visible and validated. Do not implement live-editable browser settings solely as build-time environment constants: Vite replaces those at build time. Runtime settings must actually reach the deployed client through an appropriate nonsecret configuration path. [S47]

Persist revisions and explicit values across restart and upgrade. Migrate supported schemas explicitly, retain historical interpretation, and do not silently replace choices or widen financial behavior when defaults change. Section 11.7 governs adoption and rollback; record state as saved, pending application, applied, or failed where those distinctions matter.

Only relevant execution-setting revisions affect trading workers. A theme or display-preference change does not restart execution, reset a run, or alter orders.

POLYMARKET CAPABILITY BASELINE

External facts below were checked against official documentation on 25 November 2026. Revalidate them at implementation and before releases that depend on them. A provider's documentation describes a contract; compatibility tests establish our integration's behavior.

8.1 Data API

The documented baseline is Data API v2. The migration guide dates v1 retirement to 2 November 2026. New integrations should use v2 contracts, response envelopes, cursor pagination, and the documented field and position lifecycle conventions. The old accounting snapshot archive does not have an equivalent v2 replacement. [S01]

Derive endpoint paths, field names, response envelopes, and pagination from the selected current contract and checked fixtures.

8.2 Trading protocol and assets

Data API v2 and Polymarket Protocol V2 are different migrations. Protocol V2 rollout began in phases on 23 November 2026; existing CTF holdings are not automatically converted. Route identifiers and operations according to market version. [S02]

Current documentation identifies pUSD as trading collateral. Use explicit asset, network, decimals, and contract metadata; do not hardcode old USDC assumptions into money types or presentation. [S03]

Only enable a market version after its order, position, and settlement contract is supported. Explicitly explain unsupported instruments instead of silently processing them through the wrong model.

8.3 Authentication and account capabilities

Request authentication and order-signing authority are separate. The documented CLOB design uses API credentials for authenticated requests and a wallet signature to authorize an order. [S04]

Current delegated Session Keys are documented for Deposit Wallets, without withdrawal authority. Support for other wallet types must be verified; a planned migration is not an available feature. [S05]

At connection time, discover and record supported read, trade, cancel, wallet-wide visibility, and owner operations. Do not request an owner key as a silent fallback for unsupported delegation.

8.4 Leaderboard definitions

The current leaderboard documentation differentiates finite-window marked equity changes from lifetime realized PnL and describes volume in shares. Preserve these distinctions in labels and formulas. Pagination and rank semantics must follow the endpoint contract. [S06]

Verification gap observed on 25 November 2026: the public leaderboard tooltip described realized-only PnL, while the v2 endpoint documentation described marked changes for finite windows. Do not assume the UI and endpoint use identical data. Verify the actual selected endpoint, window, and accounting basis before claiming exact parity or deriving results; keep any unresolved discrepancy visible in the integration task. [S06, S26]

8.5 Fees and eligibility

Fees are market-dependent and applied under the current trading contract. Read and version the relevant fee information; do not assume a universal rate or permanently fee-free trading. [S07]

The geographic endpoint evaluates the requesting IP. Browser location and execution-server location may differ. An allowed server response alone does not establish all conditions of user eligibility. [S08]

8.6 Capacity and test environments

Documented limits include endpoint/IP controls and separate per-signer trading buckets. Capacity must model all applicable constraints. [S09, S10]

NEX is documented as an access-controlled early sandbox using test funds and separate books. Its availability is not guaranteed for the project, and its results do not establish production economics. [S11]

8.7 Implementation rule

Build a small capability matrix and contract fixtures during Stage A. Keep live values, package versions, supported account types, and compatibility outcomes with the adapter. Avoid spreading provider assumptions across the UI and business logic.

8.8 Managed data and automation: Goldsky evaluation

DEFAULT:
Before building custom chain indexing, contract decoding, or historical backfill, compare an available managed source against the direct-provider baseline. Goldsky is a concrete candidate, not an accepted dependency. Select the smallest approach that satisfies the required contracts and materially improves delivery effort, maintenance, data quality, or performance within the operating budget. It need not win every dimension. Use the existing capability matrix and one bounded experiment; do not build two complete competing ingestion systems.

Goldsky advertises decoded Polymarket fills, matched orders, positions, historical data, filtering, and delivery into our database or an HTTP endpoint. Confirm the exact dataset, contract coverage, historical interval, and plan entitlement with samples. Its January 2024 Polymarket case study explains the managed-indexing rationale but is not a current benchmark or a turnkey application. Generic wallet feeds do not by themselves establish correct Polymarket positions, reservations, or portfolio equity. [S30, S31]

The smallest candidate integration is a data-only adapter into PolySia's authenticated, durable event intake. Our existing policy, reservations, signer, accounting, and reconciliation remain responsible for financial actions. Turbo supports HTTP destinations, so adopting its data feed does not require Compose or relocating the trading key. [S33]

Evaluate only data needed for the current milestone:

Compare the same identifiable source events for completeness, first-arrival delay, duplicates, and recovery. Measure the full observation-to-execution path under section 13; on-chain event availability and follower fills are distinct from vendor pipeline processing time.

Persist accepted input before acknowledging it. Retain stable source identity, observation time, and correction information. Turbo documents at-least-once delivery and correction handling; test redelivery, receiver restart, reorg corrections, and historical replay against A19. Historical repair must never become an unintended new live trade. [S33]

Keep vendor schemas behind the adapter, name the authoritative source for each fact, reconcile samples, and preserve usable export. Retire superseded ingestion code under section 17; retain overlapping sources only for a justified recovery or verification purpose.

Estimate compute, events/updates, historical loads, storage, and any task-call costs. Verify exhaustion behavior and the effect of a stopped feed. Self-hosting PolySia does not make a managed provider free or locally self-hosted. Compose currently requires Scale; Starter credits are one-time and exhausted resources pause. Recheck terms before adoption. [S36]

The Compose copy-trader guide is a pattern reference: on-chain fills trigger a separate follower order, and its example starts at the latest block without prior backfill. It targets the April 2026 CTFExchangeV2 generation; that does not establish coverage of the later Protocol V2 markets in section 8.2. Hosted signing, approvals, execution geography, and account support require an explicit architecture and compatibility decision. Do not import tutorial routing as an eligibility workaround. A chain balance check does not replace our concurrent reservations or approved test allowance. [S02, S32]

Compose can be evaluated separately if managed execution reduces the total system burden while preserving the same authority and financial contracts. This review does not establish live integration, actual speedup, exact costs, historical order-book availability, or profitability. Missing provider access blocks that experiment only, not unrelated product work.

DATA, ACCOUNTING, AND HISTORICAL EVIDENCE

9.1 Data identity

Use stable identifiers for workspace, user, trading account, signer, leader, event, market, outcome, strategy, allocation, run, signal, intent, order, fill, and release.

Preserve external identifiers separately from internal identifiers. An address may have several roles; do not infer that two addresses represent the same person without evidence.

Resolve supported connections by verified provider, network, and underlying trading-account identity. Credentials and labels are access paths, not extra assets or budgets. Reconnecting or replacing credentials for the same financial account preserves its history, reservations, and coordinated execution ownership, subject to current permissions, while showing the resulting access capabilities. Do not merge genuinely distinct accounts merely because their owner or signer appears related.

9.2 Time and provenance

For important actions record:

Source event time when supplied.

First observation time.

Decision time.

Submission and response times.

Match, confirmation, or reconciliation times.

Source, schema version, and relevant configuration/software versions.

Use consistent UTC timestamps for storage and explicit display time zones. Handle clock skew and timestamp precision. Keep original values when normalization could lose meaning.

9.3 Financial representation

Use decimal or integer base-unit arithmetic for money, shares, prices, and fees. Define rounding at each venue boundary. Avoid binary floating point for authoritative financial calculations.

Maintain an append-only financial journal or equivalently auditable ledger for fills, fees, rebates, deposits, withdrawals, transfers, redemptions, and corrections. Correct prior facts with explicit adjustments rather than rewriting history invisibly.

Record every debit, credit, and fee in its actual asset and base units. Reporting-currency valuations are separate and carry their conversion basis and timestamp. Ledger returns use actual fill prices; spread and slippage estimates are attribution measures and must not be deducted a second time.

Separate:

External flows.

Realized trading result.

Open-position marked result.

Estimated liquidation value.

Operational and subscription costs.

Cash reserved for unresolved orders.

Derived portfolio views must reconcile to authoritative records. Expose unresolved differences.

9.4 Position attribution

Track which shares belong to which strategy, leader allocation, manual activity, or pre-existing holding. Several strategies trading the same outcome must not silently share ownership.

External manual trades or transfers trigger reconciliation and the defined allocation policy. Do not sell another strategy's shares merely because a leader exited.

A manual close must state whether future copying may reopen the exposure. Persist any promised exclusion across restart. DEFAULT: unexplained external reductions pause increases for the affected allocation until reconciled under its declared intervention policy; removed inventory is not automatically a deficit to refill. Ordinary reconciliation does not override an owner's instruction.

9.5 Data quality

Record freshness, coverage, missing intervals, duplicate events, invalid values, pagination completeness, and source corrections.

Unknown, unavailable, stale, estimated, and zero are different states. Absence from one signer-scoped result is not proof of absence across the account.

Explain uncertainty through evidence, freshness, coverage, assumptions, and measurable error where available. A probability or interval needs a defined meaning and defensible method; compare predictions with later outcomes where applicable. Otherwise state the estimate or missing evidence plainly. Do not invent a universal confidence percentage, require confidence to increase monotonically, or treat 100% as the inevitable destination. Probability calibration is a possible evaluation method when probabilities are actually used, not a requirement to build a prediction model. [S51]

Handle stream disconnection, out-of-order delivery, duplicated fills, chain reorganizations where relevant, and delayed settlement. A websocket "connected" indicator alone is not evidence of fresh data.

9.6 Historical evidence worth preserving early

Preserve the information needed to answer later:

What did the system know at decision time?

Which options and constraints existed?

Why did it copy, skip, resize, or stop?

What execution conditions were observed?

Which configuration, algorithm, and release produced the result?

What happened to rejected candidates and failed experiments?

Record concise decision facts and selected book/quote evidence, not unlimited full-stream archives by default. Use bounded retention and storage budgets. Preserve durable financial and experiment summaries with export capability.

Keep current observation/freshness state separate from retained history. Repeated unchanged observations need not create full history snapshots unless a defined consumer requires them. Choose change records, periodic samples, or fuller capture according to the actual analysis and recovery need; do not silently invalidate an evaluation's sampling assumptions. Never collapse distinct fills or financial events merely because their values match. Bound generated diagnostics, reports, and backup copies while preserving required financial evidence, decision inputs, and recovery checkpoints. Check storage growth with a representative repeated-observation workload before expanding retention.

Do not assume a provider will later reconstruct missing historical books or the exact information available to the follower.

An authorized user can export a selected run/period with account and mode, effective configuration revisions, metric definitions, financial components, times, and coverage limits. Include retained rows or references needed to reconcile the principal results, without secrets. State which historical inputs were not retained and which analyses cannot be reproduced. Provide this through the existing run/report surface; a general research platform is not required.

9.7 Independent evidence

Many fill rows can represent one underlying decision. Preserve order, market, event, and time relationships so evaluations can account for dependence.

An artificial split of a fill into many identical partial fills must not create more economic profit or unjustified confidence in skill. Validation must respect relevant time and group structure. [S20]

9.8 Normalize the participant's economic action

Decode each supported leader execution into its account wallet, native outcome/position, side, executed amounts, and reliable execution identity under the versioned adapter. Attach source-order identity where reliably available; otherwise preserve its unavailability and disable modes that require it. Matching can involve opposite sides of one outcome or the same side of complementary outcomes; blindly reversing another participant's BUY/SELL is invalid. Preserve both leader attributions when both participants are watched. Exchange/router addresses are not leaders. [S37]

Relate aggregate and per-order representations before sizing; distinct log IDs can describe overlapping activity. Balance transfers, splits, merges, conversions, and redemptions are not automatically ordinary BUY/SELL signals. Recognize unsupported inventory-dependent activity and disclose the copying limitation. Public observations cannot establish every hidden hedge. Authenticated follower streams do not imply access to a leader's private stream. [S37]

DISCOVERY, SELECTION, AND VERIFICATION

10.1 Baseline discovery

Prefer official APIs for supported leaderboards, profiles, positions, and activity. Use external scraping only when a necessary datum is unavailable, rights and maintenance costs are acceptable, and the benefit is demonstrated.

Inventory available categories and instrument types. The goal of broad leaderboard coverage does not justify inventing provider features or treating distinct instruments as interchangeable.

10.2 Metric dictionary

Every displayed metric needs:

A plain-language meaning.

Unit, period, and accounting basis.

Formula and version.

Source and last refresh.

Eligibility or missing-data behavior.

Material assumptions and uncertainty.

Begin with a few useful measures rather than dozens of impressive columns. Candidate measures include realized/marked performance, drawdown, activity history, exposure, holding period, execution cost, and copy coverage.

Provider-specific checks:

Map meaning rather than field names: the documented profile trades field counts distinct markets, not executions. Label it accordingly and obtain execution counts separately. Unknown users, absent observations, and measured zero remain distinct. [S28]

The native PnL series is cumulative. Label cumulative totals, selected-period changes, and return percentages separately. Period change requires suitable boundary observations; never sum cumulative samples. Missing boundaries mean incomplete coverage, and a percentage requires a valid capital denominator. [S29]

Preserve source-reported whole-wallet performance, but assess copy suitability using the supported activity subset. Identify excluded or unattributable contributions, such as unsupported instruments or LP activity. Do not imply that an ordinary-market copying policy reproduces success earned through other activities. [S06, S29]

Use the same metric identity across leaderboard, profile, comparison, and copy preview. Explain differences caused by period, source time, formula, or coverage. An official rank and a locally computed rank must be visibly distinguishable.

10.3 Selection workflow

DEFAULT:
Start with eligibility screening, transparent filters, sorting, candidate detail, and shortlist comparison.

Provide an optional assisted route for users who know no wallets. Use their intended allocation, a supported copying preset, and any relevant stated horizon/risk constraints to apply the same transparent rules and present a small explained shortlist. Show why candidates qualify, material limitations, and the exclusion/no-match reason. Preserve the choices into copy preview. Public-data exploration need not require trading credentials; clearly mark assumed account conditions and verify actual readiness before activation. Expert users can use the direct filter/paste route.

Check budget/policy feasibility during discovery, not only at the last activation step. Distinguish supported under observed conditions, unsupported, and unknown because evidence is missing. Offer useful next steps such as other candidates, deliberate filter changes, or an honest same-budget shadow run. Never silently relax constraints or make depositing more the sole continuation. Future liquidity/activity remains uncertain. Show recent eligible activity and freshness when available; selection assistance cannot guarantee an immediate signal or profit.

Apply portfolio constraints before activation:

Capital and minimum order feasibility.

Event and outcome concentration.

Overlap between leaders.

Liquidity and likely follower execution cost.

Holding horizon and turnover.

Available operational capacity.

Ten highly ranked wallets are not automatically a diversified or suitable set.

Assess the wallet together with the proposed copying policy, follower capital, execution delay, and account terms. Copy suitability is conditional on those tested settings. A change of sizing or exit rule can change the strategy being evaluated; preserve that identity instead of carrying forward an unqualified "good wallet" badge.

10.4 Candidate advanced methods

EXPERIMENT:
Compare a simple baseline with transparent multi-criteria scoring, portfolio selection, prediction, or AI judgment only when each addresses a concrete deficiency.

Distinguish mathematical decision models from LLM-based judges. Neither is necessary merely because many wallets exist. A model's output becomes actionable only through the same deterministic controls as other selection methods.

Evaluate incremental benefit, explanation quality, stability, inference cost, and maintenance burden. Remove a method that cannot justify itself.

10.5 Spread and copy-quality testing

The PolyCop example motivates an understandable test of how leader activity might translate into follower fills.

A verification result must state:

Which wallet, markets, time period, and sample were tested.

Test notional or sizing policy.

Order-book timing and latency assumption.

Spread, depth, fee, and partial-fill treatment.

Whether quantities were fixed or resized.

Coverage, skipped trades, and unresolved positions.

Calculation and simulator versions.

Do not retain a hypothetical fixed-notional quote while presenting unchanged leader quantities as actual executable follower results. Recalculate the follower quantity and cost consistently.

Redemption uses the relevant actual payout mechanics; it is not automatically a simulated market sale. A spread test does not establish profitability, identity, or future execution quality.

Use separate labels for provider identity verification, data completeness, completed simulation, and independently observed live execution.

10.6 Continuous usefulness

Monitor how leaders and selection rules change after admission. Define review and removal conditions, but avoid excessive churn based on noisy short-term results. Removing a leader stops new copying according to policy; existing exposure follows the explicit exit contract.

10.7 Flagship leaderboard and comparative acceptance

REQUIREMENT:
Deliver one coherent journey: browse or search -> narrow candidates -> inspect a trader and supporting evidence -> compare a shortlist -> enter clearly configured shadow or live copying. A functioning wallet list alone does not satisfy this requirement.

PolyCop's public leaderboard and trader analysis are a dated product reference, not a prescribed design or a promise that every visible calculation is correct. The inspected public UI exposed filters, sorting, favorites and notes, inline history charts, trader analysis, risk and behavior metrics, and entry points for backtesting and copying. Its inspected spread-test explanation described simulated quotes and excluded fees. Treat those observations as interface evidence, not verified economic performance. [S25]

Additional reference roles: Polymarket illustrates a focused source leaderboard with clear time/category controls; Rivo illustrates cohesive product presentation, public trader discovery, and a visible route toward simulated copying. Combine useful interaction principles, not every feature from every reference. Rivo's inspected historical copy example used leader prices and excluded fees and slippage, so it is not the realism standard for our shadow execution. No additional venue, full terminal, or bot builder becomes required through this comparison. [S26, S27]

Required first-release experience:

Browse and search discoverable candidates by supported identity fields; use supported periods/categories, transparent filters, and sorting. Distinguish the discovered candidate set from all existing wallets and disclose material coverage limits.

Show recognizable identity, wallet address, provider link, a small useful default set of metrics, and compact historical context where data supports it. Let users reveal additional measures without forcing a novice to interpret a dense table.

Keep a shortlist or favorites and compare candidates using the same metric definitions and periods. Show relevant overlap and concentration before activating several leaders.

Provide a trader detail view with performance history, material risk and behavior measures, available positions/activity, evidence coverage, and freshness. A missing or stale measure is visibly missing or stale, never a fabricated zero.

Distinguish leader performance, modeled follower performance, and observed live follower results. Explain the sizing, costs, delay, and incomplete coverage behind a copy estimate. Explain any score or badge; a proprietary competitor score is not a required algorithm.

Preserve the selected trader and relevant settings when entering copy setup. Show mode, account, allocation, readiness, and consequences before activation.

Provide coherent desktop and mobile layouts, readable charts, and usable loading, empty, error, stale-data, and partial-data states. Core comparison and activation must remain understandable on a narrow screen.

Use one short capability checklist in the existing implementation task: required, adapted, deferred, or omitted, with a reason for consequential omissions. Notes, additional metrics, and an elaborate historical backtest interface are examples to evaluate rather than automatic release requirements. The honest shadow journey remains required. Do not clone the competitor's branding, palette, layout, or arbitrary score thresholds.

Data feasibility comes before promising a metric. Extend the existing metric dictionary with its obtainable source, historical availability, formula, sample coverage, refresh plan, and computation/API cost. Official leaderboard endpoints do not by themselves establish availability of follower returns, historical order books, or all derived risk measures. If a required outcome cannot be supported, record an explicit scope or data-acquisition decision. Label representative prototype data; replace it with working integrations for release acceptance.

Define comparable tasks and pass rules before evaluating the implementation. Include finding a suitable shortlist, understanding a trader's history and evidence, distinguishing simulated from real results and costs, comparing concentration, and reaching a correctly configured copy preview. Use representative data and supported layouts. Measure completion, material misunderstandings, effort/time, responsiveness, and visual coherence separately. Automated checks and agent walkthroughs supply evidence; do not describe them as observed novice usability without an actual novice trial.

Choose the default sort deliberately and label its metric and period. Past rank, popularity, and verification badges must not silently mean "recommended for you". A novice should explain what the first-ranked row establishes and what remains untested. Primary observational copy-trading research found associations between interface rankings and copying choices on two other platforms; it motivates this comprehension check, not an assumed financial effect size for PolySia. [S41]

"Comparable or better" is a design target, not an automatic result of this document. Record the reference date, tested tasks, and conditions. Claim improvement only in dimensions supported by a fair comparison; otherwise state that the experience meets our acceptance criteria. Visual superiority needs rendered review and user preference evidence. Profitable copying needs separate economic evidence. Do not add infrastructure, metrics, or AI models merely to make the comparison appear more sophisticated.

COPY EXECUTION AND FINANCIAL INVARIANTS

11.1 Define what is copied

DEFAULT:
React to newly observed, eligible leader executions after the run's start boundary. Do not assume access to arbitrary leaders' private unfilled orders.

Copying existing holdings is a separate opt-in feature. A fresh run must not replay historical trades as new opportunities.

Initially support the market and order types covered by verified contracts. Reject unsupported multi-leg or leveraged activity with an explanation.

11.2 Entry and exit policy

The first policy should specify:

Triggering event.

Fixed or proportional sizing and rounding.

Per-order and total allocation limits.

Maximum acceptable price movement.

Signal expiry.

Order duration and cancellation behavior.

Exit and partial-reduction behavior.

Treatment of insufficient funds or liquidity.

DEFAULT:
Begin with a simple bounded sizing rule. Use a marketable limit with an explicit acceptable price boundary when immediate execution is desired. Avoid unbounded price acceptance.

Define the economic unit of sizing: source order, incremental executed quantity/notional, or another explicit unit. A delivery event or transaction hash is not automatically a new trade allowance. For fixed amounts per source order, require reliable source-order identity; otherwise use a supported sizing mode or mark that mode unavailable. Track cumulative source execution and follower commitment. Apply rounding, minimum-size handling, and caps cumulatively so splitting one order into many fills cannot multiply authorized exposure. Equivalent fragmentation/batching must preserve the target and total reservation; actual fills may differ when timing or liquidity differs. [S37]

A leader's sell should reduce the follower's attributed copied exposure proportionally under the chosen policy. Do not assume equal balances or identical holdings.

Define the reduction's denominator: reliable pre-sale leader inventory or an explicit copied-lot basis. If earlier holdings, transfers, or missed activity make that basis unknown, skip the proportional action or use a documented bounded fallback. Never infer a full exit from an unknown leader balance.

11.3 Durable intent and state

Persist the intent and its risk reservation before initiating an external effect where needed for recovery.

Maintain related but distinct state records:

Intent: observed, eligible or rejected, reserved, submission pending or uncertain, and completed.

Order: acknowledged, remaining quantity, accumulated partial fills, and cancellation/expiry/rejection of the unfilled remainder.

Fill/trade: matched, settlement pending, confirmed, or failed under the supported provider contract.

Cancellation of an order's remainder preserves its existing fills. Reconciliation applies across these records rather than acting as a fictional final order status.

Uncertain submission and unresolved settlement are explicit states, not inferred failures. Matching, settlement, and cancellation have different meanings in the provider lifecycle. [S12]

Each intent carries account, mode, run, configuration version, source event identity, and an idempotency identity. A fresh intent cannot reuse another strategy's authorization.

11.4 Financial invariants

The following are release-critical:

Spendable funds exclude pending reservations and unresolved commitments.

Inventory available to one strategy excludes inventory assigned elsewhere.

A retry or restart cannot intentionally create a second economic action for the same accepted intent.

An ambiguous provider response is reconciled before a replacement action.

A cancellation does not reverse a completed fill.

Risk checks run again immediately before submission when inputs may have changed.

Fees, minimums, tick sizes, and quantities use the current supported contract.

No action silently changes the account or mode.

A control-plane error cannot bypass the risk boundary.

Unknown account state blocks new exposure that depends on that state until the defined recovery condition is met.

Exactly-once external execution cannot be assumed from a local flag. Use provider-supported identifiers, durable records, reconciliation, and narrow retries.

11.5 Risk controls

Apply limits at account, strategy, event, and order level as appropriate:

Allocation and maximum order size.

Available balance and inventory.

Price tolerance and maximum signal age.

Concentrated exposure.

Loss or drawdown thresholds when defined.

Operational capacity and data freshness.

Supported market state and eligibility.

Give risk-reducing actions a protected execution path. A pause of new entries must not accidentally prevent reconciliation or an authorized cancellation.

The initial risk policy should be simple enough to explain. Do not invent a complex risk-scoring service.

11.6 One effective execution owner

Each trading account must have one coordinated execution authority for the initial design. Multiple strategies can submit through it.

A restored backup, old deployment, developer machine, or second agent session cannot independently activate trading using copied state. Default recovered clones to nontrading until authority and state are verified.

Handover must prevent the previous owner from acting after losing authority. A label saying "new leader" is insufficient if the old process still has unrestricted credentials.

Coordinate heartbeat ownership per API key. The documented mechanism can affect all open orders associated with that key across processes, and cancellation is best effort rather than a guaranteed instant event. [S13]

Treat the first heartbeat as a state-changing action, never a harmless connection test. Once enabled, ending the loop does not disarm the server deadline. Coordinate shutdown and verify cancellation, or transfer heartbeat responsibility while intended orders remain active. [S13]

11.7 Mode and configuration transitions

Shadow -> Live:
Create a new authorized run using reconciled real balances and positions. Transfer approved configuration, not simulated holdings, unfilled hypothetical orders, or old queued commands.

The same separation principle is reflected in established dry-run/live operating guidance. It does not require adopting another trading framework. [S15]

Pause -> Resume:
Revalidate state and stale signals. DEFAULT: do not catch up missed entries automatically.

Persist the user's requested control state separately from worker health. Restart, reconnect, upgrade, configuration reload, or added funds cannot silently undo a pause or exclusion. Pausing new entries blocks increases to existing positions as well as new positions; authorized reductions and reconciliation can continue. Freqtrade explicitly documents a nonpersistent pause; PolySia deliberately requires persistence. [S39]

Configuration change:
Read the current revision, edit, validate/preview effective differences and consequences, then apply through the authorized path in section 7.7. Show account/scope, effect timing, and how pending orders and existing positions are affected, including whether an existing position keeps its prior exit policy. Preserve applicable confirmations from section 5.3 without requiring a development PR for an ordinary supported setting.

Commit the complete valid change and revision atomically; reject stale concurrent edits rather than silently overwriting them. Record actor, scope, time, changed nonsecret values, and old/new revision. A saved revision is not proof that a worker has adopted it. Workers use complete snapshots at declared decision boundaries; new exposure cannot bypass current authority, control state, or applicable limits because a worker is stale. Report pending adoption/restart and failures honestly.

Retain each intent's original decision evidence. Invalidate or re-evaluate unsubmitted intents and adjust reservations consistently; a raised limit does not automatically enlarge an old intent. Already submitted or uncertain requests retain reconciliation/cancellation obligations and may still fill. Define the submission/cutover boundary; never claim a change retroactively stops an external request already sent.

Restoring earlier settings creates a new validated revision for subsequent decisions. It cannot undo fills, erase commitments, reset consumed allowance, revive stale commands, clear a pause/exclusion, or restore revoked authority. Reject old settings that violate current constraints. Preserve effective nonsecret snapshots, schema/code versions, and transition history so results remain explainable.

Allocation change:
DEFAULT: depositing into the account does not increase strategy authority. An explicit allocation increase supplies capacity for future eligible signals, without immediate rebalancing. A reduction releases only verified uncommitted cash; canceling orders or selling positions to release more is a separately explained action. Preview any limit recalculation. This differs from products that automatically rebalance on funding changes; it is a deliberate first-policy choice. [S40]

Deployment or restore:
Reconcile external state and execution authority before permitting new exposure.

11.8 Stop and recovery

Expose three separate actions:

Pause new entries.

Cancel unfilled orders.

Attempt to close positions under stated price/liquidity constraints.

The entry pause invalidates pending entry intents that have not been submitted; accepted external orders require separate cancellation. An emergency disable prevents further signal-driven submissions, including automated exits, while preserving reconciliation and explicitly authorized protective cancellation. Disabling locally does not by itself cancel resting orders at the venue.

Closing may be partial or impossible at the desired price. Show remaining quantity, pending action, and estimated value.

On partial infrastructure failure:

Keep execution independent of the UI and optional analytics.

Stop new exposure in the affected account, market, action, or shared dependency when its required present state cannot be verified.

Continue authorized reconciliation and protective actions where possible.

Recover from durable state.

Require verified readiness before reactivation.

Continue independent verified flows when their own preconditions hold. Missing optional analytics or uncertainty about future profitability is not a global readiness failure. Shared dependencies determine the true scope of a block. Estimates of future outcomes cannot substitute for verified present authority, funds, or unresolved order state.

11.9 Resolution and settlement

Support the documented lifecycle for resolved, disputed, delayed, winning, losing, and redeemable positions. Zero payout is a valid economic result. Preserve unresolved positions rather than inventing closure.

Route redemption and related operations through verified market-version adapters. Fractional or exceptional payouts must follow authoritative resolution data when supported. [S14]

Auto-redemption is an optional explicit permission and policy. It must not imply withdrawal authority.

11.10 Later leader activity can supersede a pending intent

Track ordered intent versions and the current authorized target/exit obligation for each supported leader allocation and outcome. Before submission, check subsequent reliable leader activity. An observed exit can supersede an unsubmitted entry in the same run, even if both signals are young enough to pass the age limit.

For an accepted entry, retain the pending cancellation/reduction obligation until actual exposure is reconciled. A temporarily empty available balance does not complete an exit. Handle late partial fills under the authorized exit policy; never sell unrelated shares. Some provider delay windows prevent immediate cancellation, so the UI must show residual exposure rather than promise that a reversal prevents every fill. [S12]

SHADOW OPERATION AND ECONOMIC VALIDATION

12.1 Shared logic, separate state

Use the same signal eligibility, allocation, and risk logic for shadow and live execution. Separate execution adapters and account state prevent hypothetical actions from becoming real.

A shadow run has a run ID, observation start, configuration version, assumed capital, sizing rules, and data-quality record.

Preserve its initial configuration and subsequent effective revisions. Freeze the policy for a comparative experiment; a change informed by its results is a new experimental variant, while ordinary product settings changes need not invent a new run or reset the observation boundary.

12.2 Realistic follower execution

Simulate with information available after the follower observes the leader, plus a measured or declared execution delay.

Account for:

Available book depth and spread.

Fees and relevant charges.

Minimum size, tick size, and rounding.

Partial fills and failed or stale orders.

Queue uncertainty for passive orders.

Shared liquidity across simultaneous signals.

Shared capital across selected strategies.

API delays, missing observations, and inability to act.

A leader's fill price or a midpoint mark is not an assumed follower fill. Avoid deterministic certainty where order priority is unknown.

Apply the follower account's verified or explicitly assumed fee, rebate, and reward eligibility at the relevant time. Do not award it the leader's volume tier or quoting incentives. Current Polymarket programs distinguish account tiers and qualifying liquidity provision; taker-tier changes apply prospectively. Keep observed incentive income distinct from assumptions or unavailable data. [S38]

Evaluate a small declared range of capital and delay around the intended operating case. A tiny live proof does not establish larger-size capacity. Report tested conditions and sensitivity, including unfilled/skipped activity and idle capital; do not extrapolate returns linearly.

12.3 Incomplete outcomes

Stopping a trial does not force every position to become closed.

Report:

Realized result.

Open quantity and marked value.

Estimated liquidation value with depth assumptions.

Pending orders and commitments.

Coverage and missing information.

Costs already incurred versus estimated.

Show a range or explicitly approximate value when appropriate. Preserve whether the result was observed, simulated, or estimated.

12.4 Economic evaluation

Measure net follower outcomes, drawdown, capital utilization, event exposure, missed opportunities, tracking difference, and uncertainty. Separate strategy returns from deposits and withdrawals.

Compare alternatives prospectively under matched capital, risk, observation windows, and execution assumptions. Keep the simple baseline available.

For a claim about wallet selection, name the control: for example, a frozen, seeded eligibility-only shortlist with the same leader count, permitted risk, copying policy, dates, capital, and account terms. Do not cherry-pick the control seed. Include the no-copy cash outcome as an absolute reference. Compare portfolio outcomes and unused capital, not only returns from successful individual copies. Profit alone does not establish that selection added value.

Register before evaluation:

Hypothesis and change.

Eligible universe and selection time.

Metrics and costs.

Evaluation period.

Stopping and failure conditions.

Configuration and code version.

Experiment family, attempted variants, and evaluation windows already inspected by a person or AI.

Preserve failed trials. Avoid selecting only surviving wallets or using later information to choose historical candidates.

12.5 Statistical judgment

Do not treat repeated fills, correlated markets, or repeated parameter searches as independent demonstrations of skill.

Use time-aware and group-aware validation appropriate to the question. Correctly representing dependence matters more than claiming a fixed universal minimum number of trades. [S20]

After a result informs a human or AI revision, that window is development evidence for the revised rule, not untouched confirmation. Preserve all attempted variants and original outcomes within the existing experiment record; a new session or configuration name does not reset the search history. Confirm on subsequent/untouched observations or an explicitly justified adaptive method. Multiple-testing research supports tracking the search; no particular adjusted score becomes a required leaderboard metric. [S42]

A small live experiment calibrates execution assumptions; it does not prove sustainable profitability. A sandbox validates integration behavior; it does not reproduce production liquidity.

12.6 Development priorities after the first proof

Prefer changes that improve measured user outcomes, execution fidelity, risk-adjusted economic evidence, or operating efficiency.

For a proposed analytic feature, ask:

What decision will change?

Which baseline does it improve?

What will demonstrate failure?

What does it cost to run and maintain?

Can it be removed cleanly?

Do not equate a higher leaderboard score with a better investment outcome.

PERFORMANCE AND DYNAMIC CAPACITY

13.1 Measure the whole chain

Record observation latency, normalization time, decision time, risk-check time, queue delay, request duration, acknowledgment, fill delay, and reconciliation delay.

Use distributions such as p50, p95, and p99. State the workload, deployment region, provider path, market conditions, and release. Separate system-controlled latency from leader waiting and venue execution time.

Keep LLM inference outside the mandatory per-order path. Use AI asynchronously for development, explanation, or evaluated research.

13.2 Capacity estimation

Estimate usable leader/account capacity from:

Observed activity and burstiness.

Shared versus per-leader data subscriptions.

Endpoint and IP limits.

Signer-specific order and cancellation limits.

Reconciliation and retry demand.

CPU, memory, network, and storage.

Available funds and actual market liquidity.

Protect a measured adaptive reserve for critical operations. Do not impose an arbitrary permanent limit such as ten wallets regardless of workload.

Provide a clear user message:
"Your current setup can support approximately this workload. The limiting factor is this resource. Here is what changes if you add these leaders."

If confidence is low, admit conservatively and learn from observed load.

13.3 Priorities and backpressure

Prioritize:

Reconciliation, safety controls, and authorized cancellation.

Time-sensitive trading and account updates.

Discovery refreshes.

Optional reports, experiments, and notifications.

Bound queues and expire stale work. Measure provider throttling rather than blindly increasing concurrency.

13.4 Scaling and migration

Scale the proven bottleneck. Examples include a dedicated worker process, batched reads, shared subscriptions, indexes, or a larger host.

Horizontal execution requires authority and reservation controls before adding replicas. Preserve data export and adapter interfaces so a future provider or hosting migration is practical.

SECURITY, ELIGIBILITY, AND AUTHORIZED TESTING

14.1 Account authority

Distinguish viewing public data, reading private data, trading, canceling, transferring, and withdrawing. A connected account is not automatically authorized for every operation.

Prefer minimum practical delegated authority. Clearly show the account's actual capability. The custody and signing design must be validated before live operation.

Application identity is separate from trading identity. Use a maintained authentication implementation with secure sessions and recovery. Passkeys, federated login, or passwords are implementation choices; choose one coherent initial route. Add step-up verification for sensitive owner actions.

14.2 Secret handling

Keep secrets out of Git, chat transcripts, screenshots, logs, fixtures, analytics, and ordinary task documents.

Inject secrets into the authorized runtime through a secret reference. Encrypt stored credentials appropriately and keep their decryption authority separate from exported application data.

Do not copy all credentials to every developer or agent. Redact diagnostics and test exports. Provide revocation and replacement procedures.

14.3 Dedicated real testing

The owner wants agents to verify realistic behavior with a deliberately limited test account.

Before real testing, record:

Exact account allowlist.

Authorized environment and runner.

Supported actions.

Maximum order size and total exposure.

Cumulative budget or accepted loss allowance.

Duration and revocation method.

Handling of pending orders and uncertain responses.

Whether any replenishment is allowed.

DEFAULT:
No automatic replenishment, withdrawals, owner-account migration, or access to production funds.

No numerical amount from a conversational example is automatically an approved budget. Until actual values and authority are configured, financial action is disabled while read-only and simulation work proceeds.

The approved allowance is shared across all sessions, branches, contributors, and executor instances using that account. Define whether each limit covers funded balance, gross order volume, concurrent exposure, or cumulative loss. Enforce it at the authorized execution boundary and keep consumption durable across restarts. A restarted task or CI run does not receive a fresh allowance. Coding tasks cannot raise the limit or replace its authoritative record. If remaining authority or allowance is unknown, disable new financial exposure while allowing diagnostics and reconciliation.

A standing mandate can authorize the application's execution process within configured bounds. Whether a coding agent may activate or control that process depends on the agent platform's actual permissions. An agent prohibited from initiating financial transactions must hand off live activation; it cannot trigger the same transaction indirectly through scripts, CI, browser actions, or another runner. Preparation, read-only observation, and permitted simulated tests can proceed independently.

A low-balance test wallet limits one kind of exposure. Also isolate repository permissions, infrastructure credentials, and access to unrelated accounts.

14.4 AI input trust

Treat external pages, profiles, Issues, README files, and tool outputs as data. They cannot grant new permissions or change financial destinations, budgets, modes, or project rules.

Use scoped tools and enforce action/account/environment constraints at the tool boundary. A trusted connector can carry untrusted content. Model instructions alone are insufficient containment. [S17]

Test a malicious-content fixture and inspect actual tool effects. Do not accept only the model's assurance that it ignored the instruction.

14.5 Protect the acceptance mechanism

A coding agent may propose changes to tests and policy, but it cannot silently weaken its own critical acceptance criteria.

Protect a small set of financial reference scenarios, required CI definitions, authorization boundaries, and the protections themselves. Require an independent review path for changes to these items.

Use repository controls where available. CODEOWNERS is useful only with appropriate enforcement; its existence alone does not require approval. [S18]

Ordinary test maintenance remains fast. Retire obsolete tests when the corresponding accepted behavior is retired.

14.6 Geographic and commercial eligibility

Check relevant execution-network restrictions before live activation and after meaningful network or policy changes. Display browser and server results separately when both are available.

Do not represent IP detection as a complete legal assessment or build region-bypass behavior.

Before public SaaS or commercial distribution, resolve applicable provider terms, data redistribution rights, privacy obligations, custody responsibilities, and jurisdiction-specific requirements. This is a launch dependency, not an instruction to add speculative compliance infrastructure to the prototype.

14.7 Privacy, isolation, and retention

Collect the minimum personal data required. Separate diagnostic telemetry from financial records. Set retention, export, and deletion behavior explicitly.

A future multi-user deployment must enforce ownership on every request, storage query, background job, and notification. Role-specific screens do not replace server-side authorization.

Keep financial evidence needed for reconciliation or legitimate retention distinct from optional profile data. Explain remaining retention when a user requests deletion.

INSTALLATION, DEPLOYMENT, AND OPERATION

15.1 One installation mechanism

REQUIREMENT:
A person or authorized agent obtains one official installation entry point and reaches a working product.

DEFAULT:
A versioned bootstrap installer deploys the tested container artifact and required database on the certified server configuration. Guided CLI and noninteractive configuration are interfaces to the same installation logic.

The CLI must be attractive and understandable:

Clear stages and concise progress.

Friendly names and useful next actions.

Redacted inputs and explicit account/mode display.

Detection of ports, resources, dependencies, and configuration conflicts.

Safe retry and resume.

An actionable final summary with URL, version, health, and remaining steps.

Structured machine-readable output and meaningful exit codes.

Before owner initialization, access is local-only or protected by an authenticated single-use setup mechanism. Do not ship shared default credentials. Remote credential entry and authenticated use require secure transport. Explain any remaining network or certificate step clearly. Installation never enables live execution automatically, and rerunning setup must preserve established ownership.

Do not present several competing old/new installers in the active README.

15.2 Reproducibility and updates

Build once and promote the same validated artifact. Record source revision, resolved dependencies, build identity, migrations, and test evidence.

Use supported stable releases and reproducible lockfiles. Automate dependency-update proposals and compatibility checks. "Stay current" does not mean resolving untested latest versions every time the application starts.

Handle direct and transitive dependencies. Do not force incompatible transitive upgrades merely to make every version numerically newest.

15.3 Persistent-data changes

Before the first upgrade affecting data:

Define migration ordering and compatibility.

Back up the relevant state.

Verify restore behavior.

Plan forward repair or rollback.

Identify which migrations cannot be undone safely.

Returning to an older application image is not sufficient after an incompatible database migration.

15.4 Runtime resilience

Use health indicators that distinguish:

Process is running.

Provider data is fresh.

Account state is reconciled.

Execution is permitted.

Strategy is making valid decisions.

Economic results are acceptable.

An alive process can be operationally unready. Optional UI, analytics, or notification failures should not stop safe core work.

Use bounded retries with classification and backoff. Avoid retry storms and unbounded self-healing. Do not create new exposure while correcting unknown financial state.

15.5 Logs, telemetry, and support

Use structured events with run, account, intent, and trace identifiers. Record the causal chain without secrets.

Provide:

User-friendly explanations.

Operator diagnostics and alerts.

A redacted support bundle.

Links from an incident to the responsible workflow and recent changes.

Diagnostics should identify bottlenecks, stale data, permissions, provider failures, and internal defects. Telemetry itself must have a cost and retention budget.

15.6 Recovery and exit

Test backup restoration into a nontrading environment. Reconcile with the provider before activating a restored execution owner.

Provide data export, direct-management instructions, uninstall behavior, and migration documentation. Uninstalling must not be described as canceling external orders.

Define the service's behavior after loss of its host, database, network, signer, or owner access. Do not promise uninterrupted trading through a total execution-environment failure.

HUMAN AND AI DEVELOPMENT WORKFLOW

16.1 Provider-neutral collaboration

The repository must carry enough current knowledge for a new human, AI session, or model provider to continue without private chat memory.

Use shared instructions and commands. Provider-specific instruction files should reference the canonical rules rather than duplicate them.

Define tasks using section 22.2 in the existing issue or PR, with an owner, affected interfaces, dependencies, and explicit exclusions where relevant. The task, review, evidence, and handoff fields describe information in that same record; they do not require separate documents. Keep the single current-state summary aligned and omit inapplicable fields for trivial changes.

16.2 Default task loop

Read the current-state record, task, relevant instructions, and affected contracts.
Bind the task to its base commit, relevant accepted decisions, applicable acceptance scenarios, and affected naming/design authorities. Verify that this session can run the required checks and inspect the changed journey.

Establish the baseline or reproduce the issue.

Resolve material uncertainty with a focused check or small prototype.

Implement the smallest useful complete change.

Run risk-proportionate automated checks.

Directly exercise the changed UI/CLI journey where applicable.

Inspect results and fix observed problems.

Update affected documentation and decisions.

Check continued necessity of the affected workflow and retire unnecessary artifacts under section 17.4.

Submit evidence and a concise handoff.

Avoid repeated broad audits without a defined decision or failure hypothesis.

At initial setup, verify repository access, build/run tools, browser inspection, required network access, secret references, and permitted test-runner capabilities for the next milestone. The agent prepares ordinary tooling, fixtures, repeatable tests, and isolated test identities; arrange a test inbox only when the chosen login or notification flow requires it. Group remaining owner-only access, budget, or authority questions with proposed defaults in the existing task/current-state record, then continue independent work. Do not require every future account or credential before starting.

Apply the proactive collaboration rule in section 1.5 during normal work. Keep the few consequential open assumptions and the next evidence-producing action in the existing current-state record. Do not add a recurring review ceremony or produce an exhaustive gap catalogue. Once the next decision has sufficient evidence, proceed with authorized work.

16.3 Shared commands

Provide a small stable command surface for:

Setup.

Run.

Fast check.

Relevant tests.

Full or release validation.

Build.

Diagnostics.

The exact runner is a routine implementation choice. Humans, agents, and CI must invoke the same underlying tasks.

16.4 Five independent contributors or AI accounts

Support separate credentials and consumption accounts working on one repository.

Each concurrent task needs an isolated branch/worktree or environment and a clear interface agreement. One task has one active owner.

An initial allocation may cover architecture/integration, backend, frontend, trading, and verification. Prefer vertical feature slices once contracts exist; permanent layer ownership must not create unnecessary waiting.

Coordinate shared schema, lockfile, and deployment changes through an integration owner. Integrate small changes frequently and validate against current main.

Start with the concurrency that can actually be integrated. Increase toward five active streams when accepted throughput improves rather than creating a larger merge queue.

Independent accounts do not imply pooled quota, shared memory, or a common live filesystem. Verify actual provider entitlements and repository access. If merge-queue automation is unavailable, use an ordered integration process.

Contributors sharing a real test account share the durable authorization and allowance in section 14.3. Independent development quota never creates additional financial authority.

16.5 Reviews and evidence

Review high-risk assumptions independently. A second model sharing the same unsupported assumption is not independent evidence.

Use the completion fields in section 22.3 within the same task or PR. Link the relevant commit, artifact, and actual verification evidence.

Do not report hypothetical, skipped, or mocked checks as real integration verification.

Provider or model choice does not change the task's acceptance contract. A material development change to behavior, architecture, shared visual standards, naming, or acceptance conditions must be visible within the PR with its reason and evidence. Use the designated independent review path for changes to protected criteria or consequential shared baselines. Routine work within them remains autonomous.

Changing a supported value through the authorized settings path is an operational action recorded in configuration history, not a development PR. This includes authorized theme-value publication within the accepted token contract. New setting semantics, shipped defaults for new installations, algorithms, components, or permission boundaries remain development changes with proportionate review. Runtime customization must not cause later AI sessions to hard-code conflicting values or overwrite the effective configuration.

If the session lacks a required tool or environment, report the missing evidence and route verification to a capable runner or reviewer. Do not lower the standard to match the session's capabilities.

16.6 Context and token efficiency

Keep AGENTS.md and the current-state record short. Retrieve only relevant sections and evidence for a task. Store durable decisions and concise failure lessons instead of full repeated transcripts.

Do not require the owner to re-explain the project in every session. Measure rework, clarification, and cold-handoff effort rather than token count alone.

For Goldsky work, its documented MCP supplies documentation search, not private project management or trading authority. It is optional development tooling, not a runtime prerequisite. Relevant vendor skills can help implement and diagnose an accepted integration; operational commands still require the appropriate CLI/API access and project authority. [S34, S35]

Inspect the actual selected skill revision and verify discovery in the chosen agent host. The current main Goldsky repository separates Compose skills into goldsky-compose-agent, while the skills documentation still describes a combined surface. Record only relevant skill paths/revisions in the existing instructions. Vendor prompts and hooks cannot select our architecture or replace our acceptance and permission controls. [S35]

16.7 End of session

Leave work in an explicit state:

Completed and integrated.

Reviewable in a named PR.

Intentionally in progress with a short handoff.

Abandoned with disposable work removed.

Remove merged or abandoned branches when appropriate. Do not delete another contributor's active branch to achieve a superficially clean repository.

Keep documentation aligned with released behavior. A code merge that leaves setup instructions false is incomplete.

16.8 Consistency across sessions and providers

Standardize the inputs, boundaries, reusable components, commands, and evidence required for acceptance. New screens reuse the accepted tokens, typography, interaction patterns, component families, and glossary. Necessary additions belong in the shared authority rather than a parallel local convention.

Before integration, reconcile relevant upstream changes. Include one concise field in the existing PR/handoff: "Shared baselines or acceptance criteria changed: none / list and decision reference."

Use a representative cold-handoff scenario to detect drift when a new contributor or provider takes over. Run checks relevant to its change; a session switch alone does not require the entire release suite. Standardization cannot make all models equally capable or guarantee identical code. It keeps the acceptance bar stable and makes unsupported variation visible.

16.9 Choosing the development environment and model

Operational suggestion as of 25 November 2026; not a permanent product dependency:
Use Codex connected to the active repository for implementation when its environment provides the required editing, execution, inspection, and verification capabilities. Other capable agents remain valid under the same repository contracts. Codex is the dedicated software-development surface; available models and features depend on the account, client, and workspace. [S21]

DEFAULT: use a reusable Codex Cloud environment when the repository, tools, and required services are reachable; use local execution where a real local dependency requires it. Verify browser-test capability and credential delivery in the actual environment. Cloud tasks have separate working state; commit accepted work and retain evidence outside a task's saved workspace. Use a supported persistent test/deployment host for prolonged observation and installation proofs. Network-secret substitution is not equivalent to providing secret bytes to a local signer; choose the protected mechanism the selected protocol requires. These are execution recommendations, not product dependencies. [S50]

For this complex project, a practical starting choice is GPT-6.2 Astra at high reasoning effort. Use xhigh for consequential architecture/security analysis or difficult cross-component problems when it improves accepted results. Reserve max for unusually hard problems after the lighter setting proves insufficient. These are recommendations to evaluate, not claims that a setting is optimal for every task. Official guidance associates Astra with demanding engineering and treats reasoning effort as a quality/latency/cost tradeoff. [S22, S23]

Ultra is documented as using subagents for divisible work; do not treat it as merely another name for the next sequential reasoning level. Use it when independent tasks and integration ownership are clear. GPT-6.2 Sol is an alternative for well-scoped routine work where its results meet the same acceptance bar at lower cost. Verify the actual selector options before relying on a mode. [S22]

Compare representative tasks using total time to an accepted outcome, rework, verification quality, and cost. Keep the lightest configuration that satisfies the same quality bar. Revisit the choice when evidence or available models materially changes. [S24]

Start with the current milestone and its acceptance scenarios. Do not ask one unattended run to implement the entire document at once.
Several milestones may continue in one session when practical. Checkpoint accepted work and the next action so an interruption or new session does not require restarting the project.

QUALITY GATES AND PREVENTION OF ACCUMULATION

17.1 Quality is outcome-based

Test that the intended behavior exists and failure conditions are handled. Avoid tests that merely repeat implementation details or preserve obsolete functionality.

Use:

Unit tests for important deterministic rules.

Contract tests for provider and internal boundaries.

Integration tests for transactions, reservations, and reconciliation.

Browser and CLI tests for critical user journeys.

Controlled fault tests for financial recovery.

Visual/accessibility checks for changed critical surfaces.

Use selective mutation testing or independent reference calculations for high-consequence rules when they resolve a meaningful uncertainty.

17.2 CI structure

DEFAULT:
One stable required CI result with parallel work underneath.

Fast checks:
Formatting, static validation, and relevant tests.

PR checks:
Affected integration, contract, and critical user-journey checks.

Release checks:
The actual artifact's installation, upgrade, recovery, and critical end-to-end scenarios.

Optional skipped work must remain distinguishable from passed required work. Do not make essential checks vanish through broad path filters.

The required result succeeds only when all checks needed for the change succeed against the actual integration candidate. Failure, cancellation, timeout, or an unexplained skip cannot produce a successful aggregate. Recheck affected behavior when the candidate changes. Bind the gate to the trusted CI identity where supported; an ordinary coding identity must not satisfy it by posting a same-named status. Use ordered integration when automated merge-queue support is unavailable.

Run broader tests when a gate or concrete risk requires them. A small UI wording change does not need a full trading experiment.

17.3 Agent testing as a user

Agents must be able to run the application, inspect UI/CLI state, complete flows, and observe outcomes. Automated test success alone does not satisfy a usability acceptance scenario.

Use seeded demonstrations, fake-provider fixtures, local integration tests, approved sandbox access, and bounded real-service tests in increasing order of consequence.

Record which environment produced each result.

17.4 Keep only necessary work

Every significant capability must serve a current supported user journey, external contract, operational/safety obligation, supported transition, or bounded committed experiment. Its purpose, owner, acceptance behavior, and status belong in existing code, tasks, or decisions; do not create another capability or per-file registry.

A topic, role, requirement, or acceptance case in this plan does not by itself justify a new file, document, folder, test suite, service, or checklist. Update the existing authoritative location first. Create a separate artifact only when a current reader or executable consumer needs it and separation improves use or maintenance. Write the shortest explanation that preserves necessary actions, conditions, failure behavior, and evidence. Store routine review/session results in the task or PR and generated evidence in the appropriate artifact store with bounded retention.

When goals, provider contracts, implementations, or milestones change, inspect the affected workflow for continued necessity, including whole branches that still import and test one another. Reachability, passing tests, stylistic quality, and past investment do not establish current value. A capability can become unnecessary without a replacement being built. Use this relevance check during the actual change or milestone instead of adding recurring repository-wide audits.

When replacing or retiring a capability, remove its exclusive:

Code, adapters, tests, and fixtures.

Instructions, examples, and obsolete active documents.

Configuration, environment variables, flags, and dependencies.

CI jobs, deployment scripts, and deployed processes or schedules.

Persistent structures that no supported consumer or retention obligation requires.

Verify remaining consumers before removal. Stop former writers before retiring stored structures, and preserve required financial records, decision evidence, and recovery paths. Low usage, file age, or lack of ordinary imports alone does not justify deleting recovery, security, CLI entry points, or supported migrations.

Any temporary compatibility path, migration, or experimental artifact needs a concrete removal trigger in its existing task or decision. Resolve it when that trigger occurs; do not silently carry it forward. Preserve source history through version control instead of active archive folders. Uncertain necessity calls for a bounded investigation, not automatic deletion or permanent retention.

17.5 Experiments and feature flags

Each experiment needs a hypothesis, evaluation point, owner, and retain/revise/remove decision. Every temporary flag needs a removal condition.

Give each feature switch a type, scope, safe default/error behavior, and an effective variant record where decisions depend on it. Switches cannot grant trading authority, activate live mode, bypass eligibility, or disable protected checks. OpenFeature is an optional reference for typed/default evaluation, not a substitute for the configuration or financial authority contract. [S48]

Do not keep an unsuccessful subsystem merely because it is already implemented. Preserve its concise lesson and result, not an active maintenance obligation.

17.6 Learning from development

Use existing task/PR records and CI artifacts to retain the intended outcome and comparator, relevant revision/environment, consequential decisions, actual checks/measurements, rework and defects found after integration, human intervention and its reason, and useful time/cost/model information when available. These facts should support comparisons across approaches and sessions; a trivial edit does not require a research dossier or another report file.

17.7 Operational quality of dependencies

Automate compatibility checking and dependency-update PRs. Re-run the relevant behavioral contracts for breaking changes.

A repair is accepted only when verified. "Self-healing" must not silently change financial policy or repeatedly mask an unresolved defect.

MEASUREMENT AND ACCEPTANCE TARGETS

18.1 Establish baselines early

Measure:

Time from setup start to a working application.

Time from connection to readiness.

Time and assistance from starting wallet selection to an understood, executable configuration; separate user effort, account prerequisites, waiting for an eligible signal, and venue execution time. More trades or faster risk-taking alone do not establish user success.

Time from eligible leader observation to follower action.

Time to first understood result.

Time from a user action to clear interface feedback, and time to complete the task under representative data/network conditions; distinguish interface delay from legitimate waiting for a leader or venue.

Unassisted completion of critical user tasks.

Reconciliation discrepancies and unresolved-state duration.

Rework, integration delay, and accepted-task throughput.

Operating cost at an observed workload.

Net follower outcomes and risk.

Do not invent performance numbers before the first measured slice. After measurement, publish numerical targets with the test conditions and keep them stable during an evaluation.

For a consequential milestone, record one short acceptance agreement in the existing task: user outcome, baseline/comparator, measurement method, quality constraints, target, time/cost budget, decision owner, and pass/revise/stop rule. Use initial measurements to calibrate a target, then fix it before evaluating the candidate change. If evidence is insufficient, report "not yet established" rather than "passed".

Measure development speed as accepted useful outcomes per elapsed time and cost while preserving required quality. Faster generation, more PRs, or fewer tokens alone do not establish improvement. Prefer current supported methods when they pass the relevant compatibility and outcome checks; novelty alone is not evidence of speed or quality.

18.2 Non-negotiable behavioral criteria

No cross-account or cross-mode financial action.

No deliberate duplicate action after an ambiguous response.

No new exposure above configured reservations and authority.

No unsupported claim that a pending action completed.

No secret in ordinary logs or repository artifacts.

No silent conversion of simulated state into real orders.

No unexplained loss of position attribution.

No live activation from an unverified restored clone.

No unannounced weakening of critical acceptance rules.

These are invariants to test, not statistical goals that allow a small error percentage.

18.3 Thresholds required before live activation

Record actual values for:

Maximum order notional.

Total allocation and accepted test budget.

Maximum price deviation and signal age.

Data freshness and reconciliation timeout.

Retry and queue bounds.

Minimum supported account/market conditions.

Stop and reactivation policy.

An unset financial limit disables new live exposure. It must not mean unlimited.

18.4 Benchmarking

Compare with:

Accepted product versions with reproducible evidence.

Relevant competitor journeys under stated conditions.

The current simple internal baseline.

Compare task success, clarity, reliability, latency, economic fidelity, and cost. Do not compare only screenshots, lines of code, or unverified marketing claims.

18.5 Cost and stop rules

Set a small stage-specific time and cost budget. If a spike fails to establish necessary feasibility, record the failure and simplify, change approach, or stop that branch.

Forecast delivery from accepted milestones and observed throughput; model capability alone does not establish a completion date.

IMPLEMENTATION SEQUENCE

Milestone 0: Establish the executable baseline.

Create or designate the clean active repository.

Add the concise shared instructions and canonical commands.

Record current implementation state and provisional defaults.

Verify the minimum provider capability matrix.

Scope the current milestone's data source. Evaluate a managed candidate under section 8.8 before committing to custom chain-indexing work; unavailable access does not block independent setup.

Identify the authorized test-account path without collecting secrets into documents.
Exit: another agent can run the starter project and understand its current scope.

Milestone 1: Walking skeleton and account truth.

Install the built artifact on the certified server configuration.

Open the web interface.

Connect one supported account in read-only mode.

Display actual data, freshness, and readiness.

Render a clickable leaderboard-to-trader-detail preview and establish the visual direction early. Use clearly labeled representative data where integration is not ready; this preview is not proof of working analytics or execution. Review the interaction against section 10.7 and refine the same components as real data arrives.

Walk the assisted/direct routes against the relevant P01-P07 cases, including no-match and changed-settings states. Demonstrate one real runtime preference/theme change through the shared settings path; grow the same contract as operational controls appear.

Trace a request through UI, backend, provider, and diagnostics. Present a minimal owner overview of the implemented journey, milestone, verified capabilities, blockers, and next action. Derive it from existing records; a simple rendered page is sufficient. Expand it at Milestone 4.
Exit: a clean install and a connected-account journey work with inspectable evidence.

Milestone 2: One leader and honest shadow copying.

Search or paste a leader.

Observe eligible activity.

Apply one simple sizing and risk policy.

Simulate execution using contemporaneous data.

Display real/simulated distinctions and incomplete results.

Implement pause, stop, and state-safe restart.

Accept incremental workflows when a user can reach them from discovery, complete a decision, inspect durable effects and recover the same state. A bounded series may run while the operator keeps the portfolio open. Save the receipt, source identity and policy for each completed window. Model size and fee assumptions explicitly. Track exits, marks and continuous coverage separately as they become supported.

Exit: the complete shadow journey passes its critical acceptance scenarios.

Milestone 3: Bounded live execution.

Configure explicit test authority and numeric limits.

Complete signing and eligibility checks.

Verify financial reservations, uncertain-response recovery, and execution ownership.

Submit a bounded real copy through the approved executor.

Reconcile the outcome and demonstrate controlled stopping.
Exit: at least one authorized, bounded copy is genuinely executed, with settlement status, ledger effect, elapsed time, and remaining exposure visible. A rejected order verifies an error path, not the first-trade journey. No profitability claim is inferred.

Milestone 4: Useful individual release.

Add multiple accounts and leaders within measured capacity.

Deliver the flagship leaderboard, trader detail, shortlist comparison, and copying-entry journey against section 10.7, using working data integrations and explicit coverage limits.

Complete polished key flows, notifications, diagnostics, and owner visibility.

Verify installation, upgrade, backup, restore, and exit.
Exit: another eligible user can operate the product with limited assistance; the relevant P01-P07 tasks and flagship discovery journey pass their predefined acceptance checks. Everyday supported configuration/theme changes pass A38-A39. Record evidence for any claimed advantage over the reference experience.

Milestone 5: Evidence-driven economic and engineering improvement.

Compare the baseline with narrowly selected changes.

Calibrate simulation with allowed real observations.

Improve actual bottlenecks and user misunderstandings.

Remove features or experiments that do not justify themselves.
Exit: improvements have reproducible evidence and a clear maintenance cost.

Milestone 6: Optional expansion.

Confirm demand and cost for managed hosting, billing, mobile/desktop, new instruments, or advanced selection.

Resolve the relevant identity, isolation, commercial, and operational dependencies.

Reuse established contracts and acceptance scenarios.
Exit: the additional distribution or capability has its own verified user outcome.

At every milestone, preserve a runnable product. Parallelize independent work after interfaces are sufficiently clear. Do not begin all milestones simultaneously.

Choose the next task by the most consequential unresolved assumption. Prioritize a bounded source-to-follower/shadow proof at the intended capital, delay, and costs before expanding settings machinery or polishing broad persona coverage. Record what the proof will establish and what will be revised or stopped if it fails. Keep the existing live-execution gates and eventual installation/visual/user acceptance requirements; a successful fill alone is not economic validation.

CRITICAL ACCEPTANCE SCENARIOS

Use these as behavioral anchors. Implement the smallest tests that establish the stated behavior. Cross-references to evidence may replace repeated prose in future versions.

A01. Clean install
For a distributed release, begin at the repository page with ordinary reader access. Obtain the tested bytes through its published instructions, verify their identity, and reach the first understood result (A03). Include how to recover, update, and get help. Record clean-host execution and observed first-time user completion separately under section 5.5.

On a fresh certified host, the single installer reaches a usable application and reports remaining user steps. A second run preserves data and resumes safely.
An uninvited visitor cannot claim the initialized instance, overwrite the owner, or retrieve stored credentials through setup.

A02. Invalid or insufficient connection
Invalid credentials, unsupported account capabilities, insufficient funds, and geographic restrictions produce distinct explanations without leaking secrets.

A03. First understood result
A user identifies the selected account, mode, action, amount, elapsed time, actual outcome, and remaining exposure.
The returning-user variant in P05 makes those answers available for the selected interval without reconstructing logs, including healthy waiting and a paused/stale case.

A04. Honest waiting
A leader that has not traded produces a waiting state, not fabricated activity or an unexplained failure.

A05. Partial fill
A partly executed order updates only the executed quantity, retains remaining commitments correctly, and shows its state.
Mixed successful, pending, and failed settlements remain visible individually; an SDK success return alone cannot establish full execution. See S44 for a version-specific reported test lead, not a confirmed current defect.

A06. Lost submission response
A network failure after submission does not cause an immediate duplicate. Reconciliation determines the next permitted action.

A07. Concurrent reservations
Two strategies competing for the same funds or inventory cannot overcommit them.

A08. Strategy attribution
One leader's exit cannot sell another strategy's or the user's manually owned position.
Unknown prior leader holdings cannot be interpreted as a verified full liquidation signal.

A09. External account change
A manual trade, transfer, or revoked permission is detected and reconciled under the documented policy.
A promised close-and-exclude instruction survives restart; later signals cannot silently undo it. Unexplained external reductions follow the intervention policy rather than automatic replenishment.

A10. Shadow to Live
Queued shadow orders and simulated holdings cause no automatic real orders when Live is enabled.

A11. Resume with stale commands
A paused run does not blindly execute missed or expired entries after resuming.
Restart/reload and added funds preserve the pause. A fresh BUY in an already-held market cannot increase exposure while paused; an authorized reduction remains possible.

A12. Duplicate deployment
An old instance, restored backup, or second test session cannot act as a competing authorized executor.

A13. Heartbeat coordination
An isolated test cannot interfere with the active loop using the same key. Timeout cancellation is reported according to confirmed results.
A diagnostic check does not arm cancellation; a handover does not assume that SDK shutdown disables the server deadline.

A14. Scope of visibility
An empty signer-specific result does not cause the UI to claim the entire wallet has no orders.

A15. Cancel versus close
Canceling an order does not erase existing fills; stopping copying does not silently liquidate positions.

A16. Offboarding
Disconnect, revocation, subscription termination, and uninstall show what remains and how control continues.

A17. Delayed or exceptional resolution
Unresolved, disputed, losing, and redeemable positions remain correctly represented. Zero payout is valid.

A18. Provider migration
Different supported market versions, asset identifiers, fee rules, and schema revisions use the correct adapter behavior or are explicitly blocked.

A19. Data integrity
Duplicate/out-of-order events, incomplete pagination, stale quotes, and missing intervals cannot silently inflate balances or confidence.
Metric fixtures check cumulative-to-period conversion (100 at the start and 140 at the end means a change of 40 regardless of intermediate sample count), market-versus-execution counts, and separation of supported copy activity from whole-wallet performance. Cross-screen differences expose their changed basis.
For a managed event source, redelivery, interruption/restart, correction, and historical replay preserve consistent records and create no duplicate or historical live action. A stopped or exhausted feed is visible and follows the existing stale-data policy.

A20. Shared simulated resources
Concurrent copies share simulated capital and liquidity rather than each consuming an impossible full book.

A21. Fill-splitting invariance
Splitting an economic fill into many equal partial records with the same aggregate economics does not invent profit or independent evidence.
For equivalent execution conditions, replaying one source order as one fill or twenty fragments preserves its authorized copy target and total reservation. Duplicate and aggregate representations and per-fragment minimum rounding cannot create additional allowance.

A22. Historical integrity
An evaluation cannot use future observations or silently replace the selected universe after seeing outcomes.
A revised rule cannot report a previously inspected window as untouched validation. Attempted variants, evaluation-window use, and the predeclared comparison remain traceable across sessions.

A23. Failure isolation
The dashboard or notification service can fail without disabling safe execution. Unknown financial state prevents exposure dependent on that state. A degraded account or optional analytic does not block independent verified flows; shared financial or provider dependencies determine the actual scope.

A24. Recovery
An interrupted upgrade or restored backup produces a recoverable state; activation requires verified ownership and reconciliation.

A25. Permission isolation
A user, job, or notification cannot access another account or workspace outside its authority.

A26. Malicious external content
Injected instructions in a profile, README, or tool result cannot expand tool authority or change financial policy.

A27. Protected acceptance
A PR that skips a protected financial scenario or weakens required checks cannot self-approve under the coding identity.
Stale, canceled, missing, or counterfeit required-check results cannot authorize the integration candidate.

A28. Accessible critical journey
Keyboard-only operation, clear focus, non-color status, responsive layout, and understandable error states work for the core journey.

A29. Cold handoff
A fresh human or AI session can explain the active workflow, locate evidence, and complete a scoped task without this chat.
The new session preserves accepted interface, naming, design, and acceptance baselines unless a change is explicitly justified and reviewed. Missing tools are reported as missing evidence.

A30. Continued necessity and complete retirement
Replacing or retiring a capability removes its exclusive artifacts and deployed activity under section 17.4. A whole workflow is not retained solely because its components reference and test one another. Remaining supported consumers, safety duties, and required historical evidence stay intact; temporary retention has a concrete removal trigger.
Routine completion updates the same task/PR and current instructions without producing parallel reports. Verify the affected retirement in the actual change; this criterion does not require a generic automated judge of business necessity.

A31. Current dependency update
A dependency change is reproducible and passes the behavior it could affect before release.

A32. Honest economic report
The report separates cash flows, realized and unrealized results, costs, simulation assumptions, and uncertainty.
It uses the follower's applicable economic terms and states tested capital/delay. A selection claim reports its eligibility-only control and absolute outcome separately; the leader's rebate tier cannot be inherited. Tier changes affect only eligible subsequent activity.
An authorized export of a fixed period allows reconciliation of the displayed realized result and actual costs, with external flows, open estimates, configuration changes, and missing evidence distinguishable.

A33. Deliberate visual quality
The critical journey is inspected in its supported rendered layouts and states. It is coherent, attractive, readable, and efficient under the accepted design intent. A fixed palette is not required by this plan; a later session cannot silently invent a conflicting visual system or declare success solely by updating screenshots.

A34. Flagship leaderboard outcome
The section 10.7 journey works from discovery through trader evidence and shortlist comparison to a correctly configured copy preview. It uses working integrations, honest metric coverage, and usable desktop/mobile states. Task completion and material misunderstandings meet the rules set before evaluation. A generic wallet list, unlabeled demo data, or attractive screenshots without working interactions cannot satisfy this scenario. Any superiority claim identifies the measured dimension and comparison evidence.
Opening a trader and returning preserves discovery context; proceeding to setup preserves applicable choices and makes changed mode, account, or calculation assumptions clear.
A novice can distinguish the default historical rank from a recommendation or evidence of profitable copying under their settings.
With no supplied wallet address, a novice can use the assisted route to reach an explained candidate and correct preview. Budget fixtures cover a feasible candidate, no supported candidate, and insufficient evidence. The user distinguishes these outcomes and finds a useful next action without an automatic budget increase or weakened controls. Measure selection effort separately from signal waiting.

A35. Participant-relative decoding
For each supported position system and exchange revision, fixtures for ordinary BUY/SELL, complementary BUY/BUY, complementary SELL/SELL, both parties watched, and overlapping aggregate/per-order logs produce the correct wallet, outcome, side, and quantity. Unsupported inventory operations are explicit; a transfer or merge is not fabricated as a standalone sale.

A36. Leader reversal during pending entry
Replay leader BUY -> pending follower entry -> leader exit -> late partial fill. Unsubmitted stale exposure is suppressed; accepted orders retain cancellation/reduction obligations and honest residual exposure until reconciled under the exit policy.

A37. Allocation and understandable limits
With $100 allocated, $60 in positions, $20 committed, and $20 free, a $30 reduction cannot silently sell or report $30 immediately released. An added $50 causes no immediate trade. Monetary previews make percentage limits and resulting actions understandable; withdrawing free allocation is not a trading loss, and a pause/exit trigger is not represented as guaranteed maximum loss.
A cautious and a deliberately risk-tolerant user can each reach and explain a different supported economic configuration, preserve it, and revise it within authority while the same correctness checks remain active.

A38. Everyday changes without development
An authorized user changes a supported copy amount or signal-age value through product settings; the next applicable eligible decision uses the complete effective revision without source edits, PR, rebuild, or redeployment. A personal theme selection and an authorized shared-token change work independently and persist across restart/upgrade. Invalid values, unsupported keys, inaccessible supported combinations, or unauthorized scopes cannot partially publish.

A39. Configuration cutover and prospective rollback
Concurrent stale edits cannot overwrite one another silently. Crash recovery exposes the old or new complete revision, not a mix. A delayed worker cannot increase exposure under superseded applicable limits. Tightening limits handles pending intents/reservations and already-submitted orders honestly; raising a limit does not enlarge an old intent. Restoring settings preserves fills, obligations, allowance consumption, pauses, exclusions, and current authority. Saved/applied state and consequences for existing positions are visible. UI/API/CLI/imports, supported environment overrides, and flags share the same validation boundary.

A40. Reconnection without duplicate money
Connect the same supported trading wallet using different verified credentials or labels. It remains one financial account with one balance/reservation/budget authority; credential replacement preserves history and shows actual capabilities. Distinct accounts remain distinct.

DECISIONS, DEPENDENCIES, AND UNRESOLVED VALUES

21.1 Defaults selected by this baseline

D01. Self-hosted web first; managed SaaS and native clients are later.
D02. TypeScript/React/Vite frontend and Python backend/trading core.
D03. Modular application, PostgreSQL, isolated API/execution processes.
D04. One supported installation mechanism with human and noninteractive interfaces.
D05. Official contracts and direct APIs provide the initial baseline. Evaluate a managed source before custom indexing; select on demonstrated total value, with no predetermined vendor choice.
D06. Simple filter/sort and bounded copy rules before advanced selection models.
D07. One account and one leader prove the journey; multi-account identity is designed early.
D08. No automatic historical catch-up when starting or resuming.
D09. Funding and position-exit workflows use explicit authority and user-visible consequences; no owner-level financial permission is inferred from a connection.
D10. Shared instructions and small evidence-based tasks for all contributors.
D11. Exact dependency versions are resolved and locked at implementation, then updated through checks.
D12. The independent control implementation is selected during setup; the protected constraints below remain mandatory.
D13. Supported everyday settings and theme values use one typed, versioned runtime configuration path inside the existing application. Dedicated configuration/flag services and generic rule builders are deferred unless justified.

Changing a technology default needs a short reason, affected contracts, evidence, and validation impact. After a default is accepted as an implementation decision, it remains the working baseline until explicitly superseded. This does not require redesigning the whole plan.

Protected requirements, not discretionary technology defaults:

Financial authority, test allowances, and withdrawal/transfer permissions cannot be expanded by a coding task.

No automatic replenishment or forced liquidation is inferred from the current scope.

Financial records and critical acceptance controls remain protected independently of ordinary agent edits.

Applicable platform permissions remain binding.

A written preference for a different implementation cannot weaken these constraints.

21.2 Values to resolve at the relevant gate

Before repository setup:

Active repository location and access.

Available GitHub protections and collaboration capabilities.

Before certifying installation:

Exact supported host configuration and artifact distribution route.

Authentication/recovery implementation.

Backup, migration, and secret-store implementation.

Before live testing:

Supported wallet/account type and delegation path.

Actual test-account identity and authorized executor.

Numeric budget, limits, and expiry.

Current provider compatibility and geographic readiness.

Before promising performance:

Recorded workload and measured baseline.

Agreed latency, capacity, reliability, and usability targets.

Before public managed service:

Tenant isolation, billing/end-of-service behavior, commercial terms, privacy, support, and operating economics.

Do not invent values merely to make the document appear complete. Unresolved values block only the relevant action; they do not block independent development.

21.3 Important hypotheses

The selected leader activity is observable quickly and completely enough for the proposed copying method.

Follower execution remains economically meaningful after delay and costs.

The first deployment is capable of the target workload.

The proposed simple selection process is useful enough for the first release.

Additional analytics or AI judges can provide incremental value.

A managed event source reduces implementation/maintenance work or improves data/performance enough to justify its total cost while satisfying the same contracts.

Each hypothesis needs a focused experiment. Failure is a reason to change the method, not conceal the result.

21.4 Bounded next investigations

Before live execution, resolve the source-to-intent fixtures in A21/A35/A36 and the control/allocation behavior in A09/A11/A37 for the first supported account and copying policy. Before claiming selection value, run the predeclared comparison in section 12 with available point-in-time evidence, account terms, and capital/delay sensitivity. Before accepting discovery UX, test A34's rank and result comprehension on the rendered journey.

These are focused proofs within the existing stages, not a new research platform. Missing economic evidence limits economic claims; it need not block independent UI or engineering work. Stop open-ended tool hunting once the next decision can be made; preserve unresolved hypotheses instead of manufacturing certainty.

For the useful individual release, resolve the P01-P07 task outcomes with rendered evidence and appropriate user trials, and demonstrate A38-A40. Paper persona review predicts obstacles; it does not establish actual task success, satisfaction, profit, or a measured improvement in speed.

CONTINUATION PACKET AND REUSABLE TASK TEMPLATES

22.1 Current-state record

Maintain one short record with:

Active repository and commit.

Current release and deployment.

Milestone and active task owners.

Verified capabilities and evidence links.

Open blockers and consequential decisions.

Next concrete action.

Relevant budget/authority references, never secrets.

Base revision and links to the accepted design, interface, naming, and acceptance authorities relevant to the next task.

Use the current README continuation point and accepted main branch to resume work. Each milestone exit requires evidence for its own claims.

22.2 Task template

Outcome:
Who needs what observable improvement?

Context:
Relevant plan sections, issue, code, interfaces, dependencies, and evidence.

Constraints:
Authority, cost, compatibility, financial invariants, and scope.

Acceptance:
Concrete successful, partial, and failure scenarios.

Implementation:
Smallest reasonable approach; alternatives only when consequential.

Verification:
Commands, user journey, environment, and observed result.

Cleanup:
Continued necessity of affected work, justified new artifacts, and complete retirement under section 17.4.

Handoff:
Commit/PR, remaining limitations, and next action.
Shared baselines or acceptance criteria changed: none / list and decision reference.

22.3 Session completion template

Changed:
Verified:
Evidence:
Removed or superseded:
Unresolved:
Next action:

Use these fields in the existing task/PR, not a separate session document. Do not claim checks that were not run.

22.4 Starter instruction for a new AI session

"Use this PolySia Master Plan as the intent baseline. Read the current-state record, assigned task, base revision, and relevant accepted decisions before acting. Distinguish requirements, provisional defaults, accepted decisions, experiments, and later options. Proactively identify consequential missing needs, unsupported assumptions, and unnecessary work; help clarify the goal instead of waiting for the owner to supply a checklist. Verify current provider contracts where your task depends on them. Implement a small complete outcome, test its relevant behavior and rendered UX, update affected truth, and apply section 17.4 to artifact creation and continued necessity. Preserve shared naming/design standards, account/mode/financial boundaries, acceptance criteria, and tool permissions. Report actual evidence, proposed baseline changes, and remaining uncertainty in the existing task/PR. Do not infer implementation completion from this planning document."

22.5 Updating this plan

Update affected sections in place when a consequential decision changes. Keep the reason and acceptance impact in the existing task/PR or version history; create a separate durable decision note only when continued discovery requires it. Keep historical revisions in version control or document version history, without appending a cumulative changelog or accumulating duplicate "final" plans.

This plan, the repository's current state, and its verification evidence should allow the project to continue even if the original chat disappears.

SOURCES AND EVIDENCE

23.1 Official and primary sources

Provider facts are time-sensitive. Accessed 25 November 2026 unless otherwise recorded. Keep each source attached to the limited claim it supports.

Distinguish a documented mechanism, an original incident report, inspected code, a reproduced result, and our design inference. For consequential GitHub findings, retain package/revision, date, reproduction, maintainer status, and relevance to the selected current adapter. README claims and issue comments are test leads, not automatic proof. S43 is a methodological example with material limits; no external profit figure is a PolySia target or verified outcome.

[S01] Polymarket: Data API v1 to v2 migration.
https://docs.polymarket.com/migrate/data-api-v1-to-v2

[S02] Polymarket: Protocol V2 migration overview.
https://docs.polymarket.com/migrate/polymarket-v2/overview

[S03] Polymarket: pUSD collateral.
https://docs.polymarket.com/concepts/pusd

[S04] Polymarket: API and authentication layers.
https://docs.polymarket.com/getting-started/api

[S05] Polymarket: Session Keys, wallet-wide order management, revocation.
https://docs.polymarket.com/trading/session-keys

[S06] Polymarket: Trader leaderboard definitions.
https://docs.polymarket.com/api-reference/boards/get-the-trader-leaderboard

[S07] Polymarket: Trading fees.
https://docs.polymarket.com/trading/fees

[S08] Polymarket: Geographic restrictions.
https://docs.polymarket.com/api-reference/geoblock

[S09] Polymarket: API rate limits.
https://docs.polymarket.com/api-reference/rate-limits

[S10] Polymarket: Trading rate limits.
https://docs.polymarket.com/api-reference/trading-rate-limits

[S11] Polymarket: NEX Sandbox.
https://docs.polymarket.com/nex/overview

[S12] Polymarket: Order lifecycle.
https://docs.polymarket.com/concepts/order-lifecycle

[S13] Polymarket: Order management, cancellation, and heartbeats.
https://docs.polymarket.com/trading/manage-orders

[S14] Polymarket: Resolution.
https://docs.polymarket.com/concepts/resolution

[S15] Freqtrade: Configuration and separation of dry-run/live state.
https://www.freqtrade.io/en/stable/configuration/

[S16] NASA: Technical requirements definition and validation.
https://www.nasa.gov/reference/4-2-technical-requirements-definition/

[S17] Anthropic: How we contain Claude across products.
https://www.anthropic.com/research/how-we-contain-claude

[S18] GitHub: Code owners and enforcement.
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

[S19] W3C: Web Content Accessibility Guidelines 2.2.
https://www.w3.org/TR/WCAG22/

[S20] scikit-learn: Cross-validation, grouped samples, and time dependence.
https://scikit-learn.org/stable/modules/cross_validation.html

[S21] OpenAI: ChatGPT Work and Codex.
https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex

[S22] OpenAI: Models in Work and Codex, reasoning controls, and Ultra.
https://learn.chatgpt.com/docs/models

[S23] OpenAI: Reasoning effort.
https://developers.openai.com/api/docs/guides/reasoning

[S24] OpenAI: Model selection and evaluation of settings.
https://developers.openai.com/api/docs/guides/model-selection

[S25] PolyCop: public leaderboard and trader-analysis interface.
https://polycop.fun/leaderboard
Inspected in the rendered public browser interface on 25 November 2026. Observed leaderboard identity, filtering/sorting, favorites/notes, inline trend and P/L charts, Analyze/Backtest entry points, the spread-test explanation, and a public trader analysis with period controls, P/L curve/calendar controls, risk/behavior measures, and positions/closed/activity records. Analysis settings exposed a record-count range. The inspected spread-test explanation described a simulated 200 USDC buy, unchanged original quantities, and excluded fees; this is a disclosure to examine, not an endorsed follower-accounting method. One profile request returned an error while older analysis remained visible, illustrating why observed controls do not establish complete operational reliability. No login, transaction, or backtest execution was performed, and calculations were not independently reproduced. These observations support interface comparison only.

[S26] Polymarket: public leaderboard interface.
https://polymarket.com/leaderboard
Public desktop UI inspected on 25 November 2026: instrument tabs, period/category controls, name search, PnL/volume sorting, profile links, and a biggest-wins panel. The realized-only PnL tooltip requires reconciliation with the selected API contract as noted in section 8.4. No transaction or mobile usability test was performed.

[S27] Rivo: public product presentation and trader journey.
https://rivo.markets/
https://rivo.markets/traders
https://rivo.markets/trader/polymarket/0x664ce9fb97ae1bbd538d7381b2f4e92dab16f49c
Public desktop UI inspected on 25 November 2026: a landing-page terminal preview, trader filters and summary metrics, a detailed profile, inactivity explanation, historical copy controls, and a paper-bot entry link. The inspected copy explanation used tracked settled entries at leader prices without fees or slippage. Preview controls, published claims, and links are not verified execution. No sign-in, subscription, bot creation, or trade was performed; calculations were not independently reproduced.

[S28] Polymarket: user profile-stat semantics.
https://docs.polymarket.com/api-reference/wallet/get-a-users-profile-stats

[S29] Polymarket: cumulative user-PnL series and components.
https://docs.polymarket.com/api-reference/wallet/get-a-users-pnl-series

[S30] Goldsky: platform overview and historical Polymarket case study.
https://goldsky.com/
https://goldsky.com/case-studies/polymarket-goldsky
The case study is dated 16 January 2024 and discusses Mirror/Subgraphs. Treat vendor examples and performance statements as dated claims, not measurements of PolySia.

[S31] Goldsky: prediction-market datasets and wallet-data scope.
https://goldsky.com/solutions/prediction-markets
https://goldsky.com/solutions/wallets

[S32] Goldsky: Compose Polymarket copy-trader guide.
https://docs.goldsky.com/compose/guides/build-a-polymarket-copy-trader
Documentation and visible-code review only. No installation, account connection, deployment, or transaction was performed; the complete example repository was not audited.

[S33] Goldsky: Turbo delivery guarantees and HTTP destination.
https://docs.goldsky.com/turbo-pipelines/delivery-guarantees
https://docs.goldsky.com/turbo-pipelines/sinks/webhook

[S34] Goldsky: documentation MCP.
https://docs.goldsky.com/mcp-server

[S35] Goldsky: agent-skill documentation and current official repositories.
https://docs.goldsky.com/ai-skills
https://github.com/goldsky-io/goldsky-agent
https://github.com/goldsky-io/goldsky-compose-agent
Documentation and repository summaries were reviewed; individual installed skill behavior and host compatibility were not exercised.

[S36] Goldsky: current pricing and credit-exhaustion behavior.
https://goldsky.com/pricing
https://docs.goldsky.com/pricing/summary

[S37] Polymarket: participant, position-system, order, and event semantics.
https://docs.polymarket.com/trading/realtime-order-updates
https://docs.polymarket.com/resources/onchain-position-data
https://github.com/Polymarket/polymarket-v2-external/blob/main/docs/exchange.md
https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/exchange/mixins/Events.sol
Official documentation/code support partial execution, participant-relative matching, and overlapping event representations. Repository exchange prose contains a signing-domain value different from current migration/onchain documentation; use it here for matching-path descriptions only. Verify signing and decoding against the supported deployed market/revision, not an undated generic example.

[S38] Polymarket: account-specific rebates and liquidity rewards.
https://docs.polymarket.com/programs/maker-rebates
https://docs.polymarket.com/programs/taker-rebates
https://docs.polymarket.com/programs/liquidity-rewards
Current mechanisms distinguish wallet tiers, execution role, qualifying quoting, and effective time. Rates and thresholds remain implementation-time provider data.

[S39] Freqtrade: pause/stopentry operation.
https://www.freqtrade.io/en/stable/telegram-usage/#pause-stopentry-stopbuy
Official guidance documents reduction-only position adjustments during pause and a pause state that resets on restart. This is documented product behavior, not a new defect claim.

[S40] eToro: copy systems, reallocation, and copy stop-loss conventions.
https://www.etoro.com/copytrader/how-it-works/
First-party product policy illustrates funding-triggered reallocation and percentage ambiguity. It does not prescribe PolySia's policy or establish guaranteed executable exits.

[S41] Kawai et al., Stranger Danger? Investor Behavior and Incentives on Cryptocurrency Copy-Trading Platforms, CHI 2024.
https://www.andrew.cmu.edu/user/nicolasc/publications/Kawai-CHI24.pdf
https://doi.org/10.1145/3613904.3642715
Primary observational study of two platforms; ranking-choice associations have platform, period, and confounding limits. No effect size is transferred to PolySia.

[S42] Bailey and Lopez de Prado, The Deflated Sharpe Ratio, author-hosted 2014 paper.
https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf
Primary methodological support for recording attempted alternatives and selection bias. Its specific statistic requires suitable assumptions and is not mandated here.

[S43] OrcaLayer: original Polymarket copy-trading backtest repository.
https://github.com/orcalayer/polymarket-copy-trading-whales-backtest
Method inspected, results not reproduced. Uses fixed-notional copies at a fixed price penalty and holds to resolution; discloses look-ahead in one screen and uneven statistical treatment. Full rerun requires its API. Useful experiment ideas, not live execution or universal profitability evidence.

[S44] Polymarket py-sdk issue 266: reported mixed settlement outcomes.
https://github.com/Polymarket/py-sdk/issues/266
Opened 12 August 2026 for polymarket-client 0.5.0; still labeled needs-triage when inspected. Reporter describes partial failures omitted from a settlement helper's result. Not reproduced here or established for the current release; use as an A05 regression-test lead. No claim of lost funds is adopted.

[S45] Nielsen Norman Group: cognitive walkthrough method.
https://www.nngroup.com/articles/cognitive-walkthroughs/
Structured task inspection can predict learnability problems; it is distinct from observing real users. The P01-P07 needs and three review passes are this plan's application of the method, not externally established customer research.

[S46] Design Tokens Community Group: Format Module 2025.10.
https://www.designtokens.org/tr/2025.10/format/
Primary reference for typed, interchangeable token values and aliases. This is a Community Group specification, not a W3C Standard. It does not provide a runtime editor or guarantee accessible rendered combinations.

[S47] Vite: environment variables and modes.
https://vite.dev/guide/env-and-mode
Build-time substitution of client environment constants is distinct from runtime configuration; client-exposed values must not contain secrets.

[S48] OpenFeature: Flag Evaluation API.
https://openfeature.dev/specification/sections/flag-evaluation/
Primary reference for typed evaluation and explicit default/error behavior. Optional implementation aid; not an authorization system or an atomic financial-configuration mechanism.

[S49] OWASP: Authorization Cheat Sheet.
https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
Supports permission enforcement for every request regardless of entry path. The scoped configuration, economic authority, and transition rules in this plan remain our design requirements.

[S50] OpenAI: current Cloud environments, execution modes, and browser testing.
https://learn.chatgpt.com/docs/environments/cloud-environments
https://learn.chatgpt.com/docs/environments/modes
https://learn.chatgpt.com/docs/browser
Cloud access, tools, credentials, and task state must be verified in the selected environment. A separate persistent product/test host is a project recommendation, not a claim that Cloud provides production hosting.

[S51] scikit-learn: probability calibration.
https://scikit-learn.org/stable/modules/calibration.html
Supports checking probabilistic estimates against observed outcomes. Methodology reference only; no library adoption or prediction subsystem is required.

END OF BASELINE VERSION 1.10