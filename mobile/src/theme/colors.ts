// Warm, appetizing palette in light and dark variants.
// Both share the same shape so components can read `colors.<name>` blindly.

export type Palette = {
  /** App background. */
  bg: string;
  /** Raised card / sheet surface. */
  surface: string;
  /** Secondary surface: inputs, pressed cards, chips. */
  surfaceAlt: string;
  /** Hairline borders / dividers. */
  border: string;

  /** Primary body text. */
  text: string;
  /** Secondary text. */
  textMuted: string;
  /** Tertiary text: captions, metadata. */
  textFaint: string;
  /** Input placeholder text. */
  placeholder: string;

  /** Brand red — primary accent / actions. */
  brand: string;
  /** Two-stop brand gradient (top → bottom) for filled buttons. */
  brandGradient: readonly [string, string];
  /** Muted brand for disabled / soft fills. */
  brandSoft: string;
  /** Tint behind soft brand fills (chips, highlights). */
  brandTint: string;
  /** Text/icon colour on a brand-filled surface. */
  onBrand: string;

  /** Positive / success. */
  success: string;
  /** Warm neutral (e.g. stop button). */
  neutral: string;
  /** Scrim / press overlay. */
  overlay: string;
};

export const light: Palette = {
  bg: '#faf7f5',
  surface: '#ffffff',
  surfaceAlt: '#f1eae7',
  border: '#e7ddd7',

  text: '#2c2420',
  textMuted: '#7a6f6a',
  textFaint: '#9b908a',
  placeholder: '#a89e98',

  brand: '#c0392b',
  brandGradient: ['#d24536', '#b5352a'],
  brandSoft: '#d8b3ad',
  brandTint: '#f7e7e3',
  onBrand: '#ffffff',

  success: '#1e7a46',
  neutral: '#5a5048',
  overlay: 'rgba(44, 36, 32, 0.06)',
};

export const dark: Palette = {
  bg: '#16110f',
  surface: '#211b18',
  surfaceAlt: '#2c2521',
  border: '#3a322d',

  text: '#f4ede9',
  textMuted: '#b6aaa2',
  textFaint: '#867a72',
  placeholder: '#6f655e',

  // Brand is brightened on dark so it stays legible as an accent.
  brand: '#e0594a',
  brandGradient: ['#e8675a', '#d54e3f'],
  brandSoft: '#6e3a34',
  brandTint: '#33211e',
  onBrand: '#ffffff',

  success: '#3ec27a',
  neutral: '#9a8d84',
  overlay: 'rgba(255, 255, 255, 0.07)',
};
