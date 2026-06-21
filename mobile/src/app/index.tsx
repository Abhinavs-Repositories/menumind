import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { Stack, useFocusEffect, useRouter } from 'expo-router';

import { fetchMenus } from '@/lib/api';
import { AppText, Button, Card, Screen } from '@/components/ui';
import { useTheme } from '@/theme';

export default function MenusScreen() {
  const router = useRouter();
  const t = useTheme();
  const [menus, setMenus] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMenus(await fetchMenus());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load menus');
    } finally {
      setLoading(false);
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setMenus(await fetchMenus());
      setError(null);
    } catch {
      // keep current list on a failed refresh
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Silently refresh when returning to this screen (e.g. after adding a menu).
  useFocusEffect(
    useCallback(() => {
      let active = true;
      fetchMenus()
        .then((m) => {
          if (active) setMenus(m);
        })
        .catch(() => {});
      return () => {
        active = false;
      };
    }, []),
  );

  if (loading) {
    return (
      <Screen style={styles.centered} edges={['bottom']}>
        <ActivityIndicator size="large" color={t.colors.brand} />
      </Screen>
    );
  }

  if (error) {
    return (
      <Screen style={styles.centered}>
        <AppText variant="heading" color={t.colors.brand} center>
          {error}
        </AppText>
        <AppText variant="muted" center style={styles.gap}>
          Is the backend running and EXPO_PUBLIC_API_URL set correctly?
        </AppText>
        <Button title="Retry" onPress={load} full={false} style={styles.retry} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable onPress={() => router.push('/add-menu')} hitSlop={8}>
              <AppText variant="heading" color={t.colors.brand} style={styles.addBtn}>
                ＋ Add
              </AppText>
            </Pressable>
          ),
        }}
      />
      <AppText variant="muted" style={styles.subtitle}>
        Pick a menu to start chatting
      </AppText>
      <FlatList
        data={menus}
        keyExtractor={(item) => item}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={t.colors.brand}
          />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <AppText variant="title" center>
              No menus yet
            </AppText>
            <AppText variant="muted" center style={styles.gap}>
              Add a restaurant menu and start asking about dishes, prices and
              dietary options.
            </AppText>
            <Button
              title="＋ Add a menu"
              onPress={() => router.push('/add-menu')}
              full={false}
              style={styles.retry}
            />
          </View>
        }
        renderItem={({ item, index }) => (
          <Animated.View entering={FadeInDown.delay(Math.min(index, 8) * 45).duration(260)}>
          <Card
            onPress={() => router.push({ pathname: '/chat', params: { restaurant: item } })}
            style={styles.card}
          >
            <View style={[styles.monogram, { backgroundColor: t.colors.brandTint }]}>
              <AppText variant="title" color={t.colors.brand}>
                {item.charAt(0).toUpperCase()}
              </AppText>
            </View>
            <View style={styles.cardBody}>
              <AppText variant="heading" numberOfLines={1}>
                {item}
              </AppText>
              <AppText variant="caption">Tap to ask about the menu</AppText>
            </View>
            <AppText style={[styles.chevron, { color: t.colors.brand }]}>›</AppText>
          </Card>
          </Animated.View>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  centered: { alignItems: 'center', justifyContent: 'center', padding: 24 },
  subtitle: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  list: { padding: 16, gap: 12, flexGrow: 1 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  monogram: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardBody: { flex: 1, gap: 2 },
  chevron: { fontSize: 26, fontWeight: '300' },
  addBtn: { fontSize: 16 },
  gap: { marginTop: 8 },
  retry: { marginTop: 20, paddingHorizontal: 28 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, marginTop: 40 },
});
