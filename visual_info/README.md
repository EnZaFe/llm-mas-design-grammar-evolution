# Visual Information

This directory contains the visual materials generated for the companion paper, including figures, diagrams, plots, and image analysis.

## Contents

- **Architecture diagrams** — schematic representations of the evolved LLM-based multi-agent system architectures.
- **Grammar visualisations** — graphical views of the context-free grammar defining the MAS design space.
- **Evolutionary dynamics** — plots of fitness, diversity, degeneracy, and runtime behaviour across generations.
- **Image analysis** — analysis of generated figures and visual outputs used in the study.

## Key visual assets

- `fitness_progression_global.png` — shows the evolution of best and average fitness across generations.
- `all_EA_syntax_valids_evolution.png` — tracks syntax validity of generated code over time.
- `all_EA_execution_valids_evolution.png` — tracks execution validity of generated code over time.
- `all_EA_correct_answers_evolution.png` — shows correctness rates across generations.
- `similarity_progression_global.png` — measures population similarity and convergence dynamics.
- `degeneracy_progression_global.png` — shows how the proportion of degenerate individuals changes over time.
- `degeneracy_reasons_global.png` — breaks down the causes of degeneracy, such as grammar violations and runtime errors.
- `time_progression_global.png` — wall-clock time per generation for the evolutionary process.
- `runtime_by_hardware.png` — compares runtime performance across hardware setups.

## Interactive cases

- `improve_same_ind.html` — example of improvement via crossover when the same individual is recombined with itself.
- `improve_both_children_worse_parents.html` — shows a case where two children improve despite coming from worse parents.
- `catastrophic_crossover_zero_fitness.html` — shows a crossover event that produces two zero-fitness children.
- `generation_009_interactive_explore.html` — interactive view of a full generation; the population is displayed. Note: the animation button is not working.

## Formats

Figures are provided in PNG, and individuals can be analyse in .html files, both in tree and terminal node formats.
