import { useState } from 'react';
import Card from '../components/Card';
import TabNavigation from '../components/TabNavigation';
import Button from '../components/Button';
import { useCookieConsent } from '../hooks/useCookieConsent';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const {
    preferences,
    hasConsented,
    consentDate,
    savePreferences,
    revokeConsent,
  } = useCookieConsent();

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'notifications', label: 'Notifications' },
    { id: 'security', label: 'Security' },
    { id: 'privacy', label: 'Privacy' },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gold-400">Settings</h1>
        <p className="text-dark-400 mt-1">Manage application settings</p>
      </div>

      {/* Tab Navigation */}
      <TabNavigation tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'general' && (
          <Card title="General Settings">
            <div className="space-y-6">
              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">Dark Mode</span>
                    <span className="text-sm text-dark-400">Use dark theme (default)</span>
                  </div>
                  <input type="checkbox" defaultChecked className="w-5 h-5" />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">Compact View</span>
                    <span className="text-sm text-dark-400">Reduce spacing in tables</span>
                  </div>
                  <input type="checkbox" className="w-5 h-5" />
                </label>
              </div>

              <div>
                <label className="block">
                  <span className="text-gold-400 block mb-2">Timezone</span>
                  <select className="input">
                    <option value="UTC">UTC</option>
                    <option value="America/New_York">Eastern Time</option>
                    <option value="America/Chicago">Central Time</option>
                    <option value="America/Denver">Mountain Time</option>
                    <option value="America/Los_Angeles">Pacific Time</option>
                  </select>
                </label>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'notifications' && (
          <Card title="Notification Settings">
            <div className="space-y-6">
              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">Email Notifications</span>
                    <span className="text-sm text-dark-400">Receive email for important events</span>
                  </div>
                  <input type="checkbox" defaultChecked className="w-5 h-5" />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">System Alerts</span>
                    <span className="text-sm text-dark-400">Get notified about system issues</span>
                  </div>
                  <input type="checkbox" defaultChecked className="w-5 h-5" />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">Weekly Reports</span>
                    <span className="text-sm text-dark-400">Receive weekly summary email</span>
                  </div>
                  <input type="checkbox" className="w-5 h-5" />
                </label>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'security' && (
          <Card title="Security Settings">
            <div className="space-y-6">
              <div>
                <label className="flex items-center justify-between">
                  <div>
                    <span className="text-gold-400 block">Two-Factor Authentication</span>
                    <span className="text-sm text-dark-400">Add extra security to your account</span>
                  </div>
                  <input type="checkbox" className="w-5 h-5" />
                </label>
              </div>

              <div>
                <label className="block">
                  <span className="text-gold-400 block mb-2">Session Timeout</span>
                  <select className="input">
                    <option value="15">15 minutes</option>
                    <option value="30">30 minutes</option>
                    <option value="60" selected>1 hour</option>
                    <option value="480">8 hours</option>
                  </select>
                </label>
              </div>

              <div className="pt-4 border-t border-dark-700">
                <h3 className="text-gold-400 mb-3">Active Sessions</h3>
                <div className="text-dark-400 text-sm">
                  <p>Current session: This device</p>
                  <p className="text-dark-500 mt-1">Last active: Just now</p>
                </div>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'privacy' && (
          <div className="space-y-6">
            <Card title="Cookie Preferences">
              <div className="space-y-6">
                <p className="text-dark-400 text-sm">
                  Manage how we use cookies on this site. Your preferences will be saved and
                  applied immediately.
                </p>

                {hasConsented && consentDate && (
                  <div className="text-sm text-dark-500">
                    Consent given on: {new Date(consentDate).toLocaleDateString()}
                  </div>
                )}

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-dark-900 rounded-lg">
                    <div>
                      <span className="text-gold-400 block">Necessary Cookies</span>
                      <span className="text-sm text-dark-400">
                        Required for the website to function properly
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={true}
                      disabled
                      className="w-5 h-5 opacity-50"
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 bg-dark-900 rounded-lg">
                    <div>
                      <span className="text-gold-400 block">Analytics Cookies</span>
                      <span className="text-sm text-dark-400">
                        Help us understand how visitors use our site
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={preferences.analytics}
                      onChange={(e) => savePreferences({ analytics: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 bg-dark-900 rounded-lg">
                    <div>
                      <span className="text-gold-400 block">Functional Cookies</span>
                      <span className="text-sm text-dark-400">
                        Enable enhanced functionality and personalization
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={preferences.functional}
                      onChange={(e) => savePreferences({ functional: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 bg-dark-900 rounded-lg">
                    <div>
                      <span className="text-gold-400 block">Marketing Cookies</span>
                      <span className="text-sm text-dark-400">
                        Used to display relevant advertisements
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={preferences.marketing}
                      onChange={(e) => savePreferences({ marketing: e.target.checked })}
                      className="w-5 h-5"
                    />
                  </div>
                </div>

                <div className="pt-4 border-t border-dark-700">
                  <Button variant="secondary" onClick={revokeConsent}>
                    Reset Cookie Consent
                  </Button>
                  <p className="text-xs text-dark-500 mt-2">
                    This will clear your cookie preferences and show the consent banner again.
                  </p>
                </div>
              </div>
            </Card>

            <Card title="Privacy Information">
              <div className="space-y-4 text-dark-400 text-sm">
                <p>
                  We are committed to protecting your privacy. This section explains how we
                  collect, use, and protect your personal information.
                </p>
                <h4 className="text-gold-400 font-medium">Data We Collect</h4>
                <ul className="list-disc list-inside space-y-1">
                  <li>Account information (email, name)</li>
                  <li>Usage data (page views, clicks)</li>
                  <li>Technical data (browser type, IP address)</li>
                </ul>
                <h4 className="text-gold-400 font-medium">Your Rights</h4>
                <ul className="list-disc list-inside space-y-1">
                  <li>Right to access your data</li>
                  <li>Right to rectification</li>
                  <li>Right to erasure ("right to be forgotten")</li>
                  <li>Right to data portability</li>
                </ul>
                <p className="pt-2">
                  For more information, please contact our data protection officer at{' '}
                  <a href="mailto:privacy@example.com" className="text-gold-400 hover:underline">
                    privacy@example.com
                  </a>
                </p>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
