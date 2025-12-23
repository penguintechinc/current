/**
 * Cookie consent management hook for GDPR compliance.
 *
 * Manages user cookie preferences with localStorage persistence.
 * Categories:
 * - necessary: Always enabled, required for site functionality
 * - analytics: Performance and analytics tracking
 * - marketing: Advertising and marketing cookies
 * - functional: Enhanced functionality cookies
 */

import { useState, useEffect, useCallback } from 'react';

export interface CookiePreferences {
  necessary: boolean;  // Always true, cannot be disabled
  analytics: boolean;
  marketing: boolean;
  functional: boolean;
}

export interface CookieConsentState {
  preferences: CookiePreferences;
  hasConsented: boolean;
  consentDate: string | null;
}

const STORAGE_KEY = 'cookie_consent';
const DEFAULT_PREFERENCES: CookiePreferences = {
  necessary: true,
  analytics: false,
  marketing: false,
  functional: false,
};

export function useCookieConsent() {
  const [state, setState] = useState<CookieConsentState>({
    preferences: DEFAULT_PREFERENCES,
    hasConsented: false,
    consentDate: null,
  });
  const [showBanner, setShowBanner] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Load consent from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as CookieConsentState;
        setState({
          preferences: {
            ...DEFAULT_PREFERENCES,
            ...parsed.preferences,
            necessary: true, // Always true
          },
          hasConsented: true,
          consentDate: parsed.consentDate,
        });
        setShowBanner(false);
      } catch {
        setShowBanner(true);
      }
    } else {
      setShowBanner(true);
    }
  }, []);

  // Save consent to localStorage
  const saveConsent = useCallback((preferences: CookiePreferences) => {
    const consentState: CookieConsentState = {
      preferences: {
        ...preferences,
        necessary: true, // Always true
      },
      hasConsented: true,
      consentDate: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(consentState));
    setState(consentState);
    setShowBanner(false);
    setShowSettings(false);

    // Dispatch event for other components to react
    window.dispatchEvent(new CustomEvent('cookieConsentUpdate', {
      detail: consentState.preferences,
    }));
  }, []);

  // Accept all cookies
  const acceptAll = useCallback(() => {
    saveConsent({
      necessary: true,
      analytics: true,
      marketing: true,
      functional: true,
    });
  }, [saveConsent]);

  // Accept only necessary cookies
  const acceptNecessary = useCallback(() => {
    saveConsent({
      necessary: true,
      analytics: false,
      marketing: false,
      functional: false,
    });
  }, [saveConsent]);

  // Save custom preferences
  const savePreferences = useCallback((preferences: Partial<CookiePreferences>) => {
    saveConsent({
      ...state.preferences,
      ...preferences,
      necessary: true, // Always true
    });
  }, [saveConsent, state.preferences]);

  // Revoke consent and show banner again
  const revokeConsent = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setState({
      preferences: DEFAULT_PREFERENCES,
      hasConsented: false,
      consentDate: null,
    });
    setShowBanner(true);
  }, []);

  // Check if a specific cookie category is allowed
  const isAllowed = useCallback((category: keyof CookiePreferences): boolean => {
    return state.preferences[category] ?? false;
  }, [state.preferences]);

  return {
    preferences: state.preferences,
    hasConsented: state.hasConsented,
    consentDate: state.consentDate,
    showBanner,
    showSettings,
    setShowSettings,
    acceptAll,
    acceptNecessary,
    savePreferences,
    revokeConsent,
    isAllowed,
  };
}

// Type for the cookie consent event
declare global {
  interface WindowEventMap {
    cookieConsentUpdate: CustomEvent<CookiePreferences>;
  }
}
