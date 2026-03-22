/**
 * Mira brand colours and shared style constants.
 * Purple/indigo palette matching the dashboard.
 */

export const COLORS = {
  // Brand
  primary: '#7C3AED',        // Violet-600
  primaryLight: '#A78BFA',   // Violet-400
  primaryDark: '#5B21B6',    // Violet-800
  accent: '#6366F1',         // Indigo-500

  // Backgrounds
  backgroundDark: '#0F0B1A',
  backgroundCard: '#1A1425',
  backgroundInput: '#251E35',

  // Text
  textPrimary: '#F5F3FF',
  textSecondary: '#C4B5FD',
  textMuted: '#6B7280',

  // Status
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',

  // Borders
  border: '#2D2640',
  borderLight: '#3D3555',
} as const;

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const FONT_SIZES = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
} as const;
