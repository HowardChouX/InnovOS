# InnovOS Frontend

React 19 + TypeScript + Vite 8 + Tailwind CSS v4 + Zustand 5

## Dev

```bash
npm run dev        # Vite dev server → localhost:5173
npm run build      # Production build
npm test           # Run tests
npx tsc --noEmit   # Type check
```

## Structure

```
src/
  features/     # Feature-based pages (knowledge, admin, dashboard, workflow, auth, etc.)
  components/   # Shared UI components (layout, common, rich-editor, etc.)
  store/        # Zustand 5 stores
  api/          # API client functions (auto JWT injection)
  types/        # TypeScript type definitions
  routes/       # React Router v7 routing (lazy-loaded pages)
  hooks/        # Custom hooks
  utils/        # Utility functions (constants, cn, formatters)
  lib/          # Library configurations
  assets/       # Static assets
```
