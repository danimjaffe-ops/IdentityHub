import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Unmount React trees and reset spies between tests so state can't leak.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom doesn't fully implement the native <dialog> API that ui/Modal relies
// on. Polyfill just enough (showModal/close + the "close" event) so modal
// components render and close in tests.
if (typeof HTMLDialogElement !== "undefined") {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.open = true;
    };
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function close() {
      this.open = false;
      this.dispatchEvent(new Event("close"));
    };
  }
}
