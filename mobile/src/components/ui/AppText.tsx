// Typed text with a small variant scale so screens stop re-declaring font sizes.
import { Text, type TextProps, type TextStyle } from 'react-native';

import { useTheme } from '@/theme';

export type TextVariant =
  | 'display' // big serif — restaurant names, hero titles
  | 'title' // serif section title
  | 'heading' // bold sans subsection
  | 'body' // default paragraph
  | 'muted' // secondary paragraph
  | 'caption' // small metadata
  | 'label'; // form labels / overlines

type Props = TextProps & {
  variant?: TextVariant;
  /** Override the variant's default colour with a palette value. */
  color?: string;
  center?: boolean;
};

export function AppText({ variant = 'body', color, center, style, ...rest }: Props) {
  const t = useTheme();

  const base: Record<TextVariant, TextStyle> = {
    display: {
      fontFamily: t.fonts.display,
      fontSize: t.fontSize.display,
      fontWeight: '700',
      color: t.colors.text,
      letterSpacing: 0.2,
    },
    title: {
      fontFamily: t.fonts.display,
      fontSize: t.fontSize.xl,
      fontWeight: '700',
      color: t.colors.text,
    },
    heading: {
      fontFamily: t.fonts.body,
      fontSize: t.fontSize.lg,
      fontWeight: '700',
      color: t.colors.text,
    },
    body: {
      fontFamily: t.fonts.body,
      fontSize: t.fontSize.md,
      color: t.colors.text,
      lineHeight: 21,
    },
    muted: {
      fontFamily: t.fonts.body,
      fontSize: t.fontSize.md,
      color: t.colors.textMuted,
      lineHeight: 21,
    },
    caption: {
      fontFamily: t.fonts.body,
      fontSize: t.fontSize.sm,
      color: t.colors.textFaint,
    },
    label: {
      fontFamily: t.fonts.body,
      fontSize: 14,
      fontWeight: '600',
      color: t.colors.textMuted,
    },
  };

  return (
    <Text
      style={[base[variant], center && { textAlign: 'center' }, color && { color }, style]}
      {...rest}
    />
  );
}
