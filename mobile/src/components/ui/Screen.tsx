// Screen wrapper: themed background + safe-area handling in one place.
import { type ReactNode } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { useTheme } from '@/theme';

type Props = {
  children: ReactNode;
  /** Safe-area edges to inset. Defaults to bottom only (header covers top). */
  edges?: readonly Edge[];
  style?: ViewStyle;
  /** Skip SafeAreaView (e.g. when a keyboard-avoiding view owns layout). */
  unsafe?: boolean;
};

export function Screen({ children, edges = ['bottom'], style, unsafe }: Props) {
  const t = useTheme();
  const bg = { backgroundColor: t.colors.bg };

  if (unsafe) {
    return <View style={[styles.flex, bg, style]}>{children}</View>;
  }
  return (
    <SafeAreaView style={[styles.flex, bg, style]} edges={edges}>
      {children}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({ flex: { flex: 1 } });
