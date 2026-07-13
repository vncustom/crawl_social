import "@testing-library/jest-dom/vitest";

class TestResizeObserver implements ResizeObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element) {
    this.callback(
      [
        {
          target,
          contentRect: {
            width: 800,
            height: 300,
            top: 0,
            right: 800,
            bottom: 300,
            left: 0,
            x: 0,
            y: 0,
            toJSON: () => ({}),
          },
        } as ResizeObserverEntry,
      ],
      this,
    );
  }
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = TestResizeObserver;

Object.defineProperties(HTMLElement.prototype, {
  clientWidth: { configurable: true, get: () => 800 },
  clientHeight: { configurable: true, get: () => 300 },
});
