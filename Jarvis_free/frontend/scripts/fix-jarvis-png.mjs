/**
 * Убирает «шахматку» прозрачности из jarvis.png — делает фон прозрачным (RGBA).
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PNG } from 'pngjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const input = path.join(root, 'jarvis.png')

function isCheckerPixel(r, g, b, a) {
  if (a < 16) return true
  const lum = (r + g + b) / 3
  const spread = Math.max(r, g, b) - Math.min(r, g, b)
  if (lum >= 168 && spread <= 28) return true
  return false
}

const buf = fs.readFileSync(input)
const png = PNG.sync.read(buf)

let cleared = 0
for (let y = 0; y < png.height; y++) {
  for (let x = 0; x < png.width; x++) {
    const i = (png.width * y + x) << 2
    const r = png.data[i]
    const g = png.data[i + 1]
    const b = png.data[i + 2]
    const a = png.data[i + 3]
    if (isCheckerPixel(r, g, b, a)) {
      png.data[i + 3] = 0
      cleared++
    }
  }
}

console.log(`jarvis.png ${png.width}x${png.height}, cleared ${cleared} checker pixels`)
fs.writeFileSync(input, PNG.sync.write(png))
