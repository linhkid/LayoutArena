const { launch } = require('puppeteer');
const { logger } = require('./logger');

class BrowserPool {
  constructor(options = {}) {
    this.maxInstances = options.maxInstances || 3;
    this.idleTimeout = options.idleTimeout || 60000; // 1 minute
    this.waitTimeout = options.waitTimeout || 120000; // 2 minutes max wait for browser
    this.maxRenders = options.maxRenders || 100; // Recycle browser after N renders to prevent GPU memory bloat
    this.maxAge = options.maxAge || 300000; // Recycle browser after 5 minutes max age
    this.pool = [];
    this.browserOptions = options.browserOptions || {
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--font-render-hinting=medium'],
    };
  }

  async getBrowser() {
    // Try to find an idle browser
    for (let i = 0; i < this.pool.length; i++) {
      const item = this.pool[i];
      if (!item.inUse) {
        // Check if browser is still connected
        if (item.browser.connected) {
          item.inUse = true;
          item.renderCount++;
          clearTimeout(item.idleTimer);
          item.idleTimer = null;
          logger.debug('browserPool.reuse', { poolSize: this.pool.length, renderCount: item.renderCount });
          return item.browser;
        } else {
          // Browser disconnected, remove it
          this.pool.splice(i, 1);
          i--;
        }
      }
    }

    // No idle browser available, create a new one if under limit
    if (this.pool.length < this.maxInstances) {
      logger.info('browserPool.create', { currentSize: this.pool.length, max: this.maxInstances });
      const browser = await launch({
        ...this.browserOptions,
        timeout: 60000,
      });

      const item = {
        browser,
        inUse: true,
        idleTimer: null,
        renderCount: 1, // First use
        createdAt: Date.now(),
      };

      this.pool.push(item);
      return browser;
    }

    // Pool is full, wait for one to become available
    logger.warn('browserPool.waiting', { poolSize: this.pool.length });
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const checkInterval = setInterval(() => {
        // Check for timeout
        if (Date.now() - startTime > this.waitTimeout) {
          clearInterval(checkInterval);
          const error = new Error('Browser pool timeout: no browser available within timeout period');
          logger.error('browserPool.timeout', error, {
            poolSize: this.pool.length,
            inUse: this.pool.filter(i => i.inUse).length,
            waitTimeout: this.waitTimeout
          });
          reject(error);
          return;
        }

        // Directly check pool for available browser instead of recursive call
        for (let i = 0; i < this.pool.length; i++) {
          const item = this.pool[i];
          if (!item.inUse && item.browser.connected) {
            // Found an available browser
            item.inUse = true;
            item.renderCount++;
            clearTimeout(item.idleTimer);
            item.idleTimer = null;
            clearInterval(checkInterval);
            logger.debug('browserPool.reuse.afterWait', { poolSize: this.pool.length, renderCount: item.renderCount });
            resolve(item.browser);
            return;
          }
        }
      }, 100);
    });
  }

  releaseBrowser(browser) {
    const item = this.pool.find((i) => i.browser === browser);
    if (item) {
      const age = Date.now() - item.createdAt;
      const shouldRecycle = item.renderCount >= this.maxRenders || age >= this.maxAge;

      if (shouldRecycle) {
        // Browser exceeded limits, close it instead of returning to pool
        logger.info('browserPool.recycle', {
          reason: item.renderCount >= this.maxRenders ? 'maxRenders' : 'maxAge',
          renderCount: item.renderCount,
          age: Math.round(age / 1000) + 's',
          poolSize: this.pool.length
        });
        this.closeBrowser(browser);
        return;
      }

      item.inUse = false;

      // Set idle timeout to close the browser if not used
      item.idleTimer = setTimeout(() => {
        this.closeBrowser(browser);
      }, this.idleTimeout);

      logger.debug('browserPool.release', { poolSize: this.pool.length, renderCount: item.renderCount });
    }
  }

  async closeBrowser(browser) {
    const index = this.pool.findIndex((i) => i.browser === browser);
    if (index !== -1) {
      const item = this.pool[index];
      clearTimeout(item.idleTimer);
      this.pool.splice(index, 1);

      try {
        if (browser.connected) {
          await browser.close();
        }
        logger.info('browserPool.close', { poolSize: this.pool.length });
      } catch (e) {
        logger.error('browserPool.closeError', e);
      }
    }
  }

  async closeAll() {
    logger.info('browserPool.closeAll', { count: this.pool.length });
    const promises = this.pool.map((item) => {
      clearTimeout(item.idleTimer);
      return item.browser.connected ? item.browser.close() : Promise.resolve();
    });
    await Promise.all(promises).catch((e) => logger.error('browserPool.closeAllError', e));
    this.pool = [];
  }

  getStats() {
    return {
      total: this.pool.length,
      inUse: this.pool.filter((i) => i.inUse).length,
      idle: this.pool.filter((i) => !i.inUse).length,
      maxInstances: this.maxInstances,
    };
  }
}

// Singleton instance
let poolInstance = null;

function getPool(options) {
  if (!poolInstance) {
    poolInstance = new BrowserPool(options);
  }
  return poolInstance;
}

// Cleanup on process exit
process.on('SIGTERM', () => {
  if (poolInstance) {
    poolInstance.closeAll();
  }
});

process.on('SIGINT', () => {
  if (poolInstance) {
    poolInstance.closeAll();
  }
});

module.exports = { BrowserPool, getPool };
