import { QRCodeSVG } from 'qrcode.react'

export default function ResultPanel({ result, loading }) {
  if (loading) {
    return (
      <section className="card result-card">
        <div className="result-loading">
          <div className="spinner" />
          <p>Running FaceFusion swap (may take 1–3 min on first run)…</p>
          <span className="muted">This may take up to a minute on first run</span>
        </div>
      </section>
    )
  }

  if (!result?.url) return null

  const aspectRatio =
    result.width && result.height ? `${result.width} / ${result.height}` : '3 / 4'

  const handlePrint = () => {
    window.print()
  }

  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = result.url
    link.download = `face-swap-${Date.now()}.png`
    link.target = '_blank'
    link.rel = 'noopener'
    link.click()
  }

  return (
    <section className="card result-card" id="print-area">
      <div className="card-head">
        <h2>Your result</h2>
        <p>Scan the QR code to download on your phone</p>
      </div>

      <div
        className="result-frame"
        style={{ aspectRatio }}
      >
        <img src={result.url} alt="Face swap result" className="result-img" />
      </div>

      <div className="result-actions no-print">
        <button type="button" className="btn btn-secondary" onClick={handleDownload}>
          Download
        </button>
        <button type="button" className="btn btn-primary" onClick={handlePrint}>
          Print
        </button>
      </div>

      <div className="qr-block no-print">
        <QRCodeSVG value={result.url} size={140} level="M" includeMargin />
        <p className="qr-label">Scan to download</p>
      </div>
    </section>
  )
}
