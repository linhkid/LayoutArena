# Implementation Flow Diagram

## How Your New Format is Processed

```
┌─────────────────────────────────────────────────────────────────┐
│                      YOUR INPUT DATA                            │
│  {                                                              │
│    "width": 1920,                                               │
│    "height": 1080,                                              │
│    "elements": [                                                │
│      { "class": "headline", "x": 618, "y": 234, ... },         │
│      { "class": "graphicShape", "x": 565, "y": 200, ... },     │
│      { "class": "image", "x": 564, "y": 488, ... },            │
│      { "class": "logo", "x": 864, "y": 368, ... }              │
│    ]                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           STEP 1: Format Detection (renderTemplate)            │
│                                                                 │
│  if (runtime && Array.isArray(runtime.elements)) {             │
│    console.log('Detected new format...');                      │
│    // Convert to internal format                               │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           STEP 2: Normalization & Mapping                      │
│                                                                 │
│  "elements" → "children"                                        │
│  "class": "headline" → type: "text", elementType: "headline"   │
│  "class": "image" → type: "image", elementType: "image"        │
│  "class": "logo" → elementType: "logo"                         │
│  "class": "graphicShape" → type: "shape", elementType: ...     │
│                                                                 │
│  Auto-generate missing IDs                                     │
│  Set defaults for missing properties                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              STEP 3: Internal Format                           │
│  {                                                              │
│    "width": 1920,                                               │
│    "height": 1080,                                              │
│    "children": [                                                │
│      { "id": "...", "type": "text", "elementType": "headline", │
│        "class": "headline", "x": 618, "y": 234, ... },         │
│      { "id": "...", "type": "shape", "elementType": ...,       │
│        "class": "graphicShape", "x": 565, "y": 200, ... },     │
│      ...                                                        │
│    ]                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           STEP 4: Rendering Loop                               │
│                                                                 │
│  for (const child of children) {                               │
│    const elementClass = child.class || child.elementType || ..│
│                                                                 │
│    if (elementClass === 'headline') {                          │
│      await drawTextElement(ctx, child, box);                   │
│    }                                                            │
│    else if (elementClass === 'image') {                        │
│      await drawImageElement(ctx, child, box);                  │
│    }                                                            │
│    else if (elementClass === 'logo') {                         │
│      await drawLogoElement(ctx, child, box);                   │
│    }                                                            │
│    else if (elementClass === 'graphicShape') {                 │
│      await drawShapeElement(ctx, child, box);                  │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│         STEP 5: Bounding Box Drawing (if enabled)              │
│                                                                 │
│  if (options.showBoundingBoxes) {                              │
│    const meta = getBoundingBoxMeta(child);                     │
│    // meta.key = child.class || child.elementType || ...       │
│                                                                 │
│    drawBoundingBox(ctx, box, meta);                            │
│    // Draws colored box + label                                │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  STEP 6: Output                                │
│  {                                                              │
│    "dataUrl": "data:image/png;base64,iVBORw0KGgo...",          │
│    "boundingBoxes": [                                           │
│      {                                                          │
│        "x": 618, "y": 234, "width": 684, "height": 75,        │
│        "label": "headline",                                     │
│        "color": "rgb(0, 255, 0)",                              │
│        "elementType": "headline"                                │
│      },                                                         │
│      ...                                                        │
│    ],                                                           │
│    "dimensions": { "width": 1920, "height": 1080 }            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Detection Points

### Point A: Format Detection
```javascript
if (runtime && Array.isArray(runtime.elements))
  → NEW FORMAT DETECTED
else if (runtime && Array.isArray(runtime.children))
  → OLD FORMAT (still supported)
```

### Point B: Element Type Resolution
```javascript
const elementClass = child.class || child.elementType || child.type || 'default';

// Checks in order:
// 1. child.class (NEW)
// 2. child.elementType (OLD)
// 3. child.type (OLD)
// 4. 'default' (fallback)
```

### Point C: Bounding Box Color
```javascript
BBOX_COLORS = {
  'headline': [0, 255, 0],      // Green
  'image': [255, 0, 0],          // Red
  'logo': [0, 0, 255],           // Blue
  'graphicShape': [255, 128, 0], // Orange
  'cta': [157, 0, 255],          // Purple
  // ...
}
```

## Rendering Decision Tree

```
Element with class?
│
├─ Yes → Use child.class
│        └─ "headline" → drawTextElement()
│        └─ "image" → drawImageElement()
│        └─ "logo" → drawLogoElement()
│        └─ "graphicShape" → drawShapeElement()
│        └─ "cta" → drawCTAElement()
│
└─ No → Check child.elementType
         └─ Has elementType? → Use child.elementType
         └─ No elementType? → Check child.type
                              └─ Has type? → Use child.type
                              └─ No type? → Use 'default'
```

## Element Class Mapping Table

| Your Input | Internal Type | Internal ElementType | Renderer Function |
|------------|---------------|---------------------|-------------------|
| `class: "headline"` | `"text"` | `"headline"` | `drawTextElement()` |
| `class: "image"` | `"image"` | `"image"` | `drawImageElement()` |
| `class: "logo"` | — | `"logo"` | `drawLogoElement()` |
| `class: "graphicShape"` | `"shape"` | `"graphicShape"` | `drawShapeElement()` |
| `class: "cta"` | — | `"cta"` | `drawCTAElement()` |

## Color Coding System

```
┌─────────────────┬───────────┬──────────────────┐
│ Element Class   │ Color     │ RGB              │
├─────────────────┼───────────┼──────────────────┤
│ headline        │ 🟢 Green  │ (0, 255, 0)      │
│ image           │ 🔴 Red    │ (255, 0, 0)      │
│ logo            │ 🔵 Blue   │ (0, 0, 255)      │
│ graphicShape    │ 🟠 Orange │ (255, 128, 0)    │
│ cta             │ 🟣 Purple │ (157, 0, 255)    │
│ body            │ ⚫ Gray   │ (128, 128, 128)  │
└─────────────────┴───────────┴──────────────────┘
```

## Data Flow Summary

```
INPUT (Your Format)
    ↓
FORMAT DETECTION
    ↓
NORMALIZATION (elements → children, class → type/elementType)
    ↓
INTERNAL FORMAT (unified)
    ↓
RENDERING LOOP (with class-aware logic)
    ↓
BOUNDING BOXES (color-coded by class)
    ↓
OUTPUT (PNG + JSON)
```

## Backward Compatibility Flow

```
NEW FORMAT                  OLD FORMAT
(elements + class)          (children + type/elementType)
       ↓                              ↓
       └──────────┬───────────────────┘
                  ↓
          UNIFIED INTERNAL FORMAT
                  ↓
          SAME RENDERING ENGINE
                  ↓
            SAME OUTPUT
```

---

**Key Insight:** Your new format is converted to the internal format at the very beginning, then follows the exact same rendering path as the old format. This ensures 100% compatibility and consistency! 🎯
