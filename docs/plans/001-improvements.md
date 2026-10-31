# General

- Confirm support for repositories containing these languages at the least: Python, C, C#, Rust, Zig, JavaScript/React, HTML/CSS, shell scripts
- Remove "Executive summary" and "Contents" cards from the following reports:
  - Gaps and assumptions
  - Corrections
  - Risk register
- Shade or color the cards on each report differently:
  - Shade/color 1: Cards containing only facts gathered from the repository
  - Shade/color 2: Cards containing statements produced by an LLM, which may include a mixture of retrieved facts and cited, inferred, and unknown statements.

# This dossier

## About this build

- Remove the "THIS PROJECT" box
- Rename this card to "About this dossier"

## Reading coverage

- These statistics should become BANs in the "About this build" card. No "What it means" column needed. Then this card can be removed.
  - Files analyzed and files not counted should be in one BAN separated by a `/`
  - Reading mode and chunks should be in one BAN

## History of updates

- Rename to "Dossier changelog"

# Overview

- Rename this report to "This repository"
- Remove the "Most changed files" card
- Remove the "Project manifests" card

## Repository at a glance

- Rename this card to "Overview"
- Remove "Commits over time" graphic
- Remove the "Contributors" BAN
- Remove the "Dependencies" BAN
- Add a box that shows:
  - Repository name
  - Branch
  - Remote URL
  - Pinned commit
  - Commit date
- Add a box that shows:
  - Project name
  - Project version
  - Project author

# Risk register

- Rename this report to just "Risks"
- Rename the "Risks register" card to just "Tracker"
- Move this report into the "TRACKING" section

# Contributors

## Contributor knowledge map

- Remove the "Last 12 mo" toggle from Measure
- The "N commits carry an AI-assistant marker..." should be formatted as subtext
- Remove "Blend" as a measure

# Gaps and assumptions

- Rename this report to just "Gaps"
- Move the BANs outside the card and color-code them, to align with the style used in the Risks report

# Corrections

- Rename the "Recorded corrections" card to "Tracker"
