'use client'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getMyGamificationStats, GamificationBadge, GamificationStats } from '@services/users/gamification'
import { Award, Flame, Footprints, Heart, MessageSquare, Star, Zap } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

const BADGE_ICONS: Record<string, React.ElementType> = {
  footprints: Footprints,
  flame: Flame,
  'message-square': MessageSquare,
  heart: Heart,
  award: Award,
  star: Star,
}

function BadgeTile({ badge }: { badge: GamificationBadge }) {
  const { t } = useTranslation()
  const Icon = BADGE_ICONS[badge.icon] || Award
  return (
    <div
      className={`flex flex-col items-center text-center gap-1.5 p-3 rounded-xl border ${
        badge.earned ? 'bg-white border-gray-100 nice-shadow' : 'bg-gray-50 border-gray-100 opacity-50'
      }`}
      title={badge.description}
    >
      <Icon size={22} className={badge.earned ? 'text-yellow-500' : 'text-gray-300'} />
      <p className={`text-[11px] font-semibold ${badge.earned ? 'text-gray-800' : 'text-gray-400'}`}>
        {t(`account.achievements_page.badge_${badge.id}`, { defaultValue: badge.label })}
      </p>
    </div>
  )
}

/**
 * Self-service points/streak/badges view — see apps/api's
 * services/gamification/gamification.py module docstring for the scope
 * decision (private to the viewing student, never a public leaderboard,
 * computed live from existing durable data rather than a stored ledger).
 */
export default function AccountAchievements({ orgId }: { orgId: number }) {
  const { t } = useTranslation()
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token

  const [stats, setStats] = useState<GamificationStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!orgId) return
    let stale = false
    ;(async () => {
      setLoading(true)
      try {
        const res = await getMyGamificationStats(orgId, access_token)
        if (!stale) setStats(res)
      } catch {
        // empty state on failure
      } finally {
        if (!stale) setLoading(false)
      }
    })()
    return () => {
      stale = true
    }
  }, [orgId, access_token])

  if (loading) {
    return <p className="text-xs text-gray-400">{t('common.loading', { defaultValue: 'Loading…' })}</p>
  }
  if (!stats) {
    return null
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col bg-gray-50 -space-y-1 px-5 py-3 mx-3 my-3 rounded-md">
        <h1 className="font-bold text-xl text-gray-800">
          {t('account.achievements', { defaultValue: 'Achievements' })}
        </h1>
        <h2 className="text-gray-500 text-md">
          {t('account.achievements_subtitle', { defaultValue: 'Your points, streak, and badges in this organization.' })}
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3 px-3">
        <div className="bg-white rounded-xl nice-shadow p-4 flex items-center gap-3">
          <Star size={20} className="text-yellow-500 shrink-0" />
          <div>
            <p className="text-lg font-extrabold text-gray-900 leading-none">{stats.points}</p>
            <p className="text-[11px] text-gray-500 mt-1">{t('account.achievements_page.points', { defaultValue: 'Points' })}</p>
          </div>
        </div>
        <div className="bg-white rounded-xl nice-shadow p-4 flex items-center gap-3">
          <Flame size={20} className="text-orange-500 shrink-0" />
          <div>
            <p className="text-lg font-extrabold text-gray-900 leading-none">
              {stats.current_streak_days}
              <span className="text-xs font-medium text-gray-400 ms-1">
                {t('account.achievements_page.days', { defaultValue: 'days' })}
              </span>
            </p>
            <p className="text-[11px] text-gray-500 mt-1">
              {t('account.achievements_page.streak', { defaultValue: 'Current streak' })}
            </p>
          </div>
        </div>
      </div>

      <div>
        <p className="text-xs font-bold text-gray-700 mb-2">
          {t('account.achievements_page.badges_title', { defaultValue: 'Badges' })}
        </p>
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {stats.badges.map((badge) => (
            <BadgeTile key={badge.id} badge={badge} />
          ))}
        </div>
      </div>

      <p className="text-[11px] text-gray-400 flex items-center gap-1">
        <Zap size={12} />
        {t('account.achievements_page.footer', {
          defaultValue: 'Only you can see this. It has no effect on your grades.',
        })}
      </p>
    </div>
  )
}
