---
version: alpha
name: "KALDRAX"
description: "A desktop engineering control center for orchestrating, inspecting and verifying autonomous software work."
colors:
  primary: "#171717"
  background: "#F7F7F6"
  surface: "#FFFFFF"
  surfaceMuted: "#F1F1EF"
  text: "#191919"
  muted: "#777875"
  border: "#E7E7E4"
  accent: "#7457D9"
  success: "#18845B"
  warning: "#A56A16"
  danger: "#B8403A"
typography:
  sans:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, monospace"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.5rem"
  pill: "999px"
spacing:
  page-gutter: "2rem"
  section-gap: "1.25rem"
  rail-width: "84px"
components:
  navigation: {}
  metric-card: {}
  data-table: {}
  status-badge: {}
  execution-timeline: {}
---
# KALDRAX Design System

## Overview
### Creative North Star
A quiet engineering instrument panel: the calm geometry of a precision lab console combined with the directness of a modern developer tool. The Runey screenshots supplied by the user are the primary layout reference: one expandable dark icon rail with an attached edge toggle, bright workspace, rounded white panels and restrained black actions. There is no second contextual sidebar.

### Product context and register
- **Audience and primary job:** a single engineer configuring a local KALDRAX Python control plane, defining bounded tasks, inspecting execution reports, evaluator evidence and project memory.
- **Target market(s) and evidence:** developer tooling; based on the KALDRAX product brief and current Python CLI implementation.
- **Locale(s) and language policy:** English UI; local machine timezone for timestamps; ISO timestamps in exported evidence.
- **Usage scene:** desktop-first Windows application with dense, frequently inspected operational data.
- **Register:** product UI, not marketing.
- **Memorable signature:** an execution trace rail that visually connects agent activity, tool calls and evidence checkpoints.
- **Restraint:** use neutral surfaces and typography; reserve violet for active execution and links, green for verified success, amber for warnings and red for failures.
- **Anti-references:** generic analytics SaaS, decorative gradients, fake live metrics, inventory/ERP metaphors.
- **Token ownership/runtime mapping:** this document records accepted semantic values; `src/styles/kaldrax.css` is the runtime token and component implementation. Update both in the same change.

## Colors
Use the near-black rail and bright workspace to retain the source template's visual character. Violet marks active work only; semantic status colors must always be paired with text.

## Typography
Inter is the interface face. JetBrains Mono is reserved for identifiers, paths, hashes, diffs and terminal output. Use tabular numerals for metrics and timestamps.

## Layout
Desktop layout follows the supplied Runey rail reference: one 84px near-black rounded navigation rail and a flexible bright workspace. The rail expands to about 260px to reveal labels, and collapses to an icon-only rail using the attached circular chevron toggle. There is no second navigation sidebar. On narrow widths the single rail becomes compact horizontal navigation.

## Elevation & Depth
Prefer hairline borders and tonal surface changes. Use shadows only for menus, dialogs and floating controls. No glass effects.

## Shapes
Cards use 16–20px radii; controls use 9–11px radii; primary actions may use a full pill radius to retain the Runey reference.

## Components
### Foundational visual states
Every interactive control has hover, focus-visible, pressed and disabled states. Async actions show pending state without changing geometry. Errors retain the user's input and explain recovery.
### Buttons and actions
Primary actions are near-black pill buttons. Secondary actions are neutral outlined controls. Destructive actions are red and require confirmation when irreversible.
### Navigation and data display
Match the supplied Runey reference closely: tall rounded black icon rail with a protruding expand/collapse control, top-right circular utility actions, spacious workspace, large white cards, fine neutral borders and near-black pill actions. Tables are compact and readable; charts must represent labelled execution data, not decorative placeholders.
### Forms and overlays
Use labelled fields, inline validation and explicit save/cancel actions. Dialogs restore focus to their trigger.
### Iconography
Use the existing custom 24px outline icon family from `src/components/Icons.tsx`; keep icons secondary to labels.
### Motion
Short 140–200ms transitions. Respect reduced motion. Execution progress may animate only when real events arrive.
### Content and data visualization
Clearly label local sample data as demo until connected to the engine. Do not claim the Python engine is live when no API connection exists.

## Do's and Don'ts
- **Do:** show provenance, timestamps and verification state alongside execution results.
- **Do:** make task submission and repository selection the primary workflows.
- **Don't:** present seeded demo values as live engine telemetry.
- **Don't:** show controls that imply code editing, shell execution or agent orchestration are already wired when they are not.

## v0.6 workflow components

- **Operation panel:** status and event-backed progress only; cancellation appears only for active operations. Terminal status and messages remain textual, not color-only.
- **Memory cards:** separate pending from active state and show provenance, freshness/retrieval score and confidence. Approve/reject and contradiction resolution require deliberate actions.
- **Team trace:** show role, agent namespace, cycle and output excerpt with the independent evaluator outcome separated from reviewer approval.
- **Sandbox result:** show exit status, duration, container image, stdout and stderr. Label the single-file scope and resource limits.
- **Repository editor:** list supported files beside the editor; show selected path and SHA-256; make the write action explicit. The confirmation explains backup creation and the single-file boundary.
