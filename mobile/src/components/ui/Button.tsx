// Themed, animated button. Variants: primary | secondary | ghost.
import { Pressable, ActivityIndicator, StyleSheet, View, type ViewStyle } from 'react-native';
import Animated from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

import { useTheme } from '@/theme';
import { AppText } from './AppText';
import { haptics } from './haptics';
import { usePressScale } from './press';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

type Variant = 'primary' | 'secondary' | 'ghost';

type Props = {
  title: string;
  onPress?: () => void;
  variant?: Variant;
  disabled?: boolean;
  loading?: boolean;
  loadingTitle?: string;
  /** Fire a light haptic on press (default true on native). */
  haptic?: boolean;
  style?: ViewStyle;
  full?: boolean;
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  loadingTitle,
  haptic = true,
  style,
  full = true,
}: Props) {
  const t = useTheme();
  const press = usePressScale(0.97);
  const off = disabled || loading;

  const bg: Record<Variant, string> = {
    primary: off ? t.colors.brandSoft : t.colors.brand,
    secondary: t.colors.surfaceAlt,
    ghost: 'transparent',
  };
  const fg: Record<Variant, string> = {
    primary: t.colors.onBrand,
    secondary: t.colors.text,
    ghost: t.colors.brand,
  };

  const handlePress = () => {
    if (off) return;
    if (haptic) haptics.tap();
    onPress?.();
  };

  // Primary uses a subtle "lit from above" gradient when enabled.
  const gradient = variant === 'primary' && !off;

  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!off }}
      onPress={handlePress}
      onPressIn={off ? undefined : press.onPressIn}
      onPressOut={off ? undefined : press.onPressOut}
      disabled={off}
      style={[
        styles.base,
        { backgroundColor: bg[variant], borderRadius: t.radius.md, overflow: 'hidden' },
        full && styles.full,
        off && variant !== 'primary' && styles.dim,
        press.style,
        style,
      ]}
    >
      {gradient && (
        <LinearGradient
          colors={t.colors.brandGradient}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
          style={StyleSheet.absoluteFill}
        />
      )}
      {loading ? (
        <View style={styles.row}>
          <ActivityIndicator color={fg[variant]} />
          <AppText variant="heading" color={fg[variant]} style={styles.label}>
            {loadingTitle ?? title}
          </AppText>
        </View>
      ) : (
        <AppText variant="heading" color={fg[variant]} style={styles.label}>
          {title}
        </AppText>
      )}
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  base: {
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  full: { alignSelf: 'stretch' },
  dim: { opacity: 0.5 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  label: { fontSize: 16 },
});
