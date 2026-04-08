# Design System

## Colors
```css
:root {
  --primary:        #E11D48;
  --primary-light:  #FFF1F2;
  --success:        #16A34A;
  --warning:        #F59E0B;
  --danger:         #DC2626;
  --bg-main:        #F9FAFB;
  --bg-card:        #FFFFFF;
  --border:         #E5E7EB;
  --text-primary:   #111827;
  --text-secondary: #6B7280;
  --text-muted:     #9CA3AF;
}
```

## Typography
```css
:root {
  --font-family:  'Inter', -apple-system, sans-serif;
  --font-cjk:     'Noto Sans TC', sans-serif;
  --text-xs:      0.75rem;
  --text-sm:      0.875rem;
  --text-base:    1rem;
  --text-lg:      1.125rem;
  --text-xl:      1.25rem;
  --text-2xl:     1.5rem;
  --text-3xl:     1.875rem;
}
```

## Layout & Components
```css
:root {
  --radius:       0.75rem;
  --radius-sm:    0.5rem;
  --shadow-card:  0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
  --shadow-hover: 0 4px 6px rgba(0,0,0,0.1);
  --sidebar-width: 260px;
  --gap:          1.5rem;
}
```

## 設計原則
- 使用 CSS Grid / Flexbox 做佈局
- 卡片一致的 padding (`1.5rem`) 和 `border-radius`
- 數字使用 `font-variant-numeric: tabular-nums` 對齊
- 圖表用 inline SVG 或 CSS（conic-gradient、flexbox bar chart 等）
- 支援 1280px+ 寬度
