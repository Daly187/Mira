/**
 * LocationService — Passive GPS location tracking.
 *
 * Sends periodic location updates to Mira for context-aware memories
 * (e.g., "you were at the gym when you said X"). Uses a low-power
 * strategy with infrequent updates to minimise battery drain.
 */
import Geolocation, {
  GeoPosition,
  GeoError,
} from 'react-native-geolocation-service';
import {PermissionsAndroid, Platform} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import MiraApi from './MiraApi';

const UPDATE_INTERVAL_MS = 5 * 60_000; // 5 minutes
const MIN_DISTANCE_METRES = 100; // Only report if moved 100m+

class LocationServiceManager {
  private watchId: number | null = null;
  private lastSentAt = 0;
  private lastLat = 0;
  private lastLng = 0;

  /**
   * Request permissions and start passive tracking.
   */
  async startTracking(): Promise<void> {
    const enabled = await AsyncStorage.getItem('@location_enabled');
    if (enabled === 'false') {
      console.log('LocationService: disabled by user setting');
      return;
    }

    const hasPermission = await this.requestPermission();
    if (!hasPermission) {
      console.warn('LocationService: permission denied');
      return;
    }

    // Watch position with low-power settings
    this.watchId = Geolocation.watchPosition(
      position => this.onPosition(position),
      error => this.onError(error),
      {
        accuracy: {android: 'balanced', ios: 'hundredMeters'},
        enableHighAccuracy: false,
        distanceFilter: MIN_DISTANCE_METRES,
        interval: UPDATE_INTERVAL_MS,
        fastestInterval: 60_000, // At most once per minute
        forceRequestLocation: false,
        showLocationDialog: false,
      },
    );

    console.log('LocationService: started tracking');
  }

  /**
   * Stop tracking and clear watch.
   */
  stopTracking(): void {
    if (this.watchId !== null) {
      Geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }
    console.log('LocationService: stopped');
  }

  /**
   * Get current position once (for on-demand use).
   */
  async getCurrentPosition(): Promise<GeoPosition | null> {
    const hasPermission = await this.requestPermission();
    if (!hasPermission) return null;

    return new Promise((resolve, reject) => {
      Geolocation.getCurrentPosition(
        position => resolve(position),
        error => {
          console.warn('LocationService: getCurrentPosition failed', error);
          reject(error);
        },
        {
          enableHighAccuracy: false,
          timeout: 15_000,
          maximumAge: 60_000,
        },
      );
    });
  }

  // ── Internal ──

  private async requestPermission(): Promise<boolean> {
    if (Platform.OS !== 'android') return true;

    try {
      const fineLocation = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
        {
          title: 'Mira Location Access',
          message:
            'Mira uses your location to add context to your memories. ' +
            'This helps Mira understand where events happened.',
          buttonPositive: 'Allow',
          buttonNegative: 'Deny',
        },
      );

      if (fineLocation !== PermissionsAndroid.RESULTS.GRANTED) {
        // Try coarse as fallback
        const coarseLocation = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_COARSE_LOCATION,
        );
        return coarseLocation === PermissionsAndroid.RESULTS.GRANTED;
      }

      // Also request background location for when app is minimised
      if (Platform.Version >= 29) {
        await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_BACKGROUND_LOCATION,
          {
            title: 'Mira Background Location',
            message:
              'Allow Mira to track location in the background for ' +
              'continuous context-aware memories.',
            buttonPositive: 'Allow',
            buttonNegative: 'Deny',
          },
        );
      }

      return true;
    } catch (err) {
      console.warn('LocationService: permission request failed', err);
      return false;
    }
  }

  private onPosition(position: GeoPosition): void {
    const now = Date.now();
    const {latitude, longitude, accuracy} = position.coords;

    // Throttle: only send if enough time has passed
    if (now - this.lastSentAt < UPDATE_INTERVAL_MS) return;

    // Only send if we've moved meaningfully
    const distance = this.haversineDistance(
      this.lastLat,
      this.lastLng,
      latitude,
      longitude,
    );
    if (this.lastLat !== 0 && distance < MIN_DISTANCE_METRES) return;

    this.lastSentAt = now;
    this.lastLat = latitude;
    this.lastLng = longitude;

    MiraApi.sendLocation(latitude, longitude, accuracy ?? 0).catch(err =>
      console.warn('LocationService: failed to send location', err),
    );
  }

  private onError(error: GeoError): void {
    console.warn('LocationService: watch error', error.code, error.message);
  }

  /**
   * Calculate distance between two lat/lng points in metres.
   */
  private haversineDistance(
    lat1: number,
    lon1: number,
    lat2: number,
    lon2: number,
  ): number {
    const R = 6371e3; // Earth radius in metres
    const toRad = (deg: number) => (deg * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }
}

const LocationService = new LocationServiceManager();
export default LocationService;
