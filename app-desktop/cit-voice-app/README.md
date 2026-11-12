# Giao diện CIT Voice Studio

React 19 + Vite + Tailwind 4 + shadcn/ui. Bản build (`dist/`) được máy chủ Python
(`apps/web_stream.py`) phục vụ ở `/`, và cửa sổ PyWebView của app mở chính trang đó.

Khởi tạo từ template [create-tauri-react](https://github.com/MrLightful/create-tauri-react)
(xem `LICENSE`); phần Tauri đã bỏ vì bản phát hành dùng PyWebView.

```bash
npm ci
npm run dev        # Vite ở cổng 1420; cần máy chủ chạy sẵn ở 8001 (run_stream.bat)
npm run build      # tsc + vite build -> dist/
npm run check      # Biome (ultracite); `npm run fix` để tự sửa
npm run typecheck
npm test           # node:test, không cần trình duyệt
```

Địa chỉ máy chủ khi chạy `npm run dev` lấy từ `VITE_API_URL` (xem `.env.example`),
mặc định `http://127.0.0.1:8001`.
