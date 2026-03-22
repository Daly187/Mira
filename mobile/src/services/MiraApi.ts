/**
 * MiraApi — HTTP client for communicating with the Mira desktop agent.
 *
 * Connects to the FastAPI backend (api.py) running on the Windows desktop,
 * typically via Tailscale VPN. All endpoints match those defined in api.py.
 */
import axios, {AxiosInstance} from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import RNFS from 'react-native-fs';

const STORAGE_KEY_HOST = '@mira_host';
const DEFAULT_HOST = '100.64.0.1:8000';
const TIMEOUT_MS = 15_000;

export interface MiraStatus {
  connected: boolean;
  uptime: string;
  memoryCount: number;
  tradeCount: number;
  actionCount: number;
  autonomyPaused: boolean;
}

export interface RecentMemory {
  id: string;
  type: string;
  content: string;
  timeAgo: string;
  createdAt: string;
}

class MiraApiClient {
  private client: AxiosInstance;
  private baseUrl: string = `http://${DEFAULT_HOST}`;

  constructor() {
    this.client = axios.create({
      timeout: TIMEOUT_MS,
      headers: {'Content-Type': 'application/json'},
    });

    // Load saved host on init
    this.refreshBaseUrl();
  }

  private async refreshBaseUrl(): Promise<void> {
    try {
      const savedHost = await AsyncStorage.getItem(STORAGE_KEY_HOST);
      if (savedHost) {
        this.baseUrl = `http://${savedHost}`;
      }
    } catch {
      // Use default
    }
  }

  private async url(path: string): Promise<string> {
    await this.refreshBaseUrl();
    return `${this.baseUrl}${path}`;
  }

  // ── Status ──

  async getStatus(): Promise<MiraStatus> {
    const resp = await this.client.get(await this.url('/api/status'));
    const d = resp.data;
    return {
      connected: true,
      uptime: d.uptime ?? '',
      memoryCount: d.memory_count ?? 0,
      tradeCount: d.trade_count ?? 0,
      actionCount: d.action_count ?? 0,
      autonomyPaused: d.autonomy_paused ?? false,
    };
  }

  // ── Memories ──

  async getRecentMemories(limit: number = 10): Promise<RecentMemory[]> {
    const resp = await this.client.get(
      await this.url(`/api/memories?limit=${limit}`),
    );
    return (resp.data.memories ?? []).map((m: any) => ({
      id: m.id,
      type: m.type ?? 'note',
      content: m.content ?? '',
      timeAgo: m.time_ago ?? '',
      createdAt: m.created_at ?? '',
    }));
  }

  // ── Commands ──

  async sendCommand(command: string): Promise<void> {
    await this.client.post(await this.url('/api/command'), {command});
  }

  // ── Capture: Audio ──

  async uploadAudio(filePath: string): Promise<void> {
    const base64 = await RNFS.readFile(filePath, 'base64');
    await this.client.post(await this.url('/api/capture/audio'), {
      audio_b64: base64,
      format: 'aac',
      source: 'mobile',
    });
  }

  // ── Capture: Photo ──

  async uploadPhoto(uri: string): Promise<void> {
    const base64 = await RNFS.readFile(uri, 'base64');
    await this.client.post(await this.url('/api/capture/photo'), {
      image_b64: base64,
      source: 'mobile',
    });
  }

  // ── Capture: Text note ──

  async sendNote(text: string): Promise<void> {
    await this.client.post(await this.url('/api/capture/note'), {
      content: text,
      source: 'mobile',
    });
  }

  // ── Location ──

  async sendLocation(
    latitude: number,
    longitude: number,
    accuracy: number,
  ): Promise<void> {
    await this.client.post(await this.url('/api/capture/location'), {
      latitude,
      longitude,
      accuracy,
      source: 'mobile',
    });
  }

  // ── Push notification token ──

  async registerPushToken(token: string): Promise<void> {
    await this.client.post(await this.url('/api/mobile/register'), {
      push_token: token,
      platform: 'android',
    });
  }
}

const MiraApi = new MiraApiClient();
export default MiraApi;
