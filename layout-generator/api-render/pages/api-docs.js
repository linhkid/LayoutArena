import { useRouter } from 'next/router';

export default function ApiDocs() {
  const router = useRouter();

  return (
    <div style={{ 
      maxWidth: '900px', 
      margin: '0 auto', 
      padding: '32px 16px',
      fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
      lineHeight: '1.6',
      color: '#111'
    }}>
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>📖 Render API Reference</h1>
        <button 
          onClick={() => router.push('/')}
          style={{
            background: '#111',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 20px',
            cursor: 'pointer',
            fontWeight: '500'
          }}
        >
          ← Back to Renderer
        </button>
      </div>

      <div style={{ 
        background: '#f5f5f5', 
        padding: '16px', 
        borderRadius: '8px',
        marginBottom: '24px',
        borderLeft: '4px solid #0070f3'
      }}>
        <p style={{ margin: 0 }}>
          This document describes the JSON → PNG rendering API exposed by the Next.js app.
        </p>
        <p style={{ margin: '8px 0 0', fontSize: '0.9rem', color: '#666' }}>
          <strong>Base URL (dev):</strong> http://localhost:3000
        </p>
      </div>

      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ 
          borderBottom: '2px solid #eee', 
          paddingBottom: '8px',
          marginTop: '32px'
        }}>Endpoints</h2>

        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '24px',
          marginBottom: '24px'
        }}>
          <h3 style={{ marginTop: 0, color: '#0070f3' }}>
            <code style={{ 
              background: '#111', 
              color: '#fff', 
              padding: '4px 8px', 
              borderRadius: '4px',
              fontSize: '0.9rem',
              fontWeight: 'bold'
            }}>POST</code> /api/render/preview
          </h3>
          <p>Render a single JSON payload and return a base64 PNG data URL.</p>

          <h4>Request</h4>
          <ul>
            <li><strong>Content-Type:</strong> application/json</li>
            <li><strong>Body:</strong> A JSON object representing the template. If your object does not contain a top-level <code>data</code> property, it will be wrapped as <code>{'{ data: <yourObject> }'}</code> automatically.</li>
          </ul>

          <h4>Query Parameters</h4>
          <ul>
            <li><code>showBoundingBoxes=true</code> - Include bounding boxes in the rendered image (server-side)</li>
            <li><code>downloadBoundingBoxes=true</code> - Download image with bounding boxes as PNG file</li>
            <li><code>format=png</code> - Return PNG binary instead of JSON (sets Content-Type: image/png)</li>
            <li><code>download=true</code> - Force download with Content-Disposition header</li>
          </ul>

          <h4>Minimal Example Payload</h4>
          <pre style={{ 
            background: '#1e1e1e', 
            color: '#d4d4d4', 
            padding: '16px', 
            borderRadius: '8px',
            overflow: 'auto',
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: '0.85rem'
          }}>{`{
  "data": {
    "width": 1080,
    "height": 1080,
    "background": "#ffffff",
    "children": []
  }
}`}</pre>

          <h4>Response</h4>
          <pre style={{ 
            background: '#1e1e1e', 
            color: '#d4d4d4', 
            padding: '16px', 
            borderRadius: '8px',
            overflow: 'auto',
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: '0.85rem'
          }}>{`{
  "dataUrl": "data:image/png;base64,...",
  "boundingBoxes": [],
  "dimensions": { "width": 1080, "height": 1080 },
  "includesBoundingBoxes": false
}`}</pre>

          <h4>Example (curl → file)</h4>
          <pre style={{ 
            background: '#1e1e1e', 
            color: '#d4d4d4', 
            padding: '16px', 
            borderRadius: '8px',
            overflow: 'auto',
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: '0.85rem'
          }}>{`curl -sS -X POST \\
  -H 'Content-Type: application/json' \\
  -d '{"data":{"width":1080,"height":1080,"background":"#fff","children":[]}}' \\
  http://localhost:3000/api/render/preview \\
| jq -r .dataUrl \\
| sed 's#^data:image/png;base64,##' \\
| base64 --decode > preview.png`}</pre>

          <h4>Example (download with bounding boxes)</h4>
          <pre style={{ 
            background: '#1e1e1e', 
            color: '#d4d4d4', 
            padding: '16px', 
            borderRadius: '8px',
            overflow: 'auto',
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: '0.85rem'
          }}>{`curl -X POST \\
  -H 'Content-Type: application/json' \\
  -d @your-template.json \\
  'http://localhost:3000/api/render/preview?downloadBoundingBoxes=true' \\
  -o render_with_bbox.png`}</pre>

          <div style={{ 
            background: '#fff3cd', 
            border: '1px solid #ffc107', 
            padding: '12px', 
            borderRadius: '6px',
            marginTop: '16px'
          }}>
            <strong>📝 Notes/limits:</strong>
            <ul style={{ marginBottom: 0, paddingLeft: '20px' }}>
              <li>Max body size: ~5MB</li>
              <li>Renders at the canvas native size (1080×1080 unless your JSON sets otherwise)</li>
              <li>Bounding boxes are rendered server-side when requested</li>
            </ul>
          </div>
        </div>

        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '24px',
          marginBottom: '24px'
        }}>
          <h3 style={{ marginTop: 0, color: '#0070f3' }}>
            <code style={{ 
              background: '#111', 
              color: '#fff', 
              padding: '4px 8px', 
              borderRadius: '4px',
              fontSize: '0.9rem',
              fontWeight: 'bold'
            }}>POST</code> /api/render/batch
          </h3>
          <p>Upload multiple JSON files and receive a ZIP of PNG renders.</p>

          <h4>Request</h4>
          <ul>
            <li><strong>Content-Type:</strong> multipart/form-data</li>
            <li><strong>Form field:</strong> <code>files</code> (repeatable). Each item must be a <code>.json</code> file containing an object as described above.</li>
          </ul>

          <h4>Response</h4>
          <ul>
            <li><strong>Content-Type:</strong> application/zip</li>
            <li><strong>Filename:</strong> renders.zip</li>
            <li><strong>Contents:</strong> PNG files named after each JSON filename (replacing <code>.json</code> with <code>.png</code>)</li>
          </ul>

          <h4>Example</h4>
          <pre style={{ 
            background: '#1e1e1e', 
            color: '#d4d4d4', 
            padding: '16px', 
            borderRadius: '8px',
            overflow: 'auto',
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: '0.85rem'
          }}>{`curl -sS -X POST \\
  -F 'files=@/path/layout1.json' \\
  -F 'files=@/path/layout2.json' \\
  http://localhost:3000/api/render/batch \\
  -o renders.zip`}</pre>

          <div style={{ 
            background: '#fff3cd', 
            border: '1px solid #ffc107', 
            padding: '12px', 
            borderRadius: '6px',
            marginTop: '16px'
          }}>
            <strong>📝 Notes/limits:</strong>
            <ul style={{ marginBottom: 0, paddingLeft: '20px' }}>
              <li>Max file size per JSON: ~10MB</li>
              <li>Total request size depends on your server limits</li>
            </ul>
          </div>
        </div>
      </section>

      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ 
          borderBottom: '2px solid #eee', 
          paddingBottom: '8px'
        }}>Template Structure</h2>

        <p>The renderer expects an object with the following structure:</p>

        <pre style={{ 
          background: '#1e1e1e', 
          color: '#d4d4d4', 
          padding: '16px', 
          borderRadius: '8px',
          overflow: 'auto',
          fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
          fontSize: '0.85rem'
        }}>{`{
  "data": {
    "width": 1080,
    "height": 1080,
    "background": "#ffffff",
    "children": [
      // elements in back-to-front order (or use 'index' for z-order)
    ]
  }
}`}</pre>

        <h3>Common Child Element Fields</h3>
        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '16px'
        }}>
          <ul style={{ paddingLeft: '20px' }}>
            <li><strong>Visibility/z-index:</strong> <code>visible: true</code>, <code>index: 0</code></li>
            <li><strong>Geometry:</strong> <code>x</code>, <code>y</code>, <code>width</code>, <code>height</code></li>
            <li><strong>Transform:</strong> <code>rotation</code>, <code>flipHorizontal</code>, <code>flipVertical</code>, <code>opacity</code></li>
            <li><strong>Corners:</strong> <code>cornerRadiusTopLeft</code>, <code>cornerRadiusTopRight</code>, <code>cornerRadiusBottomRight</code>, <code>cornerRadiusBottomLeft</code></li>
            <li><strong>Fills/strokes:</strong> <code>fill</code>, <code>stroke</code>, <code>strokeWidth</code>, <code>dash</code></li>
            <li><strong>Crop (images):</strong> <code>cropX</code>, <code>cropY</code>, <code>cropWidth</code>, <code>cropHeight</code> (0..1 fractional or absolute px)</li>
            <li><strong>Text:</strong> <code>text</code>, <code>richTextArr</code>, <code>textFill</code>, <code>fontFamily</code>, <code>fontStyle</code>, <code>fontSize</code>, <code>lineHeight</code>, <code>align</code>, <code>verticalAlign</code>, <code>textTransform</code>, <code>s3FilePath</code> (font URL)</li>
            <li><strong>Image/logo:</strong> <code>src</code>, optional <code>overlayFill</code> + <code>alpha</code></li>
            <li><strong>CTA:</strong> <code>elementType: &apos;cta&apos;</code>, uses background fill + auto-fit text</li>
            <li><strong>Line:</strong> <code>elementType: &apos;line&apos;</code>, <code>points: [x0,y0,x1,y1,...]</code></li>
          </ul>
        </div>

        <h3>Element Types</h3>
        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '16px'
        }}>
          <ul style={{ paddingLeft: '20px' }}>
            <li><strong>Images:</strong> <code>type: &apos;image&apos;</code> | <code>&apos;svg&apos;</code></li>
            <li><strong>Text:</strong> <code>type: &apos;text&apos;</code> or <code>elementType: &apos;headline&apos;</code></li>
            <li><strong>Shapes/lines:</strong> <code>type: &apos;shape&apos;</code> or <code>elementType: &apos;graphicShape&apos;</code> | <code>&apos;line&apos;</code></li>
            <li><strong>Logo:</strong> <code>elementType: &apos;logo&apos;</code> (special padding handling)</li>
            <li><strong>CTA:</strong> <code>elementType: &apos;cta&apos;</code></li>
          </ul>
        </div>

        <div style={{ 
          background: '#d1ecf1', 
          border: '1px solid #0c5460', 
          padding: '12px', 
          borderRadius: '6px',
          marginTop: '16px'
        }}>
          <strong>💡 Tip:</strong> Remote assets (images/fonts) must be publicly reachable with CORS enabled.
        </div>
      </section>

      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ 
          borderBottom: '2px solid #eee', 
          paddingBottom: '8px'
        }}>Errors</h2>

        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '16px'
        }}>
          <ul style={{ paddingLeft: '20px' }}>
            <li><code>400</code> - Invalid JSON or missing files</li>
            <li><code>405</code> - Method not allowed (use POST)</li>
            <li><code>500</code> - General rendering error (see server logs)</li>
          </ul>
        </div>
      </section>

      <section style={{ marginBottom: '48px' }}>
        <h2 style={{ 
          borderBottom: '2px solid #eee', 
          paddingBottom: '8px'
        }}>Implementation Details</h2>

        <div style={{ 
          background: '#fafafa', 
          border: '1px solid #eee', 
          borderRadius: '8px', 
          padding: '16px'
        }}>
          <p>
            Rendering is done by navigating a headless browser to <code>public/renderer.html</code>, 
            injecting your JSON, and reading <code>canvas.toDataURL()</code>.
          </p>
          <p style={{ marginBottom: 0 }}>
            The renderer attempts to load custom fonts via <code>FontFace</code>; if unavailable, 
            it falls back to system fonts.
          </p>
        </div>
      </section>

      <div style={{ 
        textAlign: 'center', 
        paddingTop: '32px', 
        borderTop: '1px solid #eee',
        color: '#666',
        fontSize: '0.9rem'
      }}>
        <button 
          onClick={() => router.push('/')}
          style={{
            background: '#111',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '12px 24px',
            cursor: 'pointer',
            fontWeight: '500',
            fontSize: '1rem'
          }}
        >
          ← Back to Renderer
        </button>
      </div>
    </div>
  );
}
