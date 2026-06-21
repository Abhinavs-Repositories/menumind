// Three bouncing dots shown while the assistant "thinks" (before first token).
import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { useTheme } from '@/theme';

function Dot({ delay, color }: { delay: number; color: string }) {
  const v = useSharedValue(0);
  useEffect(() => {
    v.value = withDelay(
      delay,
      withRepeat(
        withSequence(withTiming(1, { duration: 320 }), withTiming(0, { duration: 320 })),
        -1,
        false,
      ),
    );
  }, [delay, v]);

  const style = useAnimatedStyle(() => ({
    opacity: 0.35 + v.value * 0.65,
    transform: [{ translateY: -3 * v.value }],
  }));

  return <Animated.View style={[styles.dot, { backgroundColor: color }, style]} />;
}

export function TypingDots() {
  const t = useTheme();
  return (
    <View style={styles.row}>
      <Dot delay={0} color={t.colors.brand} />
      <Dot delay={160} color={t.colors.brand} />
      <Dot delay={320} color={t.colors.brand} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 4 },
  dot: { width: 7, height: 7, borderRadius: 4 },
});
