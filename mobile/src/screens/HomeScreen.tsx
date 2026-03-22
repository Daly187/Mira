/**
 * HomeScreen — Mira status dashboard
 *
 * Shows: connection status, agent uptime, recent memories,
 * quick action buttons (briefing, kill switch, sync).
 */
import React, {useCallback, useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import MiraApi, {MiraStatus, RecentMemory} from '../services/MiraApi';
import {COLORS, SPACING, FONT_SIZES} from '../utils/theme';

const HomeScreen: React.FC = () => {
  const [status, setStatus] = useState<MiraStatus | null>(null);
  const [memories, setMemories] = useState<RecentMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        MiraApi.getStatus(),
        MiraApi.getRecentMemories(10),
      ]);
      setStatus(s);
      setMemories(m);
    } catch (err) {
      console.warn('Failed to fetch Mira status:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Poll every 30 seconds
    const interval = setInterval(fetchData, 30_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleQuickAction = async (action: string) => {
    try {
      await MiraApi.sendCommand(action);
    } catch (err) {
      console.warn(`Quick action "${action}" failed:`, err);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Connecting to Mira...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={COLORS.primary}
        />
      }>
      {/* Connection Status Banner */}
      <View
        style={[
          styles.statusBanner,
          {
            backgroundColor: status?.connected
              ? COLORS.success + '20'
              : COLORS.error + '20',
          },
        ]}>
        <Icon
          name={status?.connected ? 'check-circle' : 'alert-circle'}
          size={20}
          color={status?.connected ? COLORS.success : COLORS.error}
        />
        <Text
          style={[
            styles.statusText,
            {color: status?.connected ? COLORS.success : COLORS.error},
          ]}>
          {status?.connected ? 'Mira Online' : 'Mira Offline'}
        </Text>
        {status?.uptime && (
          <Text style={styles.uptimeText}>Uptime: {status.uptime}</Text>
        )}
      </View>

      {/* KPI Cards */}
      <View style={styles.kpiRow}>
        <KpiCard
          icon="brain"
          label="Memories"
          value={status?.memoryCount?.toString() ?? '--'}
        />
        <KpiCard
          icon="chart-line"
          label="Trades"
          value={status?.tradeCount?.toString() ?? '--'}
        />
        <KpiCard
          icon="robot-happy"
          label="Actions"
          value={status?.actionCount?.toString() ?? '--'}
        />
      </View>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionsRow}>
        <ActionButton
          icon="weather-sunny"
          label="Briefing"
          onPress={() => handleQuickAction('briefing')}
        />
        <ActionButton
          icon="sync"
          label="Sync"
          onPress={() => handleQuickAction('sync')}
        />
        <ActionButton
          icon="pause-octagon"
          label="Kill Switch"
          onPress={() => handleQuickAction('killswitch')}
          danger
        />
      </View>

      {/* Recent Memories */}
      <Text style={styles.sectionTitle}>Recent Memories</Text>
      {memories.length === 0 ? (
        <Text style={styles.emptyText}>No memories yet</Text>
      ) : (
        memories.map((mem, idx) => (
          <View key={mem.id ?? idx} style={styles.memoryCard}>
            <View style={styles.memoryHeader}>
              <Icon
                name={memoryTypeIcon(mem.type)}
                size={16}
                color={COLORS.primaryLight}
              />
              <Text style={styles.memoryType}>{mem.type}</Text>
              <Text style={styles.memoryTime}>{mem.timeAgo}</Text>
            </View>
            <Text style={styles.memoryContent} numberOfLines={3}>
              {mem.content}
            </Text>
          </View>
        ))
      )}

      <View style={{height: SPACING.xl}} />
    </ScrollView>
  );
};

/* ── Sub-components ── */

const KpiCard: React.FC<{icon: string; label: string; value: string}> = ({
  icon,
  label,
  value,
}) => (
  <View style={styles.kpiCard}>
    <Icon name={icon} size={22} color={COLORS.primaryLight} />
    <Text style={styles.kpiValue}>{value}</Text>
    <Text style={styles.kpiLabel}>{label}</Text>
  </View>
);

const ActionButton: React.FC<{
  icon: string;
  label: string;
  onPress: () => void;
  danger?: boolean;
}> = ({icon, label, onPress, danger}) => (
  <TouchableOpacity
    style={[styles.actionBtn, danger && styles.actionBtnDanger]}
    onPress={onPress}
    activeOpacity={0.7}>
    <Icon
      name={icon}
      size={24}
      color={danger ? COLORS.error : COLORS.primary}
    />
    <Text
      style={[styles.actionLabel, danger && {color: COLORS.error}]}>
      {label}
    </Text>
  </TouchableOpacity>
);

function memoryTypeIcon(type: string): string {
  const map: Record<string, string> = {
    voice: 'microphone',
    photo: 'camera',
    note: 'note-text',
    observation: 'eye',
    trade: 'chart-line',
    calendar: 'calendar',
  };
  return map[type] ?? 'circle-small';
}

/* ── Styles ── */

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.backgroundDark,
    paddingHorizontal: SPACING.md,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.backgroundDark,
  },
  loadingText: {
    color: COLORS.textMuted,
    marginTop: SPACING.sm,
    fontSize: FONT_SIZES.sm,
  },

  // Status banner
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: SPACING.md,
    borderRadius: 12,
    marginTop: SPACING.md,
    gap: SPACING.sm,
  },
  statusText: {
    fontSize: FONT_SIZES.md,
    fontWeight: '700',
  },
  uptimeText: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginLeft: 'auto',
  },

  // KPI cards
  kpiRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
    marginTop: SPACING.md,
  },
  kpiCard: {
    flex: 1,
    backgroundColor: COLORS.backgroundCard,
    borderRadius: 12,
    padding: SPACING.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  kpiValue: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.xl,
    fontWeight: '700',
    marginTop: SPACING.xs,
  },
  kpiLabel: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginTop: 2,
  },

  // Quick actions
  sectionTitle: {
    color: COLORS.textSecondary,
    fontSize: FONT_SIZES.sm,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: SPACING.lg,
    marginBottom: SPACING.sm,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
  },
  actionBtn: {
    flex: 1,
    backgroundColor: COLORS.backgroundCard,
    borderRadius: 12,
    padding: SPACING.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
    gap: SPACING.xs,
  },
  actionBtnDanger: {
    borderColor: COLORS.error + '40',
  },
  actionLabel: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.xs,
    fontWeight: '600',
  },

  // Memory cards
  memoryCard: {
    backgroundColor: COLORS.backgroundCard,
    borderRadius: 12,
    padding: SPACING.md,
    marginBottom: SPACING.sm,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  memoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.xs,
    marginBottom: SPACING.xs,
  },
  memoryType: {
    color: COLORS.primaryLight,
    fontSize: FONT_SIZES.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  memoryTime: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.xs,
    marginLeft: 'auto',
  },
  memoryContent: {
    color: COLORS.textPrimary,
    fontSize: FONT_SIZES.sm,
    lineHeight: 20,
  },
  emptyText: {
    color: COLORS.textMuted,
    fontSize: FONT_SIZES.sm,
    textAlign: 'center',
    paddingVertical: SPACING.lg,
  },
});

export default HomeScreen;
