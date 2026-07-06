# CONTRIBUTING — SENTIENCE CORE

## Overview

Sentience Core is designed as an **open cognitive infrastructure system**.

Contributions are not limited to code. Improvements can include:

- Architecture design improvements
- Agent behavior refinements
- Documentation enhancements
- Performance optimizations
- New cognitive modules or tools
- Security and reliability upgrades

This project prioritizes **system coherence, clarity, and long-term scalability** over raw feature addition.

---

## Contribution Philosophy

### 1. System First Thinking
Every contribution must consider the impact on the full cognitive architecture, not just isolated modules.

### 2. Stability Over Complexity
Prefer simple, maintainable improvements over overly complex solutions.

### 3. Explainability Requirement
All contributions must be explainable in terms of:
- Why it exists
- What problem it solves
- How it integrates into the system

### 4. Agent-Aware Design
Any change must consider how it affects:
- Analyst behavior
- Strategist logic
- Decision Engine flow
- Memory persistence
- Learning feedback loops

---

## Types of Contributions

### 1. Core Architecture
Changes to system structure:
- Agent topology
- Decision pipeline
- Memory engine design
- Model routing logic

### 2. Intelligence Layer
Improvements in reasoning:
- Strategy generation
- Confidence scoring
- Multi-agent consensus logic
- Learning mechanisms

### 3. Infrastructure
System performance and reliability:
- API optimization
- Database improvements
- Latency reduction
- Scaling architecture

### 4. Documentation
High-value contributions include:
- Architecture explanations
- System diagrams
- Cognitive flow descriptions
- API documentation clarity

---

## Development Workflow

### Step 1 — Fork the Repository
Create your own version of the system.

### Step 2 — Create Feature Branch
Use descriptive naming:

```bash
feature/agent-improvement
fix/memory-leak
docs/decision-engine-update
```

### Step 3 — Local Testing

Ensure system integrity:
- All agents initialize correctly
- Decision Engine produces valid outputs
- Memory writes are consistent
- No routing failures in Model Router

### Step 4 — Commit Standards

Commit messages must be clear and structured:
feat: improve strategist confidence weighting
fix: memory retrieval inconsistency in edge cases
docs: update agent communication protocol
refactor: simplify decision aggregation layer

### Step 5 — Pull Request Requirements

Each PR must include:
- Description of change
- Reason for change
- Impact on system architecture
- Any performance implications
- Optional diagrams (recommended for architecture changes)

---

## Code Standards

### 1. Clarity Over Cleverness
Readable code is mandatory.

### 2. Deterministic Behavior
All core systems must behave predictably.

### 3. Stateless Logic Where Possible
Prefer stateless design for agents and tools.

### 4. Logging Required
All critical actions must be traceable.

---

## System Safety Rules

Contributors must not:
- Break agent isolation boundaries
- Remove Guardian validation layer
- Bypass decision engine arbitration
- Hardcode model dependencies
- Disable memory logging

---

## Agent Contribution Guidelines

### Analyst Improvements
Must enhance:
- Signal extraction
- Context structuring
- Noise reduction

### Strategist Improvements
Must enhance:
- Decision diversity
- Risk-aware planning
- Scenario generation

### Executor Improvements
Must maintain:
- Safe execution guarantees
- API reliability
- Failure recovery mechanisms

### Memory Engine Improvements
Must ensure:
- Consistent persistence
- Fast retrieval
- Structured knowledge storage

### Learning Engine Improvements
Must ensure:
- Stable weight updates
- Traceable learning paths
- No catastrophic forgetting

---

## Review Process

All contributions are reviewed based on:
- System coherence
- Architectural alignment
- Performance impact
- Safety compliance
- Maintainability

---

## Acceptance Criteria

A contribution is accepted if:
- It improves or stabilizes system behavior
- It does not break existing agent interactions
- It respects architecture constraints
- It is clearly documented
- It passes basic integration tests

---

## Final Note

Sentience Core is not just software.

It is a cognitive system architecture experiment.

Contributions must respect the long-term vision of building a modular, evolving, and explainable intelligence framework.
