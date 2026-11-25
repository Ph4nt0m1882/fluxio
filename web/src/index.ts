import { FluxioViewer, type MountOptions } from "./viewer";

export { FluxioViewer };
export * from "./protocol";
export * from "./themes";
export * from "./layout";

export function mount(
  target: HTMLElement | string,
  spec: unknown,
  options?: MountOptions,
): FluxioViewer {
  const el =
    typeof target === "string" ? document.getElementById(target) : target;
  if (!el) {
    throw new Error(`Fluxio target element not found: ${String(target)}`);
  }
  return new FluxioViewer(el, spec, options);
}
