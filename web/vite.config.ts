import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Dùng chung 1 file .env ở thư mục gốc dự án (cùng với backend) thay vì web/.env riêng.
  envDir: '..',
})
