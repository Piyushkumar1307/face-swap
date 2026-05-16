import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export const api = axios.create({ baseURL: API_URL })

export async function fetchTemplates() {
  const { data } = await api.get('/templates')
  return data.templates
}

export async function uploadTemplate(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/templates', form)
  return data
}

export async function deleteTemplate(id) {
  await api.delete(`/templates/${encodeURIComponent(id)}`)
}

export async function swapFace(sourceFile, targetUrl) {
  const form = new FormData()
  form.append('source', sourceFile, sourceFile.name || 'source.jpg')
  form.append('target_url', targetUrl)
  const { data } = await api.post('/swap-face', form, {
    timeout: 600_000,
  })
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/')
  return data
}
