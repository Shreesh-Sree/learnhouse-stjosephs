'use client'
import React from 'react'
import { RefreshCw, Users } from 'lucide-react'
import { useLHSession } from '@components/Contexts/LHSessionContext'
import { getScormResults, type ScormResultRow } from '@services/courses/scorm'

const STATUS_STYLES: Record<string, string> = {
  passed: 'bg-emerald-50 text-emerald-700',
  completed: 'bg-emerald-50 text-emerald-700',
  failed: 'bg-rose-50 text-rose-700',
  incomplete: 'bg-amber-50 text-amber-700',
  browsed: 'bg-gray-100 text-gray-600',
  not_attempted: 'bg-gray-100 text-gray-500',
}

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m`
  return '<1m'
}

interface ScormResultsTableProps {
  activityUuid: string
}

function ScormResultsTable({ activityUuid }: ScormResultsTableProps) {
  const session = useLHSession() as any
  const access_token = session?.data?.tokens?.access_token

  const [rows, setRows] = React.useState<ScormResultRow[] | null>(null)
  const [error, setError] = React.useState(false)

  const load = React.useCallback(async () => {
    if (!access_token) return
    setError(false)
    const res = await getScormResults(activityUuid, access_token)
    if (res?.success === false) {
      setError(true)
      return
    }
    setRows(res?.data ?? [])
  }, [activityUuid, access_token])

  React.useEffect(() => {
    load()
  }, [load])

  if (error) {
    return <p className="text-xs text-gray-400 py-4 text-center">Couldn't load results.</p>
  }

  if (rows === null) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw size={16} className="animate-spin text-gray-400" />
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center text-gray-400">
        <Users size={20} />
        <p className="text-xs">No learner has started this activity yet.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-gray-400 border-b border-gray-100">
            <th className="font-medium py-1.5 pe-2">Learner</th>
            <th className="font-medium py-1.5 px-2">Status</th>
            <th className="font-medium py-1.5 px-2">Score</th>
            <th className="font-medium py-1.5 ps-2">Time</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.user_id} className="border-b border-gray-50 last:border-0">
              <td className="py-1.5 pe-2 font-medium text-gray-700">
                {row.first_name && row.last_name ? `${row.first_name} ${row.last_name}` : `@${row.username}`}
              </td>
              <td className="py-1.5 px-2">
                <span
                  className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${
                    STATUS_STYLES[row.lesson_status] ?? STATUS_STYLES.not_attempted
                  }`}
                >
                  {row.lesson_status.replace('_', ' ')}
                </span>
              </td>
              <td className="py-1.5 px-2 text-gray-600">
                {row.score_raw != null ? `${row.score_raw}${row.score_max ? ` / ${row.score_max}` : ''}` : '—'}
              </td>
              <td className="py-1.5 ps-2 text-gray-600">{formatDuration(row.total_time_seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default ScormResultsTable
