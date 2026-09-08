'use client'
// Shared legal/footer bits.
//
// AuthFooter   — the "By continuing, you agree to … Terms of Service and
//                Privacy Policy." line shown under the auth forms.
// CopyrightFooter — the "© {year} St. Joseph's Placements and Training Cell"
//                line for app surfaces (the apex /home hub, the onboarding page, …).
//
// This deployment has no hosted Terms/Privacy pages of its own, so both
// links only render when an org has explicitly configured a platform URL —
// there is no external fallback to point at.
import React from 'react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import { getPlatformUrl } from '@services/config/config'

const TERMS_URL = getPlatformUrl('/terms')
const PRIVACY_URL = getPlatformUrl('/privacy')

export function AuthFooter({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  if (!TERMS_URL && !PRIVACY_URL) return null
  return (
    <div className={`pb-8 pt-6 text-center px-6 ${className}`}>
      <p className="text-[13px] text-black/30 font-medium">
        {t('auth.terms_text', { defaultValue: "By continuing, you agree to St. Joseph's Placements and Training Cell's" })}{' '}
        {TERMS_URL && (
          <Link
            href={TERMS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-black/50 hover:text-black/70 transition-colors"
          >
            {t('auth.terms_of_service', { defaultValue: 'Terms of Service' })}
          </Link>
        )}
        {TERMS_URL && PRIVACY_URL && <>{' '}{t('auth.and', { defaultValue: 'and' })}{' '}</>}
        {PRIVACY_URL && (
          <Link
            href={PRIVACY_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-black/50 hover:text-black/70 transition-colors"
          >
            {t('auth.privacy_policy', { defaultValue: 'Privacy Policy' })}
          </Link>
        )}
        .
      </p>
    </div>
  )
}

export function CopyrightFooter({
  year,
  className = '',
  tone = 'light',
}: {
  year: number
  className?: string
  // `light` → dark text on light bg; `dark` → light text on dark bg.
  tone?: 'light' | 'dark'
}) {
  const { t } = useTranslation()
  const base = tone === 'dark' ? 'text-white/40' : 'text-black/35'
  const link = tone === 'dark' ? 'text-white/60 hover:text-white/80' : 'text-black/55 hover:text-black/75'
  return (
    <footer className={`w-full py-6 px-6 ${className}`}>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-x-5 gap-y-2 text-[13px] font-medium">
        <p className={base}>
          {t('common.copyright', { defaultValue: "© {{year}} St. Joseph's Placements and Training Cell", year })}
        </p>
        {(TERMS_URL || PRIVACY_URL) && (
          <nav className="flex items-center gap-x-5">
            {TERMS_URL && (
              <Link
                href={TERMS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={`${link} transition-colors`}
              >
                {t('auth.terms_of_service', { defaultValue: 'Terms of Service' })}
              </Link>
            )}
            {PRIVACY_URL && (
              <Link
                href={PRIVACY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={`${link} transition-colors`}
              >
                {t('auth.privacy_policy', { defaultValue: 'Privacy Policy' })}
              </Link>
            )}
          </nav>
        )}
      </div>
    </footer>
  )
}
