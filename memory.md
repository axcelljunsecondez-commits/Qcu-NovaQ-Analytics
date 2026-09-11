# NovaQ Project Memory

## Product Direction

NovaQ is currently a web-based, pilot-deployable capstone system, not a full commercial SaaS product.

Primary development priorities:

1. Correctness
2. Understandability
3. Usability
4. Deployability

The system should remain usable by people without formal queueing-theory knowledge.

## Architecture

- Frontend: React 19 + Vite
- Backend: FastAPI
- Database: PostgreSQL 16
- Reverse proxy: nginx
- Deployment architecture: Docker Compose
- Simulation: SimPy discrete-event simulation
- Monte Carlo simulation is also supported

## Queueing Principles

- Queueing-model selection must use the existing centralized model-selection service.
- Do not silently substitute one queueing model for another.
- Service-time variability must be considered when determining whether M/M/c or M/G/c is appropriate.
- Analytical, optimization, and DES outputs answer different questions and must not be presented as interchangeable.

## Optimization

- Utilization targets are configurable operational/study parameters.
- A utilization target must not be presented as a universal mathematical optimum.
- Stability constraints must be enforced.
- Optimizer recommendations must respect configured constraints.

## Monte Carlo

- Default Monte Carlo trials: 2,000.
- Monte Carlo failure must have an explicit operational definition.
- Monte Carlo settings must remain configurable where exposed by the application.

## UX Direction

Preferred user flow:

Login
→ Introduction / onboarding
→ Setup
→ Upload data
→ Current Analysis
→ Optimize
→ Simulation
→ Comparison
→ Report

Avoid duplicate setup inputs across pages.

Technical queueing terminology should be translated into understandable operational language where possible.

## Engineering Rules

- Preserve established queueing formulas unless a verified defect requires correction.
- Prefer minimal regression-safe changes.
- Investigate root cause before modifying code.
- Validate frontend, backend, and relevant tests before claiming completion.
