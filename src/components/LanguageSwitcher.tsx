import { useTranslation } from '@/i18n';
import { Button } from '@/components/ui/button';
import { Languages } from 'lucide-react';

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();

  const toggleLanguage = () => {
    const currentLang = i18n.language;
    const newLang = currentLang === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(newLang);
  };

  const currentLanguage = t(`languages.${i18n.language}` as any);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleLanguage}
      className="text-muted-foreground hover:text-foreground relative"
      aria-label={t('languages.switch')}
      title={`${currentLanguage} - ${t('languages.switch')}`}
    >
      <Languages className="h-[1.2rem] w-[1.2rem]" />
      <span className="sr-only">{t('languages.switch')}</span>
      <span className="absolute -bottom-1 -right-1 text-[0.6rem] font-bold text-foreground">
        {i18n.language === 'en' ? 'EN' : '中'}
      </span>
    </Button>
  );
}
