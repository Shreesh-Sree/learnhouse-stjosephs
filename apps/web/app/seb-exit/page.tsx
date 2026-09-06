import { ShieldCheck } from 'lucide-react'

// Static exit page for the Safe Exam Browser quit flow (see
// apps/api/src/services/courses/activities/seb.py for the full design).
// Every assignment's .seb file sets this exact URL as its `quitURL`; SEB
// watches for the browser loading it and shows its own "Exit Safe Exam
// Browser" button once it does — nothing on this page needs to trigger
// that itself, it's purely the human-readable confirmation shown while
// SEB's own UI takes over.
//
// No i18n here, matching not-found.tsx and other top-level pages outside
// the [orgslug] tree: this route sits above any org context, so it keeps
// to plain English rather than depending on locale machinery that expects
// an org-scoped provider tree.
export default function SebExitPage() {
  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-white px-6 text-center">
      <div className="mx-auto w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center mb-4">
        <ShieldCheck className="text-emerald-600" size={24} />
      </div>
      <h1 className="text-xl font-semibold text-gray-900 mb-2">
        Submission received
      </h1>
      <p className="max-w-md text-sm text-gray-500 leading-relaxed">
        Your assignment has been submitted. You can now exit Safe Exam
        Browser using its own exit button. Once it closes, reopen your
        regular browser to see your dashboard.
      </p>
    </div>
  )
}
