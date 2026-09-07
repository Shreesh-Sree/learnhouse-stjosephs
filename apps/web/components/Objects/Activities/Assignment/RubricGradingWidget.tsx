'use client'
import React from 'react'
import { useTranslation } from 'react-i18next'

interface Criterion {
  criterion_uuid: string
  title: string
  description?: string
  max_points: number
}

interface RubricGradingWidgetProps {
  rubric: Criterion[]
  initialScores?: Record<string, number> | null
  onChange: (_scores: Record<string, number>, _total: number) => void
}

/**
 * Click-to-score rubric: one row per criterion, a set of point buttons
 * (0..max_points) per row. Reports the full scores map plus the resulting
 * 0-100 total on every change so the caller (AssignmentBoxUI) can drive its
 * existing manual-grade input/submit flow — the server is what actually
 * derives the authoritative grade from `rubric_scores`, this total is only
 * a live preview.
 */
export default function RubricGradingWidget({ rubric, initialScores, onChange }: RubricGradingWidgetProps) {
  const { t } = useTranslation()
  const [scores, setScores] = React.useState<Record<string, number>>(initialScores || {})

  React.useEffect(() => {
    setScores(initialScores || {})
  }, [initialScores])

  const totalPossible = rubric.reduce((acc, c) => acc + (Number(c.max_points) || 0), 0)

  const setScore = (criterionUuid: string, points: number) => {
    const next = { ...scores, [criterionUuid]: points }
    setScores(next)
    const awarded = rubric.reduce((acc, c) => acc + (next[c.criterion_uuid] ?? 0), 0)
    const total = totalPossible > 0 ? Math.round((100 * awarded) / totalPossible) : 0
    onChange(next, total)
  }

  if (!rubric || rubric.length === 0) return null

  return (
    <div className="w-full space-y-2 rounded-lg bg-gray-50 border border-gray-200 p-2.5 mb-2">
      {rubric.map((c) => {
        const maxPoints = Number(c.max_points) || 0
        const points = Array.from({ length: maxPoints + 1 }, (_, i) => i)
        const awarded = scores[c.criterion_uuid]
        return (
          <div key={c.criterion_uuid} className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-gray-700">{c.title}</p>
              <p className="text-[10px] text-gray-400">
                {awarded ?? 0}/{maxPoints}
              </p>
            </div>
            {c.description && <p className="text-[10px] text-gray-400">{c.description}</p>}
            <div className="flex flex-wrap gap-1">
              {points.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setScore(c.criterion_uuid, p)}
                  className={`h-6 min-w-6 px-1.5 rounded-md text-[11px] font-bold transition-colors ${
                    awarded === p
                      ? 'bg-gray-900 text-white'
                      : 'bg-white text-gray-500 border border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )
      })}
      <p className="text-[10px] text-gray-400 pt-1 border-t border-gray-200">
        {t('activities.rubric_widget.hint', {
          defaultValue: 'Click a point value per row — the grade field above fills in automatically.',
        })}
      </p>
    </div>
  )
}
