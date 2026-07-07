import { describe, expect, it } from "vitest";

import {
  findToolUiResourceUri,
  getToolUiResourceUri,
  toMcpUiResource,
} from "./ui-resource.js";
import { MCP_APP_MIME_TYPE } from "./types.js";

describe("ui-resource helpers", () => {
  it("reads meta.ui.resourceUri from tool meta", () => {
    expect(
      getToolUiResourceUri({ ui: { resourceUri: "ui://what-the-rep/demo" } }),
    ).toBe("ui://what-the-rep/demo");
    expect(getToolUiResourceUri(undefined)).toBeNull();
  });

  it("finds a linked ui:// URI from listTools output", () => {
    expect(
      findToolUiResourceUri(
        [
          {
            name: "get_home_summary",
            meta: { ui: { resourceUri: "ui://what-the-rep/home-summary" } },
          },
        ],
        "get_home_summary",
      ),
    ).toBe("ui://what-the-rep/home-summary");
  });

  it("builds the MCP-UI resource shape for AppRenderer", () => {
    expect(
      toMcpUiResource({
        uri: "ui://what-the-rep/demo",
        mimeType: MCP_APP_MIME_TYPE,
        text: "<html></html>",
      }),
    ).toEqual({
      type: "resource",
      resource: {
        uri: "ui://what-the-rep/demo",
        mimeType: MCP_APP_MIME_TYPE,
        text: "<html></html>",
      },
    });
  });
});
