// Shared press-scale animation used by Button and Card for a tactile feel.
import { useCallback } from 'react';
import {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';

const SPRING = { damping: 18, stiffness: 320, mass: 0.5 };

export function usePressScale(to = 0.97) {
  const scale = useSharedValue(1);

  const onPressIn = useCallback(() => {
    scale.value = withSpring(to, SPRING);
  }, [scale, to]);

  const onPressOut = useCallback(() => {
    scale.value = withSpring(1, SPRING);
  }, [scale]);

  const style = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  return { style, onPressIn, onPressOut };
}
