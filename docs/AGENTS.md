# AGENTS SYSTEM — SENTIENCE CORE

## Overview

The Sentience Core system is built on a **multi-agent cognitive architecture**.

Instead of relying on a single monolithic AI, the system distributes cognition across specialized agents, each responsible for a specific function within the decision-making pipeline.

Agents operate under constraints, communicate through structured interfaces, and converge through controlled arbitration mechanisms.

---

## Core Design Principles

### 1. Specialization Over Generalization
Each agent performs a narrow cognitive role with high precision.

### 2. Limited Context Scope
No agent has full system visibility. Context is intentionally partitioned.

### 3. Controlled Communication
Agents do not directly execute actions. They propose, evaluate, or validate.

### 4. Consensus-Based Decisioning
Critical outputs require agreement between multiple agents or validation by a Guardian layer.

---

## System Agent Topology

```mermaid
graph TD

Input[User / External Input] --> Analyst
Input --> Strategist

Analyst --> Memory
Strategist --> Memory

Analyst --> DecisionEngine
Strategist --> DecisionEngine

DecisionEngine --> Executor
DecisionEngine --> Guardian

Executor --> Tools
Guardian --> ValidationLayer

ValidationLayer --> Executor
Executor --> Memory
Memory --> Analyst
