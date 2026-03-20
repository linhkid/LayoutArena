// Minimal structured logger with redaction and request context helpers
const MAX_STRING_LENGTH = 2048;

const REDACT_KEYS = [
  'authorization',
  'cookie',
  'set-cookie',
  'password',
  'token',
  'access_token',
  'id_token',
  'refresh_token',
  'api_key',
  'secret',
  'x-api-key',
  'x-api-key-id',
  'x-auth-token',
];

const isDev = process.env.NODE_ENV !== 'production';
const LOG_LEVEL = process.env.LOG_LEVEL || (isDev ? 'debug' : 'info');
const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 };

function shouldLog(level) {
  return LEVELS[level] <= LEVELS[LOG_LEVEL];
}

function redactValue(val) {
  if (val == null) return val;
  if (typeof val === 'string') return '***';
  return '***';
}

function safeStringify(obj, depth = 0) {
  try {
    const json = JSON.stringify(obj, (_k, v) => {
      if (typeof v === 'string' && v.length > MAX_STRING_LENGTH) {
        return `${v.slice(0, MAX_STRING_LENGTH)}...<truncated ${v.length - MAX_STRING_LENGTH} chars>`;
      }
      return v;
    });
    return json;
  } catch (_e) {
    return '[Unserializable]';
  }
}

function redactObject(input) {
  if (!input || typeof input !== 'object') return input;
  if (Array.isArray(input)) return input.map(redactObject);
  const out = {};
  for (const [k, v] of Object.entries(input)) {
    if (REDACT_KEYS.includes(k.toLowerCase())) {
      out[k] = redactValue(v);
      continue;
    }
    if (v && typeof v === 'object') out[k] = redactObject(v);
    else out[k] = v;
  }
  return out;
}

function errorDetails(err) {
  if (!err) return {};
  return {
    name: err.name,
    message: err.message,
    stack: typeof err.stack === 'string' ? err.stack.split('\n') : err.stack,
    code: err.code,
    type: err.type,
  };
}

function getRequestContext(req) {
  if (!req) return {};
  const headers = {};
  try {
    for (const [k, v] of Object.entries(req.headers || {})) {
      headers[k] = REDACT_KEYS.includes(k.toLowerCase()) ? redactValue(v) : v;
    }
  } catch {}
  return {
    method: req.method,
    url: (req.headers && req.headers.host ? `http://${req.headers.host}` : '') + (req.url || ''),
    path: req.url,
    query: redactObject(req.query),
    headers,
    ip: req.socket && req.socket.remoteAddress,
    userAgent: req.headers && req.headers['user-agent'],
    requestId: req.headers && (req.headers['x-request-id'] || req.headers['x-correlation-id']),
  };
}

function baseLog(level, scope, data) {
  if (!shouldLog(level)) return;
  const time = new Date().toISOString();
  const payload = { level, time, scope, ...data };
  const line = safeStringify(payload);
  // eslint-disable-next-line no-console
  console[level === 'debug' ? 'log' : level](line);
}

function logError(scope, err, context = {}) {
  baseLog('error', scope, { error: errorDetails(err), context: redactObject(context) });
}

function logWarn(scope, data = {}) {
  baseLog('warn', scope, redactObject(data));
}

function logInfo(scope, data = {}) {
  baseLog('info', scope, redactObject(data));
}

function logDebug(scope, data = {}) {
  baseLog('debug', scope, redactObject(data));
}

module.exports = {
  logger: { error: logError, warn: logWarn, info: logInfo, debug: logDebug },
  getRequestContext,
  errorDetails,
  isDev,
};
