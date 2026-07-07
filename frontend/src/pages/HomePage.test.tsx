import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WhatTheRepMcpClient } from "../mcp/client.js";
import {
  HomePage,
  NOVATO_CITY_HALL,
  type ResolveLocationResult,
} from "./HomePage.js";

const NOVATO_SLUGS = [
  "novato-ca",
  "marin-county-ca",
  "california",
  "united-states",
];

const mockMcpWidget = vi.fn(
  (props: {
    toolName: string;
    toolArgs?: Record<string, unknown>;
  }) => (
    <div
      data-testid="home-summary-widget"
      data-tool={props.toolName}
      data-slugs={JSON.stringify(props.toolArgs?.jurisdiction_slugs ?? [])}
    />
  ),
);

vi.mock("../components/McpWidget.js", () => ({
  McpWidget: (props: unknown) => mockMcpWidget(props as never),
}));

function createNovatoResolveResult(): ResolveLocationResult {
  return {
    covered: true,
    lat: NOVATO_CITY_HALL.lat,
    lng: NOVATO_CITY_HALL.lng,
    jurisdictions: NOVATO_SLUGS.map((slug, index) => ({
      slug,
      name: [
        "City of Novato",
        "Marin County",
        "California",
        "United States",
      ][index],
    })),
  };
}

function createMockClient(
  resolveResult: ResolveLocationResult | "error" = createNovatoResolveResult(),
): WhatTheRepMcpClient {
  return {
    connect: vi.fn().mockResolvedValue(undefined),
    isConnected: vi.fn().mockReturnValue(false),
    callTool: vi
      .fn()
      .mockImplementation(async (name: string, args: Record<string, unknown>) => {
        if (name !== "resolve_location") {
          throw new Error(`Unexpected tool: ${name}`);
        }
        if (resolveResult === "error") {
          throw new Error("MCP connection failed");
        }
        return {
          ...resolveResult,
          lat: args.lat,
          lng: args.lng,
        };
      }),
    callToolRaw: vi.fn(),
    listTools: vi.fn(),
    readResource: vi.fn(),
    disconnect: vi.fn(),
    getUrl: vi.fn().mockReturnValue("http://127.0.0.1:8000/mcp/"),
    getConnectionStatus: vi.fn().mockReturnValue("idle"),
  } as unknown as WhatTheRepMcpClient;
}

type GeolocationMockOptions =
  | { mode: "success"; latitude?: number; longitude?: number }
  | { mode: "error"; code?: number };

function mockGeolocation(options: GeolocationMockOptions) {
  const getCurrentPosition = vi.fn(
    (
      success: PositionCallback,
      error?: PositionErrorCallback,
    ) => {
      if (options.mode === "success") {
        success({
          coords: {
            latitude: options.latitude ?? NOVATO_CITY_HALL.lat,
            longitude: options.longitude ?? NOVATO_CITY_HALL.lng,
            accuracy: 10,
            altitude: null,
            altitudeAccuracy: null,
            heading: null,
            speed: null,
          },
          timestamp: Date.now(),
        } as GeolocationPosition);
        return;
      }

      error?.({
        code: options.code ?? 1,
        message: "Geolocation error",
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      } as GeolocationPositionError);
    },
  );

  Object.defineProperty(navigator, "geolocation", {
    value: { getCurrentPosition },
    configurable: true,
  });

  return getCurrentPosition;
}

describe("HomePage", () => {
  beforeEach(() => {
    mockMcpWidget.mockClear();
  });

  it("resolves Novato via Try Novato and renders get_home_summary", async () => {
    const client = createMockClient();

    render(<HomePage client={client} />);

    await userEvent.click(screen.getByRole("button", { name: /try novato/i }));

    await waitFor(() => {
      expect(screen.getByTestId("home-summary-widget")).toBeInTheDocument();
    });

    expect(client.connect).toHaveBeenCalled();
    expect(client.callTool).toHaveBeenCalledWith("resolve_location", {
      lat: NOVATO_CITY_HALL.lat,
      lng: NOVATO_CITY_HALL.lng,
    });

    const widget = screen.getByTestId("home-summary-widget");
    expect(widget).toHaveAttribute("data-tool", "get_home_summary");
    expect(widget).toHaveAttribute(
      "data-slugs",
      JSON.stringify(NOVATO_SLUGS),
    );
  });

  it("uses geolocation success to resolve location and render the widget", async () => {
    const client = createMockClient();
    const getCurrentPosition = mockGeolocation({ mode: "success" });

    render(<HomePage client={client} />);

    await userEvent.click(
      screen.getByRole("button", { name: /use my location/i }),
    );

    await waitFor(() => {
      expect(getCurrentPosition).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByTestId("home-summary-widget")).toBeInTheDocument();
    });

    expect(client.callTool).toHaveBeenCalledWith("resolve_location", {
      lat: NOVATO_CITY_HALL.lat,
      lng: NOVATO_CITY_HALL.lng,
    });
  });

  it("shows outside-pilot coverage message when resolve_location is not covered", async () => {
    const client = createMockClient({
      covered: false,
      lat: 40.7128,
      lng: -74.006,
      message:
        "This location is outside the Marin County pilot coverage area (Novato and Marin County boundaries only).",
      jurisdictions: [],
    });

    render(<HomePage client={client} />);

    await userEvent.click(screen.getByRole("button", { name: /try novato/i }));

    await waitFor(() => {
      expect(screen.getByText(/outside pilot coverage/i)).toBeInTheDocument();
    });

    expect(
      screen.getByText(/outside the marin county pilot coverage area/i),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("home-summary-widget")).not.toBeInTheDocument();
  });

  it("shows the manual lat/lng form when geolocation is denied", async () => {
    const client = createMockClient();
    mockGeolocation({ mode: "error", code: 1 });

    render(<HomePage client={client} />);

    expect(
      screen.queryByRole("form", { name: /manual coordinates/i }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /use my location/i }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("form", { name: /manual coordinates/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/latitude/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/longitude/i)).toBeInTheDocument();
    expect(screen.getByText(/location access was denied/i)).toBeInTheDocument();
  });
});
