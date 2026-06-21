// Small rounded chip — used for source citations and tags.
import { Pressable, StyleSheet, View } from 'react-native';

import { useTheme } from '@/theme';
import { AppText } from './AppText';

type Props = {
  label: string;
  onPress?: () => void;
  tone?: 'default' | 'brand';
};

export function Pill({ label, onPress, tone = 'default' }: Props) {
  const t = useTheme();
  const bg = tone === 'brand' ? t.colors.brandTint : t.colors.surfaceAlt;
  const fg = tone === 'brand' ? t.colors.brand : t.colors.textMuted;

  const body = (
    <AppText variant="caption" color={fg} style={styles.label}>
      {label}
    </AppText>
  );
  const inner = [styles.pill, { backgroundColor: bg, borderRadius: t.radius.pill }];

  if (!onPress) return <View style={inner}>{body}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [inner, pressed && styles.pressed]}>
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' },
  label: { fontWeight: '600' },
  pressed: { opacity: 0.6 },
});
