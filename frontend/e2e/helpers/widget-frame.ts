import type { FrameLocator, Page } from "@playwright/test";

/**
 * MCP widgets render via AppRenderer inside a sandbox proxy iframe:
 *   page → .mcp-widget__frame → iframe[src="/sandbox_proxy.html"] → widget HTML (document.write)
 */
export function widgetFrame(page: Page, widgetToolName: string): FrameLocator {
  return page
    .getByRole("region", { name: new RegExp(`${widgetToolName} widget`, "i") })
    .frameLocator("iframe");
}

export async function waitForWidgetReady(
  page: Page,
  widgetToolName: string,
  timeout = 30_000,
) {
  const frame = widgetFrame(page, widgetToolName);
  await page
    .getByRole("region", { name: new RegExp(`${widgetToolName} widget`, "i") })
    .getByText("Loading widget…")
    .waitFor({ state: "hidden", timeout })
    .catch(() => undefined);
  return frame;
}
