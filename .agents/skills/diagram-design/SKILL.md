---
name: diagram-design
description: >-
  Architectural diagramming, system topology visual clarity, and data flow design (cathrynlavery/diagram-design).
---

# Diagram Design Guidelines

Based on [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design).

## Topology & Flow Rules
1. **Clear Directionality**: Downstream and upstream dependencies must be immediately intuitive (Gateway -> Auth/Orders -> Cache/DB).
2. **Dynamic Edge Animation**: Animated dash currents indicating live traffic QPS; color change reflecting latency or packet drops.
3. **Blast Radius Visualization**: Visual aura indicating cascading service impact when an upstream node fails or slows down.
4. **Interactive Node Cards**: Nodes reveal vital metrics (QPS, Latency, Error rate, Status) on inspection and hover.
