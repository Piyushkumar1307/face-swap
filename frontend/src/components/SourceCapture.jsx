import { useEffect, useRef, useState } from 'react'

export default function SourceCapture({ sourcePreview, onSourceReady, onClear }) {
  const [mode, setMode] = useState('file')
  const [cameraOn, setCameraOn] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setCameraOn(false)
  }

  useEffect(() => () => stopCamera(), [])

  const startCamera = async () => {
    stopCamera()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraOn(true)
    } catch {
      alert('Camera access denied or unavailable')
    }
  }

  useEffect(() => {
    if (mode === 'camera' && !sourcePreview) {
      startCamera()
    } else if (mode === 'file') {
      stopCamera()
    }
  }, [mode, sourcePreview])

  const capturePhoto = () => {
    const video = videoRef.current
    if (!video) return

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)

    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
        onSourceReady(file, canvas.toDataURL('image/jpeg', 0.92))
        stopCamera()
      },
      'image/jpeg',
      0.92
    )
  }

  const handleFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    onSourceReady(file, URL.createObjectURL(file))
    e.target.value = ''
  }

  return (
    <section className="card source-card">
      <div className="card-head">
        <h2>Your face</h2>
        <p>
          Use a front-facing photo with similar beard style to the template. For
          hat templates, skip wearing a hat in your selfie.
        </p>
      </div>

      <div className="mode-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className={mode === 'camera' ? 'tab active' : 'tab'}
          onClick={() => setMode('camera')}
        >
          Camera
        </button>
        <button
          type="button"
          role="tab"
          className={mode === 'file' ? 'tab active' : 'tab'}
          onClick={() => setMode('file')}
        >
          Upload file
        </button>
      </div>

      {mode === 'camera' && !sourcePreview && (
        <div className="camera-wrap">
          <video ref={videoRef} className="camera-video" playsInline muted />
          <button
            type="button"
            className="btn btn-primary capture-btn"
            onClick={capturePhoto}
            disabled={!cameraOn}
          >
            Capture photo
          </button>
        </div>
      )}

      {mode === 'file' && !sourcePreview && (
        <label className="upload-zone">
          <input type="file" accept="image/*" onChange={handleFile} hidden />
          <span className="upload-icon">+</span>
          <span>Choose image from device</span>
        </label>
      )}

      {sourcePreview && (
        <div className="preview-wrap">
          <img src={sourcePreview} alt="Your face" className="preview-img portrait" />
          <button type="button" className="btn btn-ghost" onClick={onClear}>
            Change photo
          </button>
        </div>
      )}
    </section>
  )
}
