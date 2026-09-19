import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    // El comensal abre esto de pie en la puerta, con datos moviles y wifi malo.
    // 160 kB no es un numero redondo: es React (~140 kB) mas nuestro codigo. O
    // sea que el suelo lo pone la libreria, no nosotros. Si este aviso salta es
    // que alguien metio una dependencia, y queremos enterarnos en el build y no
    // por un comensal que se cansa de esperar la pantalla.
    chunkSizeWarningLimit: 160,
  },
})
