import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { invoke } from '@tauri-apps/api/core';

// Import all translation files and merge them
import en from './locales/en/translations.json';
import zh from './locales/zh/translations.json';

// Initial language from config file (will be updated asynchronously)
let initialLanguage = 'zh'; // default fallback

// Fetch language from Tauri config and update i18n
async function initLanguageFromConfig() {
  try {
    const lang = await invoke<string>('get_app_language');
    initialLanguage = lang as 'en' | 'zh';
    // Update i18n if it was initialized with a different language
    if (i18n.language !== initialLanguage) {
      await i18n.changeLanguage(initialLanguage);
    }
  } catch (error) {
    console.error('Failed to get language from config:', error);
    // Use browser language as fallback
    const browserLang = navigator.language.startsWith('zh') ? 'zh' : 'en';
    if (i18n.language !== browserLang) {
      await i18n.changeLanguage(browserLang);
    }
  }
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: 'zh',
    lng: initialLanguage,

    interpolation: {
      escapeValue: false,
    },

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
  });

// Initialize language from config after i18n is ready
initLanguageFromConfig();

export default i18n;
