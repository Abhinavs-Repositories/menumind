// Surface card. Tappable variant springs on press; static variant is a plain View.
import { type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type ViewStyle } from 'react-native';
import Animated from 'react-native-reanimated';

import { useTheme } from '@/theme';
import { usePressScale } from './press';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

type Props = {
  children: ReactNode;
  onPress?: () => void;
  style?: ViewStyle;
  /** Apply default interior padding (default true). */
  padded?: boolean;
};

export function Card({ children, onPress, style, padded = true }: Props) {
  const t = useTheme();
  const press = usePressScale(0.98);

  const surface: ViewStyle = {
    backgroundColor: t.colors.surface,
    borderRadius: t.radius.lg,
    borderWidth: t.mode === 'dark' ? StyleSheet.hairlineWidth : 0,
    borderColor: t.colors.border,
    ...t.shadow.card,
  };
  const pad = padded ? { padding: t.spacing.lg } : null;

  if (!onPress) {
    return <View style={[surface, pad, style]}>{children}</View>;
  }
  return (
    <AnimatedPressable
      accessibilityRole="button"
      onPress={onPress}
      onPressIn={press.onPressIn}
      onPressOut={press.onPressOut}
      style={[surface, pad, press.style, style]}
    >
      {children}
    </AnimatedPressable>
  );
}
