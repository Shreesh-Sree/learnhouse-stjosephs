'use client'
import React from 'react'
import { Camera } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadProctoringSnapshot } from '@services/courses/assignments'

// Fixed, not configurable — this is meant to be an occasional check-in, not
// a continuous recording. A shorter interval would also multiply storage
// for no real proctoring benefit.
const CAPTURE_INTERVAL_MS = 90_000

interface AssignmentProctoringConsentProps {
  assignmentUuid: string
  requireWebcamProctoring?: boolean
  accessToken?: string | null
  children: React.ReactNode
}

type ConsentState = 'undecided' | 'accepted' | 'declined'

/**
 * Gates the assignment behind an explicit, informed consent screen before
 * ANY camera access is requested, then keeps a persistent on-screen
 * indicator for as long as capture is active.
 *
 * Declining is a real, non-coercive option: the assignment renders exactly
 * the same as if proctoring were off. Nothing server-side ever requires a
 * snapshot to exist (see the backend service's own docstring) — this
 * component is the only place that could ever create that expectation, and
 * it deliberately doesn't.
 */
export default function AssignmentProctoringConsent({
  assignmentUuid,
  requireWebcamProctoring,
  accessToken,
  children,
}: AssignmentProctoringConsentProps) {
  const [consent, setConsent] = React.useState<ConsentState>('undecided')
  const [stream, setStream] = React.useState<MediaStream | null>(null)
  const videoRef = React.useRef<HTMLVideoElement | null>(null)
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null)

  const handleAccept = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true })
      setStream(mediaStream)
      setConsent('accepted')
    } catch (_error) {
      toast.error("Couldn't access your camera. Continuing without proctoring.")
      setConsent('declined')
    }
  }

  const handleDecline = () => setConsent('declined')

  // Release the camera the moment it's no longer needed — on unmount, or if
  // consent state ever leaves 'accepted' for any reason.
  React.useEffect(() => {
    if (consent !== 'accepted' || !stream) return
    if (videoRef.current) videoRef.current.srcObject = stream
    return () => {
      stream.getTracks().forEach((track) => track.stop())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consent, stream])

  // Periodic capture while accepted.
  React.useEffect(() => {
    if (consent !== 'accepted' || !stream || !accessToken) return

    const capture = () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.videoWidth === 0) return
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob(
        (blob) => {
          if (blob) void uploadProctoringSnapshot(assignmentUuid, blob, accessToken)
        },
        'image/jpeg',
        0.7
      )
    }

    const intervalId = setInterval(capture, CAPTURE_INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [consent, stream, accessToken, assignmentUuid])

  if (!requireWebcamProctoring || consent === 'declined') {
    return <>{children}</>
  }

  if (consent === 'undecided') {
    return (
      <div className="max-w-lg mx-auto my-16 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-8 text-center">
        <div className="mx-auto w-14 h-14 rounded-full bg-sky-50 flex items-center justify-center mb-4">
          <Camera className="text-sky-500" size={24} />
        </div>
        <h1 className="text-xl font-semibold text-gray-900 mb-2">Webcam proctoring</h1>
        <p className="text-sm text-gray-500 mb-6 leading-relaxed">
          This assignment periodically captures a photo from your webcam while you work,
          visible only to your instructor. A photo is taken roughly every 90 seconds while
          you have the assignment open, and you&apos;ll see a recording indicator the whole time.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 justify-center">
          <button
            type="button"
            onClick={handleDecline}
            className="inline-flex items-center justify-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-semibold hover:bg-gray-200 transition-colors"
          >
            Decline and continue
          </button>
          <button
            type="button"
            onClick={handleAccept}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 transition-colors"
          >
            <Camera size={14} />
            Allow camera access
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="mb-3 flex items-center gap-3 px-3 py-2 rounded-lg bg-rose-50 text-rose-700 text-sm font-semibold">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500" />
        </span>
        Webcam proctoring active
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="ms-auto h-10 w-14 rounded-md object-cover bg-black"
        />
      </div>
      <canvas ref={canvasRef} className="hidden" />
      {children}
    </>
  )
}
