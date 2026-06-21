// Mode-agnostic design tokens: spacing, radii, typography.
// Colours live in ./colors (they differ per light/dark mode).
import { Platform } from 'react-native';

/** 4-pt spacing scale used for padding, margins and gaps. */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

/** Corner radii. `pill` is effectively fully rounded. */
export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  pill: 999,
} as const;

/**
 * Font families. We lean on the platform serif for the "appetizing" display
 * face (zero asset weight, no load flash) and the system sans for body text.
 * Swapping in a bundled font later is a one-line change here.
 */
export const fonts = {
  display: Platform.select({ ios: 'Georgia', android: 'serif', default: 'serif' })!,
  body: Platform.select({ ios: 'System', android: 'sans-serif', default: 'System' })!,
  mono: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' })!,
} as const;

export const fontSize = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  display: 28,
} as const;

export type Spacing = typeof spacing;
export type Radius = typeof radius;
