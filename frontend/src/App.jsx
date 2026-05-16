import { useCallback, useEffect, useState } from 'react'
import {
  checkHealth,
  deleteTemplate,
  fetchTemplates,
  swapFace,
  uploadTemplate,
} from './api'
import SourceCapture from './components/SourceCapture'
import TemplateSidebar from './components/TemplateSidebar'
import ResultPanel from './components/ResultPanel'
import './App.css'

function App() {
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [sourceFile, setSourceFile] = useState(null)
  const [sourcePreview, setSourcePreview] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [templatesLoading, setTemplatesLoading] = useState(true)
  const [cloudinaryOk, setCloudinaryOk] = useState(true)
  const [error, setError] = useState(null)

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true)
    setError(null)
    try {
      const list = await fetchTemplates()
      setTemplates(list)
      setSelectedTemplate((prev) => {
        if (prev && list.some((t) => t.id === prev.id)) return prev
        return list[0] || null
      })
    } catch (err) {
      const msg = err.response?.data?.detail || err.message
      setError(String(msg))
      if (err.response?.status === 503) setCloudinaryOk(false)
    } finally {
      setTemplatesLoading(false)
    }
  }, [])

  useEffect(() => {
    checkHealth()
      .then((d) => setCloudinaryOk(d.cloudinary !== false))
      .catch(() => {})
    loadTemplates()
  }, [loadTemplates])

  const handleSourceReady = (file, preview) => {
    setSourceFile(file)
    setSourcePreview(preview)
    setResult(null)
  }

  const handleSourceClear = () => {
    setSourceFile(null)
    setSourcePreview(null)
  }

  const handleUploadTemplate = async (file) => {
    setLoading(true)
    setError(null)
    try {
      const template = await uploadTemplate(file)
      await loadTemplates()
      setSelectedTemplate(template)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to upload template')
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveTemplate = async (id) => {
    if (!confirm('Remove this template from Cloudinary?')) return
    setLoading(true)
    setError(null)
    try {
      await deleteTemplate(id)
      await loadTemplates()
      setSelectedTemplate((prev) => (prev?.id === id ? null : prev))
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove template')
    } finally {
      setLoading(false)
    }
  }

  const handleSwap = async () => {
    if (!sourceFile || !selectedTemplate) {
      alert('Add your face and select a template')
      return
    }

    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const data = await swapFace(sourceFile, selectedTemplate.url)
      setResult(data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Face swap failed')
    } finally {
      setLoading(false)
    }
  }

  const canSwap = Boolean(sourceFile && selectedTemplate && !loading)

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          <div>
            <h1>Face Swap Studio</h1>
            <p>Capture · Choose template · Share your look</p>
          </div>
        </div>
        {!cloudinaryOk && (
          <p className="banner-warn">
            Cloudinary not configured — add credentials to backend/.env and restart
          </p>
        )}
      </header>

      <div className="app-layout">
        <TemplateSidebar
          templates={templates}
          selectedId={selectedTemplate?.id}
          onSelect={setSelectedTemplate}
          onUpload={handleUploadTemplate}
          onRemove={handleRemoveTemplate}
          loading={loading || templatesLoading}
        />

        <main className="main-panel">
          {error && <div className="alert">{error}</div>}

          <div className="workspace">
            <div className="workspace-left">
              <SourceCapture
                sourcePreview={sourcePreview}
                onSourceReady={handleSourceReady}
                onClear={handleSourceClear}
              />

              {selectedTemplate && (
                <section className="card template-preview-card">
                  <div className="card-head">
                    <h2>Selected template</h2>
                  </div>
                  <div
                    className="template-preview-frame"
                    style={{
                      aspectRatio:
                        selectedTemplate.width && selectedTemplate.height
                          ? `${selectedTemplate.width} / ${selectedTemplate.height}`
                          : '3 / 4',
                    }}
                  >
                    <img
                      src={selectedTemplate.url}
                      alt="Selected template"
                      className="preview-img"
                    />
                  </div>
                </section>
              )}

              <button
                type="button"
                className="btn btn-primary btn-lg swap-btn"
                onClick={handleSwap}
                disabled={!canSwap}
              >
                {loading ? 'Processing…' : 'Swap face onto template'}
              </button>
            </div>

            <ResultPanel result={result} loading={loading && !result} />
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
