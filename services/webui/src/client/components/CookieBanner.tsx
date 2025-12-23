/**
 * GDPR Cookie Consent Banner Component.
 *
 * Displays a non-intrusive banner at the bottom of the page
 * allowing users to accept or customize cookie preferences.
 */

import { useState } from 'react';
import { useCookieConsent, CookiePreferences } from '../hooks/useCookieConsent';
import Button from './Button';

interface CookieSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  preferences: CookiePreferences;
  onSave: (preferences: Partial<CookiePreferences>) => void;
}

function CookieSettingsModal({
  isOpen,
  onClose,
  preferences,
  onSave,
}: CookieSettingsModalProps) {
  const [localPreferences, setLocalPreferences] = useState<CookiePreferences>(preferences);

  if (!isOpen) return null;

  const handleToggle = (key: keyof CookiePreferences) => {
    if (key === 'necessary') return; // Cannot disable necessary cookies
    setLocalPreferences((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = () => {
    onSave(localPreferences);
  };

  const categories = [
    {
      key: 'necessary' as const,
      label: 'Necessary Cookies',
      description: 'Required for the website to function properly. Cannot be disabled.',
      required: true,
    },
    {
      key: 'analytics' as const,
      label: 'Analytics Cookies',
      description: 'Help us understand how visitors interact with our website by collecting anonymous information.',
      required: false,
    },
    {
      key: 'functional' as const,
      label: 'Functional Cookies',
      description: 'Enable enhanced functionality and personalization features.',
      required: false,
    },
    {
      key: 'marketing' as const,
      label: 'Marketing Cookies',
      description: 'Used to track visitors across websites to display relevant advertisements.',
      required: false,
    },
  ];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-dark-800 rounded-xl shadow-2xl max-w-2xl w-full border border-dark-700">
          {/* Header */}
          <div className="px-6 py-4 border-b border-dark-700">
            <h2 className="text-xl font-semibold text-gold-400">
              Cookie Preferences
            </h2>
            <p className="text-sm text-gray-400 mt-1">
              Manage your cookie preferences below. You can enable or disable different types of cookies.
            </p>
          </div>

          {/* Content */}
          <div className="px-6 py-4 max-h-96 overflow-y-auto">
            <div className="space-y-4">
              {categories.map((category) => (
                <div
                  key={category.key}
                  className="flex items-start justify-between p-4 bg-dark-900 rounded-lg"
                >
                  <div className="flex-1 pr-4">
                    <h3 className="font-medium text-white">
                      {category.label}
                      {category.required && (
                        <span className="ml-2 text-xs text-gold-500">(Required)</span>
                      )}
                    </h3>
                    <p className="text-sm text-gray-400 mt-1">
                      {category.description}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    <button
                      onClick={() => handleToggle(category.key)}
                      disabled={category.required}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        localPreferences[category.key]
                          ? 'bg-gold-500'
                          : 'bg-dark-600'
                      } ${category.required ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          localPreferences[category.key] ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-dark-700 flex justify-end gap-3">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave}>
              Save Preferences
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CookieBanner() {
  const {
    preferences,
    showBanner,
    showSettings,
    setShowSettings,
    acceptAll,
    acceptNecessary,
    savePreferences,
  } = useCookieConsent();

  if (!showBanner && !showSettings) return null;

  return (
    <>
      {/* Cookie Banner */}
      {showBanner && !showSettings && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-dark-900 border-t border-dark-700 shadow-lg">
          <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              {/* Message */}
              <div className="flex-1">
                <h3 className="text-lg font-medium text-white">
                  We value your privacy
                </h3>
                <p className="text-sm text-gray-400 mt-1">
                  We use cookies to enhance your browsing experience, serve personalized content,
                  and analyze our traffic. By clicking "Accept All", you consent to our use of cookies.{' '}
                  <button
                    onClick={() => setShowSettings(true)}
                    className="text-gold-400 hover:text-gold-300 underline"
                  >
                    Learn more
                  </button>
                </p>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-2 sm:flex-nowrap">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowSettings(true)}
                >
                  Customize
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={acceptNecessary}
                >
                  Necessary Only
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={acceptAll}
                >
                  Accept All
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Settings Modal */}
      <CookieSettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        preferences={preferences}
        onSave={savePreferences}
      />
    </>
  );
}
