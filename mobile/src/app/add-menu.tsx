import { useCallback, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';

import { getIngestStatus, uploadMenu, type PickedFile } from '@/lib/api';

type Phase = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

export default function AddMenuScreen() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [file, setFile] = useState<PickedFile | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pick = useCallback(async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'image/*'],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets?.length) return;
    const a = result.assets[0];
    setFile({ uri: a.uri, name: a.name, mimeType: a.mimeType });
    setMessage(null);
  }, []);

  const poll = useCallback(
    (jobId: string) => {
      getIngestStatus(jobId)
        .then((s) => {
          if (s.status === 'done') {
            setPhase('done');
            setMessage(
              `Ingested ${s.chunks ?? 0} items from ${s.pages ?? 0} page(s).`,
            );
          } else if (s.status === 'error') {
            setPhase('error');
            setMessage(s.error ?? 'Ingestion failed.');
          } else {
            pollRef.current = setTimeout(() => poll(jobId), 2000);
          }
        })
        .catch((e) => {
          setPhase('error');
          setMessage(e instanceof Error ? e.message : 'Status check failed');
        });
    },
    [],
  );

  const submit = useCallback(async () => {
    const restaurant = name.trim();
    if (!restaurant || !file || phase === 'uploading' || phase === 'processing') {
      return;
    }
    setPhase('uploading');
    setMessage(null);
    try {
      const jobId = await uploadMenu(restaurant, file);
      setPhase('processing');
      poll(jobId);
    } catch (e) {
      setPhase('error');
      setMessage(e instanceof Error ? e.message : 'Upload failed');
    }
  }, [name, file, phase, poll]);

  const busy = phase === 'uploading' || phase === 'processing';

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.body}>
        <Text style={styles.label}>Restaurant name</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="e.g. Blue Tokai"
          placeholderTextColor="#a89e98"
          editable={!busy}
        />

        <Text style={styles.label}>Menu file (PDF or image)</Text>
        <Pressable
          style={[styles.fileBtn, busy && styles.disabled]}
          onPress={pick}
          disabled={busy}
        >
          <Text style={styles.fileBtnText} numberOfLines={1}>
            {file ? file.name : 'Choose a file…'}
          </Text>
        </Pressable>

        {phase === 'done' ? (
          <View style={styles.resultOk}>
            <Text style={styles.resultOkText}>✅ {message}</Text>
            <Pressable
              style={styles.primaryBtn}
              onPress={() => router.replace('/')}
            >
              <Text style={styles.primaryBtnText}>Back to menus</Text>
            </Pressable>
          </View>
        ) : (
          <Pressable
            style={[
              styles.primaryBtn,
              (!name.trim() || !file || busy) && styles.disabled,
            ]}
            onPress={submit}
            disabled={!name.trim() || !file || busy}
          >
            {busy ? (
              <View style={styles.row}>
                <ActivityIndicator color="#fff" />
                <Text style={styles.primaryBtnText}>
                  {phase === 'uploading' ? 'Uploading…' : 'Reading menu…'}
                </Text>
              </View>
            ) : (
              <Text style={styles.primaryBtnText}>Upload &amp; ingest</Text>
            )}
          </Pressable>
        )}

        {phase === 'processing' && (
          <Text style={styles.hint}>
            Parsing the menu with AI and embedding it — this can take up to a
            minute for multi-page PDFs.
          </Text>
        )}
        {phase === 'error' && <Text style={styles.error}>⚠️ {message}</Text>}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#faf7f5' },
  body: { padding: 20, gap: 10 },
  label: { fontSize: 14, color: '#7a6f6a', marginTop: 10, fontWeight: '600' },
  input: {
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: '#2c2420',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#e4dcd7',
  },
  fileBtn: {
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: '#e4dcd7',
  },
  fileBtnText: { fontSize: 16, color: '#2c2420' },
  primaryBtn: {
    backgroundColor: '#c0392b',
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: 'center',
    marginTop: 16,
  },
  primaryBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  disabled: { opacity: 0.5 },
  hint: { color: '#7a6f6a', fontSize: 13, marginTop: 12, lineHeight: 19 },
  error: { color: '#c0392b', fontSize: 14, marginTop: 12, fontWeight: '600' },
  resultOk: { gap: 4 },
  resultOkText: { color: '#1e7a46', fontSize: 15, fontWeight: '600', marginTop: 12 },
});
