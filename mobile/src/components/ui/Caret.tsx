// Blinking caret appended to the answer while it streams in.
import { useEffect } from 'react';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { useTheme } from '@/theme';

export function Caret() {
  const t = useTheme();
  const v = useSharedValue(1);

  useEffect(() => {
    v.value = withRepeat(
      withSequence(withTiming(0, { duration: 480 }), withTiming(1, { duration: 480 })),
      -1,
      false,
    );
  }, [v]);

  const style = useAnimatedStyle(() => ({ opacity: v.value }));

  return (
    <Animated.Text style={[{ color: t.colors.brand, fontWeight: '700' }, style]}>
      ▍
    </Animated.Text>
  );
}
