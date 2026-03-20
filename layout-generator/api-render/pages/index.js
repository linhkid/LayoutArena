import { useState, useMemo, useRef, useEffect, useCallback } from 'react';

const ErrorPopup = ({ error, onClose }) => {
  if (!error) return null;
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{
        background: 'white', padding: '24px', borderRadius: '8px',
        maxWidth: '800px', width: '90%', maxHeight: '90vh',
        overflowY: 'auto', boxShadow: '0 4px 15px rgba(0,0,0,0.2)'
      }}>
        <h2 style={{ marginTop: 0, color: '#d32f2f' }}>Rendering Error</h2>
        <p>The server could not render the provided JSON. Please check the details below for clues.</p>

        <h3 style={{ borderBottom: '1px solid #eee', paddingBottom: '8px' }}>Error Message</h3>
        <pre style={{
          background: '#f5f5f5', padding: '12px', borderRadius: '4px',
          whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'monospace',
          maxHeight: '150px', overflowY: 'auto'
        }}>
          {error.message || 'No specific message.'}
        </pre>

        {error.details && error.details.length > 0 && (
          <>
            <h3 style={{ borderBottom: '1px solid #eee', paddingBottom: '8px', marginTop: '24px' }}>Technical Details (from browser console)</h3>
            <ul style={{
              background: '#f5f5f5', padding: '16px', borderRadius: '4px', listStyle: 'none',
              fontFamily: 'monospace', fontSize: '14px', maxHeight: '200px', overflowY: 'auto', margin: 0
            }}>
              {error.details.map((detail, i) => (
                <li key={i} style={{ borderBottom: '1px dotted #ccc', padding: '8px 0', wordBreak: 'break-all' }}>{detail}</li>
              ))}
            </ul>
          </>
        )}

        <h3 style={{ marginTop: '24px' }}>Common Causes</h3>
        <ul style={{ paddingLeft: '20px', margin: 0 }}>
          <li>Invalid JSON syntax (e.g., missing comma, extra bracket).</li>
          <li>A required property like `width`, `height`, or `children` is missing.</li>
          <li>An image or font URL (`src`, `s3FilePath`) is incorrect or not accessible (CORS error).</li>
          <li>A property value has the wrong data type (e.g., `width: &quot;1080&quot;` instead of `width: 1080`).</li>
        </ul>

        <button onClick={onClose} style={{ marginTop: '24px', background: '#111', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 14px', cursor: 'pointer' }}>Close</button>
      </div>
    </div>
  );
};

const PreviewImage = ({ item, index, onMouseMove, onMouseLeave }) => {
  const imgRef = useRef(null);

  return (
    <div
      className="preview-item"
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
    >
  {/* eslint-disable-next-line @next/next/no-img-element */}
  <img ref={imgRef} src={item.dataUrl} alt={`Preview ${index + 1}`} />
      <a
        href={item.dataUrl}
        download={`preview_${index + 1}${item.includesBoundingBoxes ? '_bbox' : ''}.png`}
      >
        Download PNG
      </a>
    </div>
  );
};

export default function Home() {
  const [jsonText, setJsonText] = useState('');
  const [previewItems, setPreviewItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isCombining, setIsCombining] = useState(false);
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, text: '' });
  const [renderError, setRenderError] = useState(null);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(false);

  const previewDataUrls = useMemo(
    () => previewItems.map((item) => item.dataUrl).filter(Boolean),
    [previewItems]
  );

  const normalizeBoundingBox = useCallback((bbox) => {
    if (!bbox) return null;
    const x = Number(bbox.x);
    const y = Number(bbox.y);
    const width = Number(bbox.width);
    const height = Number(bbox.height);
    if (!Number.isFinite(x) || !Number.isFinite(y) || width <= 0 || height <= 0) {
      return null;
    }
    return {
      x,
      y,
      width,
      height,
      label: typeof bbox.label === 'string' && bbox.label.trim() ? bbox.label : 'element',
      color: typeof bbox.color === 'string' ? bbox.color : '#ff5252',
      rotation: Number(bbox.rotation) || 0,
      elementId: bbox.elementId || null,
      elementType: bbox.elementType || null,
      type: bbox.type || null,
    };
  }, []);

  const normalizeSingleRender = useCallback((item) => {
    if (!item || typeof item.dataUrl !== 'string') return null;
    const boundingBoxes = Array.isArray(item.boundingBoxes)
      ? item.boundingBoxes.map(normalizeBoundingBox).filter(Boolean)
      : [];
    const dimensions = item.dimensions && Number.isFinite(Number(item.dimensions?.width)) && Number.isFinite(Number(item.dimensions?.height))
      ? { width: Number(item.dimensions.width), height: Number(item.dimensions.height) }
      : null;

    return {
      dataUrl: item.dataUrl,
      boundingBoxes,
      dimensions,
      includesBoundingBoxes: Boolean(item.includesBoundingBoxes),
    };
  }, [normalizeBoundingBox]);

  const normalizeRenderPayload = useCallback((payload) => {
    if (!payload) return [];

    if (Array.isArray(payload.renders) && payload.renders.length > 0) {
      return payload.renders.map(normalizeSingleRender).filter(Boolean);
    }

    if (payload.render) {
      const single = normalizeSingleRender(payload.render);
      return single ? [single] : [];
    }

    if (payload.dataUrl) {
      const single = normalizeSingleRender({
        dataUrl: payload.dataUrl,
        boundingBoxes: payload.boundingBoxes,
        dimensions: payload.dimensions,
        includesBoundingBoxes: payload.includesBoundingBoxes,
      });
      return single ? [single] : [];
    }

    if (Array.isArray(payload.dataUrls) && payload.dataUrls.length > 0) {
      const boundingBoxesList = Array.isArray(payload.boundingBoxesList) ? payload.boundingBoxesList : [];
      const dimensionsList = Array.isArray(payload.dimensionsList) ? payload.dimensionsList : [];
      return payload.dataUrls
        .map((dataUrl, index) => normalizeSingleRender({
          dataUrl,
          boundingBoxes: boundingBoxesList[index] || [],
          dimensions: dimensionsList[index] || payload.dimensions,
          includesBoundingBoxes: Array.isArray(payload.includesBoundingBoxesList)
            ? payload.includesBoundingBoxesList[index]
            : payload.includesBoundingBoxes,
        }))
        .filter(Boolean);
    }

    return [];
  }, [normalizeSingleRender]);

  const handleFile = async (file) => {
    const text = await file.text();
    setJsonText(text);
  };

  const onSelectFile = (e) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const preview = useCallback(async (options = {}) => {
    const { forceShowBoundingBoxes, preserveExisting } = options;
    const shouldShowBoundingBoxes = typeof forceShowBoundingBoxes === 'boolean'
      ? forceShowBoundingBoxes
      : showBoundingBoxes;

    try {
      setLoading(true);
      setRenderError(null);
      setIsCombining(false);
      if (!preserveExisting) {
        setPreviewItems([]);
      }

      const params = new URLSearchParams();
      if (shouldShowBoundingBoxes) {
        params.set('showBoundingBoxes', 'true');
      }
      const endpoint = `/api/render/preview${params.toString() ? `?${params.toString()}` : ''}`;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: jsonText || '{}',
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.message || result.error || 'Preview failed', { cause: result });
      }

      const items = normalizeRenderPayload(result);
      setPreviewItems(items);
    } catch (e) {
      setRenderError({
        message: e.message,
        details: e.cause?.details || [],
      });
    } finally {
      setLoading(false);
    }
  }, [jsonText, normalizeRenderPayload, showBoundingBoxes]);

  /**
   * Combines multiple image data URLs into a single image on a canvas.
   * @param {string[]} dataUrls - Array of base64 data URLs.
   * @param {number} [padding=20] - Padding between images.
   * @returns {Promise<string|null>} Data URL of the combined image.
   */
  const combineImages = async (dataUrls, padding = 20) => {
    const images = await Promise.all(
      dataUrls.map(url => new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Failed to load an image for combining.'));
        img.src = url;
      }))
    );

    if (images.length === 0) return null;

    const totalWidth = images.reduce((sum, img) => sum + img.width, 0) + padding * (images.length - 1);
    const maxHeight = Math.max(...images.map(img => img.height));

    const canvas = document.createElement('canvas');
    canvas.width = totalWidth > 0 ? totalWidth : 1;
    canvas.height = maxHeight > 0 ? maxHeight : 1;
    const ctx = canvas.getContext('2d');

    // Fill background with white
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    let currentX = 0;
    images.forEach(img => {
      // Vertically center each image
      const yOffset = (maxHeight - img.height) / 2;
      ctx.drawImage(img, currentX, yOffset);
      currentX += img.width + padding;
    });

    return canvas.toDataURL('image/png');
  };

  /**
   * Handles the click event for the batch download button.
   */
  const handleBatchDownload = async () => {
    if (previewDataUrls.length < 2) return;
    setLoading(true);
    setIsCombining(true);
    try {
      const combinedDataUrl = await combineImages(previewDataUrls);
      if (!combinedDataUrl) throw new Error("Image combining failed.");

      const a = document.createElement('a');
      a.href = combinedDataUrl;
      a.download = 'combined_render.png';
      document.body.appendChild(a); // Required for Firefox
      a.click();
      document.body.removeChild(a);
    } catch (e) {
      setRenderError({ message: e.message, details: [] });
    } finally {
      setLoading(false);
      setIsCombining(false);
    }
  };

  const onUploadBatch = async (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const files = form.elements.namedItem('files').files;
    if (!files?.length) return alert('Pick at least one JSON file');

    const fd = new FormData();
    for (const f of files) fd.append('files', f);

    setLoading(true);
    try {
      const res = await fetch('/api/render/batch', { method: 'POST', body: fd });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ message: 'Batch render failed with non-JSON response.' }));
        throw new Error(errorData.message || 'Batch render failed.', { cause: errorData });
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'renders.zip';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setRenderError({ message: e.message, details: e.cause?.details || [] });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handles keydown events on the textarea to trigger preview.
   * @param {React.KeyboardEvent<HTMLTextAreaElement>} e - The keyboard event.
   */
  const handleKeyDown = (e) => {
    // Check for Alt+Enter or Cmd+Enter
    if (e.key === 'Enter' && (e.metaKey || e.altKey)) {
      e.preventDefault(); // Prevent adding a new line
      if (!loading) {
        preview();
      }
    }
  };

  const handleMouseMove = (e) => {
    const imgElement = e.currentTarget.querySelector('img');
    if (!imgElement) return;

    const rect = imgElement.getBoundingClientRect();
    const displayX = e.clientX - rect.left;
    const displayY = e.clientY - rect.top;

    if (displayX < 0 || displayY < 0 || displayX > rect.width || displayY > rect.height) {
      handleMouseLeave();
      return;
    }

    const scaleX = imgElement.naturalWidth / imgElement.clientWidth;
    const scaleY = imgElement.naturalHeight / imgElement.clientHeight;

    const imageX = Math.round(displayX * scaleX);
    const imageY = Math.round(displayY * scaleY);

    setTooltip({
      visible: true,
      x: e.clientX + 15,
      y: e.clientY + 10,
      text: `x: ${imageX}, y: ${imageY}`
    });
  };

  const handleMouseLeave = () => {
    setTooltip(t => ({ ...t, visible: false }));
  };

  return (
    <div className="container">
      <ErrorPopup error={renderError} onClose={() => setRenderError(null)} />
      {tooltip.visible && (
        <div
          className="tooltip"
          style={{
            position: 'fixed',
            left: `${tooltip.x}px`,
            top: `${tooltip.y}px`,
          }}
        >
          {tooltip.text}
        </div>
      )}

      <h1>JSON → PNG Renderer</h1>
      
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <a href="/api-docs" style={{ display: 'inline-block', background: '#0070f3', color: '#fff', padding: '10px 20px', borderRadius: '8px', textDecoration: 'none', fontWeight: '500' }}>
          📖 View API Documentation
        </a>
      </div>

      <section>
        <h2>1) Load a JSON and preview</h2>
        <p className="footnote">
          You can paste a single JSON object or an array of objects. Press <strong>Alt+Enter</strong> (<strong>Cmd+Enter</strong> on Mac) to preview.
        </p>
        <input type="file" accept="application/json" onChange={onSelectFile} />
        <textarea
          placeholder="Paste JSON here"
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={10}
          spellCheck={false}
        />
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button onClick={preview} disabled={loading}>
            {loading && !isCombining ? 'Rendering…' : 'Preview PNG'}
          </button>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={showBoundingBoxes}
              onChange={(e) => {
                const nextValue = e.target.checked;
                setShowBoundingBoxes(nextValue);
                if (previewItems.length > 0 && !loading) {
                  preview({ forceShowBoundingBoxes: nextValue, preserveExisting: true });
                }
              }}
            />
            Show Bounding Boxes
          </label>
          {previewDataUrls.length > 1 && (
            <button onClick={handleBatchDownload} disabled={loading}>
              {loading && isCombining ? 'Combining…' : 'Batch Download'}
            </button>
          )}
        </div>
        {previewItems.length > 0 && (
          <div className="preview">
            {previewItems.map((item, index) => (
              <PreviewImage
                key={item.dataUrl ? `${item.dataUrl.slice(0, 32)}-${index}` : index}
                item={item}
                index={index}
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2>2) Batch render (ZIP)</h2>
        <form onSubmit={onUploadBatch}>
          <input name="files" type="file" accept="application/json" multiple />
          <button type="submit" disabled={loading}>
            {loading ? 'Rendering…' : 'Upload and Render'}
          </button>
        </form>
      </section>

      <p className="footnote">Rendering uses a headless Chromium and your embedded canvas template.</p>
    </div>
  );
}
