# Backgrid Frontend

Modern modular frontend for the Backgrid trading backtester.

## Architecture

- **Build Tool:** Vite (fast HMR, optimized production builds)
- **JavaScript:** Vanilla ES6+ modules (no framework dependencies)
- **CSS:** Modular CSS with BEM methodology
- **State:** Lightweight custom state manager
- **Design:** Brutalist industrial pop aesthetic

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
npm install
```

### Development

```bash
# Start Vite dev server (http://localhost:5173)
npm run dev

# In another terminal, start FastAPI backend (http://localhost:8000)
cd ..
uvicorn src.api:app --reload
```

The Vite dev server proxies `/api` requests to the FastAPI backend.

### Production Build

```bash
npm run build
```

This creates an optimized build in the `dist/` directory, which FastAPI serves in production.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── index.html              # Main HTML template
├── main.js                 # Application entry point
├── components/             # UI components
├── styles/                 # Modular CSS
├── services/               # API client, storage, utilities
├── state/                  # Application state manager
└── config/                 # Configuration constants
```

## Component Architecture

Each component is a JavaScript class that follows this pattern:

```javascript
export class ComponentName {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(data) {
    this.container.innerHTML = this.template(data);
    this.attachEvents();
  }

  template(data) {
    return `<div class="component">...</div>`;
  }

  attachEvents() {
    // Event listeners
  }
}
```

## CSS Methodology

Uses BEM (Block Element Modifier) naming convention:

```css
.block { }
.block__element { }
.block--modifier { }
```

## Design System

**Colors:**
- Primary accent: Yellow `#FDE047`
- Secondary accent: Cyan `#06B6D4`
- Background: Slate `#E2E8F0`
- Text: Ink black `#020617`

**Typography:**
- Headings: Space Grotesk (bold, uppercase)
- UI text: Inter
- Data/numbers: JetBrains Mono (monospace)

**Effects:**
- Hard shadows: `6px 6px 0px #020617`
- Thick borders: `3px solid #020617`
- No border radius (sharp corners)

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Create production build
- `npm run preview` - Preview production build

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

Modern browsers with ES6 module support.
