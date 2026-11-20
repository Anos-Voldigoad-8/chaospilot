---
name: emilkowalski-motion
description: >-
  Micro-interactions, animation craft, spring physics, and fluid choreography (emilkowalski/skills).
  Enforces delightful tactile UI feedback and seamless motion design.
---

# Emil Kowalski Animation Craft

Based on [emilkowalski/skills](https://github.com/emilkowalski/skills).

## Principles
1. **Physicality & Weight**: UI elements should feel like physical objects with mass, velocity, and damping.
2. **Spring Transitions**: Avoid linear or harsh cubic-bezier timings. Use spring physics (`damping: 20`, `stiffness: 300`) for natural responsiveness.
3. **Choreography & Stagger**: Grouped elements enter with slight offsets (15-40ms stagger) rather than popping into existence together.
4. **Purposeful Feedback**: Every click, toggle, and fault injection produces immediate, satisfying visual confirmation (subtle scale dip, glowing ripple, value roll).
5. **Reduced Motion Grace**: Always respect `prefers-reduced-motion` with clean opacity fallbacks.
