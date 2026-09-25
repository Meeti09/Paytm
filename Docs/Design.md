# Paytm Pulse — Design System

> **Visual source of truth for the Paytm Pulse hackathon MVP**
>
> Product: **Paytm Pulse — The AI workforce for Paytm**
>
> UI constraint: **Exactly 3 screens**
>
> 1. Live Mission
> 2. Approval Queue
> 3. Outcomes

---

# 1. Design Direction

Paytm Pulse should feel like a **real fintech operations product**, not an AI-generated marketing dashboard.

The visual language is inspired by Paytm's restrained cyan-blue identity:

- One confident primary blue.
- Navy/near-black typography.
- Cool off-white application background.
- White surfaces.
- Thin borders.
- Status colors only where state matters.
- Dense, task-first information layout.
- Clear numbers and actions.

The interface should communicate:

> **AI is working → AI made a decision → policy evaluated it → action happened or needs a human → outcome was recorded.**

The design should prioritize **clarity, trust, speed, and operational visibility** over decoration.

---

# 2. Core Design Principles

## 2.1 Fintech first, AI second

Do not make the interface look like a generic AI product.

Avoid visual patterns commonly associated with AI-generated dashboards:

- Purple/indigo gradients.
- Blue-purple gradient backgrounds.
- Glowing cards.
- Glassmorphism.
- Excessive rounded pills.
- Giant centered headings.
- Decorative AI illustrations.
- Excessive empty space.
- Chat-first layouts.

AI should be communicated through:

- Agent identity.
- Mission state.
- Activity timeline.
- Decision cards.
- Tool/action traces.
- Risk indicators.
- Approval requests.
- Measurable outcomes.

---

## 2.2 Task-first

The user should immediately understand:

```text
What is happening?
Why is it happening?
What did the AI decide?
Does a human need to act?
What happened?
```

Do not make the user navigate through multiple pages to answer these questions.

---

## 2.3 Information density

Paytm Pulse is an operational dashboard.

Prefer:

```text
compact cards
+
clear hierarchy
+
short labels
+
visible state
```

over:

```text
large hero sections
+
large empty spaces
+
long explanatory paragraphs
```

---

## 2.4 Trust through transparency

The UI should never merely say:

> AI is thinking...

Instead show:

```text
✓ Customer identified
✓ Transaction found
✓ Policy checked
→ Refund decision generated
⚠ Human approval required
```

The system should make agent behavior understandable without exposing chain-of-thought.

Show **actions, evidence summaries, policy reasons, and outcomes**, not private internal reasoning.

---

# 3. Color System

Use these CSS variables.

```css
:root {
  --paytm-blue: #00BAF2;
  --paytm-blue-deep: #01579B;

  --ink: #0A2540;
  --ink-muted: #5C6B7A;

  --bg: #F5F7FA;
  --surface: #FFFFFF;
  --border: #E3E8EE;

  --success: #0BA860;
  --warning: #F5A623;
  --danger: #E13B3B;
}
```

---

## 3.1 Primary blue

### `--paytm-blue`

```text
#00BAF2
```

Use for:

- Primary CTAs.
- Active navigation.
- Progress indicators.
- Links.
- Focus states.
- Selected controls.
- Important interactive accents.

Do not use it to color every component.

---

## 3.2 Deep blue

### `--paytm-blue-deep`

```text
#01579B
```

Use sparingly for:

- Strong blue headings when needed.
- Pressed states.
- Dark blue utility areas.
- High-emphasis blue text.

---

## 3.3 Primary text

### `--ink`

```text
#0A2540
```

Use for:

- Headings.
- Numbers.
- Important labels.
- Body text.
- Mission titles.
- Merchant/customer names.

Do not use pure black as the default text color.

---

## 3.4 Secondary text

### `--ink-muted`

```text
#5C6B7A
```

Use for:

- Metadata.
- Supporting labels.
- Timestamps.
- Secondary descriptions.
- Helper text.

---

## 3.5 Background

### `--bg`

```text
#F5F7FA
```

Use as the application background.

The app should not be pure white from edge to edge.

Structure:

```text
#F5F7FA
    ↓
white cards
    ↓
hairline borders
```

---

## 3.6 Surface

### `--surface`

```text
#FFFFFF
```

Use for:

- Cards.
- Panels.
- Mission details.
- Approval cards.
- Outcome metric cards.
- Timeline containers.

---

## 3.7 Border

### `--border`

```text
#E3E8EE
```

Use for:

- Card borders.
- Dividers.
- Input borders.
- Table borders.
- Section separators.

Default border:

```css
border: 1px solid var(--border);
```

Avoid heavy shadows.

---

## 3.8 Status colors

### Success

```text
#0BA860
```

Use for:

- Resolved.
- Completed.
- Autonomous.
- Approved.
- Positive outcome.

### Warning

```text
#F5A623
```

Use for:

- Pending.
- Needs review.
- Medium risk.
- Waiting.
- Attention required.

### Danger

```text
#E13B3B
```

Use for:

- Escalation.
- High risk.
- Failed actions.
- Refund approval requirement.
- Blocked action.

Status colors should communicate state, not decorate the UI.

---

# 4. Color Usage Rules

## Primary rule

**Blue is the only saturated brand color.**

Everything else should remain:

- navy
- gray
- white
- status green
- status amber
- status red

Do not create additional accent colors.

---

## Never use

```text
purple
indigo gradients
rainbow gradients
neon gradients
glassmorphism gradients
```

No gradient background.

No gradient text.

No gradient buttons.

---

# 5. Typography

Use one geometric sans-serif family throughout.

Preferred:

```text
Inter
```

Alternative:

```text
Poppins
```

Do not mix multiple font families.

---

## 5.1 Typography hierarchy

### Page title

```text
24–28px
font-weight: 700
color: --ink
```

### Section heading

```text
16–18px
font-weight: 650–700
color: --ink
```

### Card title

```text
14–16px
font-weight: 600–700
color: --ink
```

### Body

```text
14px
font-weight: 400–500
color: --ink
```

### Metadata

```text
12–13px
font-weight: 500
color: --ink-muted
```

---

# 6. Numbers Are Heroes

Large numbers should have a visual size jump.

Examples:

```text
4
Processed
```

```text
3
Resolved autonomously
```

```text
₹1,500
Refund requested
```

```text
91
Lead score
```

Recommended:

```text
font-size: 28–36px
font-weight: 700
color: var(--ink)
```

Numbers should generally be left-aligned.

---

# 7. Alignment

Default:

```text
LEFT ALIGN
```

Do not center:

- page headings
- paragraphs
- mission descriptions
- dashboard metrics
- decision cards
- operational content

Centered layouts may be used only for small empty/loading states where appropriate.

---

# 8. Spacing System

Use a consistent spacing scale.

```text
4px
8px
12px
16px
20px
24px
32px
40px
48px
```

Recommended defaults:

```text
Card padding:       20–24px
Section gap:        24px
Card gap:           16px
Element gap:        8–12px
Page padding:       24–32px
```

Do not create arbitrary spacing values unless necessary.

---

# 9. Border Radius

Use restrained rounding.

```text
Small controls: 6–8px
Cards:          8–10px
Inputs:         8px
Buttons:        8px
```

Avoid:

```text
20px
24px
9999px
```

for normal containers.

Pills are reserved for status labels.

---

# 10. Shadows

Default:

```text
NO SHADOW
```

Use borders for separation.

If a shadow is genuinely required for a floating element:

```text
very subtle
low opacity
small blur
```

Do not use large floating shadows on every card.

---

# 11. Icons

Use one consistent icon set.

Preferred:

```text
Lucide
```

Rules:

- One icon style.
- Consistent stroke width.
- No emoji as functional icons.
- Do not mix random icon libraries.
- Icons should support text, not replace important labels.

Example:

```text
✓ Resolved
⚠ Needs review
```

The actual UI should use Lucide icons rather than emoji glyphs.

---

# 12. Buttons

Buttons should use rounded rectangles, not giant pills.

## Primary button

```css
background: var(--paytm-blue);
color: white;
border-radius: 8px;
```

Use for:

- Approve.
- Start Mission.
- Run Demo.
- Confirm.

---

## Secondary button

```css
background: white;
color: var(--ink);
border: 1px solid var(--border);
border-radius: 8px;
```

Use for:

- Take Over.
- View Details.
- Pause.
- Secondary actions.

---

## Destructive button

Use danger only where the action itself is destructive.

```text
Reject
Cancel action
```

Avoid making every negative-looking operation bright red.

---

# 13. Inputs

Inputs:

```text
white background
1px border
8px radius
14px text
```

Focus:

```text
border: --paytm-blue
```

Do not use glowing focus effects.

---

# 14. Status Components

Status should be communicated with:

```text
icon + label
```

or:

```text
small status pill
```

Example:

```text
● RUNNING
✓ RESOLVED
⚠ NEEDS REVIEW
! HIGH RISK
```

Use a light tinted background with colored text.

Do not fill the entire card with the status color.

---

# 15. Mission Cards

Mission cards are central to the product.

Structure:

```text
┌──────────────────────────────────────────────┐
│ RESOLVE                                      │
│                                              │
│ ₹2,000 payment issue                         │
│ Customer: Aarav Shah                         │
│                                              │
│ ● Investigating                              │
│                                              │
│ Progress                                     │
│ ━━━━━━━━━━━━━━━░░░                           │
│                                              │
│ Last action                                  │
│ Transaction status verified                  │
└──────────────────────────────────────────────┘
```

Use:

- White surface.
- Hairline border.
- 8–10px radius.
- Bold primary information.
- Compact metadata.
- Thin blue progress bar.

---

# 16. Mission Progress

Use a thin progress bar.

```text
height: 4–6px
background: var(--border)
fill: var(--paytm-blue)
border-radius: 4px
```

No gradient.

No chunky progress components.

---

# 17. Live Mission Screen

This is the primary product screen.

Suggested structure:

```text
┌─────────────────────────────────────────────────────┐
│ PAYTM PULSE                 Live Mission             │
├─────────────────────────────────────────────────────┤
│                                                     │
│ RESOLVE                                             │
│ Resolve customer payment issue                     │
│                                                     │
│ ┌──────────────────┐ ┌────────────────────────────┐ │
│ │ CONTEXT          │ │ CURRENT DECISION           │ │
│ │                  │ │                            │ │
│ │ Customer         │ │ Refund ₹1,500              │ │
│ │ Aarav Shah       │ │                            │ │
│ │                  │ │ HIGH RISK                  │ │
│ │ Transaction      │ │ Approval required          │ │
│ │ TX-1004          │ │                            │ │
│ └──────────────────┘ └────────────────────────────┘ │
│                                                     │
│ LIVE ACTIVITY                                       │
│                                                     │
│ ✓ Customer identified                               │
│ ✓ Transaction found                                 │
│ ✓ Policy checked                                    │
│ ⚠ Approval requested                                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

The mission screen should make the agent's progress visually obvious.

---

# 18. Activity Timeline

The activity timeline should be compact.

Example:

```text
12:42:03  ✓ Customer identified
12:42:04  ✓ Transaction found
12:42:05  ✓ Payment status checked
12:42:06  ✓ Merchant status checked
12:42:07  ✓ Policy retrieved
12:42:08  → Decision generated
12:42:09  ⚠ Approval required
```

Visual hierarchy:

```text
timestamp     muted
event         primary
status icon   status color
```

Do not expose chain-of-thought.

Only display observable system actions and concise reasons.

---

# 19. Decision Card

The decision card should be visually prominent.

```text
AI DECISION

Refund ₹1,500

Reason
Customer debit confirmed, but merchant
settlement was not completed.

Risk
HIGH

Policy
Refund exceeds autonomous threshold
of ₹1,000.

NEXT
Human approval required.
```

Use a danger left border for high-risk decisions.

Do not make the entire card red.

---

# 20. Approval Queue

The Approval Queue is a governance screen.

It should feel serious and operational.

Structure:

```text
APPROVAL QUEUE

3 actions need your attention

┌─────────────────────────────────────────────┐
│ HIGH RISK                                   │
│                                             │
│ Refund ₹1,500                               │
│ Mission: TX-1004                            │
│                                             │
│ Reason                                      │
│ Amount exceeds autonomous threshold.        │
│                                             │
│ [ Approve ]   [ Reject ]   [ Take Over ]   │
└─────────────────────────────────────────────┘
```

---

# 21. Risk Indicators

Use a small left-side risk strip.

### High risk

```text
border-left: 3px solid var(--danger)
```

### Medium risk

```text
border-left: 3px solid var(--warning)
```

### Low risk

```text
border-left: 3px solid var(--success)
```

Do not turn the entire card into a red/orange/green block.

---

# 22. Approval Policy Banner

Keep the policy visible.

Example:

```text
AUTONOMY POLICY

Human approval is required for:
• Money movement above ₹1,000
• Account-level actions
• Strong negative customer sentiment
• Irreversible actions
• Actions outside agent permissions
```

Design:

- Neutral white card.
- Thin border.
- Small blue information icon.
- Compact text.

The policy should look like an operational rule, not a marketing statement.

---

# 23. Outcomes Screen

The Outcomes screen should be extremely simple.

It answers:

> What did the AI actually accomplish?

Example:

```text
OUTCOMES

LIVE DEMO

┌────────────┐ ┌────────────┐ ┌────────────┐
│     4      │ │     3      │ │     1      │
│ Processed  │ │ Autonomous │ │ Escalated  │
└────────────┘ └────────────┘ └────────────┘
```

Numbers:

```text
large
bold
navy
```

Labels:

```text
small
muted
```

---

# 24. Outcome Cards

Outcome cards should be:

```text
white
bordered
compact
left-aligned
```

Do not use:

- giant charts
- radial gauges
- gradient graphs
- decorative illustrations

A simple metric grid is preferable.

---

# 25. Autonomy Rate

Display only when meaningful.

Example:

```text
75%
Autonomy rate
```

Definition:

```text
Autonomously completed missions
────────────────────────────────
Processed missions
```

If there are no processed missions:

```text
—
Autonomy rate
```

Do not display:

```text
0%
```

as if a meaningful sample existed.

---

# 26. Outcomes Detail

Below the metric cards:

```text
MISSION OUTCOMES

TX-1001
Resolve
✓ Resolved autonomously

TX-1002
Resolve
✓ Resolved autonomously

TX-1003
Resolve
⚠ Escalated — refund above threshold

G-0001
Grow
✓ Meeting booked
```

This connects the KPI to actual missions.

---

# 27. Grow Mission Design

Grow should use the same visual language as Resolve.

Example:

```text
GROW

Acquire 5 high-potential merchants in Thane

12 evaluated
4 qualified
3 contacted
1 sales-ready
```

Merchant card:

```text
MUMBAI BREW HOUSE

Thane West
Cafe

Lead score
91

Opportunity
High

Why selected
• Strong digital presence
• High estimated transaction potential
• Not onboarded in demo dataset

NEXT ACTION
Start merchant conversation
```

---

# 28. Lead Score

Lead scores should be visually prominent but not over-styled.

Example:

```text
91
Lead score
```

Use navy.

Do not create a colorful circular gauge.

---

# 29. Agent Identity

Resolve and Grow need clear identities.

Example:

```text
RESOLVE
Customer Resolution Teammate
```

```text
GROW
Merchant Acquisition Teammate
```

Use simple Lucide icons.

Avoid robot faces, AI brains, glowing avatars, or cartoon agents.

---

# 30. Top Navigation

Because there are exactly three screens, navigation should be minimal.

```text
PAYTM PULSE

Live Mission    Approvals    Outcomes
```

Active state:

```text
blue text
blue underline or small bottom indicator
```

No large sidebar.

No nested navigation.

No hamburger menu required for the MVP desktop experience.

---

# 31. Header

Recommended:

```text
┌──────────────────────────────────────────────────┐
│ PAYTM PULSE        Live Mission   Approvals   ...│
└──────────────────────────────────────────────────┘
```

Logo/wordmark:

```text
PAYTM PULSE
```

Use text treatment rather than inventing a complicated logo.

---

# 32. Empty States

Empty states should be concise.

Example:

```text
No approvals pending

All agent actions are currently
within their permitted autonomy.
```

Use a subtle icon.

Do not use illustrations.

---

# 33. Loading States

Use skeletons for content loading.

Avoid:

```text
AI is thinking...
✨
```

Prefer:

```text
Loading mission...
```

or skeleton blocks.

---

# 34. Error States

Errors should be explicit.

Example:

```text
n8n execution failed

The action could not be completed.
Mission has been paused.

[ Retry ]
[ Take Over ]
```

Do not hide errors behind generic toast notifications.

---

# 35. Toasts

Use toasts only for short confirmation.

Good:

```text
Approval granted
```

Bad:

```text
AI has successfully completed the entire
customer resolution process!
```

Important state changes belong in the mission timeline.

---

# 36. Responsive Behavior

Primary target:

```text
Desktop
```

The hackathon demo will primarily use a desktop/laptop display.

Still support reasonable tablet widths.

At narrower widths:

```text
two-column cards
→
single-column cards
```

Do not create a separate mobile navigation system for the MVP.

---

# 37. Component Design Rules

Build reusable primitives:

```text
Button
Card
StatusBadge
RiskBadge
MetricCard
ProgressBar
Timeline
DecisionCard
ApprovalCard
MissionHeader
SectionHeader
```

Avoid creating visually different versions of the same component.

---

# 38. Component Consistency

If a component appears in multiple screens, it must use the same:

- border radius
- typography
- padding
- icon size
- status treatment
- button treatment

The product should feel like one system.

---

# 39. AI Activity Animation

Animation should be subtle.

Allowed:

- timeline item appearing
- progress bar updating
- status transition
- small fade/slide
- button loading state

Avoid:

- glowing borders
- pulsing cards
- particle effects
- typing animations everywhere
- floating AI effects
- excessive motion

The goal is **live operational visibility**, not spectacle.

---

# 40. Live Mission State Styling

```text
RUNNING
Blue

WAITING
Amber

APPROVAL REQUIRED
Red / Amber depending on risk

COMPLETED
Green

FAILED
Red

PAUSED
Muted / Amber
```

Use both color and text/icon so state is understandable without color alone.

---

# 41. Accessibility

Minimum requirements:

- Maintain readable text contrast.
- Never communicate state through color alone.
- Buttons need visible labels.
- Interactive elements need keyboard focus states.
- Use semantic HTML.
- Icons need accessible labels where they convey meaning.
- Do not make text smaller simply to fit more information.

---

# 42. Design Anti-Patterns

Claude Code must NOT introduce:

```text
❌ Purple gradients
❌ Indigo backgrounds
❌ Glass cards
❌ Excessive shadows
❌ Giant rounded containers
❌ Pill-shaped buttons everywhere
❌ Emoji functional icons
❌ Centered dashboard content
❌ Huge hero sections
❌ Decorative AI robot graphics
❌ Giant charts
❌ Fake KPI numbers
❌ Gradient progress bars
❌ Full-card status colors
❌ Multiple competing accent colors
```

---

# 43. Visual Quality Checklist

Before considering a UI feature complete, verify:

### Color

- [ ] Paytm cyan is the primary accent.
- [ ] No purple/indigo gradients.
- [ ] Status colors are used only for status.
- [ ] Background is cool off-white.
- [ ] Cards are white.

### Typography

- [ ] One font family.
- [ ] Numbers are visually prominent.
- [ ] Text is left-aligned.
- [ ] Metadata is visibly secondary.

### Components

- [ ] Cards have hairline borders.
- [ ] Radius is consistent.
- [ ] Shadows are minimal or absent.
- [ ] Buttons are rounded rectangles.
- [ ] Pills are reserved for statuses.

### Product

- [ ] Exactly three screens.
- [ ] Mission is the primary object.
- [ ] Agent activity is visible.
- [ ] Approval reason is explicit.
- [ ] Outcomes use real demo data.
- [ ] No fake production metrics.

### AI presentation

- [ ] No generic chatbot-first UI.
- [ ] No chain-of-thought exposure.
- [ ] Actions and evidence are visible.
- [ ] Policy decisions are explicit.
- [ ] Human control is clear.

---

# 44. Final Visual Formula

The complete visual formula for Paytm Pulse is:

```text
PAYTM CYAN
     +
NAVY TYPOGRAPHY
     +
COOL OFF-WHITE BACKGROUND
     +
WHITE CARDS
     +
HAIRLINE BORDERS
     +
COMPACT INFORMATION DENSITY
     +
STATUS COLORS
     +
CLEAR NUMBERS
     +
MISSION-FIRST UX
```

The intended feeling is:

> **A real fintech operations product where AI happens to be the workforce.**

Not:

> **A flashy AI demo pretending to be a fintech product.**

---

# 45. Design North Star

Every design decision should pass this test:

> **Would this help a human operator understand what the AI is doing, whether it is safe, whether they need to intervene, and what outcome it produced?**

If yes, keep it.

If it exists mainly to make the dashboard look impressive, remove it.
