# CloudPOS Design System

> Single source of truth visual para CloudPOS. Usar esta skill cada vez que se cree o modifique la app web para mantener consistencia con la app desktop (CustomTkinter).

---

## 1. Overview

CloudPOS usa un tema **"Dark Pro"** basado en elevación por luminancia con accent glow. La web debe reflejar exactamente la misma estética, con toggle dark/light.

**Principios:**
- Fondo oscuro profundo (`#0a0a0a`) con superficies elevadas por luminancia
- Acento azul (`#2563eb`) para acciones primarias
- Verde para ingresos/ventas, Rojo para gastos/errores, Naranja para alertas
- Bordes sutiles (`#2a2a2a`) en lugar de sombras
- Border-radius consistente: `6px` (inputs/botones), `8px` (badges), `12px` (cards/paneles)

---

## 2. Color Tokens

### Modo Oscuro (default)

| Token | Hex | Uso |
|-------|-----|-----|
| `--base` | `#0a0a0a` | Fondo principal de la app |
| `--surface-0` | `#111111` | Fondo de gráficos |
| `--surface-1` | `#171717` | Inputs, formularios internos |
| `--surface-2` | `#1e1e1e` | Cards, paneles principales |
| `--surface-3` | `#252525` | Botones secundarios, filas hover |
| `--surface-4` | `#2e2e2e` | Hover de surface-3 |
| `--border` | `#2a2a2a` | Bordes de cards/paneles |
| `--border-active` | `#3a3a3a` | Bordes de inputs focus |
| `--text-primary` | `#f0f0f0` | Texto principal |
| `--text-secondary` | `#888888` | Texto secundario, labels |
| `--text-muted` | `#737373` | Texto deshabilitado, hints |
| `--text-disabled` | `#525252` | Texto desactivado |

### Colores Semánticos

| Token | Hex | Hover | Dim | Text | Uso |
|-------|-----|-------|-----|------|-----|
| `--accent` | `#2563eb` | `#1d4ed8` | `#1a2744` | `#60a5fa` | Primario, links, botones |
| `--green` | `#16a34a` | `#15803d` | `#052e16` | `#4ade80` | Ventas, ingresos, éxito |
| `--orange` | `#d97706` | — | `#2d1b00` | `#fbbf24` | Alertas, descuentos |
| `--red` | `#dc2626` | `#b91c1c` | `#2d0a0a` | `#f87171` | Errores, gastos, eliminar |
| `--purple` | `#7e22ce` | — | `#2d1a4a` | `#a78bfa` | Promociones especiales |

### Modo Claro

| Token | Hex | Uso |
|-------|-----|-----|
| `--base` | `#f8f9fa` | Fondo principal |
| `--surface-0` | `#ffffff` | Fondo de gráficos |
| `--surface-1` | `#f1f3f5` | Inputs, formularios internos |
| `--surface-2` | `#e9ecef` | Cards, paneles principales |
| `--surface-3` | `#dee2e6` | Botones secundarios |
| `--surface-4` | `#ced4da` | Hover de surface-3 |
| `--border` | `#dee2e6` | Bordes de cards/paneles |
| `--border-active` | `#adb5bd` | Bordes de inputs focus |
| `--text-primary` | `#212529` | Texto principal |
| `--text-secondary` | `#6c757d` | Texto secundario |
| `--text-muted` | `#868e96` | Texto deshabilitado |

**Nota:** Los colores semánticos (accent, green, orange, red, purple) se mantienen iguales en modo claro.

---

## 3. Typography

**Familia:** `Arial, system-ui, -apple-system, sans-serif`

| Token | Font | Uso |
|-------|------|-----|
| `--font-label` | `Arial 10px` | Labels de formulario, badges |
| `--font-label-bold` | `Arial 10px bold` | Labels en negrita |
| `--font-small` | `Arial 11px` | Texto pequeño, hints |
| `--font-body` | `Arial 12px` | Texto de cuerpo, tablas |
| `--font-body-bold` | `Arial 12px bold` | Texto de cuerpo en negrita |
| `--font-subheading` | `Arial 14px` | Subtítulos |
| `--font-heading` | `Arial 14px bold` | Títulos de sección |
| `--font-title` | `Arial 18px bold` | Títulos de página |
| `--font-nav` | `Arial 13px` | Navegación |
| `--font-nav-bold` | `Arial 13px bold` | Navegación en negrita |
| `--font-stat` | `Arial 32px bold` | Números grandes (KPIs) |
| `--font-stat-lg` | `Arial 40px bold` | Números muy grandes |
| `--font-display` | `Arial 44px bold` | Display hero |
| `--font-mono` | `Consolas 11px` | Códigos, números |

---

## 4. Component Tokens

### Cards / Paneles
```
background: var(--surface-2)     /* #1e1e1e dark */
border-radius: 12px
border: 1px solid var(--border)  /* #2a2a2a */
padding: 16px
```

**Accent Bar (lado izquierdo):**
```
width: 4px
background: var(--accent)        /* o green/red/orange según contexto */
border-radius: 0
```

### Buttons

| Variante | Background | Hover | Text | Border |
|----------|-----------|-------|------|--------|
| Primary | `--accent` | `--accent-hover` | `--text-primary` | none |
| Primary Dim | `--accent-dim` | `--accent` | `--accent-text` | `1px solid --accent` |
| Danger | `--red` | `--red-hover` | `--text-primary` | none |
| Danger Dim | `--red-dim` | `--red` | `--red-text` | `1px solid --red` |
| Success Dim | `--green-dim` | `--green` | `--green-text` | `1px solid --green` |
| Ghost | `--surface-3` | `--surface-4` | `--text-secondary` | `1px solid --border` |

**Propiedades comunes:**
```
height: 42px (acciones), 36px (secundarias), 32px (pequeñas)
border-radius: 6px (8px para quick actions)
font: var(--font-body-bold)
cursor: pointer
```

### Inputs / Forms
```
background: var(--surface-1)       /* #171717 */
border: 1px solid var(--border)    /* #2a2a2a */
border-radius: 6px
height: 38px (normal), 40-45px (grandes)
text-color: var(--text-primary)
placeholder-color: var(--text-muted)
font: var(--font-body)
```

**Focus state:**
```
border-color: var(--border-active) /* #3a3a3a */
```

### Tables (Treeview)
```
background: var(--surface-2)
row-height: 32px
header-bg: var(--surface-3)
header-text: var(--text-secondary)
header-font: var(--font-label-bold)
selected-bg: var(--accent-dim)
selected-text: var(--accent-text)
border: none
```

### Modals / Popups
```
background: var(--surface-2)
border-radius: 12px
border: 1px solid var(--border)
padding: 24px
max-width: 420px (popups), 600px (dialogs grandes)
```

### Scrollbars
```
track: var(--surface-2)
thumb: var(--surface-3)
thumb-hover: var(--surface-4)
width: 8px
border-radius: 4px
```

---

## 5. Layout Patterns

### Bento Grid (Dashboard)
```
Grid de 2 columnas: 2fr / 1fr
Header: row 0, colspan 2
Quick Actions: row 1, colspan 2
Stat Cards: row 2, colspan 2 (3 cards iguales)
Chart: row 3-4, col 0
Side panels: row 3, col 1 / row 4, col 1
```

### Quick Action Tiles
```
4 tiles en fila
height: 82px
border-radius: 12px
border: 1px solid accent-color
background: dim-color
Icono + Label + Shortcut
cursor: pointer
```

### Stat Cards
```
3 cards en fila (flex: 1 cada una)
background: var(--surface-2)
border-radius: 12px
border: 1px solid var(--border)
Accent bar izquierda (4px)
Label superior (muted, uppercase)
Valor grande (accent color, 32px bold)
Subtexto (muted, 10px)
```

### Two-Panel Form
```
Izquierda: formulario (weight 1)
  - Scrollable
  - Secciones con header + divider
  - Footer con botones
Derecha: tabla/lista (weight 2)
  - Search bar
  - Treeview/Table
  - Action buttons abajo
```

---

## 6. Spacing & Radius

### Spacing Scale
| Token | Value | Uso |
|-------|-------|-----|
| `--pad-xs` | `4px` | Espaciado mínimo, entre badges |
| `--pad-sm` | `8px` | Entre elementos relacionados |
| `--pad-md` | `16px` | Padding de cards, entre secciones |
| `--pad-lg` | `24px` | Padding de página, márgenes externos |
| `--pad-xl` | `32px` | Espaciado hero |

### Border Radius
| Token | Value | Uso |
|-------|-------|-----|
| `--radius-sm` | `4px` | Badges pequeños |
| `--radius-md` | `6px` | Inputs, botones |
| `--radius-lg` | `8px` | Quick actions, modales pequeños |
| `--radius-xl` | `12px` | Cards, paneles, modales |

---

## 7. Bootstrap Mapeo

### Cómo traducir CustomTkinter → Bootstrap 5

| CustomTkinter | Bootstrap 5 + CSS Variables |
|---------------|---------------------------|
| `ctk.CTkFrame(fg_color=SURFACE2, corner_radius=12, border_width=1, border_color=BORDER)` | `<div class="card">` con CSS custom properties |
| `ctk.CTkButton(fg_color=ACCENT, text_color=TEXT_PRIMARY, height=42, corner_radius=6)` | `<button class="btn btn-primary">` con override de colores |
| `ctk.CTkEntry(fg_color=SURFACE1, border_color=BORDER, height=38)` | `<input class="form-control">` con override |
| `ctk.CTkLabel(text_color=TEXT_MUTED, font=FONT_LABEL_BOLD)` | `<span class="text-muted fw-bold">` con font-size custom |
| `ctk.CTkScrollableFrame` | `<div class="overflow-auto">` con scrollbar custom |
| `ctk.CTkComboBox` | `<select class="form-select">` con override |
| `ctk.CTkCheckBox` | `<input type="checkbox" class="form-check-input">` con override |
| `ctk.CTkImage` | `<img>` con CSS filter para dark mode |

### Clases Bootstrap a Override

```css
/* Override Bootstrap para dark mode */
[data-bs-theme="dark"] {
  --bs-body-bg: var(--base);
  --bs-body-color: var(--text-primary);
  --bs-card-bg: var(--surface-2);
  --bs-card-border-color: var(--border);
  --bs-input-bg: var(--surface-1);
  --bs-input-border-color: var(--border);
  --bs-input-color: var(--text-primary);
  --bs-btn-primary-bg: var(--accent);
  --bs-btn-primary-border-color: var(--accent);
  --bs-table-bg: var(--surface-2);
  --bs-table-color: var(--text-primary);
}
```

---

## 8. Toggle Dark/Light

### Implementación en React

```jsx
// Usar data-bs-theme en el <html> o contenedor principal
const [theme, setTheme] = useState('dark');

useEffect(() => {
  document.documentElement.setAttribute('data-bs-theme', theme);
}, [theme]);

// Toggle button
<button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
  {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
</button>
```

### CSS Variables por tema

```css
:root {
  /* Dark mode (default) */
  --base: #0a0a0a;
  --surface-0: #111111;
  --surface-1: #171717;
  --surface-2: #1e1e1e;
  --surface-3: #252525;
  --surface-4: #2e2e2e;
  --border: #2a2a2a;
  --border-active: #3a3a3a;
  --text-primary: #f0f0f0;
  --text-secondary: #888888;
  --text-muted: #737373;
}

[data-bs-theme="light"] {
  --base: #f8f9fa;
  --surface-0: #ffffff;
  --surface-1: #f1f3f5;
  --surface-2: #e9ecef;
  --surface-3: #dee2e6;
  --surface-4: #ced4da;
  --border: #dee2e6;
  --border-active: #adb5bd;
  --text-primary: #212529;
  --text-secondary: #6c757d;
  --text-muted: #868e96;
}

/* Semánticos (iguales en ambos modos) */
:root {
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-dim: #1a2744;
  --accent-text: #60a5fa;
  --green: #16a34a;
  --green-text: #4ade80;
  --green-dim: #052e16;
  --orange: #d97706;
  --orange-text: #fbbf24;
  --orange-dim: #2d1b00;
  --red: #dc2626;
  --red-hover: #b91c1c;
  --red-text: #f87171;
  --red-dim: #2d0a0a;
}
```

---

## 9. Reglas de Uso

1. **NUNCA** usar colores hardcodeados. Siempre usar las variables CSS.
2. **NUNCA** usar sombras (`box-shadow`). Usar bordes sutiles como en el desktop.
3. **SIEMPRE** respetar la jerarquía tipográfica definida.
4. **SIEMPRE** usar el spacing scale (`--pad-xs` a `--pad-xl`).
5. **SIEMPRE** usar border-radius consistente (`6px`, `8px`, `12px`).
6. **Mantener** el modo oscuro como default (es la identidad de CloudPOS).
7. **La app web es SOLO LECTURA.** No permitir edición de datos desde la web.
