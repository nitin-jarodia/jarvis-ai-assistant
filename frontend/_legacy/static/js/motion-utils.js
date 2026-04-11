'use strict';

/**
 * Jarvis AI — lightweight motion helpers (pairs with animations.css).
 * Stagger and timings respect prefers-reduced-motion.
 */
window.JarvisMotion = {
  /** @returns {boolean} */
  prefersReducedMotion() {
    try {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      return false;
    }
  },

  /**
   * CSS value for --msg-delay when staggering list items.
   * @param {number} index 0-based
   * @param {number} stepMs delay between items
   * @returns {string}
   */
  staggerDelay(index, stepMs = 45) {
    if (this.prefersReducedMotion()) return '0ms';
    return `${Math.max(0, index) * stepMs}ms`;
  },

  /** Mark document ready for shell fade-in (see animations.css body.app-ready). */
  markAppReady() {
    requestAnimationFrame(() => {
      document.body.classList.add('app-ready');
    });
  },
};
