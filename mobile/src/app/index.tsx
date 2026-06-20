import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

import { fetchMenus } from '@/lib/api';

export default function MenusScreen() {
  const router = useRouter();
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

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#c0392b" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
        <Text style={styles.errorHint}>
          Is the backend running and EXPO_PUBLIC_API_URL set correctly?
        </Text>
        <Pressable style={styles.retry} onPress={load}>
          <Text style={styles.retryText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <Text style={styles.subtitle}>Pick a menu to start chatting</Text>
      <FlatList
        data={menus}
        keyExtractor={(item) => item}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#c0392b"
          />
        }
        renderItem={({ item }) => (
          <Pressable
            style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
            onPress={() =>
              router.push({ pathname: '/chat', params: { restaurant: item } })
            }
          >
            <Text style={styles.cardTitle}>{item}</Text>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#faf7f5' },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: '#faf7f5',
  },
  subtitle: {
    fontSize: 15,
    color: '#7a6f6a',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  list: { padding: 16, gap: 12 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#fff',
    borderRadius: 14,
    paddingVertical: 20,
    paddingHorizontal: 20,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardPressed: { backgroundColor: '#f1eae7' },
  cardTitle: { fontSize: 18, fontWeight: '600', color: '#2c2420' },
  chevron: { fontSize: 26, color: '#c0392b', fontWeight: '300' },
  errorText: { fontSize: 16, color: '#c0392b', textAlign: 'center', fontWeight: '600' },
  errorHint: { fontSize: 13, color: '#7a6f6a', textAlign: 'center', marginTop: 8 },
  retry: {
    marginTop: 20,
    backgroundColor: '#c0392b',
    paddingHorizontal: 28,
    paddingVertical: 12,
    borderRadius: 10,
  },
  retryText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
