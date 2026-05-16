const MAX_TEMPLATES = 6

export default function TemplateSidebar({
  templates,
  selectedId,
  onSelect,
  onUpload,
  onRemove,
  loading,
}) {
  const slots = Array.from({ length: MAX_TEMPLATES }, (_, i) => templates[i] || null)

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h2>Templates</h2>
        <p>
          {templates.length}/{MAX_TEMPLATES} saved on Cloudinary
        </p>
      </div>

      <div className="template-grid">
        {slots.map((template, index) => (
          <div key={template?.id || `empty-${index}`} className="template-slot">
            {template ? (
              <>
                <button
                  type="button"
                  className={`template-btn ${selectedId === template.id ? 'selected' : ''}`}
                  onClick={() => onSelect(template)}
                  disabled={loading}
                >
                  <img src={template.url} alt={`Template ${index + 1}`} />
                  {selectedId === template.id && <span className="selected-badge">Selected</span>}
                </button>
                <button
                  type="button"
                  className="remove-btn"
                  onClick={() => onRemove(template.id)}
                  disabled={loading}
                  aria-label="Remove template"
                >
                  ×
                </button>
              </>
            ) : (
              <label className="template-add">
                <input
                  type="file"
                  accept="image/*"
                  hidden
                  disabled={loading || templates.length >= MAX_TEMPLATES}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) onUpload(file)
                    e.target.value = ''
                  }}
                />
                <span className="add-icon">+</span>
                <span>Add template</span>
              </label>
            )}
          </div>
        ))}
      </div>

      <p className="sidebar-note">
        Templates stay saved until you remove them — even after closing the app.
      </p>
    </aside>
  )
}
