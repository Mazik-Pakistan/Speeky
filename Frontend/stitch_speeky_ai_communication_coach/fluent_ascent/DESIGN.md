---
name: Fluent Ascent
colors:
  surface: '#faf8ff'
  surface-dim: '#dad9e0'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3fa'
  surface-container: '#eeedf4'
  surface-container-high: '#e9e7ef'
  surface-container-highest: '#e3e1e9'
  on-surface: '#1a1b21'
  on-surface-variant: '#444651'
  inverse-surface: '#2f3036'
  inverse-on-surface: '#f1f0f7'
  outline: '#757682'
  outline-variant: '#c5c6d3'
  surface-tint: '#3f5aaa'
  primary: '#00246e'
  on-primary: '#ffffff'
  primary-container: '#1d3b8a'
  on-primary-container: '#90a9ff'
  inverse-primary: '#b5c4ff'
  secondary: '#b52424'
  on-secondary: '#ffffff'
  secondary-container: '#ff5a52'
  on-secondary-container: '#600006'
  tertiary: '#262b2e'
  on-tertiary: '#ffffff'
  tertiary-container: '#3c4144'
  on-tertiary-container: '#a8adb1'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b5c4ff'
  on-primary-fixed: '#00174d'
  on-primary-fixed-variant: '#254190'
  secondary-fixed: '#ffdad6'
  secondary-fixed-dim: '#ffb4ac'
  on-secondary-fixed: '#410003'
  on-secondary-fixed-variant: '#92030f'
  tertiary-fixed: '#dfe3e7'
  tertiary-fixed-dim: '#c3c7cb'
  on-tertiary-fixed: '#171c1f'
  on-tertiary-fixed-variant: '#43474b'
  background: '#faf8ff'
  on-background: '#1a1b21'
  surface-variant: '#e3e1e9'
typography:
  display-lg:
    fontFamily: Libre Caslon Text
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
  headline-lg:
    fontFamily: Libre Caslon Text
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: Libre Caslon Text
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Libre Caslon Text
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max-width: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

The design system is built on the philosophy of "Encouraged Mastery." It balances the authoritative, academic heritage of English language learning with the modern, judgment-free accessibility of AI coaching. The personality is empowering, clear, and focused on growth.

The visual style is **Corporate / Modern** with a soft, humanistic touch. It leverages significant white space to reduce cognitive load during learning sessions, paired with high-quality typography that communicates both professional reliability and friendly approachability. Subtle depth through shadows and rounded geometry creates an environment that feels safe for practice and experimentation.

## Colors

The palette is derived from the core brand mark, utilizing a deep **Royal Blue** for primary actions and structural identity, and a **Crimson Red** for characterful accents and secondary highlights. 

- **Primary Blue:** Used for headers, primary buttons, and the AI’s presence.
- **Secondary Red:** Reserved for expressive accents, active states in charts, or specific "growth" callouts.
- **Neutrals:** A range of soft grays (Cool Gray 50-900) provides the foundation for the UI, ensuring the primary colors remain impactful without being overwhelming.
- **Confidence Tokens:** 
    - *High Fluency (Success):* A deep forest green used for correct pronunciation or grammatical mastery.
    - *Needs Improvement (Warning):* A warm amber used for areas requiring attention, designed to feel like "guidance" rather than "failure."

## Typography

This design system uses a dual-font strategy to balance tradition and technology. 

- **Headings (Libre Caslon Text):** This serif font evokes the authority of classic literature and academic publishing, reinforcing the user's goal of high-level English mastery.
- **Body & UI (Manrope):** A modern, geometric sans-serif that ensures high legibility on digital screens. Its balanced proportions keep the interface feeling clean and functional.

Text hierarchy is strictly enforced to ensure clarity in instructional content. Bold weights are used sparingly for emphasis in feedback loops.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a base unit of 8px. This ensures a consistent vertical rhythm across all views, particularly in text-heavy learning modules.

- **Desktop:** 12-column grid with a maximum content width of 1280px. 
- **Tablet:** 8-column grid with 24px margins.
- **Mobile:** 4-column grid with 16px margins to maximize horizontal real estate for chat interfaces.

Spacing is generous ("Airy") to prevent the feeling of a cluttered classroom. Lessons are presented in centralized "learning cards" to focus the user's attention.

## Elevation & Depth

Visual hierarchy is achieved through **Tonal Layers** and **Ambient Shadows**. 

1. **Base:** Light gray background (#F8FAFC) to define the workspace.
2. **Surface:** Pure white cards (#FFFFFF) for primary content and chat bubbles, using a soft, diffused shadow (0px 4px 20px rgba(0,0,0,0.05)) to lift them from the background.
3. **Active:** Elements in focus or primary buttons use a slightly higher elevation and a subtle blue-tinted shadow to signify interactivity.

Backdrop blurs (Glassmorphism) are used exclusively for navigation overlays and modal backdrops to maintain context without visual noise.

## Shapes

The shape language is defined by **Rounded** corners, removing sharp edges to foster a friendlier, non-threatening environment.

- **Standard UI elements (Buttons, Inputs):** 0.5rem (8px) radius.
- **Chat Bubbles & Cards:** 1rem (16px) radius for a softer, more organic feel.
- **Progress Indicators:** Pill-shaped (fully rounded) for fluid motion and organic growth visualization.

## Components

### Chat Bubbles
- **AI Coach:** White background with a fine light-blue border. Aligned to the left. Uses Manrope Regular.
- **User:** Primary Blue background with white text. Aligned to the right. 
- **Interactive Feedback:** Small "confidence" tags attached to specific words within a bubble, color-coded based on the fluency tokens (Green/Amber).

### Buttons & Inputs
- **Primary Action:** Solid Primary Blue with white text. Large tap targets (min 48px height).
- **Secondary Action:** Ghost style with a Primary Blue outline.
- **Text Inputs:** Soft gray fill with a subtle 1px border that shifts to Primary Blue on focus.

### Progress Charts
- **Line Charts:** Use a smooth interpolation (curved lines) rather than jagged angles to symbolize a natural learning journey.
- **Accents:** Use the Secondary Red for milestones and the Success Green for "Streaks."

### Feedback Chips
- Small, rounded labels used for grammar corrections. They appear inline or directly above the text they refer to, utilizing the "Soft" roundedness level.