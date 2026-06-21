// Thin haptics wrapper that no-ops on web (expo-haptics throws there).
import { Platform } from 'react-native';
import * as Haptics from 'expo-haptics';

const enabled = Platform.OS !== 'web';

export const haptics = {
  tap() {
    if (enabled) Haptics.selectionAsync().catch(() => {});
  },
  success() {
    if (enabled)
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
  },
  error() {
    if (enabled)
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
  },
};
