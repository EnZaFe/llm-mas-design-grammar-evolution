# Code

This directory contains the source code developed and used throughout the research presented in the companion paper.

## Contents

- **Grammar-based evolutionary algorithm** — Implementation of the grammar-guided genetic programming (GGP) approach used to automatically design LLM-based multi-agent system (MAS) architectures.
- **Multi-agent system framework** — Modules for instantiating, configuring, and executing the LLM-based agents and their communication pipelines.
- **Evaluation scripts** — Scripts for running the evolved architectures on the target benchmarks and computing performance metrics (e.g., pass@k, execution accuracy).
- **Utilities** — Helper functions for logging, configuration management, and reproducibility (e.g., seed control, result serialisation).

## Requirements

Dependencies and setup instructions are provided in the top-level `requirements.txt` (or equivalent environment file). Python ≥ 3.10 is recommended.

## Running Experiments

Refer to the individual module docstrings and the paper for a detailed description of the experimental protocol.
