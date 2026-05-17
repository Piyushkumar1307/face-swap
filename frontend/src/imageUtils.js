/** Resize/compress images before upload to keep server RAM usage low. */
export function compressImageFile(file, maxEdge = 1280, quality = 0.85) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      const longest = Math.max(width, height)
      if (longest > maxEdge) {
        const scale = maxEdge / longest
        width = Math.round(width * scale)
        height = Math.round(height * scale)
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      canvas.getContext('2d').drawImage(img, 0, 0, width, height)
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('Could not compress image'))
            return
          }
          const out = new File([blob], file.name || 'photo.jpg', { type: 'image/jpeg' })
          resolve(out)
        },
        'image/jpeg',
        quality
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Could not read image'))
    }
    img.src = url
  })
}
