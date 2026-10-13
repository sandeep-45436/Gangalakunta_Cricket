import { useEffect, useRef, useState, useCallback, ChangeEvent } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type Match,
  type RecordingSession,
  type EventMarker,
  type InningsScorecard,
  type Delivery,
  type DeliveryCreate,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Alert } from '../../components/ui/Alert'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(Math.max(0, ms) / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

export function RecordingPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const { token } = useAuth()

  // Match & score state
  const [match, setMatch] = useState<Match | null>(null)
  const [scorecard, setScorecard] = useState<InningsScorecard | null>(null)
  const [deliveries, setDeliveries] = useState<Delivery[]>([])

  // Video Mode: 'camera' (live webcam/phone camera) vs 'file' (uploaded real match video file)
  const [videoMode, setVideoMode] = useState<'camera' | 'file'>('camera')
  const [uploadedVideoUrl, setUploadedVideoUrl] = useState<string | null>(null)
  const [uploadingVideo, setUploadingVideo] = useState<boolean>(false)
  const [uploadSuccess, setUploadSuccess] = useState<string>('')

  // Recording hardware state
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const fileVideoRef = useRef<HTMLVideoElement | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordedChunksRef = useRef<Blob[]>([])

  const [permissionError, setPermissionError] = useState<string>('')
  const [isRecording, setIsRecording] = useState<boolean>(false)
  const [isPaused, setIsPaused] = useState<boolean>(false)
  const [sessions, setSessions] = useState<RecordingSession[]>([])
  const [currentSession, setCurrentSession] = useState<RecordingSession | null>(null)
  const [markers, setMarkers] = useState<EventMarker[]>([])

  // Monotonic elapsed timer
  const [elapsedMs, setElapsedMs] = useState<number>(0)
  const startTimestampRef = useRef<number | null>(null)
  const timerIntervalRef = useRef<number | null>(null)

  // Feedback states
  const [hapticBadge, setHapticBadge] = useState<string | null>(null)
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)

  // Delivery linking / editing modal
  const [linkingMarker, setLinkingMarker] = useState<EventMarker | null>(null)
  const [selectedDeliveryId, setSelectedDeliveryId] = useState<string>('')
  const [editingMarker, setEditingMarker] = useState<EventMarker | null>(null)
  const [editMarkerSec, setEditMarkerSec] = useState<string>('0')

  // Quick delivery scoring form inside recording screen
  const [showScorer, setShowScorer] = useState<boolean>(false)
  const [batterRuns, setBatterRuns] = useState<number>(0)
  const [extraType, setExtraType] = useState<'' | 'wide' | 'no_ball' | 'bye' | 'leg_bye'>('')
  const [isWicket, setIsWicket] = useState<boolean>(false)
  const [submittingDelivery, setSubmittingDelivery] = useState<boolean>(false)

  // ── Load match, scorecard, existing sessions & markers from backend ─────────
  const loadMatchData = useCallback(async () => {
    if (!token || !matchId) return
    try {
      const [m, inns, recSessions] = await Promise.all([
        apiClient.getMatch(token, matchId),
        apiClient.listMatchInnings(token, matchId),
        apiClient.listRecordingSessions(token, matchId),
      ])
      setMatch(m)
      setSessions(recSessions)

      if (inns.length > 0) {
        const cur = inns.find((i) => i.status === 'in_progress') || inns[inns.length - 1]
        const [sc, delivs] = await Promise.all([
          apiClient.getInningsScorecard(token, cur.id),
          apiClient.listDeliveries(token, cur.id),
        ])
        setScorecard(sc)
        setDeliveries(delivs)
      }

      if (recSessions.length > 0) {
        const activeOrLatest = recSessions.find((s) => s.status === 'active') || recSessions[0]
        setCurrentSession(activeOrLatest)
        if (activeOrLatest.media_url) {
          setUploadedVideoUrl(activeOrLatest.media_url)
        }
        const sessionMarkers = await apiClient.listMarkers(token, activeOrLatest.id)
        setMarkers(sessionMarkers)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [token, matchId])

  useEffect(() => {
    void loadMatchData()
  }, [loadMatchData])

  // ── Camera and media stream initialization ──────────────────────────────────
  const startCamera = async () => {
    try {
      setPermissionError('')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: true,
      })
      mediaStreamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unable to access camera'
      setPermissionError(
        `Live camera not detected (${msg}). You can switch to "Upload Match Video File" mode below to upload a real .mp4/.webm match video and mark moments!`
      )
    }
  }

  useEffect(() => {
    if (videoMode === 'camera') {
      void startCamera()
    } else {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      }
    }
    return () => {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
    }
  }, [videoMode])

  // ── Timer management ────────────────────────────────────────────────────────
  const startTimer = (initialElapsed = 0) => {
    stopTimer()
    startTimestampRef.current = performance.now() - initialElapsed
    timerIntervalRef.current = window.setInterval(() => {
      if (startTimestampRef.current !== null) {
        const nowElapsed = Math.floor(performance.now() - startTimestampRef.current)
        setElapsedMs(nowElapsed)
      }
    }, 200)
  }

  const stopTimer = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }
  }

  // Ensure a session exists before uploading video or marking moments
  const ensureSession = async (): Promise<RecordingSession | null> => {
    if (currentSession) return currentSession
    if (!token || !matchId) return null
    const session = await apiClient.createRecordingSession(token, matchId, {
      session_name: `Match Session - ${new Date().toLocaleTimeString()}`,
      media_metadata: {
        userAgent: navigator.userAgent,
        mode: videoMode,
      },
    })
    setCurrentSession(session)
    setSessions((prev) => [session, ...prev])
    return session
  }

  // ── Recording actions (Live Camera Mode) ────────────────────────────────────
  const handleStartRecording = async () => {
    if (!token || !matchId) return
    try {
      setError('')
      setUploadSuccess('')
      const session = await apiClient.createRecordingSession(token, matchId, {
        session_name: `Camera Recording - ${new Date().toLocaleTimeString()}`,
        media_metadata: {
          userAgent: navigator.userAgent,
          platform: navigator.platform,
        },
      })
      setCurrentSession(session)
      setSessions((prev) => [session, ...prev])
      setMarkers([])
      setIsRecording(true)
      setIsPaused(false)

      if (mediaStreamRef.current && typeof MediaRecorder !== 'undefined') {
        try {
          const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
            ? 'video/webm;codecs=vp8,opus'
            : 'video/webm'
          const rec = new MediaRecorder(mediaStreamRef.current, { mimeType })
          recordedChunksRef.current = []
          rec.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) recordedChunksRef.current.push(e.data)
          }
          rec.start(1000)
          mediaRecorderRef.current = rec
        } catch (recErr) {
          console.warn('MediaRecorder error:', recErr)
        }
      }

      startTimer(0)
    } catch (err: unknown) {
      setError(`Failed to start recording session: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  const handlePauseResume = async () => {
    if (!token || !currentSession) return
    try {
      const nextStatus = isPaused ? 'active' : 'paused'
      await apiClient.updateRecordingSession(token, currentSession.id, {
        status: nextStatus,
        total_duration_ms: elapsedMs,
      })

      if (isPaused) {
        startTimer(elapsedMs)
        setIsPaused(false)
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
          mediaRecorderRef.current.resume()
        }
      } else {
        stopTimer()
        setIsPaused(true)
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          mediaRecorderRef.current.pause()
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleStopRecording = async () => {
    if (!token || !currentSession) return
    try {
      stopTimer()
      setIsRecording(false)
      setIsPaused(false)

      // Stop MediaRecorder and wait briefly for final chunk
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        await new Promise<void>((resolve) => {
          if (!mediaRecorderRef.current) {
            resolve()
            return
          }
          mediaRecorderRef.current.onstop = () => resolve()
          mediaRecorderRef.current.stop()
        })
      }

      await apiClient.updateRecordingSession(token, currentSession.id, {
        status: 'completed',
        total_duration_ms: elapsedMs,
      })

      // Automatically upload the recorded camera video blob to InsForge Storage!
      if (recordedChunksRef.current.length > 0) {
        setUploadingVideo(true)
        const videoBlob = new Blob(recordedChunksRef.current, { type: 'video/webm' })
        const updatedSession = await apiClient.uploadSessionVideo(
          token,
          currentSession.id,
          videoBlob,
          `camera_${currentSession.id}.webm`
        )
        setCurrentSession(updatedSession)
        if (updatedSession.media_url) {
          setUploadedVideoUrl(updatedSession.media_url)
        }
        setUploadSuccess('Camera recording uploaded to InsForge Storage! Any linked 4s/6s are now extracting real clips.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setUploadingVideo(false)
    }
  }

  // ── Upload Real Video File from Device ──────────────────────────────────────
  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !token) return
    setUploadingVideo(true)
    setError('')
    setUploadSuccess('')
    try {
      const session = await ensureSession()
      if (!session) throw new Error('Could not create recording session')

      // Show local preview immediately
      const localUrl = URL.createObjectURL(file)
      setUploadedVideoUrl(localUrl)
      setVideoMode('file')

      const updatedSession = await apiClient.uploadSessionVideo(token, session.id, file, file.name)
      setCurrentSession(updatedSession)
      if (updatedSession.media_url) {
        setUploadedVideoUrl(updatedSession.media_url)
      }
      setUploadSuccess(`Uploaded "${file.name}" to InsForge Storage! Play the video below and tap MARK MOMENT on boundaries.`)
    } catch (err: unknown) {
      setError(`Video upload failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setUploadingVideo(false)
    }
  }

  // ── MARK MOMENT (Works in both Camera Mode and Video File Playback Mode) ────
  const handleMarkMoment = async () => {
    if (!token) return
    try {
      const session = await ensureSession()
      if (!session) return

      if ('vibrate' in navigator) {
        navigator.vibrate([40, 30, 40])
      }

      // If in Video File mode and video element is loaded, use exact media currentTime!
      const capturedElapsed =
        videoMode === 'file' && fileVideoRef.current
          ? Math.floor(fileVideoRef.current.currentTime * 1000)
          : elapsedMs

      setElapsedMs(capturedElapsed)
      setHapticBadge(`Captured at ${formatElapsed(capturedElapsed)}`)
      setTimeout(() => setHapticBadge(null), 2500)

      const clientMarkerId = `marker-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
      const created = await apiClient.createMarker(token, session.id, {
        elapsed_ms: capturedElapsed,
        segment_index: 0,
        segment_offset_ms: capturedElapsed,
        client_marker_id: clientMarkerId,
      })
      setMarkers((prev) => [created, ...prev.filter((m) => m.id !== created.id)])
    } catch (err: unknown) {
      setError(`Failed to save marker: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  // ── Link marker to delivery ─────────────────────────────────────────────────
  const handleLinkMarker = async () => {
    if (!token || !linkingMarker || !selectedDeliveryId) return
    try {
      setError('')
      const updated = await apiClient.linkMarker(token, linkingMarker.id, {
        delivery_id: selectedDeliveryId,
      })
      setMarkers((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
      setLinkingMarker(null)
      setSelectedDeliveryId('')
      setUploadSuccess('Marker linked to delivery! If this ball is a 4 or 6, FFmpeg is extracting the highlight clip now.')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleSaveMarkerEdit = async () => {
    if (!token || !editingMarker) return
    try {
      const newMs = Math.max(0, Math.round(parseFloat(editMarkerSec || '0') * 1000))
      const updated = await apiClient.updateMarker(token, editingMarker.id, {
        elapsed_ms: newMs,
        segment_offset_ms: newMs,
      })
      setMarkers((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
      setEditingMarker(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleDeleteMarker = async (markerId: string) => {
    if (!token) return
    try {
      await apiClient.deleteMarker(token, markerId)
      setMarkers((prev) => prev.filter((m) => m.id !== markerId))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  // ── Quick delivery score entry inside recording view ────────────────────────
  const handleQuickSubmitDelivery = async () => {
    if (!token || !scorecard) return
    const strikerId = scorecard.current_striker?.player_id
    const nonStrikerId = scorecard.current_non_striker?.player_id
    const bowlerId = scorecard.current_bowler?.player_id
    if (!strikerId || !nonStrikerId || !bowlerId) {
      setError('Active batters or bowler missing. Open Full Scorer to select bowler/batters.')
      return
    }

    try {
      setSubmittingDelivery(true)
      setError('')
      const payload: DeliveryCreate = {
        striker_id: strikerId,
        non_striker_id: nonStrikerId,
        bowler_id: bowlerId,
        batter_runs: batterRuns,
        extra_type: extraType || null,
        extra_runs: extraType ? 1 : 0,
        is_boundary: batterRuns === 4 || batterRuns === 6,
        boundary_type: batterRuns === 4 ? 4 : batterRuns === 6 ? 6 : null,
        is_batter_boundary: batterRuns === 4 || batterRuns === 6,
        is_wicket: isWicket,
        wicket_type: isWicket ? 'bowled' : null,
        dismissed_player_id: isWicket ? strikerId : null,
        idempotency_key: `rec-quick-${Date.now()}`,
      }

      const newDeliv = await apiClient.recordDelivery(token, scorecard.innings_id, payload)
      const unlinked = markers.find((m) => m.status === 'unlinked')
      if (unlinked && unlinked.id) {
        const linked = await apiClient.linkMarker(token, unlinked.id, {
          delivery_id: newDeliv.id,
        })
        setMarkers((prev) => prev.map((m) => (m.id === linked.id ? linked : m)))
      }

      setBatterRuns(0)
      setExtraType('')
      setIsWicket(false)
      setShowScorer(false)
      await loadMatchData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmittingDelivery(false)
    }
  }

  if (loading) {
    return (
      <AppShell>
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spinner />
        </div>
      </AppShell>
    )
  }

  if (!match) return null

  return (
    <AppShell>
      {/* Header & Back link */}
      <div style={{ marginBottom: 14 }}>
        <Link to={`/matches/${matchId}`} style={{ color: colors.textMuted, textDecoration: 'none', fontSize: 14 }}>
          ← Back to Match Details
        </Link>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 4 }}>
          <h1 style={{ margin: 0, fontSize: 20, color: colors.text }}>
            Video & Event Markers: {match.title}
          </h1>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={() => setVideoMode('camera')}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: `1px solid ${videoMode === 'camera' ? colors.primary : colors.border}`,
                background: videoMode === 'camera' ? colors.primary : '#fff',
                color: videoMode === 'camera' ? '#fff' : colors.text,
                fontWeight: 600,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              📹 Live Camera
            </button>
            <button
              onClick={() => setVideoMode('file')}
              style={{
                padding: '6px 12px',
                borderRadius: 6,
                border: `1px solid ${videoMode === 'file' ? colors.primary : colors.border}`,
                background: videoMode === 'file' ? colors.primary : '#fff',
                color: videoMode === 'file' ? '#fff' : colors.text,
                fontWeight: 600,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              📁 Upload / Match Video File
            </button>
            <Link
              to={`/matches/${matchId}/score`}
              style={{
                fontSize: 13,
                color: colors.primary,
                textDecoration: 'none',
                fontWeight: 700,
                marginLeft: 6,
              }}
            >
              Open Full Scorer ↗
            </Link>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ marginBottom: 14 }}>
          <Alert type="error">{error}</Alert>
        </div>
      )}

      {uploadSuccess && (
        <div style={{ marginBottom: 14 }}>
          <Alert type="success">{uploadSuccess}</Alert>
        </div>
      )}

      {permissionError && videoMode === 'camera' && (
        <div style={{ marginBottom: 14 }}>
          <Alert type="info">{permissionError}</Alert>
        </div>
      )}

      {/* Upload Real Video File Bar */}
      <Card style={{ marginBottom: 16, padding: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: colors.text }}>
              Upload Real Match Video (.mp4, .webm, .mov)
            </div>
            <div style={{ fontSize: 12, color: colors.textMuted }}>
              Upload a real video file to extract actual FFmpeg boundary highlights for linked 4s & 6s.
              {currentSession?.upload_status === 'uploaded' && (
                <span style={{ marginLeft: 8, color: colors.primary, fontWeight: 700 }}>✓ Video Uploaded</span>
              )}
            </div>
          </div>
          <label
            style={{
              background: uploadingVideo ? '#94a3b8' : '#0284c7',
              color: '#fff',
              padding: '8px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 700,
              cursor: uploadingVideo ? 'wait' : 'pointer',
            }}
          >
            {uploadingVideo ? '⏳ Uploading Video...' : '📤 Select & Upload Video File'}
            <input
              type="file"
              accept="video/*"
              onChange={(e) => { void handleFileUpload(e) }}
              disabled={uploadingVideo}
              style={{ display: 'none' }}
            />
          </label>
        </div>
      </Card>

      {/* VIEWFINDER & VIDEO PLAYER CONTAINER */}
      <div style={{ position: 'relative', width: '100%', borderRadius: 12, overflow: 'hidden', background: '#000', marginBottom: 16 }}>
        {videoMode === 'camera' ? (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: '100%',
              height: '360px',
              objectFit: 'cover',
              display: 'block',
              filter: isRecording ? 'none' : 'grayscale(25%)',
            }}
          />
        ) : uploadedVideoUrl ? (
          <video
            ref={fileVideoRef}
            src={uploadedVideoUrl}
            controls
            onTimeUpdate={(e) => setElapsedMs(Math.floor(e.currentTarget.currentTime * 1000))}
            style={{
              width: '100%',
              height: '360px',
              objectFit: 'contain',
              display: 'block',
              background: '#000',
            }}
          />
        ) : (
          <div style={{ height: 320, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', padding: 20, textAlign: 'center' }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>🎬</div>
            <div>Click <strong>"📤 Select & Upload Video File"</strong> above to load your real match video.</div>
          </div>
        )}

        {/* Top Overlay: Status Badge & Monotonic Timer */}
        <div
          style={{
            position: 'absolute',
            top: 14,
            left: 14,
            right: 14,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: isRecording ? 'rgba(239, 68, 68, 0.9)' : 'rgba(15, 23, 42, 0.75)',
              color: '#fff',
              padding: '6px 14px',
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: 0.5,
              backdropFilter: 'blur(4px)',
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: isRecording ? (isPaused ? '#f59e0b' : '#fff') : '#10b981',
                display: 'inline-block',
              }}
            />
            {videoMode === 'file' ? 'VIDEO FILE SYNC' : isRecording ? (isPaused ? 'PAUSED' : 'RECORDING') : 'READY'}
          </div>

          <div
            style={{
              background: 'rgba(0, 0, 0, 0.75)',
              color: '#fff',
              fontFamily: 'monospace',
              fontSize: 22,
              fontWeight: 800,
              padding: '4px 14px',
              borderRadius: 8,
              letterSpacing: 1.5,
              backdropFilter: 'blur(4px)',
            }}
          >
            {formatElapsed(elapsedMs)}
          </div>
        </div>

        {/* Haptic / Capture Confirmation Toast */}
        {hapticBadge && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              background: 'rgba(16, 185, 129, 0.95)',
              color: '#fff',
              padding: '12px 24px',
              borderRadius: 30,
              fontWeight: 800,
              fontSize: 15,
              boxShadow: '0 10px 25px rgba(0,0,0,0.4)',
              pointerEvents: 'none',
            }}
          >
            ✓ {hapticBadge}
          </div>
        )}
      </div>

      {/* HIGH-CONTRAST "MARK MOMENT" & SESSION CONTROLS */}
      <Card style={{ marginBottom: 20 }}>
        <div style={{ display: 'grid', gap: 14 }}>
          <button
            onClick={() => { void handleMarkMoment() }}
            disabled={videoMode === 'camera' && (!isRecording || isPaused)}
            style={{
              width: '100%',
              padding: '18px 0',
              fontSize: 22,
              fontWeight: 900,
              letterSpacing: 1.2,
              borderRadius: 12,
              border: 'none',
              cursor: videoMode === 'file' || (isRecording && !isPaused) ? 'pointer' : 'not-allowed',
              background:
                videoMode === 'file' || (isRecording && !isPaused)
                  ? 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)'
                  : '#cbd5e1',
              color: '#ffffff',
              boxShadow:
                videoMode === 'file' || (isRecording && !isPaused)
                  ? '0 10px 20px -3px rgba(239, 68, 68, 0.4)'
                  : 'none',
            }}
          >
            MARK MOMENT ({formatElapsed(elapsedMs)})
          </button>
          <div style={{ textAlign: 'center', fontSize: 12, color: colors.textMuted, marginTop: -6 }}>
            {videoMode === 'file'
              ? 'Play/scrub the uploaded video above and tap MARK MOMENT at any ball!'
              : 'Start the camera recording session below, then tap MARK MOMENT when a ball is played.'}
          </div>

          <div style={{ display: 'flex', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
            {videoMode === 'camera' && (
              !isRecording ? (
                <Button
                  variant="primary"
                  onClick={() => { void handleStartRecording() }}
                  style={{ flex: 1, padding: 12, fontSize: 15 }}
                >
                  ● Start Camera Recording Session
                </Button>
              ) : (
                <>
                  <Button
                    variant="secondary"
                    onClick={() => { void handlePauseResume() }}
                    style={{ flex: 1, padding: 12 }}
                  >
                    {isPaused ? '▶ Resume' : '⏸ Pause'}
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => { void handleStopRecording() }}
                    style={{ flex: 1, padding: 12 }}
                  >
                    ⏹ Stop & Upload Recording
                  </Button>
                </>
              )
            )}

            <Button
              variant="secondary"
              onClick={() => setShowScorer(!showScorer)}
              style={{ padding: '12px 18px', fontWeight: 600 }}
            >
              {showScorer ? 'Hide Quick Scorer' : '⚡ Quick Scorer'}
            </Button>
          </div>
        </div>

        {/* IN-VIEWPORT QUICK SCORER FORM */}
        {showScorer && (
          <div
            style={{
              marginTop: 18,
              padding: 16,
              background: '#f8fafc',
              borderRadius: 8,
              border: '1px solid #e2e8f0',
            }}
          >
            {!scorecard ? (
              <Alert type="info">
                Innings has not been started yet. <Link to={`/matches/${matchId}/score`} style={{ color: colors.primary, fontWeight: 700 }}>Start Innings in Full Scorer →</Link>
              </Alert>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <h4 style={{ margin: 0, fontSize: 14 }}>Enter Delivery Result (Auto-links to latest unlinked marker)</h4>
                  <span style={{ fontSize: 12, color: colors.textMuted }}>
                    Striker: {scorecard.current_striker?.player_name}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, marginBottom: 12 }}>
                  {[0, 1, 2, 3, 4, 6].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setBatterRuns(num)}
                      style={{
                        padding: '8px 0',
                        fontWeight: 700,
                        borderRadius: 6,
                        border: batterRuns === num ? `2px solid ${colors.primary}` : '1px solid #cbd5e1',
                        background: batterRuns === num ? '#eff6ff' : '#fff',
                        cursor: 'pointer',
                      }}
                    >
                      {num}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setIsWicket(!isWicket)}
                    style={{
                      padding: '8px 0',
                      fontWeight: 700,
                      borderRadius: 6,
                      border: isWicket ? '2px solid #ef4444' : '1px solid #fca5a5',
                      background: isWicket ? '#fef2f2' : '#fff',
                      color: '#dc2626',
                      cursor: 'pointer',
                    }}
                  >
                    W
                  </button>
                </div>

                <div style={{ display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'space-between' }}>
                  <select
                    value={extraType}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    onChange={(e) => setExtraType(e.target.value as any)}
                    style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                  >
                    <option value="">No Extras</option>
                    <option value="wide">Wide (+1)</option>
                    <option value="no_ball">No Ball (+1)</option>
                    <option value="bye">Bye</option>
                    <option value="leg_bye">Leg Bye</option>
                  </select>

                  <Button
                    variant="primary"
                    onClick={() => { void handleQuickSubmitDelivery() }}
                    disabled={submittingDelivery}
                    style={{ padding: '8px 16px', fontSize: 13 }}
                  >
                    {submittingDelivery ? 'Submitting...' : 'Log Delivery & Link Marker'}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </Card>

      {/* CAPTURED MARKERS LIST */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Captured Event Markers ({markers.length})</h3>
          {sessions.length > 1 && (
            <select
              value={currentSession?.id || ''}
              onChange={(e) => {
                const s = sessions.find((item) => item.id === e.target.value)
                if (s && token) {
                  setCurrentSession(s)
                  if (s.media_url) setUploadedVideoUrl(s.media_url)
                  void apiClient.listMarkers(token, s.id).then(setMarkers)
                }
              }}
              style={{ padding: '4px 8px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 12 }}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>{s.session_name} ({s.upload_status})</option>
              ))}
            </select>
          )}
        </div>

        {markers.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: colors.textMuted, fontSize: 14 }}>
            No markers captured yet. Tap <strong>MARK MOMENT</strong> whenever a ball is bowled.
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            {markers.map((m) => (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 10,
                  padding: '12px 16px',
                  borderRadius: 8,
                  border: `1px solid ${m.status === 'linked' ? '#bbf7d0' : '#e2e8f0'}`,
                  background: m.status === 'linked' ? '#f0fdf4' : '#f8fafc',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: 14, color: colors.text }}>
                      {m.marker_label}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontSize: 13, color: colors.textMuted }}>
                      {formatElapsed(m.elapsed_ms)} ({(m.elapsed_ms / 1000).toFixed(1)}s)
                    </span>
                  </div>

                  <div style={{ fontSize: 13, color: m.status === 'linked' ? '#166534' : '#64748b', marginTop: 3 }}>
                    {m.delivery_display ? `Linked: Over ${m.delivery_display}` : 'Unlinked — click "Link Ball" to connect to a delivery'}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: 10,
                      background: m.status === 'linked' ? '#dcfce7' : '#f1f5f9',
                      color: m.status === 'linked' ? '#15803d' : '#475569',
                      textTransform: 'uppercase',
                    }}
                  >
                    {m.status}
                  </span>

                  <button
                    onClick={() => {
                      setLinkingMarker(m)
                      setSelectedDeliveryId(m.delivery_id || '')
                    }}
                    style={{
                      padding: '4px 10px',
                      background: colors.primary,
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {m.status === 'linked' ? 'Relink Ball' : 'Link Ball'}
                  </button>

                  <button
                    onClick={() => {
                      setEditingMarker(m)
                      setEditMarkerSec((m.elapsed_ms / 1000).toFixed(1))
                    }}
                    style={{
                      padding: '4px 8px',
                      background: '#e2e8f0',
                      color: colors.text,
                      border: 'none',
                      borderRadius: 6,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    Edit Time
                  </button>

                  <button
                    onClick={() => { void handleDeleteMarker(m.id) }}
                    style={{
                      padding: '4px 8px',
                      background: '#fee2e2',
                      color: '#dc2626',
                      border: 'none',
                      borderRadius: 6,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* LINK MARKER MODAL */}
      {linkingMarker && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: 24,
              maxWidth: 420,
              width: '90%',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)',
            }}
          >
            <h3 style={{ margin: '0 0 10px' }}>Link {linkingMarker.marker_label} to Delivery</h3>
            <p style={{ fontSize: 13, color: colors.textMuted, margin: '0 0 16px' }}>
              Video Timestamp: <strong>{formatElapsed(linkingMarker.elapsed_ms)}</strong>. Select the scorecard delivery played at this moment:
            </p>

            {deliveries.filter((d) => !d.is_voided).length === 0 ? (
              <Alert type="info">
                No deliveries scored yet. Score a ball using Quick Scorer or Full Scorer first!
              </Alert>
            ) : (
              <select
                value={selectedDeliveryId}
                onChange={(e) => setSelectedDeliveryId(e.target.value)}
                style={{ width: '100%', padding: '10px', borderRadius: 6, border: '1px solid #cbd5e1', marginBottom: 20 }}
              >
                <option value="">Select a saved delivery...</option>
                {deliveries
                  .filter((d) => !d.is_voided)
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      Over {d.display_over} — {d.total_runs} runs
                      {d.is_batter_boundary ? ` (BOUNDARY ${d.boundary_type} ✨)` : ''}
                      {d.is_wicket ? ' (WICKET)' : ''}
                    </option>
                  ))}
              </select>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 12 }}>
              <Button variant="secondary" onClick={() => setLinkingMarker(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={() => { void handleLinkMarker() }} disabled={!selectedDeliveryId}>
                Confirm Link
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT MARKER TIMESTAMP MODAL */}
      {editingMarker && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, maxWidth: 380, width: '90%' }}>
            <h3 style={{ margin: '0 0 12px' }}>Adjust Timestamp — {editingMarker.marker_label}</h3>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
              Video Offset (in seconds):
            </label>
            <input
              type="number"
              step="0.5"
              min="0"
              value={editMarkerSec}
              onChange={(e) => setEditMarkerSec(e.target.value)}
              style={{ width: '100%', padding: 10, borderRadius: 6, border: '1px solid #cbd5e1', marginBottom: 16, boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setEditingMarker(null)}>Cancel</Button>
              <Button variant="primary" onClick={() => { void handleSaveMarkerEdit() }}>Save Timestamp</Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  )
}
