# Inventory Forecasting Scenario

## Overview

Build a reusable inventory forecasting scenario using synthetic data, a baseline forecasting approach, and a minimal demo path.

This scenario should focus on forecasting future item demand from **historical inventory movement data**. The intent is to create a practical reference implementation that can later act as a starting point for broader stock planning and predictive workflows.

The contribution should remain self-contained, use only synthetic or openly shareable data, and be designed in a way that can later align with real stock-ledger style systems.

## Problem Statement

Given historical inventory movement data, derive demand signals and forecast future item demand over a selected time horizon.

The solution should demonstrate a practical forecasting workflow that can:
- work on structured stock movement data
- derive usable demand patterns from transaction history
- generate future demand projections
- expose results through simple APIs
- provide a basic web experience to inspect and run forecasts
- produce outputs that can be reused later in broader planning flows

## Scope

The scenario should focus on:
- inventory movement history as the primary source
- demand forecasting for items over time
- synthetic sample data
- a baseline forecasting implementation
- a minimal API layer
- a minimal web app or demo path for running and viewing forecasts
- supporting documentation for setup, usage, and assumptions

## Non-Goals

This work item is not intended to cover:
- production SQL or ERP integration
- exact replication of any real database schema
- procurement or reorder automation
- full inventory optimization
- product-grade security or tenancy
- advanced platform orchestration
- customer-specific business logic

## Suggested Stack

To stay broadly aligned with our ecosystem, contributions should preferably use:
- Python for forecasting logic
- Prophet as a baseline forecasting model
- a lightweight API layer in Python
- Next.js and TypeScript for the minimal web app or demo layer

Equivalent alternatives may be proposed if well justified.

## Data Expectations

The synthetic dataset does not need to follow any exact real-world schema, but it should preferably resemble an **inventory movement ledger** rather than only a pre-aggregated demand table.

Useful field groups may include:
- item identity
- transaction timestamp
- quantity
- movement direction such as stock-in or stock-out
- movement type or transaction category
- stock before and after movement
- basic reference or counterparty context where relevant

Contributors are free to design the exact schema as long as it supports deriving time-based demand suitable for forecasting.

## Expected Deliverables

A good submission should include:

- a working forecasting implementation
- synthetic or generated sample data
- a simple API layer to trigger or retrieve forecast results
- a basic web app or UI path to run and inspect forecasts
- documentation covering setup, usage, assumptions, and limitations
- measurable output or evaluation of forecast quality

The API and UI do not need to be production-grade, but they should be usable enough for reviewers to understand and exercise the scenario.

## Success Criteria

A submission will be considered successful if:
- it clearly solves the inventory forecasting problem
- it is runnable and understandable by reviewers
- it uses synthetic or non-sensitive data only
- it demonstrates forecast output for item demand
- it shows how demand is derived from movement-style inventory history
- it exposes the scenario through a simple, usable API
- it includes a basic web app or UI path for interaction and result viewing
- it includes clear documentation for local setup and usage
- it provides enough structure to be reused later as a foundation for broader predictive scenarios

## Notes

This is intentionally framed as an open scenario, not a tightly specified build sheet. Contributors are expected to apply their own thinking to:
- data design
- demand derivation approach
- forecast method
- API shape
- web interaction model
- evaluation method
- result presentation

Strong submissions will balance practicality, clarity, and reusability.
